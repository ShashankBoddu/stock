"""Build a review-first seed inventory from the two exported stock-list Markdown files.

Current stock_list.md quantities are retained as current figures. The 030325 list is
legacy reference data: its quantities are never added to current counts and every
legacy-only item is marked for a physical count.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"
DEFAULT_CURRENT = Path(r"C:\Users\fervi\Downloads\stock_list.md")
DEFAULT_LEGACY = Path(r"C:\Users\fervi\Downloads\Stock_List_030325.md")


def cells(line: str) -> list[str]:
    return [x.strip() for x in line.strip().strip("|").split("|")]


def parse_markdown(path: Path):
    section = "Stock List"
    table, start_line = [], 0
    tables = []

    def flush():
        nonlocal table
        if table:
            tables.append((section, start_line, table))
            table = []

    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if raw.startswith("## "):
            flush()
            section = raw[3:].strip()
        elif raw.startswith("|"):
            row = cells(raw)
            if not row or all(re.fullmatch(r":?-{2,}:?", c or "-") for c in row):
                continue
            if not table:
                start_line = line_no
            table.append((line_no, row))
        else:
            flush()
    flush()
    return tables


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def safe_code(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().upper()
    value = re.sub(r"[^A-Z0-9]+", "-", value).strip("-")
    return value[:40] or "UNASSIGNED"


def qty_value(value: str):
    s = str(value or "").strip().replace(",", "")
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    if re.fullmatch(r"\d+\.0+", s):
        return int(float(s))
    return None


def cell(row, index):
    return row[index].strip() if index is not None and index < len(row) else ""


def explicit_header(table_rows):
    # The Markdown exporter puts a generic Row/Column header first; the next row
    # contains the original workbook headings. Prefer a row with a quantity label.
    for idx, (_, row) in enumerate(table_rows):
        joined = " ".join(row).casefold()
        if any(k in joined for k in ("quantity", "qunatity", "qty", "quantitiy")):
            return idx, row
    return None, None


def location_record(label: str, source: str, section: str):
    label = re.sub(r"\s+", " ", label).strip(" /-")
    if not label:
        label = f"Location needs checking / {section}"
    code = safe_code(label)
    if source == "legacy" and not label.lower().startswith("legacy"):
        code = "OLD-" + safe_code(section) + "-" + code
        label = f"Legacy reference / {section} / {label}"
    return code, label


def make_record(source, section, line_no, name, quantity, location, note=""):
    name = re.sub(r"\s+", " ", str(name or "")).strip(" ;,|-")
    if not name or norm(name) in {"total", "total cost", "s no", "sl no"} or re.fullmatch(r"[\d., ]+", name):
        return None
    code, label = location_record(location, source, section)
    return {"source": source, "section": section, "line": line_no,
            "name": name, "quantity": quantity, "location_code": code,
            "location_name": label, "note": note}


def parse_current(path: Path):
    records, skipped = [], []
    tables = parse_markdown(path)
    for section, _, rows0 in tables:
        rows = [r for _, r in rows0]
        hidx, header = explicit_header(rows0)
        if hidx is None:
            skipped.append((section, rows0[0][0], "No quantity header"))
            continue
        qidx = next((i for i, x in enumerate(header) if re.search(r"quantity|qunatity|qty|quantitiy", x, re.I)), None)
        if qidx is None:
            continue
        section_key = norm(section)
        inherited_loc = ""
        inherited_box = ""
        inherited_shelf = ""
        inherited_group = ""
        for line_no, row in rows0[hidx + 1:]:
            if not row or not any(row):
                continue
            # Skip workbook notes which were embedded below the Rack-A inventory.
            joined = " ".join(row).casefold()
            if any(x in joined for x in ("every box should", "all the material should", "a monitor, printer", "server room stock", "is there use of all", "every material present", "whatsapp group")):
                skipped.append((section, line_no, "Workbook note, not an item"))
                continue
            loc = ""
            name = ""
            qty = qty_value(cell(row, qidx))
            note = ""
            if section_key.startswith("iot rack"):
                rack = cell(row, 1)
                if rack:
                    inherited_loc = rack
                    inherited_box = ""
                if section_key == "iot rack c":
                    box = cell(row, 2)
                    if box and re.match(r"box\b", box, re.I):
                        inherited_box = box
                        name = " ".join(x for x in (cell(row, 3), cell(row, 4)) if x)
                    else:
                        name = " ".join(x for x in (box, cell(row, 3), cell(row, 4)) if x)
                    loc = " / ".join(x for x in ("IoT Rack-C", inherited_loc, inherited_box) if x)
                elif section_key == "iot rack e":
                    name = " ".join(x for x in (cell(row, 2), cell(row, 3)) if x)
                    loc = " / ".join(x for x in ("IoT Rack-E", inherited_loc) if x)
                else:
                    name = " ".join(x for x in (cell(row, col) for col in range(2, qidx)) if x and x.casefold() not in {"quantity", "qunatity"})
                    loc = " / ".join(x for x in (section, inherited_loc) if x)
            elif section_key == "on ground":
                name = cell(row, 2)
                loc = "On Ground"
            elif section_key == "white cupboard":
                shelf = cell(row, 1)
                box = cell(row, 2)
                if shelf:
                    inherited_shelf = shelf
                    inherited_group = ""
                if box:
                    inherited_group = box
                name = cell(row, 3)
                loc = " / ".join(x for x in ("White Cupboard", inherited_shelf, inherited_group) if x)
            elif section_key == "grey cupboard":
                box = cell(row, 1)
                if box:
                    inherited_group = box
                name = cell(row, 2)
                loc = " / ".join(x for x in ("Grey Cupboard", inherited_group) if x)
            else:
                name = cell(row, 2) or cell(row, 1)
                loc = section
            if not name:
                continue
            # A numeric value that is not a whole count remains a reference note.
            if qty is None and cell(row, qidx):
                note = f"Source quantity not imported as a whole number: {cell(row, qidx)}"
            rec = make_record("current", section, line_no, name, qty, loc, note)
            if rec:
                records.append(rec)
    return records, skipped


NAME_HINTS = ("name", "sensor", "board", "equipment", "component", "resistor", "capacitor", "diode", "connector", "display", "product", "item", "description", "module", "battery", "transistor", "jst", "inductor", "mosfet", "ic", "tools", "material")
QTY_HINTS = ("quantity available", "quantity", "qty", "qunatity", "quantitiy", "total no of boards", "total quantity")


def is_qty_header(value):
    val = value.casefold().strip()
    return any(x in val for x in QTY_HINTS) and not any(x in val for x in ("unit price", "total price", "total cost", "quantity taken", "used quantity", "used boards"))


def quantity_indices(row):
    available = [i for i, value in enumerate(row) if "quantity available" in value.casefold()]
    if available:
        return available
    ordinary = [i for i, value in enumerate(row) if is_qty_header(value) and "total quantity" not in value.casefold()]
    if ordinary:
        return ordinary
    total = [i for i, value in enumerate(row) if "total quantity" in value.casefold()]
    if total:
        return total
    return [i for i, value in enumerate(row) if is_qty_header(value)]


def infer_category(section, name):
    s, n = norm(section), norm(name)
    if any(x in n for x in ("sensor", "analyzer", "analyser")) or "sensors" in s:
        return "Sensors"
    if any(x in n for x in ("battery", "batteries", "cell holder")):
        return "Batteries"
    if any(x in n for x in ("connector", "jst", "cable", "header", "terminal block")):
        return "Connectors"
    if any(x in n for x in ("pcb", "prototype", "circuit board", "peripheral board", "board v")) or "pcb" in s or "prototype" in s:
        return "PCB materials"
    if any(x in n for x in ("resistor", "capacitor", "diode", "transistor", "mosfet", "inductor", "relay", "regulator", "crystal", "ic ", " ic")) or any(x in s for x in ("resistor", "capacitor", "diode", "transistor", "inductor")):
        return "Electronic components"
    if any(x in n for x in ("screw", "nut", "enclosure", "spacer", "clamp", "gland")):
        return "Mechanical components"
    if any(x in n for x in ("soldering", "crimping", "screwdriver", "wire stripper", "glue gun", "tool kit", "hacksaw", "cutter")):
        return "Tools"
    if any(x in n for x in ("oscilloscope", "multimeter", "monitor", "weighing scale", "weighing machine", "cro", "drill gun", "3d printing machine", "power supply", "pressure pump", "flow meter")):
        return "Equipment"
    if "equipment sheet" in s:
        return "Equipment"
    if "display" in s or "display" in n or "module" in n or "robot" in n:
        return "Modules"
    return "Uncategorized"


def infer_kind(name):
    n = norm(name)
    reusable = ("oscilloscope", "multimeter", "monitor", "weighing scale", "weighing machine", "cro", "drill gun", "3d printing machine", "soldering station", "crimping tool", "glue gun", "wire stripper", "camera", "power supply", "pressure pump", "robot", "analyzer", "analyser", "paper cutter")
    return "asset" if any(x in n for x in reusable) else "consumable"


def parse_legacy(path: Path):
    records, skipped = [], []
    for section, _, rows in parse_markdown(path):
        current_groups = []
        current_location = ""
        for pos, (line_no, row) in enumerate(rows):
            qidxs = quantity_indices(row)
            if qidxs:
                groups = []
                for qidx in qidxs:
                    # Find the closest meaningful item heading before this quantity
                    # heading; ignore sequence numbers, vendors, and location fields.
                    candidates = []
                    for i in range(qidx):
                        text = row[i].strip()
                        low = text.casefold()
                        if any(h in low for h in NAME_HINTS) and not any(x in low for x in ("sl.no", "s.no", "box no", "box number", "unit price", "total price", "quantity")):
                            candidates.append(i)
                    nameidx = candidates[-1] if candidates else qidx - 1
                    # For boards, the adjacent module column is useful item detail.
                    extra_nameidx = None
                    if norm(section) == "prototypes" and nameidx >= 1:
                        extra_nameidx = nameidx - 1
                        if not any(h in row[extra_nameidx].casefold() for h in ("board", "module")):
                            extra_nameidx = None
                    loc_candidates = [i for i in range(qidx) if re.search(r"box\s*(no|number)|set\s*no|shelf\s*no|rack\s*no", row[i], re.I) and not re.search(r"components in|description", row[i], re.I)]
                    locidx = loc_candidates[-1] if loc_candidates else None
                    descriptor = row[nameidx].strip() if nameidx < len(row) else ""
                    group_start = 0
                    seq_idxs = [i for i in range(qidx) if re.fullmatch(r"s(?:l)?\.?\s*no\.?", row[i].strip(), re.I)]
                    if seq_idxs:
                        group_start = seq_idxs[-1]
                        # Recompute within a side-by-side table group.
                        local = [i for i in candidates if i > group_start]
                        if local:
                            nameidx = local[-1]
                            descriptor = row[nameidx].strip()
                    groups.append({"q": qidx, "name": nameidx, "extra": extra_nameidx, "loc": locidx, "descriptor": descriptor, "start": group_start})
                current_groups = groups
                continue
            # A new workbook header without an available-count column (for example
            # Used Quantity / Not Used Quantity) changes the row layout. Do not
            # carry a prior table's column map into those rows.
            if any(re.search(r"box number|components in it|used quantity|not used quantity|sl\.no|s\.no", x, re.I) for x in row):
                current_groups = []
                continue
            if not current_groups:
                continue
            row_values = [str(x).strip() for x in row]
            joined = " ".join(row_values).casefold()
            if any(x in joined for x in ("total cost", "total quantity", "grand total")) and all(not qty_value(row_values[g["q"]] if g["q"] < len(row_values) else "") for g in current_groups):
                skipped.append((section, line_no, "Summary row"))
                continue
            for group in current_groups:
                qraw = cell(row_values, group["q"])
                nameval = cell(row_values, group["name"])
                extra = cell(row_values, group["extra"])
                locraw = cell(row_values, group["loc"])
                if locraw and not re.search(r"box\s*(no|number)|set\s*no|shelf\s*no|rack\s*no", locraw, re.I):
                    current_location = locraw
                loc = current_location or f"Location needs checking / {section}"
                if not nameval and not extra:
                    continue
                # Compact per-row labels (Male/Female, etc.) complete the heading.
                generic = norm(nameval) in {"male", "female", "single side female", "single side femle", "female to female", "single side female 2510"}
                if generic and group["descriptor"]:
                    name = f"{group['descriptor']} - {nameval}"
                elif extra and extra != nameval:
                    name = " - ".join(x for x in (extra, nameval) if x)
                else:
                    name = nameval
                qty = qty_value(qraw)
                note = "Legacy quantity is reference only; recount before use."
                if qraw and qty is None:
                    note += f" Source quantity: {qraw}"
                rec = make_record("legacy", section, line_no, name, qty, loc, note)
                if rec:
                    records.append(rec)
    return records, skipped


def merge_records(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[norm(record["name"])].append(record)
    merged = []
    locations = {}
    stock_rows = []
    for idx, (key, group) in enumerate(sorted(grouped.items()), 1):
        current = [r for r in group if r["source"] == "current"]
        legacy = [r for r in group if r["source"] == "legacy"]
        chosen = (current or legacy)[0]
        name_record = next((r for r in current if r["name"]), chosen)
        item_code = f"STK-{idx:05d}"
        cat = infer_category(name_record["section"], name_record["name"])
        notes = []
        if legacy:
            old_refs = "; ".join(f"{r['section']} row {r['line']} qty={r['quantity'] if r['quantity'] is not None else '?'}" for r in legacy[:8])
            notes.append("Legacy reference only: " + old_refs)
        if current:
            current_refs = "; ".join(f"{r['section']} row {r['line']}" for r in current[:8])
            notes.append("Current source: " + current_refs)
        if len(group) > 1 and current:
            notes.append(f"Merged {len(current)} current/legacy source row(s) by exact normalized item name; legacy quantities not added.")
        item_locations = []
        if current:
            by_loc = defaultdict(list)
            for r in current:
                by_loc[(r["location_code"], r["location_name"])].append(r)
            needs_item_count = False
            for (loc_code, loc_name), loc_group in by_loc.items():
                loc_key = (loc_code, loc_name)
                locations[loc_key] = {"code": loc_code, "name": loc_name}
                quantities = [r["quantity"] for r in loc_group]
                if len(loc_group) == 1 and quantities[0] is not None:
                    quantity = quantities[0]
                    needs = False
                else:
                    quantity = 0
                    needs = True
                    needs_item_count = True
                if any(r["note"] for r in loc_group):
                    needs = True
                    needs_item_count = True
                stock_rows.append({"item_code": item_code, "location_code": loc_code, "quantity": quantity, "needs_count": needs,
                                   "reference_quantity": quantities[0] if len(quantities)==1 else None})
                item_locations.append(loc_name)
            if any(r["quantity"] is None or r["note"] for r in current):
                needs_item_count = True
        else:
            needs_item_count = True
            by_loc = defaultdict(list)
            for r in legacy:
                by_loc[(r["location_code"], r["location_name"])].append(r)
            for (loc_code, loc_name), loc_group in by_loc.items():
                locations[(loc_code, loc_name)] = {"code": loc_code, "name": loc_name}
                stock_rows.append({"item_code": item_code, "location_code": loc_code, "quantity": 0, "needs_count": True,
                                   "reference_quantity": loc_group[0]["quantity"] if len(loc_group)==1 else None})
                item_locations.append(loc_name)
        merged.append({"item_code": item_code, "name": name_record["name"], "category": cat, "kind": infer_kind(name_record["name"]),
                       "unit": "Nos", "min_qty": None, "needs_count": bool(needs_item_count),
                       "notes": " | ".join(notes), "locations": sorted(set(item_locations))})
    # Review spelling variants only when the token structure and numbers match.
    # Different connector pin counts, genders, capacities, or model numbers are
    # meaningful variants, not likely duplicates.
    possible = []
    names = [(m["item_code"], m["name"], norm(m["name"])) for m in merged]
    for i, (code_a, name_a, norm_a) in enumerate(names):
        for code_b, name_b, norm_b in names[i+1:]:
            if not norm_a or not norm_b or norm_a == norm_b:
                continue
            tokens_a, tokens_b = norm_a.split(), norm_b.split()
            if len(tokens_a) != len(tokens_b):
                continue
            if re.findall(r"\d+(?:\.\d+)?", norm_a) != re.findall(r"\d+(?:\.\d+)?", norm_b):
                continue
            special = {"male","female","old","new","big","small","single","double","used","damaged","black","white","red","green","yellow"}
            diffs = [(a,b) for a,b in zip(tokens_a,tokens_b) if a!=b]
            if not diffs or any(a in special or b in special for a,b in diffs):
                continue
            ratios = [SequenceMatcher(None,a,b).ratio() for a,b in diffs]
            ratio = sum(ratios)/len(ratios)
            if len(diffs) <= 2 and ratio >= 0.84 and all(not a.isdigit() and not b.isdigit() for a,b in diffs):
                possible.append({"item_code_a":code_a,"name_a":name_a,"item_code_b":code_b,"name_b":name_b,"similarity":round(ratio,3)})
    return merged, list(locations.values()), stock_rows, possible


def write_outputs(current_path: Path, legacy_path: Path):
    OUT.mkdir(exist_ok=True)
    current, current_skipped = parse_current(current_path)
    legacy, legacy_skipped = parse_legacy(legacy_path)
    records = current + legacy
    merged, locations, stock_rows, possible = merge_records(records)
    seed = {"source_files":[current_path.name, legacy_path.name], "items":merged,
            "locations":locations, "stock":stock_rows,
            "source_records":records}
    (OUT / "stock_seed.json").write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "stock_import_review.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(["source","section","line","item","reference quantity","location","note"])
        for r in records:
            w.writerow([r["source"],r["section"],r["line"],r["name"],"" if r["quantity"] is None else r["quantity"],r["location_name"],r["note"]])
    with (OUT / "possible_duplicate_review.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=["item_code_a","name_a","item_code_b","name_b","similarity"])
        w.writeheader(); w.writerows(possible)
    # Keep a verbatim, sectioned source merge so no original text is lost.
    body_current = current_path.read_text(encoding="utf-8-sig")
    body_legacy = legacy_path.read_text(encoding="utf-8-sig")
    combined = ("# Merged Stock List — Review Copy\n\n"
        "This file preserves both source lists. The 030325 workbook is treated as legacy reference data; its quantities are not added to the current stock list. Blank, conflicting, or legacy-only counts need a physical count.\n\n"
        "## Current stock list source\n\n" + body_current + "\n\n---\n\n## Legacy Stock List 030325 source\n\n" + body_legacy)
    (OUT / "stock_lists_merged.md").write_text(combined, encoding="utf-8")
    summary = {
        "current_source_rows":len(current), "legacy_source_rows":len(legacy),
        "merged_items":len(merged), "storage_locations":len(locations),
        "stock_location_rows":len(stock_rows), "possible_duplicate_pairs":len(possible),
        "current_rows_not_used_as_items":len(current_skipped), "legacy_rows_not_used_as_items":len(legacy_skipped),
        "current_items_with_counts":sum(1 for r in current if r["quantity"] is not None),
        "current_items_needing_count":sum(1 for r in current if r["quantity"] is None),
        "legacy_only_items":sum(1 for x in merged if not any(r["source"]=="current" and norm(r["name"])==norm(x["name"]) for r in records)),
    }
    (OUT / "stock_merge_report.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    cur = Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_CURRENT
    old = Path(sys.argv[2]) if len(sys.argv)>2 else DEFAULT_LEGACY
    write_outputs(cur, old)
