import sqlite3

conn = sqlite3.connect('data/inventory.sqlite3')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- TOP LOCATIONS ---")
for r in c.execute("SELECT id, code, name, parent_id FROM locations WHERE parent_id IS NULL OR parent_id=1"):
    print(" ", dict(r))

print("\n--- INVENTORY METRICS ---")
print("Total Locations:", c.execute("SELECT count(id) FROM locations").fetchone()[0])
print("Total Unique Items:", c.execute("SELECT count(id) FROM items WHERE active=1").fetchone()[0])
print("Total Stock Units:", c.execute("SELECT COALESCE(sum(quantity), 0) FROM stock").fetchone()[0])
print("Items Needing Count:", c.execute("SELECT count(id) FROM items WHERE active=1 AND needs_count=1").fetchone()[0])
print("Active Users:", c.execute("SELECT count(id) FROM users WHERE active=1").fetchone()[0])
print("Active Projects:", c.execute("SELECT count(id) FROM projects WHERE active=1").fetchone()[0])
