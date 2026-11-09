import sqlite3
import re
import json
from collections import Counter

def classify(name, old_cat="", notes=""):
    n = name.strip()
    nl = n.lower()
    
    # 0. High priority hardware & specific parts
    if any(k in nl for k in ["irfz44n", "irlz44n", "irf830", "bt136", "bta26", "bta41", "vishay-irf"]):
        return "Through Hole Transistors & MOSFETs"
    if "esp wroom" in nl or "esp-wroom" in nl or "esp 32- wroom" in nl or "esp 32-d" in nl or "esp 32-e" in nl or "ec200u" in nl:
        return "Wireless & IoT Modules"
    if any(k in nl for k in ["hongfa", "songle"]):
        return "Relays"
    if any(k in nl for k in ["hi-link", "hilink", "da5-ps0005"]):
        return "Power & Converter Modules"
    if any(k in nl for k in ["sunca", "samsung"]):
        return "Batteries & Battery Holders"
    if nl == "ir" or "ir sensor" in nl:
        return "Sensors"
    if "digital multi meter" in nl:
        return "Tools & Lab Equipment"
    if "pendrive" in nl:
        return "Prototyping & Consumables"
    if "interfacing ciruit" in nl or "interfacing circuit" in nl:
        return "Development & Breakout Boards"
    if any(k in nl for k in ["m66 module", "radio frequency transmitter"]):
        return "Wireless & IoT Modules"
    if any(k in nl for k in ["i2c module", "mcp2515_can", "rs232 wave", "dtmf decoder"]):
        return "ICs & Semiconductors"
    if any(k in nl for k in ["joystick module", "rotatory encoder module"]):
        return "Sensors"
    if any(k in nl for k in ["powerpro", "tc unit", "feedback system anna", "demo module", "person tracking"]):
        return "Development & Breakout Boards"

    # 1. Motors, Pumps & Actuators (check before watt/valves)
    if any(k in nl for k in ["motor", "motors", "servo", "stepper", "solenoid", "solonidal", "valve", "pump", "pumps"]):
        return "Motors, Pumps & Actuators"

    # 2. Batteries, Adapters & Power
    if any(k in nl for k in ["battery", "batteries", "18650", "cr2032", "vrla", "lead acid", "lithium iron", "lithium ion", "battries", "battry", "duracell", "everyday", "amptex", "fanso", "east power", "eenrzone", "indo national", "maxpower", "copro"]):
        return "Batteries & Battery Holders"
    if re.search(r"\b\d+(\.\d+)?\s*mah\b", nl) or re.search(r"\b\d+(\.\d+)?\s*ah\b", nl):
        return "Batteries & Battery Holders"
    if any(k in nl for k in ["adapter", "adapters", "charger", "power supply", "laptop adapter", "ups", "extension board"]):
        return "Adapters & Power Supplies"

    # 3. Power & Converter Modules
    if any(k in nl for k in ["converter", "buck", "boost", "step up", "step down", "charger module", "charging module", "tp4056", "tp5100", "dc-dc", "dc -dc", "power multiplier", "protection board", "smps", "solar power manager", "solar panel", "stabiliser", "tps100", "200w 1k"]):
        return "Power & Converter Modules"

    # 4. Potentiometers & Trimmers
    if any(k in nl for k in ["potentiometer", "potention", "trimmer"]):
        return "Potentiometers & Trimmers"
        
    # 5. Diodes & Rectifiers (check before resistors to catch 1W zener diodes)
    if any(k in nl for k in ["bridge rectifier", "bridge rectifiers", "rectifier", "rectifiers", "mb10s", "db107s"]):
        return "SMD Diodes" if "smd" in nl or any(p in nl for p in ["mb10s", "db107s"]) else "Through Hole Diodes"
    if any(k in nl for k in ["smd diode", "diodes smd", "tvs diode", "schottky diode", "smd schottky", "smd zener", "smd-diode", "transient voltage supressor"]):
        return "SMD Diodes"
    if any(k in nl for k in ["through hole diode", "through hole zener", "diodes th", "zener diode", "1n4007", "1n4148", "1n4001", "1n5819", "1n5346", "ph4733a"]):
        if "smd" in nl:
            return "SMD Diodes"
        return "Through Hole Diodes"
    if "diode" in nl or "diodes" in nl or "zener" in nl:
        if "smd" in nl or any(p in nl for p in ["0603", "0805", "1206", "0402", "sod", "sma", "smb", "smc"]):
            return "SMD Diodes"
        return "Through Hole Diodes"

    # 6. Resistors (SMD vs Through Hole)
    if "smd resistor" in nl or "resistors smd" in nl or "resistor smd" in nl or "box13 smd resistor" in nl:
        return "SMD Resistors"
    if "through hole resistor" in nl or "resistors th" in nl or "wire wound resistor" in nl:
        return "Through Hole Resistors"
    if "resistor" in nl or "resistors" in nl:
        if "smd" in nl or any(p in nl for p in ["0603", "0805", "1206", "0402"]):
            return "SMD Resistors"
        return "Through Hole Resistors"
    if re.search(r"\b\d+(\.\d+)?[kKmM]?\s*(ohm|r)\b", nl):
        if "smd" in nl or any(p in nl for p in ["0603", "0805", "1206", "0402"]):
            return "SMD Resistors"
        return "Through Hole Resistors"
    if any(w in nl for w in ["metal film", "wire wound"]) or (re.search(r"\b(0\.25|0\.5|1|2|5)\s*w\b", nl) and "resistor" in nl):
        return "Through Hole Resistors"

    # 7. Capacitors
    if "smd capacitor" in nl or "capacitors smd" in nl or "capacitor smd" in nl:
        return "SMD Capacitors"
    if "through hole capacitor" in nl or "capacitors th" in nl or "electrolyte" in nl or "tantalum" in nl or "polyster" in nl:
        if "smd" in nl:
            return "SMD Capacitors"
        return "Through Hole Capacitors"
    if "capacitor" in nl or "capacitors" in nl:
        if "smd" in nl or any(p in nl for p in ["0603", "0805", "1206", "0402"]):
            return "SMD Capacitors"
        return "Through Hole Capacitors"

    # 8. Inductors & Transformers
    if "inductor" in nl or "inductors" in nl or "ferrite coil" in nl or "ferrite bead" in nl or "ferrite" in nl:
        if "smd" in nl or any(p in nl for p in ["0603", "0805", "1206", "0402", "201", "806"]):
            return "SMD Inductors"
        return "Through Hole Inductors"

    # 9. Transistors, MOSFETs, TRIACs & JFETs
    if any(k in nl for k in ["mosfet", "transistor", "transistors", "bjt", "triac", "jfet"]):
        if "smd" in nl or any(p in nl for p in ["sot", "fdn", "ao34", "2n7002", "sl2323", "mmbt", "bc847", "2sa812", "s8050"]):
            return "SMD Transistors & MOSFETs"
        return "Through Hole Transistors & MOSFETs"
    if any(nl.startswith(prefix) for prefix in [
        "2n2222", "2n3904", "2n3906", "2n4918", "bc109", "bc527", "bc547", "bc548", 
        "bc557", "bc567", "bc327", "d882", "tcpl", "bs170", "irlz44n", "irfz44n", "irf830", "bt136", "bta26", "bta41"
    ]):
        if "smd" in nl:
            return "SMD Transistors & MOSFETs"
        return "Through Hole Transistors & MOSFETs"
    if any(nl.startswith(prefix) for prefix in ["fdn3", "ao34", "a034", "2n7002", "sl2323", "irf", "f9540", "bc847"]):
        if "smd" in nl or any(nl.startswith(prefix) for prefix in ["fdn3", "ao34", "a034", "2n7002", "sl2323", "bc847"]):
            return "SMD Transistors & MOSFETs"
        return "Through Hole Transistors & MOSFETs"
    if "tl061" in nl or "tl071" in nl or "tl081" in nl:
        return "Through Hole Transistors & MOSFETs"

    # 10. Optocouplers & Isolators
    if any(k in nl for k in ["optocoupler", "opto coupler", "photocoupler", "photo coupler", "photo transistor", "el817", "moc3021", "moc3043", "moc3083", "4n35", "optotriac", "isolator"]):
        return "Optocouplers & Isolators"

    # 11. Voltage Regulators
    if any(k in nl for k in ["voltage regulator", "linear voltage regulator", "ams1117", "ld1117", "ws78l05", "tl431", "mic29302", "7805", "78l05"]):
        return "Voltage Regulators"

    # 12. Crystals & Oscillators
    if any(k in nl for k in ["crystal oscillator", "oscillator", "16mhz", "32mhz", "250sx", "16osdf"]):
        return "Crystals & Oscillators"

    # 13. Microcontrollers & ICs
    if any(k in nl for k in ["mcu", "microcontroller", "stm32", "atmega", "pic16", "arm cortex", "attiny", "at tiny"]):
        return "Microcontrollers & ICs"
    if any(k in nl for k in ["eeprom", "rtc", "ds3231", "cd4017", "priority encoder", "transceiver", "max485", "rs485", "rs422", "adum", "tps2113", "ads1115", "op-amp", "ca3130", "timer", "tlc555", "pcf timer"]):
        return "ICs & Semiconductors"
    if " ic" in nl or nl.startswith("ic-") or nl.startswith("ic ") or "smd ic" in nl or "through hole ic" in nl:
        return "ICs & Semiconductors"

    # 14. LEDs & Displays (check re.search to avoid 'sealed' or 'assembled')
    if any(k in nl for k in ["lcd", "tft", "oled", "display", "seven segment", "7 segment", "matrix display", "hmi screen"]):
        return "Displays & Screens"
    if re.search(r"\bleds?\b", nl):
        if "smd" in nl or any(p in nl for p in ["0603", "0805", "1608"]):
            return "SMD LEDs"
        return "Through Hole LEDs"

    # 15. Switches, Buttons & Relays
    if "relay" in nl or "hfe19" in nl:
        return "Relays"
    if any(k in nl for k in ["switch", "switches", "tactile", "push button", "slide switch", "cap 6x6"]):
        if "smd" in nl:
            return "SMD Switches & Buttons"
        return "Through Hole Switches & Buttons"

    # 16. Connectors, Headers & Cables
    if any(k in nl for k in ["cable", "cables", "jumper", "lead", "cord", "wire", "wires", "flat cable", "rg1.13", "rg0.81", "female to female", "male to female", "male to male"]):
        return "Cables & Wires"
    if any(k in nl for k in ["connector", "connectors", "connectos", "jst", "header", "headers", "berg", "socket", "terminal block", "jack", "plug", "sma", "rp-sma", "ipex", "usb", "db9", "fuse holder", "bulb holder", "h2eaders", "sim card slot", "hdmi"]):
        return "Connectors & Headers"

    # 17. Sensors
    if any(k in nl for k in ["sensor", "sensors", "load cell", "accelerometer", "gyroscope", "turbidity", "level switch", "mpu6050", "aht10", "current sensor", "finger print", "flow cell", "bod, toc", "thermistor", "ldr", "anometer", "ncv detector", "soil servey", "thermal camera", "level controller"]):
        return "Sensors"

    # 18. Wireless & IoT Modules
    if any(k in nl for k in ["lora", "gsm", "gprs", "wi-fi", "wifi", "bluetooth", "ble", "gps", "gnss", "quectel", "sim800", "a9", "esp32", "esp 32", "esp8266", "esp 8266", "esp - 12f", "rak3172", "beacon", "gateway"]):
        return "Wireless & IoT Modules"

    # 19. Development & Breakout Boards
    if any(k in nl for k in ["arduino", "breakout board", "breakout boards", "devkit", "proto board", "peripheral board", "feedback board", "tu board", "development board", "tqfp breakout", "raspberry pi", "pico", "power pro", "logic kit", "terminal control", "tc board", "wapi", "panel board"]):
        return "Development & Breakout Boards"

    # 20. Buzzers & Audio
    if any(k in nl for k in ["buzzer", "buzzers", "speaker", "audio", "microphone", "voice recorder"]):
        return "Buzzers & Audio"

    # 21. Cameras & Vision Modules
    if any(k in nl for k in ["camera", "cameras"]):
        return "Cameras & Vision Modules"

    # 22. Antennas
    if "antenna" in nl or "antennas" in nl or "5db" in nl:
        return "Antennas"

    # 23. Enclosures & Mechanical Hardware
    if any(k in nl for k in ["enclosure", "enclosures", "encloser", "screw", "screws", "nut", "nuts", "spacer", "spacers", "standoff", "3d printed", "3d enclosure", "cabinet", "clamp", "clamps", "tray", "trays", "stand for electric"]):
        return "Enclosures & Mechanical Hardware"

    # 24. Tools & Lab Equipment
    if old_cat in ["Tools", "Equipment"] or any(k in nl for k in ["machine", "tool", "cutter", "tweezer", "soldering", "multimeter", "printer", "drill", "microscope", "monitor", "monitors", "programmer", "debugger", "pic kit", "pickit", "st-link", "drone", "robot", "vr headset", "scale"]):
        return "Tools & Lab Equipment"

    # 25. Prototyping & Consumables
    if any(k in nl for k in ["breadboard", "dot board", "pcb", "copper", "solder", "flux", "fevikick", "tape", "zip tag", "glue", "sleeving", "heat shrink", "araldite", "dendrile", "fuse", "resettable fuse", "bulb", "bulbs", "sticker", "stickers", "sd card"]):
        return "Prototyping & Consumables"

    # 26. Project Storage, Kits & Lab Supplies
    if any(k in nl for k in [
        "box", "boxes", "safepaani", "safe pani", "chemicals", "bio digestive", "clicker", 
        "quadprob", "dress", "blanket", "zip cover", "keyboard", "light along with stand",
        "book", "books", "invoice", "catalog", "brochure", "market", "shashank"
    ]):
        return "Project Kits & Lab Supplies"

    # 27. Component Assortments & Kits
    if any(k in nl for k in [
        "amazon", "amici", "asanca", "evelta", "fervid", "foxlink", "forte", "moko", 
        "monson", "nice", "phoenix", "phoneix", "rishabh", "robokits", "robu", 
        "sea", "shah", "sino", "universal", "unknown", "virtual", "vk enterprises",
        "elec future"
    ]):
        return "Component Assortments & Kits"

    # Fallbacks based on old category
    if old_cat in ["Connectors", "Batteries", "Sensors", "Tools", "Equipment"]:
        return old_cat
    if old_cat == "PCB materials":
        return "Development & Breakout Boards"
    if old_cat == "Mechanical components":
        return "Enclosures & Mechanical Hardware"

    return "General Electronic Components"

