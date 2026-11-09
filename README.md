# Stockroom

A small self-hosted stock management prototype. It uses Python's standard library and SQLite; it does not need npm, a cloud server, or a recurring software subscription.

## Start Stockroom on the office Wi-Fi

1. Install Python 3.10 or newer on the stock person's office laptop.
2. **First-time Wi-Fi setup**: Run `enable_wifi_access.bat` as Administrator. This configures Windows Firewall to allow port 8080 and sets the Wi-Fi connection to Private so other devices on the same Wi-Fi can connect.
3. Run `run_stockroom.bat`. It prints the laptop URL (`http://127.0.0.1:8080/`) and the same-Wi-Fi URL (e.g. `http://<laptop-ip>:8080/`), and opens the local app in the default browser.
4. On smartphones or other office computers connected to the same Wi-Fi:
   - Either type the `http://<laptop-ip>:8080/` URL printed in the launcher, OR
   - Click the **Wi-Fi / Mobile link** button in the stock app topbar and scan the QR code using a phone camera.
5. Create the stock person account or sign in to start managing stock and employee requests.

Keep the launcher window open while staff use the live app. The laptop must be on, and this first version does not save movement forms while offline. If other devices cannot connect even when using the printed Wi-Fi URL, verify that `enable_wifi_access.bat` has been run and both devices are connected to the exact same Wi-Fi network.

## First-use setup

- The current workspace already includes both supplied lists: 1,152 catalog items across 190 locations. The 030325 workbook is treated as legacy reference data; its quantities are not added to live stock.
- 291 opening transactions record the known quantities from `stock_list.md` (1,342 total units). Items with blank current quantities, ambiguous duplicate rows, or legacy-only quantities are marked **Needs count**; the app does not let staff issue them until counted.
- Five possible spelling duplicates are listed in `data/possible_duplicate_review.csv` for review. The importer merges only exact normalized names and never adds legacy quantities to current counts.
- Storage is shown as a hierarchy, for example `Stock Room / IoT Rack-C / C-3 / BOX -21`. Inventory, movement history, purchase receipts, and CSV exports show the complete path.
- An issue records the signed-in person and a searchable employee recipient; both appear in movement history. **Edit** can move each item's location balance while preserving its quantity and count-needed status.
- Purchase requests support manually entered items, optional vendor and product link per item, and record the signed-in requester and project.
- **Movements** includes searchable, type-filtered history. The stock person can confirm or reject pending inward entries and returns; rejected returns become active loans again.
- Use **Count** on an item to verify a location. Counted quantities and any adjustment are recorded in the audit history. Use **Edit** to correct its category/type and set a minimum stock level.
- Add projects from **Setup**; employees can also choose **General/Internal**.
- Add employee accounts using company email addresses and unique passwords.
- Use the purchase request screen for items not yet in inventory. The stock person adds new items when receiving the purchase.

If you replace the seed data, first back up the database. Rebuild the review files with `python build_stock_import.py "<current stock_list.md>" "<legacy Stock_List_030325.md>"`, then run `python import_seed_into_db.py` only against an empty database. The importer refuses to overwrite an existing inventory.

## Data and backups

The live database is `data/inventory.sqlite3`. Stop the server before copying this file for a simple backup, and keep backups on another drive. The inventory screen can export a CSV overview.

The merged source copy is `data/stock_lists_merged.md`; `data/stock_import_review.csv` preserves parsed source rows and references. `data/stock_seed.json` is the structured import used for the current catalog.

The Google Sheets snapshot connection is not configured yet. It needs a destination sheet and an authorized connection method. The app currently provides a CSV export for review; it does not claim to sync the sheet automatically until that connector is set up.

After updating the server code, stop any running Stockroom window with Ctrl+C and start `run_stockroom.bat` again so it loads the latest screens and count-review actions.

## Network note

The app uses HTTP on the office network. HTTP does not encrypt sign-in details or stock data in transit, so use unique passwords and keep the server off public internet. If the managed firewall blocks incoming connections, an administrator-approved firewall rule or a separately hosted HTTPS service is needed for phone access.
