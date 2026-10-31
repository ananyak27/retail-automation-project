"""
audit_readonly.py  —  READ-ONLY deep audit of the NLP training dataset.
Produces a detailed report.  Modifies NO files.
"""
import ast, json, re, sys, os
from collections import Counter, defaultdict

BASE  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSONL = os.path.join(BASE, "Retail_NLP_Training_Dataset.jsonl")
XLSX  = os.path.join(BASE, "Retail_NLP_Training_Dataset.xlsx")
SEED  = os.path.join(BASE, "backend", "seed_database.py")

import openpyxl

# ── unit token universe ───────────────────────────────────────────────────────
UNIT_TOKENS_TO_DBUNIT = {
    "kg":"kg","kgs":"kg","kilogram":"kg","kilograms":"kg","kilo":"kg",
    "litre":"litre","litres":"litre","liter":"litre","liters":"litre","L":"litre",
    "piece":"piece","pieces":"piece","pcs":"piece",
    "pack":"pack","packs":"pack","packet":"pack","packets":"pack",
    "bottle":"bottle","bottles":"bottle",
    "gm":"gm","gms":"gm","gram":"gm","grams":"gm","g":"gm",
    "ml":"litre",
}

SEP = "=" * 72

# ─────────────────────────────────────────────────────────────────────────────
def load_catalogue():
    with open(SEED, encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"products_list\s*=\s*(\[.*?\])\s*$", txt, re.DOTALL|re.MULTILINE)
    if not m:
        sys.exit("products_list not found in seed_database.py")
    raw = ast.literal_eval(m.group(1))
    cat = {}
    for p in raw:
        cat.setdefault(p["name"], set()).add(p["unit"])
    return cat               # name -> {db-units}

