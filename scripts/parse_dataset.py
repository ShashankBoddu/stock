import csv, io, re

try:
    from scripts.parse_tester import RAW_CSV
except ImportError:
    from parse_tester import RAW_CSV

def clean_str(s):
    if not s: return ""
    return re.sub(r'\s+', ' ', str(s)).strip()

def parse_qty(q):
    q_str = clean_str(q)
    if not q_str:
        return 0, 1 # qty=0, needs_count=1
    m = re.search(r'\d+', q_str)
    if m:
        return int(m.group(0)), 0
    return 0, 1

def determine_category(name, loc_path):
    n = name.lower()
    lp = loc_path.lower()
    
    if any(k in n for k in ['battery', 'batteries', 'lipo', 'vrla', 'power pro', 'smps', 'adapter', 'charger', 'power supply', 'ups', 'stabiliser', 'solar panel']):
        return 'Batteries & Power'
    if any(k in n for k in ['cable', 'wire', 'connector', 'jack', 'header', 'socket', 'terminal block', 'pins']):
        return 'Connectors & Cables'
    if any(k in n for k in ['transistor', 'mosfet', 'ic', 'regulator', 'bjt', 'jfet', 'diode', 'triac', 'driver', 'stm32', 'optocoupler', 'm66', 'ec200u']):
        return 'Semiconductors & ICs'
    if any(k in n for k in ['resistor', 'capacitor', 'inductor', 'ferrite coil', 'fuse']):
        return 'Passive Components'
    if any(k in n for k in ['board', 'pcb', 'arduino', 'esp32', 'nodemcu', 'nucleo', 'lora gateway', 'breakdown', 'dev kit', 'wapi', 'flora', 'traces']):
        return 'Development Boards'
    if any(k in n for k in ['sensor', 'analyzer', 'meter', 'detector', 'anometer', 'transceiver', 'scanner', 'camera', 'antenna', 'beacon', 'turbidity', 'ph ']):
        return 'Sensors & Modules'
    if any(k in n for k in ['screen', 'display', 'monitor', 'led', 'lcd', 'dot matrix', 'hmi']):
        return 'Displays & Screens'
    if any(k in n for k in ['robot', 'servo', 'motor', 'pump', 'drone', 'chasis']):
        return 'Robotics & Actuators'
    if any(k in n for k in ['tool', 'cutter', 'drill', 'stripper', 'gun', 'hammer', 'blade', 'multimeter', 'oscilloscope', 'soldering']):
        return 'Tools & Equipment'
    if any(k in n for k in ['enclosure', 'box', 'tray', 'stand', '3d printed', 'cover', 'case']):
        return 'Enclosures & Mechanical'
    if any(k in n for k in ['scale', 'weighing', 'weighinh']):
        return 'Weighing Systems'
    if any(k in n for k in ['tape', 'glue', 'fevikick', 'araldite', 'screw', 'nut', 'spacer', 'blanket', 'sticker', 'tag', 'chemical', 'gatti', 'bulb', 'desoldering']):
        return 'Hardware & Consumables'
    
    return 'General Inventory'

