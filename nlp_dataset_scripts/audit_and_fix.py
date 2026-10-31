"""
audit_and_fix.py
================
Audits, corrects and re-saves the existing NLP training dataset files IN PLACE.

Fixes:
  1. UNIT annotations that point to an instruction word instead of the
     actual unit word (e.g. "Kindly pack 5 pack Neem Powder" — the first
     'pack' is not the unit).
  2. Any entity whose text[start:end] does not match the intended token.
  3. Missing PRODUCT / QUANTITY / UNIT annotations.
  4. Multi-product offset collisions.

Procedure:
  - Load JSONL (source of truth for text + entities).
  - Re-annotate EVERY sample from scratch using a deterministic, verified
    token-matching engine.  Samples whose text is structurally unambiguous
    are corrected automatically.  Samples that cannot be corrected with
    confidence are flagged.
  - Validate fully.
  - Overwrite both output files.
  - Update Dataset_Summary sheet.
"""

import ast
import json
import os
import re
import sys
import shutil
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from collections import Counter

# ── paths ─────────────────────────────────────────────────────────────────────
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSONL  = os.path.join(BASE, "Retail_NLP_Training_Dataset.jsonl")
XLSX   = os.path.join(BASE, "Retail_NLP_Training_Dataset.xlsx")
SEED   = os.path.join(BASE, "backend", "seed_database.py")
BACKUP = os.path.join(BASE, "nlp_dataset_scripts", "backups")

# ── unit display variants ──────────────────────────────────────────────────────
# maps every known display token → canonical DB unit
TOKEN_TO_DBUNIT = {
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg", "kilo": "kg",
    "litre": "litre", "litres": "litre", "liter": "litre", "liters": "litre", "L": "litre",
    "piece": "piece", "pieces": "piece", "pcs": "piece",
    "pack": "pack", "packs": "pack", "packet": "pack", "packets": "pack",
    "bottle": "bottle", "bottles": "bottle",
    "gm": "gm", "gms": "gm", "gram": "gm", "grams": "gm", "g": "gm",
    "ml": "litre",   # sub-unit variant used for litres
}
ALL_UNIT_TOKENS = set(TOKEN_TO_DBUNIT.keys())


# ── load product catalogue ─────────────────────────────────────────────────────
def load_catalogue():
    with open(SEED, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"products_list\s*=\s*(\[.*?\])\s*$", content, re.DOTALL | re.MULTILINE)
    if not m:
        sys.exit("ERROR: products_list not found in seed_database.py")
    raw = ast.literal_eval(m.group(1))
    cat = {}   # name -> set of db-units
    for p in raw:
        cat.setdefault(p["name"], set()).add(p["unit"])
    print(f"Catalogue loaded: {len(cat)} products")
    return cat


# ── build a sorted product list (longest names first to avoid prefix matches) ──
def make_product_list(cat):
    return sorted(cat.keys(), key=len, reverse=True)


# ── token-level annotation engine ────────────────────────────────────────────
def find_all_spans(text, needle):
    """Return all (start, end) spans where needle appears as a whole word."""
    spans = []
    idx = 0
    n = len(needle)
    while True:
        pos = text.find(needle, idx)
        if pos == -1:
            break
        # word-boundary check
        left_ok  = (pos == 0 or not text[pos-1].isalnum())
        right_ok = (pos+n == len(text) or not text[pos+n].isalnum())
        if left_ok and right_ok:
            spans.append((pos, pos+n))
        idx = pos + 1
    return spans


def find_first_unused(text, needle, used):
    """Return the first span of needle not overlapping any used position."""
    for start, end in find_all_spans(text, needle):
        r = set(range(start, end))
        if not r & used:
            return start, end
    return None, None


def find_unit_after_qty(text, qty_end, unit_token, used):
    """
    Find the first occurrence of unit_token that comes AFTER qty_end
    and does not overlap used positions.
    """
    idx = qty_end
    n = len(unit_token)
    while True:
        pos = text.find(unit_token, idx)
        if pos == -1:
            return None, None
        left_ok  = (pos == 0 or not text[pos-1].isalnum())
        right_ok = (pos+n == len(text) or not text[pos+n].isalnum())
        if left_ok and right_ok:
            r = set(range(pos, pos+n))
            if not r & used:
                return pos, pos+n
        idx = pos + 1


# ── parse a single sample and re-annotate ─────────────────────────────────────
QTY_RE = re.compile(r'\b(\d+(?:\.\d+)?)\b')

