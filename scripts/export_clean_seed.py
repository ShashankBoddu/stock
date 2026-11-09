import sqlite3, json, csv, datetime

DB_PATH = 'data/inventory.sqlite3'

def export_clean_files():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get location paths helper
    def get_path(loc_id):
        curr_id = loc_id
        parts = []
        while curr_id:
            row = c.execute("SELECT id, name, parent_id FROM locations WHERE id=?", (curr_id,)).fetchone()
            if not row: break
            parts.append(row["name"])
            curr_id = row["parent_id"]
        return " / ".join(reversed(parts))

    locations = c.execute("SELECT * FROM locations ORDER BY id").fetchall()
    loc_list = []
    for l in locations:
        loc_list.append({
            "id": l["id"],
            "code": l["code"],
            "name": l["name"],
            "parent_id": l["parent_id"],
            "path": get_path(l["id"])
        })

    items = c.execute("SELECT * FROM items WHERE active=1 ORDER BY id").fetchall()
    stock_rows = c.execute("SELECT * FROM stock").fetchall()

    item_list = []
    for i in items:
        # Get locations and quantities
        item_stocks = [s for s in stock_rows if s["item_id"] == i["id"]]
        loc_entries = []
        for s in item_stocks:
            loc_entries.append({
                "location_id": s["location_id"],
                "path": get_path(s["location_id"]),
                "quantity": s["quantity"],
                "needs_count": bool(s["needs_count"])
            })
        item_list.append({
            "id": i["id"],
            "item_code": i["item_code"],
            "name": i["name"],
            "category": i["category"],
            "part_number": i["part_number"],
            "kind": i["kind"],
            "unit": i["unit"],
            "min_qty": i["min_qty"],
            "needs_count": bool(i["needs_count"]),
            "notes": i["notes"],
            "created_at": i["created_at"],
            "stock_locations": loc_entries,
            "total_quantity": sum(s["quantity"] for s in item_stocks)
        })

    # 1. Write clean data/stock_seed.json
    seed_payload = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "total_items": len(item_list),
            "total_locations": len(loc_list),
            "total_units": sum(i["total_quantity"] for i in item_list),
            "needs_count_items": sum(1 for i in item_list if i["needs_count"])
        },
        "locations": loc_list,
        "items": item_list
    }
    with open('data/stock_seed.json', 'w', encoding='utf-8') as f:
        json.dump(seed_payload, f, indent=2, ensure_ascii=False)
    print("Exported data/stock_seed.json successfully.")

    # 2. Write clean data/stock_import_review.csv
    with open('data/stock_import_review.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(["Item Code", "Item Name", "Category", "Total Qty", "Needs Count", "Storage Locations", "Notes"])
        for i in item_list:
            loc_str = "; ".join(f"{sl['path']}: {sl['quantity']}" for sl in i["stock_locations"])
            w.writerow([
                i["item_code"],
                i["name"],
                i["category"],
                i["total_quantity"],
                "Yes" if i["needs_count"] else "No",
                loc_str,
                i["notes"]
            ])
    print("Exported data/stock_import_review.csv successfully.")

    # 3. Write clean data/stock_lists_merged.md
    md_lines = [
        "# Official Stockroom Inventory",
        "",
        f"Updated: {datetime.datetime.now().strftime('%d %b %Y')}",
        "",
        "## Inventory Overview",
        f"- **Total Catalog Items:** {len(item_list)}",
        f"- **Total Units in Stock:** {sum(i['total_quantity'] for i in item_list)}",
        f"- **Storage Locations:** {len(loc_list)}",
        f"- **Items Needing Physical Count:** {sum(1 for i in item_list if i['needs_count'])}",
        "",
        "## Storage Locations Map",
        ""
    ]
    
    # Group by top rack
    top_racks = [l for l in loc_list if l["parent_id"] == 1] # Direct children of Stock Room
    for tr in sorted(top_racks, key=lambda x: x["name"]):
        md_lines.append(f"### {tr['name']}")
        sub_locs = [l for l in loc_list if l["path"].startswith(f"Stock Room / {tr['name']}")]
        for sl in sorted(sub_locs, key=lambda x: x["path"]):
            # Items in this location
            items_here = []
            for itm in item_list:
                for sl_entry in itm["stock_locations"]:
                    if sl_entry["location_id"] == sl["id"]:
                        items_here.append((itm["name"], sl_entry["quantity"], sl_entry["needs_count"]))
            if items_here:
                md_lines.append(f"- **{sl['name']}** ({len(items_here)} items):")
                for iname, iqty, inc in sorted(items_here, key=lambda x: x[0].lower()):
                    qty_disp = f"{iqty} Nos" if not inc else "Needs count"
                    md_lines.append(f"  - {iname}: {qty_disp}")
        md_lines.append("")

    with open('data/stock_lists_merged.md', 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
    print("Exported data/stock_lists_merged.md successfully.")

if __name__ == '__main__':
    export_clean_files()

