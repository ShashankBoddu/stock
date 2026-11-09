"""Convert existing flat storage names into a parent/child location tree safely."""
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "inventory.sqlite3"
SEED = ROOT / "data" / "stock_seed.json"

seed = json.loads(SEED.read_text(encoding="utf-8"))
conn = sqlite3.connect(DB, timeout=30)
conn.execute("PRAGMA foreign_keys=ON")
conn.execute("BEGIN IMMEDIATE")
try:
    existing = {code: (loc_id, name, parent) for loc_id, code, name, parent in
                conn.execute("SELECT id,code,name,parent_id FROM locations")}
    root = existing.get("STOCK-ROOM")
    if root:
        root_id = root[0]
    else:
        cur = conn.execute("INSERT INTO locations(code,name,parent_id) VALUES('STOCK-ROOM','Stock Room',NULL)")
        root_id = cur.lastrowid
        existing["STOCK-ROOM"] = (root_id, "Stock Room", None)

    by_path = {(): root_id}
    updated = 0
    parents_added = 0
    for loc in seed["locations"]:
        code = loc["code"]
        if code not in existing:
            raise RuntimeError(f"Expected imported storage location is missing: {code}")
        parts = tuple(part.strip() for part in loc["name"].split(" / ") if part.strip())
        if not parts:
            raise RuntimeError(f"Location has an empty path: {code}")
        parent_id = root_id
        prefix = ()
        for part in parts[:-1]:
            prefix += (part,)
            if prefix not in by_path:
                digest = hashlib.sha1(" / ".join(prefix).casefold().encode()).hexdigest()[:12].upper()
                parent_code = f"PATH-{digest}"
                row = conn.execute("SELECT id FROM locations WHERE code=?", (parent_code,)).fetchone()
                if row:
                    node_id = row[0]
                    conn.execute("UPDATE locations SET name=?,parent_id=?,active=1 WHERE id=?", (part,parent_id,node_id))
                else:
                    cur = conn.execute("INSERT INTO locations(code,name,parent_id) VALUES(?,?,?)", (parent_code,part,parent_id))
                    node_id = cur.lastrowid
                    parents_added += 1
                by_path[prefix] = node_id
            parent_id = by_path[prefix]
        loc_id = existing[code][0]
        conn.execute("UPDATE locations SET name=?,parent_id=?,active=1 WHERE id=?", (parts[-1],parent_id,loc_id))
        updated += 1

    conn.commit()
    result = {
        "root": "Stock Room",
        "imported_locations_reparented": updated,
        "parent_locations_added": parents_added,
        "stock_rows": conn.execute("SELECT count(*) FROM stock").fetchone()[0],
        "transactions": conn.execute("SELECT count(*) FROM transactions").fetchone()[0],
        "locations_total": conn.execute("SELECT count(*) FROM locations").fetchone()[0],
    }
    print(json.dumps(result, indent=2))
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