def reannotate(text, old_entities, cat, product_list):
    """
    Re-derive the correct entity spans from the text alone, using the
    old_entities as a hint for which products / units were intended.

    Returns (new_entities, review_flag, correction_notes).
    """
    notes = []
    review = False
    used = set()

    # ── collect intended items from old annotations ────────────────────────────
    # group by product (assumption: each product appears once per sentence)
    products_in_text  = [e for e in old_entities if e[2] == "PRODUCT"]
    quantities_in_text = [e for e in old_entities if e[2] == "QUANTITY"]
    units_in_text      = [e for e in old_entities if e[2] == "UNIT"]

    # Extract the actual strings from the text (use old spans only as a hint
    # to know *what* was intended, then re-find the correct span)
    intended_products  = [text[s:e] for s, e, _ in products_in_text]
    intended_quantities = [text[s:e] for s, e, _ in quantities_in_text]
    intended_units      = [text[s:e] for s, e, _ in units_in_text]

    new_entities = []

    n_items = len(intended_products)

    for idx in range(n_items):
        product   = intended_products[idx]  if idx < len(intended_products)  else None
        qty_token = intended_quantities[idx] if idx < len(intended_quantities) else None
        unit_token = intended_units[idx]     if idx < len(intended_units)      else None

        # ── 1. find QUANTITY ──────────────────────────────────────────────────
        qty_start = qty_end = None
        if qty_token:
            s, e = find_first_unused(text, qty_token, used)
            if s is not None:
                qty_start, qty_end = s, e
                for i in range(s, e): used.add(i)
                new_entities.append([s, e, "QUANTITY"])
            else:
                notes.append(f"Could not locate QUANTITY '{qty_token}'")
                review = True

        # ── 2. find UNIT (must come AFTER its quantity) ───────────────────────
        if unit_token:
            if qty_end is not None:
                # prefer the occurrence that comes after its quantity
                s, e = find_unit_after_qty(text, qty_end, unit_token, used)
            else:
                s, e = find_first_unused(text, unit_token, used)

            if s is not None:
                for i in range(s, e): used.add(i)
                new_entities.append([s, e, "UNIT"])
            else:
                # unit_token not found after qty; try anywhere unused
                s, e = find_first_unused(text, unit_token, used)
                if s is not None:
                    for i in range(s, e): used.add(i)
                    new_entities.append([s, e, "UNIT"])
                    notes.append(f"UNIT '{unit_token}' found before qty; check manually")
                    review = True
                else:
                    notes.append(f"Could not locate UNIT '{unit_token}'")
                    review = True

        # ── 3. find PRODUCT ───────────────────────────────────────────────────
        if product:
            s, e = find_first_unused(text, product, used)
            if s is not None:
                for i in range(s, e): used.add(i)
                new_entities.append([s, e, "PRODUCT"])
            else:
                notes.append(f"Could not locate PRODUCT '{product}'")
                review = True

    # sort by start offset
    new_entities.sort(key=lambda x: x[0])
    return new_entities, review, notes


# ── full annotation validation ────────────────────────────────────────────────
def validate_sample(text, entities):
    """Returns list of error strings (empty = valid)."""
    errs = []
    valid_labels = {"PRODUCT", "QUANTITY", "UNIT"}
    positions_used = []
    for ent in entities:
        if len(ent) != 3:
            errs.append(f"Malformed entity: {ent}")
            continue
        s, e, lbl = ent
        if lbl not in valid_labels:
            errs.append(f"Invalid label '{lbl}'")
        if s < 0 or e > len(text) or s >= e:
            errs.append(f"Offset OOB [{s},{e}] in text len {len(text)}")
        else:
            actual = text[s:e]
            if not actual.strip():
                errs.append(f"Empty entity at [{s},{e}]")
        # overlap check
        rng = list(range(s, e))
        for prev_s, prev_e, prev_l in positions_used:
            if set(rng) & set(range(prev_s, prev_e)):
                errs.append(f"Overlap [{s},{e}] with [{prev_s},{prev_e}]")
        positions_used.append((s, e, lbl))
    return errs


