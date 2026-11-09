import sqlite3, shutil, datetime, re, secrets
try:
    from scripts.parse_dataset import parse_full_dataset, determine_category, clean_str
except ImportError:
    from parse_dataset import parse_full_dataset, determine_category, clean_str

DB_PATH = 'data/inventory.sqlite3'
BACKUP_PATH = 'data/inventory_backup_before_fresh.sqlite3'

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def run_import():
    print(f"--- Step 1: Backing up database to {BACKUP_PATH} ---")
    shutil.copyfile(DB_PATH, BACKUP_PATH)
    print("Backup created successfully.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Enable foreign keys
    c.execute("PRAGMA foreign_keys = OFF;") # Temporarily off for bulk wipe

    print("\n--- Step 2: Wiping old inventory & transaction history ---")
    # Tables to wipe completely
    tables_to_clear = [
        'transactions',
        'loans',
        'purchase_requests',
        'request_lines',
        'stock_counts',
        'stock',
        'items',
        'locations'
    ]
    for tbl in tables_to_clear:
        c.execute(f"DELETE FROM {tbl};")
        try:
            c.execute(f"DELETE FROM sqlite_sequence WHERE name='{tbl}';")
        except sqlite3.OperationalError:
            pass

    # Verify users are preserved
    user_count = c.execute("SELECT count(*) FROM users WHERE active=1").fetchone()[0]
    proj_count = c.execute("SELECT count(*) FROM projects WHERE active=1").fetchone()[0]
    print(f"Preserved {user_count} active user accounts and {proj_count} active projects.")

    print("\n--- Step 3: Building complete Location Hierarchy ---")
    # We will build a helper to get or create location by path
    # Root is always 'Stock Room'
    location_id_map = {} # path -> id

    def get_or_create_loc(path_str):
        if path_str in location_id_map:
            return location_id_map[path_str]
        
        parts = [clean_str(p) for p in path_str.split('/') if clean_str(p)]
        curr_path = ""
        parent_id = None
        
        for part in parts:
            curr_path = f"{curr_path} / {part}" if curr_path else part
            if curr_path in location_id_map:
                parent_id = location_id_map[curr_path]
            else:
                # Generate unique code
                slug = re.sub(r'[^A-Z0-9]+', '-', part.upper()).strip('-')
                code = f"LOC-{slug[:20]}-{secrets.token_hex(2).upper()}"
                cur = c.execute("INSERT INTO locations(code, name, parent_id, active) VALUES(?,?,?,1)",
                                (code, part, parent_id))
                parent_id = cur.lastrowid
                location_id_map[curr_path] = parent_id
                
        return parent_id

    # Create base empty slots for complete map even if 0 items right now
    base_locations = [
        "Stock Room / IoT Rack-A / A-1", "Stock Room / IoT Rack-A / A-2", "Stock Room / IoT Rack-A / A-3", "Stock Room / IoT Rack-A / A-4",
        "Stock Room / IoT Rack-A / A-5", "Stock Room / IoT Rack-A / A-6", "Stock Room / IoT Rack-A / A-7", "Stock Room / IoT Rack-A / A-8",
        "Stock Room / IoT Rack-B / B-1", "Stock Room / IoT Rack-B / B-2", "Stock Room / IoT Rack-B / B-3", "Stock Room / IoT Rack-B / B-4", "Stock Room / IoT Rack-B / B-5",
        "Stock Room / IoT Rack-C / C-1", "Stock Room / IoT Rack-C / C-2", "Stock Room / IoT Rack-C / C-3", "Stock Room / IoT Rack-C / C-4", "Stock Room / IoT Rack-C / C-5",
        "Stock Room / IoT Rack-D / D-1", "Stock Room / IoT Rack-D / D-2", "Stock Room / IoT Rack-D / D-3", "Stock Room / IoT Rack-D / D-4", "Stock Room / IoT Rack-D / D-5",
        "Stock Room / IoT Rack-E / E-1", "Stock Room / IoT Rack-E / E-2", "Stock Room / IoT Rack-E / E-3", "Stock Room / IoT Rack-E / E-4", "Stock Room / IoT Rack-E / E-5",
        "Stock Room / IoT Rack-F / F-1", "Stock Room / IoT Rack-F / F-2", "Stock Room / IoT Rack-F / F-3", "Stock Room / IoT Rack-F / F-4", "Stock Room / IoT Rack-F / F-5",
        "Stock Room / IoT Rack-G / G-1", "Stock Room / IoT Rack-G / G-2", "Stock Room / IoT Rack-G / G-3", "Stock Room / IoT Rack-G / G-4", "Stock Room / IoT Rack-G / G-5",
        "Stock Room / IoT Rack-H / H-1", "Stock Room / IoT Rack-H / H-2", "Stock Room / IoT Rack-H / H-3", "Stock Room / IoT Rack-H / H-4", "Stock Room / IoT Rack-H / H-5",
        "Stock Room / White Cupboard / Shelf - 1", "Stock Room / White Cupboard / Shelf - 2", "Stock Room / White Cupboard / Shelf - 3",
        "Stock Room / Grey Cupboard / Transistors, Mosfets & ICs", "Stock Room / Grey Cupboard / Batteries",
        "Stock Room / On Ground"
    ]
    for bl in base_locations:
        get_or_create_loc(bl)

    # Parse all items from raw dataset
    raw_items = parse_full_dataset()
    print(f"Parsed {len(raw_items)} entries from Excel.")

    # Ensure all paths in raw_items are created
    for entry in raw_items:
        get_or_create_loc(entry[1])

    print(f"Total location hierarchy nodes created: {len(location_id_map)}")

    print("\n--- Step 4: Normalizing items and inserting catalog ---")
    # Group by normalized item name
    item_map = {} # canonical_name_lower -> dict
    for entry in raw_items:
        raw_name = clean_str(entry[0])
        # Clean obvious typos
        if raw_name.lower() == 'weighinh scale':
            raw_name = 'Weighing scale'
        key = raw_name.lower()
        loc_path = entry[1]
        qty = entry[2]
        needs_count = entry[3]
        note = entry[4] if len(entry) > 4 else ""

        if key not in item_map:
            cat = determine_category(raw_name, loc_path)
            # Determine kind: asset for reusable tools/testers/printers/machines
            is_asset = any(k in raw_name.lower() for k in [
                'machine', 'multimeter', 'oscilloscope', 'drill', 'cutter', 'gun', 'scale', 
                'testing box', 'analyzer', 'meter', 'robot', 'drone', 'weighing'
            ])
            item_map[key] = {
                'name': raw_name,
                'category': cat,
                'kind': 'asset' if is_asset else 'consumable',
                'locations': {}, # loc_id -> {'qty': int, 'needs_count': int}
                'notes': note
            }
        
        loc_id = location_id_map[loc_path]
        if loc_id not in item_map[key]['locations']:
            item_map[key]['locations'][loc_id] = {'qty': 0, 'needs_count': 0}
            
        item_map[key]['locations'][loc_id]['qty'] += qty
        if needs_count:
            item_map[key]['locations'][loc_id]['needs_count'] = 1

    print(f"Unique catalog items: {len(item_map)}")

    # Insert items and stock into database
    admin_user = c.execute("SELECT id FROM users WHERE role='stock' LIMIT 1").fetchone()
    admin_id = admin_user[0] if admin_user else 1

    item_idx = 1
    total_stock_rows = 0
    total_physical_units = 0
    items_needing_count_count = 0

    now_time = now_iso()

    for key, data in item_map.items():
        item_code = f"ITM-{item_idx:04d}"
        item_idx += 1

        # Check if item overall needs count (if all locations need count or total qty == 0)
        overall_needs_count = 1 if all(v['needs_count'] == 1 for v in data['locations'].values()) else 0
        if overall_needs_count:
            items_needing_count_count += 1

        cur = c.execute("""INSERT INTO items(item_code, name, category, part_number, kind, unit, min_qty, needs_count, notes, active, created_at)
            VALUES(?,?,?,'',?,'Nos',NULL,?,?,1,?)""",
            (item_code, data['name'], data['category'], data['kind'], overall_needs_count, data['notes'], now_time))
        item_id = cur.lastrowid

        for loc_id, sdata in data['locations'].items():
            qty = sdata['qty']
            nc = sdata['needs_count']
            c.execute("""INSERT INTO stock(item_id, location_id, quantity, needs_count, reference_quantity)
                VALUES(?,?,?,?,NULL)""", (item_id, loc_id, qty, nc))
            total_stock_rows += 1
            total_physical_units += qty

            # If quantity > 0, record an initial opening transaction
            if qty > 0:
                tx_ref = f"TX-INIT-{secrets.token_hex(3).upper()}"
                c.execute("""INSERT INTO transactions(ref, kind, item_id, location_id, quantity, user_id, purpose, status, created_at, confirmed_by, confirmed_at)
                    VALUES(?, 'opening', ?, ?, ?, ?, 'Initial inventory import', 'confirmed', ?, ?, ?)""",
                    (tx_ref, item_id, loc_id, qty, admin_id, now_time, admin_id, now_time))

    c.execute("PRAGMA foreign_keys = ON;")
    integrity = c.execute("PRAGMA integrity_check").fetchall()
    fks = c.execute("PRAGMA foreign_key_check").fetchall()
    conn.commit()

    print("\n--- Step 5: Verification & Integrity Summary ---")
    print(f"Total Unique Items: {len(item_map)}")
    print(f"Total Stock Location Rows: {total_stock_rows}")
    print(f"Total Physical Units in Stock: {total_physical_units}")
    print(f"Items Marked as Needing Count (highlighted for staff check): {items_needing_count_count}")
    print(f"PRAGMA integrity_check: {integrity}")
    print(f"PRAGMA foreign_key_check: {fks}")
    assert integrity[0][0] == 'ok', f"Integrity check failed: {integrity}"
    assert fks == [], f"Foreign key check failed: {fks}"

    # Print Category Breakdown
    print("\n--- Category Breakdown ---")
    cat_rows = c.execute("SELECT category, count(*), sum((SELECT sum(quantity) FROM stock WHERE item_id=items.id)) FROM items GROUP BY category ORDER BY count(*) DESC").fetchall()
    for cat, count, units in cat_rows:
        print(f" - {cat}: {count} items, {units or 0} units")

    # Print Rack Breakdown
    print("\n--- Rack / Cupboard Breakdown ---")
    racks = c.execute("""WITH RECURSIVE loc_tree AS (
            SELECT id, name, name AS top_loc FROM locations WHERE parent_id=(SELECT id FROM locations WHERE parent_id IS NULL)
            UNION ALL
            SELECT c.id, c.name, t.top_loc FROM locations c JOIN loc_tree t ON c.parent_id=t.id
        )
        SELECT top_loc, count(DISTINCT s.item_id), COALESCE(sum(s.quantity), 0)
        FROM loc_tree lt LEFT JOIN stock s ON s.location_id=lt.id
        GROUP BY top_loc ORDER BY top_loc""").fetchall()
    for rack, count, units in racks:
        print(f" - {rack}: {count} items, {units} units")

    print("\n=== FRESH INVENTORY IMPORT COMPLETE & 100% VERIFIED! ===")

if __name__ == '__main__':
    run_import()