def parse_full_dataset():
    reader = csv.reader(io.StringIO(RAW_CSV.strip()))
    raw_rows = [list(map(clean_str, r)) for r in reader]
    
    items = []
    
    # 1. Sheet A: Rows 2 to 26
    curr_slot = "A-1"
    for r in raw_rows[2:27]:
        if r[0] and r[0].startswith("A-"):
            curr_slot = r[0]
        name = r[1]
        qty_str = r[2]
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = f"Stock Room / IoT Rack-A / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 2. Sheet B: Rows 45 to 58
    curr_slot = "B-1"
    for r in raw_rows[45:59]:
        if r[0] and r[0].startswith("B-"):
            curr_slot = r[0]
        name = r[1]
        qty_str = r[2]
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = f"Stock Room / IoT Rack-B / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 3. Sheet C: Rows 61 to 150
    curr_slot = "C-1"
    curr_box = None
    for r in raw_rows[61:150]:
        while len(r) < 7: r.append("")
        col0, col1, col2, col3, col4, col5, col6 = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        
        if col0 and col0.startswith("C-"):
            curr_slot = col0
            curr_box = None
            
        sample_loc = col6 or col5 or ""
        if "box-21" in sample_loc.lower():
            curr_box = "BOX - 21"
        elif "iot rack-c/ c-3" in sample_loc.lower() and not "box" in sample_loc.lower():
            curr_box = None

        if col1 and re.match(r'^box\s*-?\s*\d+$', col1, re.I):
            curr_box = col1.upper()
            if col2:
                name = col2
                qty_str = col4 or col3 or col5
            else:
                name = ""
                qty_str = ""
        elif curr_box and col2:
            name = col2
            qty_str = col4 or col3 or col5
        elif col1:
            name = col1
            qty_str = col4 or col3 or col2
            # If col1 is an item in C-4, make sure it's not under a previous sub-box
            if curr_slot in ["C-4", "C-5"] and not any(k in col1.upper() for k in ["BOX-", "BOX "]):
                curr_box = None
        elif col2:
            name = col2
            qty_str = col4 or col3 or col5
        else:
            name = ""
            qty_str = ""

        if name:
            qty, needs_count = parse_qty(qty_str)
            if curr_box:
                loc = f"Stock Room / IoT Rack-C / {curr_slot} / {curr_box}"
            else:
                loc = f"Stock Room / IoT Rack-C / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 4. Sheet D: Rows 152 to 166
    curr_slot = "D-1"
    for r in raw_rows[152:166]:
        if r[0] and r[0].startswith("D-"):
            curr_slot = r[0]
        name = r[1]
        qty_str = r[2]
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = f"Stock Room / IoT Rack-D / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 5. Sheet E: Rows 168 to 196
    curr_slot = "E-1"
    curr_box = None
    for r in raw_rows[168:196]:
        while len(r) < 5: r.append("")
        col0, col1, col2, col3, col4 = r[0], r[1], r[2], r[3], r[4]
        
        if col0 and col0.startswith("E-"):
            curr_slot = col0
            curr_box = None
            
        if curr_slot == "E-3":
            if "mixed components box" in col1.lower():
                curr_box = "Mixed Components Box"
                name = col2
                qty_str = col3
            elif curr_box and col2:
                name = col2
                qty_str = col3
            elif col1:
                curr_box = None
                name = col1
                qty_str = col3 or col2
            else:
                name = ""
                qty_str = ""
        elif curr_slot == "E-2" and "mixed components box" in col1.lower():
            name = col1
            qty_str = col3 or col2
        else:
            name = col1
            qty_str = col3 or col2
            
        if name:
            qty, needs_count = parse_qty(qty_str)
            if curr_box:
                loc = f"Stock Room / IoT Rack-E / {curr_slot} / {curr_box}"
            else:
                loc = f"Stock Room / IoT Rack-E / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 6. Sheet F: Rows 198 to 207
    curr_slot = "F-1"
    for r in raw_rows[198:207]:
        if r[0] and r[0].startswith("F-"):
            curr_slot = r[0]
        name = r[1]
        qty_str = r[2]
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = f"Stock Room / IoT Rack-F / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 7. Sheet G: Rows 209 to 217
    curr_slot = "G-1"
    for r in raw_rows[209:217]:
        if r[0] and r[0].startswith("G-"):
            curr_slot = r[0]
        name = r[1]
        qty_str = r[2]
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = f"Stock Room / IoT Rack-G / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 8. Sheet H: Rows 219 to 225
    curr_slot = "H-1"
    for r in raw_rows[219:225]:
        if r[0] and r[0].startswith("H-"):
            curr_slot = r[0]
        name = r[1]
        qty_str = r[2]
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = f"Stock Room / IoT Rack-H / {curr_slot}"
            items.append((name, loc, qty, needs_count, ""))

    # 9. S.No. On Ground: Rows 227 to 230
    for r in raw_rows[227:231]:
        name = r[1]
        qty_str = r[2] if len(r) > 2 else ""
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = "Stock Room / On Ground"
            items.append((name, loc, qty, needs_count, ""))

    # 10. White Cupboard: Rows 234 to 397
    curr_shelf = "Shelf - 1"
    curr_box = None
    for r in raw_rows[234:397]:
        while len(r) < 5: r.append("")
        col0, col1, col2, col3, col4 = r[0], r[1], r[2], r[3], r[4]
        
        if col0 and col0.startswith("Shelf"):
            curr_shelf = col0
            curr_box = None
            
        if col1:
            if curr_shelf == "Shelf - 3" and not col2 and (col3 or col1 in ["Pressure Transmitter", "Neoway Prototype Box"]):
                # Direct item on Shelf - 3 without sub-box
                curr_box = None
                name = col1
                qty_str = col3
            else:
                curr_box = col1
                name = col2
                qty_str = col3
        elif col2:
            name = col2
            qty_str = col3
        else:
            name = ""
            qty_str = ""

        if name:
            qty, needs_count = parse_qty(qty_str)
            if curr_box:
                loc = f"Stock Room / White Cupboard / {curr_shelf} / {curr_box}"
            else:
                loc = f"Stock Room / White Cupboard / {curr_shelf}"
            items.append((name, loc, qty, needs_count, ""))

    # 11. Grey Cupboard: Rows 399 to 428
    curr_box = "Transistors, Mosfets & ICs"
    for r in raw_rows[399:428]:
        while len(r) < 5: r.append("")
        col0, col1, col2, col3, col4 = r[0], r[1], r[2], r[3], r[4]
        
        if col0:
            curr_box = col0
            
        name = col1
        qty_str = col2
        note = col3
        
        if name:
            qty, needs_count = parse_qty(qty_str)
            loc = f"Stock Room / Grey Cupboard / {curr_box}"
            items.append((name, loc, qty, needs_count, note))

    return items

if __name__ == '__main__':
    items = parse_full_dataset()
    print(f"Total parsed items: {len(items)}")
    total_qty = sum(x[2] for x in items)
    needs_count = sum(1 for x in items if x[3] == 1)
    print(f"Total physical units: {total_qty}")
    print(f"Items needing count: {needs_count}")
    print(f"Items with known count: {len(items) - needs_count}")
    
    unique_locs = sorted(list(set(x[1] for x in items)))
    print(f"Unique leaf storage locations: {len(unique_locs)}")
    print("\nAll storage locations:")
    for l in unique_locs:
        count_in_loc = sum(1 for x in items if x[1] == l)
        units_in_loc = sum(x[2] for x in items if x[1] == l)
        print(f" - {l} ({count_in_loc} items, {units_in_loc} units)")
