# Stockroom

A clean, self-hosted office stock management system. Built entirely with Python's standard library and SQLite; zero npm dependencies, zero cloud lock-in, and fast on smartphones, tablets, and desktops.

---

## Quick Start on the Office Wi-Fi

1. **Prerequisite**: Python 3.10 or newer on the stock person's laptop.
2. **First-time Wi-Fi setup**: Run `enable_wifi_access.bat` as Administrator (allows port 8080 through Windows Firewall).
3. **Start the app**: Run `run_stockroom.bat`. It displays the local URL (`http://127.0.0.1:8080/`) and the office Wi-Fi URL (e.g. `http://<laptop-ip>:8080/`).
4. **On Mobile Phones / Tablets**:
   - Connect to the office Wi-Fi.
   - Open the Wi-Fi URL or scan the QR code from the app topbar.
5. **Sign in**:
   - Stock person: `jagannadh.p@fervidsmart.com`
   - Employee: `shashank.b@fervidsmart.com`

---

## Stockroom Physical Map

All storage locations are organized under the **Stock Room** hierarchy matching the physical laboratory racks and cupboards:

- **IoT Rack-A**: Shelves `A-1` through `A-8` (Weighing scales, cables, adapters, sensors, flow meters).
- **IoT Rack-B**: Shelves `B-1` through `B-5` (Monitors, turbidity analyzers, robots, kits).
- **IoT Rack-C**: Shelves `C-1` through `C-5` and dedicated sub-boxes:
  - `C-3 / BOX - 21`: Battery bank (Li-ion, LiPo, VRLA, Ni-MH)
  - `C-3 / BOX13`: SMD Resistors
  - `C-4 / BOX - 19`: Switches, terminal blocks, DC jacks
  - `C-4 / BOX-22`: Soldering materials
  - `C-4 / BOX - 23`: Power Pro devices
  - `C-4 / BOX - 10`: LCD displays
- **IoT Rack-D**: Shelves `D-1` through `D-5` (Weighing scales, monitors, oscilloscopes, enclosures).
- **IoT Rack-E**: Shelves `E-1` through `E-5`:
  - `E-3 / Mixed Components Box`: Power cables, Ethernet, HDMI, laptop & 12V adapters.
- **IoT Rack-F**: Shelves `F-1` through `F-5` (Power Pro adapters, robotic components).
- **IoT Rack-G**: Shelves `G-1` through `G-5` (3D printing machine, demo modules, robokits).
- **IoT Rack-H**: Shelves `H-1` through `H-5` (Trays, invoices, catalogs, brochures).
- **White Cupboard**:
  - `Shelf - 1`: Power Pro units and SMD component boxes (`Box 8`, `Box 14`, `BOX 15`).
  - `Shelf - 2`: Trays `Tray-1` through `Tray - 5` and `Camera Modules` (breakdown modules, dev kits, sensors, ICs, LEDs, micro cameras).
  - `Shelf - 3`: `Tool Kit Box`, `Jumper Cables Box`, `M16 Water Proof Connectors`, `GX Connectors`, `Zip Tags`, `Pressure Transmitter`.
- **Grey Cupboard**:
  - `Transistors, Mosfets & ICs`: 27 distinct transistor, mosfet, and IC components.
  - `Batteries`: Li-ion batteries (3.6V).
- **On Ground**: Heavy equipment (`Weight Scale (Big)`, `Dendrile`, `Valve`, `ROBOT`).

---

## Inventory Status & Count Rules

- **Current Stock**: 368 verified catalog items across 1,354 physical units.
- **Needs Count (80 items)**: Items where the initial Excel sheet had blank quantities (e.g. miscellaneous cables, coils, spacers) are highlighted with the **"⚠️ Needs count"** filter. When staff verify the physical count on the shelf, they use the **Count** button to update the quantity in place.
- **Connected Activity Links**: Checkouts are tracked as complete lifecycles:
  `[ Taken ] ───> [ ↻ Returned to shelf ] & [ ✓ Used in project ]`
  Items currently held by staff show instant `Return` and `Mark used` buttons.

---

## Data Files

- Live database: `data/inventory.sqlite3` (WAL mode enabled for fast concurrent read/write).
- Structured catalog export: `data/stock_seed.json`.
- Spreadsheet export: `data/stock_import_review.csv` (or click **↓ Export CSV** directly in the app).
- Human-readable inventory: `data/stock_lists_merged.md`.