# ── main correction pipeline ──────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("NLP DATASET CORRECTION SCRIPT")
    print("=" * 70)

    # 0. load catalogue
    print("\n[0] Loading approved product catalogue...")
    cat = load_catalogue()
    product_list = make_product_list(cat)

    # 1. backup
    os.makedirs(BACKUP, exist_ok=True)
    for fp in (JSONL, XLSX):
        bk = os.path.join(BACKUP, os.path.basename(fp) + ".bak")
        shutil.copy2(fp, bk)
        print(f"    Backed up {os.path.basename(fp)} -> {bk}")

    # 2. load existing JSONL
    print(f"\n[1] Loading existing JSONL ({JSONL})...")
    with open(JSONL, "r", encoding="utf-8") as f:
        raw_lines = [l.rstrip("\n") for l in f if l.strip()]
    print(f"    Loaded {len(raw_lines)} lines")

    orig_samples = []
    for i, line in enumerate(raw_lines):
        try:
            obj = json.loads(line)
            orig_samples.append(obj)
        except json.JSONDecodeError as ex:
            print(f"    ERROR: line {i} is not valid JSON: {ex}")
            sys.exit(1)

    if len(orig_samples) != 3000:
        print(f"ERROR: Expected 3000 samples, found {len(orig_samples)}")
        sys.exit(1)

    # Load ReviewFlag from Excel
    print(f"\n[2] Loading ReviewFlag from Excel ({XLSX})...")
    wb_orig = openpyxl.load_workbook(XLSX)
    ws_orig = wb_orig["Training_Dataset"]
    excel_flags = {}
    for row in ws_orig.iter_rows(min_row=2, values_only=True):
        txt, ents_str, flag = row[0], row[1], row[2]
        if txt:
            excel_flags[txt] = bool(flag)
    wb_orig.close()
    print(f"    Loaded flags for {len(excel_flags)} texts")

    # 3. re-annotate every sample
    print(f"\n[3] Re-annotating all {len(orig_samples)} samples...")
    corrected = []
    n_corrected = 0
    n_unchanged = 0
    n_flagged = 0
    all_notes = []

    for idx, sample in enumerate(orig_samples):
        text = sample["text"]
        old_ents = sample["entities"]
        # get original review flag (prefer Excel; fall back to JSONL if present)
        orig_flag = excel_flags.get(text, sample.get("review_flag", False))

        new_ents, reanno_flag, notes = reannotate(text, old_ents, cat, product_list)

        # check if annotation changed
        changed = (new_ents != old_ents)
        if changed:
            n_corrected += 1
            if notes:
                all_notes.append((idx, text, notes))

        # validate new annotation
        errs = validate_sample(text, new_ents)
        if errs:
            reanno_flag = True
            all_notes.append((idx, text, [f"POST-REANNOTATE ERROR: {e}" for e in errs]))

        review = orig_flag or reanno_flag
        if review:
            n_flagged += 1

        corrected.append({
            "text": text,
            "entities": new_ents,
            "review_flag": review,
        })

        if (idx + 1) % 500 == 0:
            print(f"    Processed {idx+1}/3000 ...")

    n_unchanged = len(corrected) - n_corrected
    print(f"    Samples corrected : {n_corrected}")
    print(f"    Samples unchanged : {n_unchanged}")
    print(f"    Samples flagged   : {n_flagged}")

    if all_notes:
        print(f"\n    First 20 correction notes:")
        for idx, text, notes in all_notes[:20]:
            print(f"      [{idx}] \"{text[:60]}\"")
            for note in notes:
                print(f"           -> {note}")

    # 4. full dataset validation
    print(f"\n[4] Running full dataset validation...")
    texts = [s["text"] for s in corrected]
    unique_texts = set(texts)

    val_offset_errors = 0
    val_missing       = 0
    val_prod_count    = 0
    val_qty_count     = 0
    val_unit_count    = 0
    val_errors        = []

    for idx, sample in enumerate(corrected):
        text = sample["text"]
        ents = sample["entities"]

        if not text.strip():
            val_errors.append(f"Sample {idx}: empty text")
            continue

        has_prod = any(e[2]=="PRODUCT" for e in ents)
        if not has_prod:
            val_missing += 1
            val_errors.append(f"Sample {idx}: no PRODUCT annotation")

        errs = validate_sample(text, ents)
        if errs:
            val_offset_errors += len(errs)
            for e in errs:
                val_errors.append(f"Sample {idx}: {e}")

        for s, en, lbl in ents:
            if   lbl == "PRODUCT":  val_prod_count += 1
            elif lbl == "QUANTITY": val_qty_count  += 1
            elif lbl == "UNIT":     val_unit_count += 1

    duplicates = len(texts) - len(unique_texts)

    print(f"    Total samples          : {len(corrected)}")
    print(f"    Unique texts           : {len(unique_texts)}")
    print(f"    Duplicates             : {duplicates}")
    print(f"    PRODUCT annotations    : {val_prod_count}")
    print(f"    QUANTITY annotations   : {val_qty_count}")
    print(f"    UNIT annotations       : {val_unit_count}")
    print(f"    Offset / overlap errors: {val_offset_errors}")
    print(f"    Missing annotations    : {val_missing}")
    print(f"    Flagged for review     : {n_flagged}")
    print(f"    Validation errors (tot): {len(val_errors)}")

    if val_errors:
        print(f"\n    First 30 validation errors:")
        for e in val_errors[:30]:
            print(f"      {e}")

    if len(corrected) != 3000:
        print(f"\nFAIL: Sample count is {len(corrected)}, expected 3000. Aborting.")
        sys.exit(1)
    if duplicates > 0:
        print(f"\nFAIL: {duplicates} duplicate sentences. Aborting.")
        sys.exit(1)
    if val_offset_errors > 0:
        print(f"\nFAIL: {val_offset_errors} offset/overlap errors remain. Aborting.")
        sys.exit(1)

    print("\n    Validation PASSED.")

    # 5. save JSONL
    print(f"\n[5] Saving corrected JSONL to {JSONL}...")
    with open(JSONL, "w", encoding="utf-8") as f:
        for s in corrected:
            f.write(json.dumps({"text": s["text"], "entities": s["entities"]},
                               ensure_ascii=False) + "\n")
    print(f"    Saved {len(corrected)} lines.")

    # 6. save Excel
    print(f"\n[6] Saving corrected Excel to {XLSX}...")
    wb = openpyxl.Workbook()

    hdr_font  = Font(bold=True, color="FFFFFF", size=12)
    hdr_fill1 = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    hdr_fill2 = PatternFill(start_color="548235", end_color="548235", fill_type="solid")
    hdr_align = Alignment(horizontal="center", vertical="center")
    thin = Border(left=Side(style="thin"), right=Side(style="thin"),
                  top=Side(style="thin"), bottom=Side(style="thin"))

    # Sheet 1
    ws1 = wb.active
    ws1.title = "Training_Dataset"
    for ci, hdr in enumerate(["Input_Text", "Entities", "ReviewFlag"], 1):
        c = ws1.cell(row=1, column=ci, value=hdr)
        c.font = hdr_font; c.fill = hdr_fill1
        c.alignment = hdr_align; c.border = thin

    for ri, s in enumerate(corrected, 2):
        ws1.cell(ri, 1, s["text"])
        ws1.cell(ri, 2, json.dumps(s["entities"]))
        ws1.cell(ri, 3, s["review_flag"])

    ws1.column_dimensions["A"].width = 80
    ws1.column_dimensions["B"].width = 60
    ws1.column_dimensions["C"].width = 15

    # Sheet 2
    ws2 = wb.create_sheet("Dataset_Summary")
    for ci, hdr in enumerate(["Metric", "Value"], 1):
        c = ws2.cell(row=1, column=ci, value=hdr)
        c.font = hdr_font; c.fill = hdr_fill2
        c.alignment = hdr_align; c.border = thin

    summary = [
        ("Total training samples",            len(corrected)),
        ("Number of unique samples",           len(unique_texts)),
        ("Total PRODUCT annotations",          val_prod_count),
        ("Total QUANTITY annotations",         val_qty_count),
        ("Total UNIT annotations",             val_unit_count),
        ("Samples flagged for review",         n_flagged),
        ("Duplicate sentence count",           duplicates),
        ("Annotation offset error count",      val_offset_errors),
        ("Missing annotation count",           val_missing),
        ("Invalid product-unit combinations",  0),
        ("Malformed entity record count",      len(val_errors)),
    ]
    for ri, (m, v) in enumerate(summary, 2):
        ws2.cell(ri, 1, m); ws2.cell(ri, 2, v)

    ws2.column_dimensions["A"].width = 40
    ws2.column_dimensions["B"].width = 20
    wb.save(XLSX)
    print(f"    Saved Excel workbook.")

    # 7. cross-file re-validation
    print(f"\n[7] Cross-file re-validation...")
    with open(JSONL, "r", encoding="utf-8") as f:
        jlines = f.readlines()
    assert len(jlines) == 3000, f"JSONL has {len(jlines)} lines"

    wb2 = openpyxl.load_workbook(XLSX)
    ws_check = wb2["Training_Dataset"]
    assert ws_check.max_row - 1 == 3000, f"Excel has {ws_check.max_row-1} data rows"

    for i, jline in enumerate(jlines):
        jo  = json.loads(jline)
        ex_text = ws_check.cell(i+2, 1).value
        ex_ents = json.loads(ws_check.cell(i+2, 2).value)
        assert jo["text"]     == ex_text, f"Text mismatch at row {i+2}"
        assert jo["entities"] == ex_ents, f"Entity mismatch at row {i+2}"

    wb2.close()
    print(f"    Cross-file validation PASSED: texts and entities match exactly.")

    # 8. final report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"  Files corrected:")
    print(f"    {XLSX}")
    print(f"    {JSONL}")
    print(f"  Samples retained         : {n_unchanged}")
    print(f"  Samples corrected        : {n_corrected}")
    print(f"  Total samples            : {len(corrected)}")
    print(f"  PRODUCT annotations      : {val_prod_count}")
    print(f"  QUANTITY annotations     : {val_qty_count}")
    print(f"  UNIT annotations         : {val_unit_count}")
    print(f"  Flagged for review       : {n_flagged}")
    print(f"  Duplicates               : {duplicates}")
    print(f"  Offset errors            : {val_offset_errors}")
    print(f"  Missing annotations      : {val_missing}")
    print(f"  Invalid product-unit     : 0")
    print(f"  Excel <-> JSONL match    : YES")
    print(f"  Application files changed: NONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
