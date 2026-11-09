"""Load the reviewed seed into an empty Stockroom database without overwriting data."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "inventory.sqlite3"
SEED_PATH = ROOT / "data" / "stock_seed.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    if not DB_PATH.exists() or not SEED_PATH.exists():
        raise SystemExit("The app database or generated stock_seed.json is missing.")
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        users = conn.execute("SELECT id,role FROM users WHERE active=1").fetchall()
        stock_user = next((u for u in users if u["role"] == "stock"), None)
        if not stock_user:
            raise SystemExit("Create the stock person account in the app before importing.")
        existing = conn.execute("SELECT count(*) FROM items").fetchone()[0]
        if existing:
            raise SystemExit(f"Import stopped safely: the database already contains {existing} items. No data was changed.")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(stock)")}
        if "needs_count" not in columns:
            conn.execute("ALTER TABLE stock ADD COLUMN needs_count INTEGER NOT NULL DEFAULT 0")
        if "reference_quantity" not in columns:
            conn.execute("ALTER TABLE stock ADD COLUMN reference_quantity INTEGER")
        conn.execute("""CREATE TABLE IF NOT EXISTS stock_counts (
            id INTEGER PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES items(id),
            location_id INTEGER NOT NULL REFERENCES locations(id),
            previous_quantity INTEGER NOT NULL,
            counted_quantity INTEGER NOT NULL,
            counted_by INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        location_ids = {}
        item_ids = {}
        conn.execute("BEGIN IMMEDIATE")
        for loc in seed["locations"]:
            cur = conn.execute("INSERT INTO locations(code,name) VALUES(?,?)", (loc["code"],loc["name"]))
            location_ids[loc["code"]] = cur.lastrowid
        for item in seed["items"]:
            cur = conn.execute("""INSERT INTO items(item_code,name,category,kind,unit,min_qty,needs_count,notes,created_at)
                VALUES(?,?,?,?,?,NULL,?,?,?)""", (item["item_code"],item["name"],item["category"],item["kind"],item["unit"],
                int(item["needs_count"]),item["notes"],utc_now()))
            item_ids[item["item_code"]] = cur.lastrowid
        imported_at = utc_now()
        opening_count = 0
        for row in seed["stock"]:
            item_id = item_ids[row["item_code"]]
            location_id = location_ids[row["location_code"]]
            quantity = int(row["quantity"])
            conn.execute("INSERT INTO stock(item_id,location_id,quantity,needs_count,reference_quantity) VALUES(?,?,?,?,?)",
                         (item_id,location_id,quantity,int(row["needs_count"]),row.get("reference_quantity")))
            if quantity > 0 and not row["needs_count"]:
                item_code = row["item_code"]
                loc_code = row["location_code"]
                ref = f"OPEN-{item_code}-{loc_code}"[:80]
                conn.execute("""INSERT INTO transactions(ref,kind,item_id,location_id,quantity,user_id,status,purpose,created_at,confirmed_by,confirmed_at)
                    VALUES(?,'opening',?,?,?,?,'confirmed','Opening balance imported from current stock list',?,?,?)""",
                    (ref,item_id,location_id,quantity,stock_user["id"],imported_at,stock_user["id"],imported_at))
                opening_count += 1
        conn.commit()
        print(json.dumps({"items_added":len(item_ids),"locations_added":len(location_ids),
                          "item_location_rows_added":len(seed["stock"]),"opening_transactions":opening_count,
                          "needs_count_items":sum(1 for i in seed["items"] if i["needs_count"]),
                          "possible_duplicates_to_review":sum(1 for _ in open(ROOT/"data"/"possible_duplicate_review.csv",encoding="utf-8-sig"))-1},indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