def apply_recategorization():
    db_path = "data/inventory.sqlite3"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    items = cur.execute("SELECT id, name, category, notes FROM items").fetchall()
    
    updated = 0
    cat_counts = Counter()
    for item_id, name, old_cat, notes in items:
        new_cat = classify(name, old_cat, notes or "")
        cat_counts[new_cat] += 1
        if new_cat != old_cat:
            cur.execute("UPDATE items SET category = ? WHERE id = ?", (new_cat, item_id))
            updated += 1
            
    con.commit()
    con.close()
    print(f"Updated {updated} items in {db_path}.")
    
    # Also sync data/stock_seed.json if present
    seed_path = "data/stock_seed.json"
    try:
        with open(seed_path, "r", encoding="utf-8") as f:
            seed = json.load(f)
        if "items" in seed and isinstance(seed["items"], list):
            seed_updated = 0
            for item in seed["items"]:
                old_c = item.get("category", "")
                new_c = classify(item.get("name", ""), old_c, item.get("notes", ""))
                if new_c != old_c:
                    item["category"] = new_c
                    seed_updated += 1
            with open(seed_path, "w", encoding="utf-8") as f:
                json.dump(seed, f, indent=2, ensure_ascii=False)
            print(f"Updated {seed_updated} items in {seed_path}.")
    except Exception as e:
        print(f"Notice: could not update {seed_path}: {e}")

    print("\nFINAL CATEGORY BREAKDOWN:")
    for c, cnt in cat_counts.most_common():
        print(f"  {c:35} : {cnt}")

if __name__ == "__main__":
    apply_recategorization()
