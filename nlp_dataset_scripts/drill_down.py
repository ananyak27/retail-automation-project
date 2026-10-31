"""
drill_down.py  — read-only drill-down on the two FAIL checks.
Produces concrete examples for the audit report. Modifies NO files.
"""
import ast, json, re, sys, os
from collections import Counter, defaultdict

BASE  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSONL = os.path.join(BASE, "Retail_NLP_Training_Dataset.jsonl")
SEED  = os.path.join(BASE, "backend", "seed_database.py")

UNIT_TOKENS_TO_DBUNIT = {
    "kg":"kg","kgs":"kg","kilogram":"kg","kilograms":"kg","kilo":"kg",
    "litre":"litre","litres":"litre","liter":"litre","liters":"litre","L":"litre",
    "piece":"piece","pieces":"piece","pcs":"piece",
    "pack":"pack","packs":"pack","packet":"pack","packets":"pack",
    "bottle":"bottle","bottles":"bottle",
    "gm":"gm","gms":"gm","gram":"gm","grams":"gm","g":"gm",
    "ml":"litre",
}

def load_catalogue():
    with open(SEED, encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"products_list\s*=\s*(\[.*?\])\s*$", txt, re.DOTALL|re.MULTILINE)
    raw = ast.literal_eval(m.group(1))
    cat = {}
    for p in raw:
        cat.setdefault(p["name"], set()).add(p["unit"])
    return cat

cat = load_catalogue()
cat_exact = set(cat.keys())

with open(JSONL, encoding="utf-8") as f:
    samples = [json.loads(l) for l in f]

print("=" * 72)
print("A. ALL PRODUCT STRINGS NOT IN CATALOGUE (with counts & example rows)")
print("=" * 72)
product_occ = defaultdict(list)
for i, s in enumerate(samples):
    for ent in s["entities"]:
        if isinstance(ent, list) and len(ent)==3:
            st, en, lbl = ent
            if lbl=="PRODUCT" and 0<=st<en<=len(s["text"]):
                p = s["text"][st:en]
                if p not in cat_exact:
                    product_occ[p].append(i)

print(f"Total distinct non-catalogue product strings: {len(product_occ)}")
print()
print(f"{'Product string':<35} {'Count':>6}  {'Example row':>12}  Canonical?")
print("-" * 75)
cat_lower = {n.lower(): n for n in cat}
for p, rows in sorted(product_occ.items(), key=lambda x: -len(x[1])):
    canonical = cat_lower.get(p.lower(), "NOT FOUND")
    print(f"  {p:<33} {len(rows):>6}  row={rows[0]:>5}      -> {canonical}")

print()
print("=" * 72)
print("B. INVALID PRODUCT-UNIT PAIRS  (g mapped as db=gm, but product allows only kg)")
print("=" * 72)
invalid_pairs = []
for i, s in enumerate(samples):
    text = s["text"]
    ents = s["entities"]
    prod_ents = [(st,en) for st,en,lbl in ents if lbl=="PRODUCT"]
    unit_ents = [(st,en) for st,en,lbl in ents if lbl=="UNIT"]
    for idx_p, (pst, pen) in enumerate(prod_ents):
        p_name = text[pst:pen]
        if idx_p < len(unit_ents):
            ust, uen = unit_ents[idx_p]
            u_tok = text[ust:uen]
            db_unit = UNIT_TOKENS_TO_DBUNIT.get(u_tok)
            if db_unit and p_name in cat and db_unit not in cat[p_name]:
                invalid_pairs.append((i, p_name, u_tok, db_unit, cat[p_name], text))

print(f"Total invalid product-unit pairs: {len(invalid_pairs)}")
print()

# Group by unit token
by_unit = defaultdict(list)
for row in invalid_pairs:
    by_unit[row[2]].append(row)
for u_tok, rows in sorted(by_unit.items(), key=lambda x: -len(x[1])):
    print(f"  Unit token '{u_tok}' (maps to db='{UNIT_TOKENS_TO_DBUNIT[u_tok]}'): {len(rows)} cases")
    for row in rows[:5]:
        i, p, utok, dbu, allowed, text = row
        print(f"    row {i:>5}: product='{p}'  allowed_units={allowed}")
        print(f"            text='{text}'")
    print()

print()
print("=" * 72)
print("C. ROOT CAUSE ANALYSIS")
print("=" * 72)
# g vs gm: 108 cases — are all the 'g' pairs with products that only allow 'kg'?
g_cases = [(i, p, utok, dbu, allowed, text) for i,p,utok,dbu,allowed,text in invalid_pairs if utok=="g"]
print(f"Unit token 'g' cases: {len(g_cases)}")
print(f"  'g' maps to db-unit 'gm'.")
print(f"  Products in these cases only allow 'kg', so 'g' (grams) is semantically")
print(f"  wrong IF the quantity is small (e.g., '500 g Sattu Flour' = OK in real")
print(f"  life but the catalogue only tracks 'kg'). This is a catalogue-scope issue,")
print(f"  not an annotation error.")
print()
# Show the g cases that ARE realistic (500g, 250g)
g_qty_ok = []
g_qty_bad = []
for i, p, utok, dbu, allowed, text in g_cases:
    # find qty for this unit
    ents = samples[i]["entities"]
    # find the QUANTITY immediately before this UNIT
    unit_ents_here = [(st,en) for st,en,lbl in ents if lbl=="UNIT"]
    qty_ents_here  = [(st,en) for st,en,lbl in ents if lbl=="QUANTITY"]
    # pair by order
    idx_u = next((k for k,(st,en) in enumerate(unit_ents_here) if text[st:en]==utok), None)
    if idx_u is not None and idx_u < len(qty_ents_here):
        qst, qen = qty_ents_here[idx_u]
        qty_str = text[qst:qen]
        try:
            qty_val = float(qty_str)
            if qty_val in (250, 500):
                g_qty_ok.append((i, qty_str, p, text))
            else:
                g_qty_bad.append((i, qty_str, p, text))
        except:
            g_qty_bad.append((i, None, p, text))

print(f"  'g' with quantity 250 or 500 (realistic sub-kg amounts): {len(g_qty_ok)}")
for row in g_qty_ok[:10]:
    print(f"    row {row[0]}: '{row[3]}'")
print()
print(f"  'g' with other quantity (potentially wrong): {len(g_qty_bad)}")
for row in g_qty_bad[:10]:
    print(f"    row {row[0]}: qty='{row[1]}' product='{row[2]}' text='{row[3]}'")

print()
print("=" * 72)
print("D. LOWERCASE PRODUCT MISMATCHES  (product annotated in lowercase / catalogue uses Title Case)")
print("=" * 72)
lc_cases = []
for i, s in enumerate(samples):
    for ent in s["entities"]:
        if isinstance(ent, list) and len(ent)==3:
            st, en, lbl = ent
            if lbl=="PRODUCT" and 0<=st<en<=len(s["text"]):
                p = s["text"][st:en]
                if p not in cat_exact and p.lower() in cat_lower:
                    lc_cases.append((i, p, cat_lower[p.lower()], s["text"]))

print(f"Total lowercase-only product annotations: {len(lc_cases)}")
by_prod = defaultdict(list)
for i, p, canonical, text in lc_cases:
    by_prod[p].append((i, canonical, text))
for p, rows in sorted(by_prod.items(), key=lambda x: -len(x[1])):
    print(f"  '{p}'  (catalogue: '{rows[0][1]}')  count={len(rows)}")
    for i, c, text in rows[:3]:
        print(f"    row {i}: '{text}'")

print()
print("FILES MODIFIED: NO")