def load_jsonl():
    with open(JSONL, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    samples = []
    bad = []
    for i, ln in enumerate(lines):
        try:
            samples.append(json.loads(ln))
        except json.JSONDecodeError as e:
            bad.append((i, str(e)))
    return samples, bad, len(lines)

def load_excel():
    wb = openpyxl.load_workbook(XLSX)
    sheets = wb.sheetnames
    rows = []
    headers = []
    summary_rows = []
    if "Training_Dataset" in sheets:
        ws = wb["Training_Dataset"]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append(row)
    if "Dataset_Summary" in sheets:
        ws2 = wb["Dataset_Summary"]
        for row in ws2.iter_rows(min_row=2, values_only=True):
            summary_rows.append(row)
    wb.close()
    return sheets, headers, rows, summary_rows

def word_spans(text, needle):
    """All (start,end) whole-word occurrences of needle in text."""
    spans, idx, n = [], 0, len(needle)
    while True:
        p = text.find(needle, idx)
        if p == -1: break
        lo = (p == 0 or not text[p-1].isalnum())
        hi = (p+n == len(text) or not text[p+n].isalnum())
        if lo and hi:
            spans.append((p, p+n))
        idx = p+1
    return spans

# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(SEP)
    print("READ-ONLY DEEP AUDIT REPORT")
    print(SEP)

    # ── A: catalogue ─────────────────────────────────────────────────────────
    print("\n[CATALOGUE]")
    cat = load_catalogue()
    cat_names_lower = {n.lower(): n for n in cat}   # lowercase -> canonical
    n_products = len(cat)
    unit_freq  = Counter(u for units in cat.values() for u in units)
    print(f"  Products in catalogue  : {n_products}")
    print(f"  Unit distribution      : {dict(unit_freq)}")

    # ── B: load JSONL ─────────────────────────────────────────────────────────
    print("\n[JSONL]")
    samples, json_bad, total_lines = load_jsonl()
    print(f"  Lines in file          : {total_lines}")
    print(f"  Valid JSON objects      : {len(samples)}")
    print(f"  Malformed lines         : {len(json_bad)}")
    if json_bad:
        for i,e in json_bad[:5]: print(f"    line {i}: {e}")

    # field check
    extra_fields, missing_fields = [], []
    for i,s in enumerate(samples):
        keys = set(s.keys())
        if keys - {"text","entities"}:
            extra_fields.append((i, keys - {"text","entities"}))
        if "text" not in keys:  missing_fields.append((i,"text"))
        if "entities" not in keys: missing_fields.append((i,"entities"))
    print(f"  Records with extra fields: {len(extra_fields)}")
    if extra_fields[:3]: print(f"    e.g. row 0: {extra_fields[0]}")
    print(f"  Records with missing fields: {len(missing_fields)}")

    # ── C: load Excel ─────────────────────────────────────────────────────────
    print("\n[EXCEL]")
    sheets, headers, ex_rows, summary_rows = load_excel()
    print(f"  Sheets                 : {sheets}")
    print(f"  Training_Dataset cols  : {headers}")
    print(f"  Training_Dataset rows  : {len(ex_rows)}")
    print(f"  Dataset_Summary rows   : {len(summary_rows)}")
    if summary_rows:
        print("  Summary sheet contents:")
        for r in summary_rows:
            print(f"    {r[0]:<45} {r[1]}")

    # ── D: dataset-level checks ───────────────────────────────────────────────
    print("\n[DATASET-LEVEL CHECKS]")
    texts_jsonl  = [s["text"] for s in samples]
    texts_excel  = [r[0] for r in ex_rows]
    dup_jsonl    = [t for t,c in Counter(texts_jsonl).items() if c>1]
    dup_excel    = [t for t,c in Counter(texts_excel).items() if c>1]
    empty_jsonl  = [i for i,t in enumerate(texts_jsonl) if not str(t).strip()]
    empty_excel  = [i for i,r in enumerate(ex_rows) if not str(r[0]).strip()]
    print(f"  JSONL unique texts      : {len(set(texts_jsonl))}")
    print(f"  JSONL duplicates        : {len(dup_jsonl)}")
    if dup_jsonl: print(f"    e.g. '{dup_jsonl[0][:60]}'")
    print(f"  JSONL empty texts       : {len(empty_jsonl)}")
    print(f"  Excel unique texts      : {len(set(texts_excel))}")
    print(f"  Excel duplicates        : {len(dup_excel)}")
    print(f"  Excel empty texts       : {len(empty_excel)}")

    # ── E: cross-file consistency ─────────────────────────────────────────────
    print("\n[CROSS-FILE CONSISTENCY]")
    mismatches = []
    limit = min(len(samples), len(ex_rows))
    for i in range(limit):
        jtext = samples[i]["text"]
        etext = ex_rows[i][0]
        jents = samples[i]["entities"]
        try:
            eents_raw = ex_rows[i][1]
            eents = json.loads(eents_raw) if eents_raw else []
        except Exception:
            eents = None
        if jtext != etext:
            mismatches.append((i,"text", jtext[:50], str(etext)[:50]))
        if eents is not None and jents != eents:
            mismatches.append((i,"entities", str(jents)[:60], str(eents)[:60]))
    print(f"  Rows compared           : {limit}")
    print(f"  Mismatches (text)       : {sum(1 for m in mismatches if m[1]=='text')}")
    print(f"  Mismatches (entities)   : {sum(1 for m in mismatches if m[1]=='entities')}")
    if mismatches[:3]:
        for m in mismatches[:3]:
            print(f"    row {m[0]} [{m[1]}]: jsonl='{m[2]}' | excel='{m[3]}'")

    # ── F: annotation-level checks ────────────────────────────────────────────
    print("\n[ANNOTATION-LEVEL CHECKS]")
    valid_labels = {"PRODUCT","QUANTITY","UNIT"}
    offset_errors, label_errors, malformed = [], [], []
    overlap_errors = []
    prod_count = qty_count = unit_count = 0
    missing_product, missing_qty, missing_unit = [], [], []

    for i, s in enumerate(samples):
        text = s["text"]
        ents = s["entities"]
        has_p = has_q = has_u = False
        positions = []
        for ent in ents:
            # malformed?
            if not (isinstance(ent, list) and len(ent)==3):
                malformed.append((i, ent)); continue
            st, en, lbl = ent
            if lbl not in valid_labels:
                label_errors.append((i, lbl)); continue
            if st<0 or en>len(text) or st>=en:
                offset_errors.append((i, st, en, lbl, text)); continue
            # overlap
            for ps,pe,pl in positions:
                if max(st,ps) < min(en,pe):
                    overlap_errors.append((i, (st,en,lbl),(ps,pe,pl), text))
            positions.append((st,en,lbl))
            if lbl=="PRODUCT": prod_count+=1; has_p=True
            elif lbl=="QUANTITY": qty_count+=1; has_q=True
            elif lbl=="UNIT": unit_count+=1; has_u=True
        if not has_p: missing_product.append(i)
        if not has_q: missing_qty.append(i)
        if not has_u: missing_unit.append(i)

    print(f"  PRODUCT annotations     : {prod_count}")
    print(f"  QUANTITY annotations    : {qty_count}")
    print(f"  UNIT annotations        : {unit_count}")
    print(f"  Malformed entities      : {len(malformed)}")
    print(f"  Invalid labels          : {len(label_errors)}")
    print(f"  Offset OOB errors       : {len(offset_errors)}")
    if offset_errors[:3]:
        for e in offset_errors[:3]: print(f"    row {e[0]}: [{e[1]},{e[2]}] {e[3]} | '{e[4][:50]}'")
    print(f"  Overlap errors          : {len(overlap_errors)}")
    if overlap_errors[:3]:
        for e in overlap_errors[:3]: print(f"    row {e[0]}: {e[1]} overlaps {e[2]}")
    print(f"  Samples missing PRODUCT : {len(missing_product)}")
    print(f"  Samples missing QUANTITY: {len(missing_qty)}")
    if missing_qty[:5]: print(f"    e.g. rows {missing_qty[:5]}")
    print(f"  Samples missing UNIT    : {len(missing_unit)}")
    if missing_unit[:5]: print(f"    e.g. rows {missing_unit[:5]}")

    # ── G: verify extracted substrings ───────────────────────────────────────
    print("\n[EXTRACTED-SUBSTRING VERIFICATION]")
    substr_errors = []
    for i, s in enumerate(samples):
        text = s["text"]
        for ent in s["entities"]:
            if not (isinstance(ent,list) and len(ent)==3): continue
            st, en, lbl = ent
            if st<0 or en>len(text) or st>=en: continue
            extracted = text[st:en]
            if not extracted.strip():
                substr_errors.append((i, st, en, lbl, text, "empty"))
    print(f"  Substring extraction errors: {len(substr_errors)}")
    if substr_errors[:5]:
        for e in substr_errors[:5]:
            print(f"    row {e[0]}: [{e[1]},{e[2]}] '{e[3]}' extracted='{e[4][e[1]:e[2]]}' text='{e[4][:60]}'")

    # ── H: PRODUCT vs catalogue ───────────────────────────────────────────────
    print("\n[PRODUCT vs CATALOGUE]")
    cat_exact   = set(cat.keys())
    cat_lower   = {n.lower() for n in cat}
    not_in_cat  = []
    in_cat_lower_only = []
    for i, s in enumerate(samples):
        for ent in s["entities"]:
            if not (isinstance(ent,list) and len(ent)==3): continue
            st, en, lbl = ent
            if lbl != "PRODUCT": continue
            if st<0 or en>len(s["text"]) or st>=en: continue
            p = s["text"][st:en]
            if p not in cat_exact:
                if p.lower() in cat_lower:
                    in_cat_lower_only.append((i, p))
                else:
                    not_in_cat.append((i, p))

    print(f"  Products NOT in catalogue (exact): {len(not_in_cat)}")
    sample_not = {}
    for i,p in not_in_cat:
        sample_not.setdefault(p,[]).append(i)
    for p, rows in list(sample_not.items())[:15]:
        print(f"    '{p}'  rows={rows[:5]}")

    print(f"  Products found via lowercase match only: {len(in_cat_lower_only)}")
    for i,p in in_cat_lower_only[:5]:
        print(f"    row {i}: '{p}'")

    # ── I: UNIT vs catalogue ──────────────────────────────────────────────────
    print("\n[UNIT vs CATALOGUE]")
    unknown_units = []
    invalid_prod_unit = []
    for i, s in enumerate(samples):
        text = s["text"]
        ents = s["entities"]
        # pair up products with their units by proximity
        prod_ents = [(st,en,lbl) for st,en,lbl in ents if lbl=="PRODUCT"]
        unit_ents = [(st,en,lbl) for st,en,lbl in ents if lbl=="UNIT"]
        for idx_p, (pst,pen,_) in enumerate(prod_ents):
            p_name = text[pst:pen]
            if idx_p < len(unit_ents):
                ust,uen,_ = unit_ents[idx_p]
                u_tok = text[ust:uen]
                db_unit = UNIT_TOKENS_TO_DBUNIT.get(u_tok)
                if db_unit is None:
                    unknown_units.append((i, u_tok, p_name))
                elif p_name in cat and db_unit not in cat[p_name]:
                    invalid_prod_unit.append((i, p_name, u_tok, db_unit, cat.get(p_name)))

    print(f"  Unknown unit tokens      : {len(unknown_units)}")
    if unknown_units[:5]:
        for e in unknown_units[:5]: print(f"    row {e[0]}: unit='{e[1]}' product='{e[2]}'")
    print(f"  Invalid product-unit pairs: {len(invalid_prod_unit)}")
    if invalid_prod_unit[:10]:
        for e in invalid_prod_unit[:10]:
            print(f"    row {e[0]}: '{e[1]}' unit='{e[2]}'(db='{e[3]}') allowed={e[4]}")

    # ── J: ReviewFlag analysis ────────────────────────────────────────────────
    print("\n[REVIEWFLAG ANALYSIS]")
    flagged_rows   = [(i,ex_rows[i]) for i in range(len(ex_rows)) if ex_rows[i][2]]
    unflagged_rows = [(i,ex_rows[i]) for i in range(len(ex_rows)) if not ex_rows[i][2]]
    print(f"  Flagged rows (Excel)    : {len(flagged_rows)}")
    print(f"  Unflagged rows (Excel)  : {len(unflagged_rows)}")

    # categorise flagged rows
    # known misspellings from the generation script
    MISSPELLING_MAP_PRODUCTS = {
        "rice","ric","rie","sugar","suger","sugr","milk","mlk",
        "wheat flour","wheat flor","wheet flour",
        "coriander powder","coriender powder","corinder powder",
        "turmeric powder","turmeric powdr","turmaric powder",
        "coconut oil","cocnut oil","coconut oill",
        "basmati rice","basmathi rice","basmti rice",
        "toor dal","toor daal",
        "sunflower oil","sunflwer oil","sunflowr oil",
        "cocnut oil",
    }

    flag_has_misspell     = []   # product not in catalogue
    flag_no_misspell      = []   # flagged but all products in catalogue
    flag_ambiguous_pack   = []   # pack verb issue
    flag_unclear          = []

    for i, row in flagged_rows:
        text  = row[0]
        try:
            ents  = json.loads(row[1]) if row[1] else []
        except: ents = []
        prods = [text[s:e] for s,e,l in ents if l=="PRODUCT" and 0<=s<e<=len(text)]
        any_misspell = any(p not in cat_exact for p in prods)
        has_pack_issue = "pack" in text.split()[:3]  # 'pack' in instruction position
        if any_misspell:
            flag_has_misspell.append((i, text, prods))
        elif has_pack_issue:
            flag_ambiguous_pack.append((i, text))
        else:
            flag_no_misspell.append((i, text, prods))

    print(f"\n  Flagged breakdown:")
    print(f"    Rows with a non-catalogue product (intentional misspelling): {len(flag_has_misspell)}")
    print(f"    Rows flagged for pack-verb ambiguity                       : {len(flag_ambiguous_pack)}")
    print(f"    Flagged but ALL products ARE in catalogue (investigate)    : {len(flag_no_misspell)}")

    print(f"\n  Sample of 'unexplained' flagged rows (first 20):")
    for i, text, prods in flag_no_misspell[:20]:
        print(f"    row {i}: '{text[:70]}' | products={prods}")

    print(f"\n  Sample of correctly flagged misspellings (first 10):")
    for i, text, prods in flag_has_misspell[:10]:
        bad = [p for p in prods if p not in cat_exact]
        print(f"    row {i}: '{text[:70]}' | non-cat products={bad}")

    # ── K: sentence pattern analysis ─────────────────────────────────────────
    print("\n[SENTENCE VARIETY]")
    n_single = n_two = n_three_plus = n_prod_first = 0
    has_decimal = 0; has_plural_unit = 0; has_abbrev = 0
    for s in samples:
        ents = s["entities"]
        n_prod = sum(1 for e in ents if isinstance(e,list) and len(e)==3 and e[2]=="PRODUCT")
        if n_prod == 1: n_single += 1
        elif n_prod == 2: n_two += 1
        elif n_prod >= 3: n_three_plus += 1
        text = s["text"]
        if any(re.search(r'\b\d+\.\d+\b', text) for _ in [1]): has_decimal += 1
        for e in ents:
            if isinstance(e,list) and len(e)==3:
                st,en,lbl = e
                if lbl=="UNIT" and 0<=st<en<=len(text):
                    tok = text[st:en]
                    if tok in ("litres","liters","kilograms","pieces","packs","packets","bottles","grams"):
                        has_plural_unit += 1
                    if tok in ("kg","kgs","L","ml","g","gm","pcs"):
                        has_abbrev += 1
        # product-first: first entity is PRODUCT
        if ents and isinstance(ents[0],list) and len(ents[0])==3 and ents[0][2]=="PRODUCT":
            n_prod_first += 1

    print(f"  Single-product samples  : {n_single}")
    print(f"  Two-product samples     : {n_two}")
    print(f"  3+-product samples      : {n_three_plus}")
    print(f"  Product-first samples   : {n_prod_first}")
    print(f"  Samples with decimal qty: {has_decimal}")
    print(f"  Annotations with plural unit : {has_plural_unit}")
    print(f"  Annotations with abbrev unit : {has_abbrev}")

    # ── L: repeated-word / pack-verb spot-check ───────────────────────────────
    print("\n[REPEATED-WORD / PACK-VERB CHECK]")
    pack_verb_errors = []
    for i, s in enumerate(samples):
        text = s["text"]
        # look for UNIT annotations that point to 'pack' as an instruction word
        for ent in s["entities"]:
            if not (isinstance(ent,list) and len(ent)==3): continue
            st, en, lbl = ent
            if lbl != "UNIT": continue
            if st<0 or en>len(text) or st>=en: continue
            tok = text[st:en]
            if tok not in ("pack","packs","packet","packets"): continue
            # find all occurrences of this token
            all_occ = word_spans(text, tok)
            if len(all_occ) <= 1: continue
            # the annotated span is the first occurrence — is it an instruction verb?
            first_occ_start = all_occ[0][0]
            if st == first_occ_start:
                # check if there's a digit BEFORE the first occurrence (instruction position)
                before = text[:first_occ_start].strip()
                # if the word before 'pack' is an imperative verb, it's wrong
                verbs = {"pack","kindly","please","do","just"}
                words_before = before.lower().split()
                if not words_before or words_before[-1] in verbs or (len(words_before)>1 and words_before[-2] in verbs):
                    pack_verb_errors.append((i, text, st, en, all_occ))

    print(f"  Possible pack-verb UNIT annotation errors: {len(pack_verb_errors)}")
    for i, text, st, en, occ in pack_verb_errors[:10]:
        print(f"    row {i}: annotated UNIT='{text[st:en]}' at [{st},{en}], all occ={occ}")
        print(f"           text='{text}'")

    # ── M: multi-product independent-offset check ─────────────────────────────
    print("\n[MULTI-PRODUCT INDEPENDENT-OFFSET CHECK]")
    multi_offset_errors = []
    for i, s in enumerate(samples):
        ents = s["entities"]
        prod_ents = [(st,en) for st,en,lbl in ents if lbl=="PRODUCT" and isinstance(ents[0],list)]
        qty_ents  = [(st,en) for st,en,lbl in ents if lbl=="QUANTITY" and isinstance(ents[0],list)]
        if len(prod_ents) > 1:
            seen_starts = set()
            for st,en in prod_ents:
                if st in seen_starts:
                    multi_offset_errors.append((i, s["text"], "duplicate product start", st))
                seen_starts.add(st)
            seen_starts = set()
            for st,en in qty_ents:
                if st in seen_starts:
                    multi_offset_errors.append((i, s["text"], "duplicate qty start", st))
                seen_starts.add(st)
    print(f"  Multi-product offset collisions: {len(multi_offset_errors)}")
    if multi_offset_errors[:5]:
        for e in multi_offset_errors[:5]:
            print(f"    row {e[0]}: {e[2]} offset={e[3]} text='{e[1][:60]}'")

    # ── N: compare reported vs actual summary ─────────────────────────────────
    print("\n[SUMMARY SHEET vs ACTUAL DATA]")
    reported = {r[0]:r[1] for r in summary_rows if r[0]}
    actual = {
        "Total training samples"          : len(samples),
        "Number of unique samples"         : len(set(texts_jsonl)),
        "Total PRODUCT annotations"        : prod_count,
        "Total QUANTITY annotations"       : qty_count,
        "Total UNIT annotations"           : unit_count,
        "Samples flagged for review"       : len(flagged_rows),
        "Duplicate sentence count"         : len(dup_jsonl),
        "Annotation offset error count"    : len(offset_errors),
        "Missing annotation count"         : len(missing_product),
        "Invalid product-unit combinations": len(invalid_prod_unit),
        "Malformed entity record count"    : len(malformed),
    }
    print(f"  {'Metric':<46} {'Reported':>10} {'Actual':>10} {'Match':>7}")
    print(f"  {'-'*46} {'-'*10} {'-'*10} {'-'*7}")
    for key, act_val in actual.items():
        rep_val = reported.get(key, "N/A")
        match = "OK" if str(rep_val) == str(act_val) else "DIFF"
        print(f"  {key:<46} {str(rep_val):>10} {str(act_val):>10} {match:>7}")

    # ── FINAL SUMMARY ────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("AUDIT SUMMARY TABLE")
    print(SEP)
    checks = [
        ("JSONL: 3000 lines",            len(samples)==3000,                     len(samples)),
        ("JSONL: no malformed JSON",      len(json_bad)==0,                      len(json_bad)),
        ("JSONL: no extra fields",        len(extra_fields)==0,                  len(extra_fields)),
        ("Excel: 3000 data rows",         len(ex_rows)==3000,                    len(ex_rows)),
        ("Excel: correct columns",        headers==["Input_Text","Entities","ReviewFlag"], headers),
        ("No duplicate texts",            len(dup_jsonl)==0,                     len(dup_jsonl)),
        ("No empty texts",                len(empty_jsonl)==0,                   len(empty_jsonl)),
        ("Excel/JSONL content match",     len(mismatches)==0,                    len(mismatches)),
        ("No offset OOB errors",          len(offset_errors)==0,                 len(offset_errors)),
        ("No overlap errors",             len(overlap_errors)==0,                len(overlap_errors)),
        ("No missing PRODUCT",            len(missing_product)==0,               len(missing_product)),
        ("No missing QUANTITY",           len(missing_qty)==0,                   len(missing_qty)),
        ("No missing UNIT",               len(missing_unit)==0,                  len(missing_unit)),
        ("No invalid labels",             len(label_errors)==0,                  len(label_errors)),
        ("No malformed entity records",   len(malformed)==0,                     len(malformed)),
        ("All products in catalogue",     len(not_in_cat)==0,                    len(not_in_cat)),
        ("No unknown unit tokens",        len(unknown_units)==0,                 len(unknown_units)),
        ("No invalid product-unit pairs", len(invalid_prod_unit)==0,             len(invalid_prod_unit)),
        ("No pack-verb annotation errors",len(pack_verb_errors)==0,              len(pack_verb_errors)),
        ("No multi-product offset collision",len(multi_offset_errors)==0,        len(multi_offset_errors)),
        ("Summary sheet matches actual",  all(str(reported.get(k,""))== str(v) for k,v in actual.items()), "—"),
        ("Unexplained ReviewFlags",       len(flag_no_misspell)==0,              len(flag_no_misspell)),
    ]
    print(f"  {'Check':<50} {'Status':>8}  {'Detail'}")
    print(f"  {'-'*50} {'-'*8}  {'-'*20}")
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  {name:<50} {status:>8}  {detail}")

    print(f"\n  FILES MODIFIED: NO\n")

if __name__ == "__main__":
    main()
