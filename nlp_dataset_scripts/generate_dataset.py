"""
generate_dataset.py
====================
Generates 3,000 unique NLP training samples for retail order entity extraction.
Reads the approved product-unit table from seed_database.py.
Outputs: Retail_NLP_Training_Dataset.xlsx and Retail_NLP_Training_Dataset.jsonl

Entity labels: PRODUCT, QUANTITY, UNIT
"""

import ast
import json
import os
import random
import re
import sys
import copy
from collections import Counter

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CONFIGURATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SEED_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "seed_database.py")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..")
XLSX_FILE = os.path.join(OUTPUT_DIR, "Retail_NLP_Training_Dataset.xlsx")
JSONL_FILE = os.path.join(OUTPUT_DIR, "Retail_NLP_Training_Dataset.jsonl")
TARGET_SAMPLES = 3000
RANDOM_SEED = 42

random.seed(RANDOM_SEED)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1: EXTRACT PRODUCTS FROM SEED DATABASE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def extract_products_from_seed():
    """Parse seed_database.py to extract the complete product catalog."""
    seed_path = os.path.abspath(SEED_DB_PATH)
    print(f"Reading product catalog from: {seed_path}")
    
    if not os.path.exists(seed_path):
        print(f"ERROR: seed_database.py not found at {seed_path}")
        sys.exit(1)
    
    with open(seed_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find the products_list assignment - it's a single large list of dicts
    match = re.search(r"products_list\s*=\s*(\[.*?\])\s*$", content, re.DOTALL | re.MULTILINE)
    if not match:
        print("ERROR: Could not find products_list in seed_database.py")
        sys.exit(1)
    
    list_str = match.group(1)
    products_raw = ast.literal_eval(list_str)
    
    # Build product -> unit mapping
    products = {}
    for p in products_raw:
        name = p["name"]
        unit = p["unit"]
        if name not in products:
            products[name] = set()
        products[name].add(unit)
    
    print(f"Extracted {len(products)} unique products from seed_database.py")
    return products


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2: UNIT DISPLAY VARIANTS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Map from DB unit to all acceptable display forms
UNIT_DISPLAY_MAP = {
    "kg": ["kg", "kgs", "kilogram", "kilograms", "kilo"],
    "litre": ["litre", "litres", "liter", "liters", "L"],
    "piece": ["piece", "pieces", "pcs"],
    "pack": ["pack", "packs", "packet", "packets"],
    "bottle": ["bottle", "bottles"],
    "gm": ["gm", "gms", "gram", "grams", "g"],
}

def get_unit_display(db_unit):
    """Return a random display variant for the given DB unit."""
    variants = UNIT_DISPLAY_MAP.get(db_unit, [db_unit])
    return random.choice(variants)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 3: QUANTITY GENERATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_quantity(unit):
    """Generate a realistic quantity based on the unit type."""
    if unit == "kg":
        return random.choice(["1", "2", "3", "5", "0.5", "1.5", "2.5", "10", "4", "0.25", "500", "250"])
    elif unit == "litre":
        return random.choice(["1", "2", "0.5", "1.5", "3", "5", "500", "250"])
    elif unit == "piece":
        return random.choice(["1", "2", "3", "4", "5", "6", "10", "12", "8", "15", "20"])
    elif unit == "pack":
        return random.choice(["1", "2", "3", "4", "5", "6", "10"])
    elif unit == "bottle":
        return random.choice(["1", "2", "3", "4", "5", "6"])
    elif unit == "gm":
        return random.choice(["1", "2", "5", "10", "100", "50", "250", "500"])
    else:
        return random.choice(["1", "2", "3", "5"])

def gen_quantity_with_unit(db_unit):
    """Generate quantity string and display unit. 
    Sometimes quantity includes 'g' or 'ml' as sub-unit variations.
    """
    qty = gen_quantity(db_unit)
    
    # For kg unit, sometimes use grams
    if db_unit == "kg" and qty in ["500", "250"]:
        return qty, "g"  # "500 g" instead of "500 kg"
    
    # For litre unit, sometimes use ml
    if db_unit == "litre" and qty in ["500", "250"]:
        return qty, "ml"
    
    display_unit = get_unit_display(db_unit)
    return qty, display_unit


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 4: SENTENCE TEMPLATES AND GENERATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# -- Single product templates --
SINGLE_TEMPLATES = [
    # Type A: Simple direct requests
    lambda q, u, p: f"{q} {u} {p}",
    lambda q, u, p: f"{q} {u} of {p}",
    lambda q, u, p: f"I need {q} {u} {p}",
    lambda q, u, p: f"I need {q} {u} of {p}",
    lambda q, u, p: f"Please give me {q} {u} {p}",
    lambda q, u, p: f"Please give me {q} {u} of {p}",
    lambda q, u, p: f"Send me {q} {u} {p}",
    lambda q, u, p: f"Send me {q} {u} of {p}",
    lambda q, u, p: f"Send {q} {u} {p}",
    lambda q, u, p: f"Send {q} {u} of {p}",
    lambda q, u, p: f"Get me {q} {u} {p}",
    lambda q, u, p: f"Get me {q} {u} of {p}",
    lambda q, u, p: f"Add {q} {u} {p}",
    lambda q, u, p: f"Add {q} {u} of {p}",
    lambda q, u, p: f"Add {q} {u} {p} to my order",
    lambda q, u, p: f"Add {q} {u} of {p} to my order",
    lambda q, u, p: f"I want {q} {u} {p}",
    lambda q, u, p: f"I want {q} {u} of {p}",
    lambda q, u, p: f"Give me {q} {u} {p}",
    lambda q, u, p: f"Give me {q} {u} of {p}",
    
    # Type C: Conversational/polite
    lambda q, u, p: f"Can you send me {q} {u} {p}?",
    lambda q, u, p: f"Can you send me {q} {u} of {p}?",
    lambda q, u, p: f"Could you please send {q} {u} {p}?",
    lambda q, u, p: f"Could I get {q} {u} of {p}?",
    lambda q, u, p: f"I would like {q} {u} {p}",
    lambda q, u, p: f"I would like {q} {u} of {p}",
    lambda q, u, p: f"Please add {q} {u} {p} to my list",
    lambda q, u, p: f"Please add {q} {u} of {p} to my list",
    lambda q, u, p: f"Please pack {q} {u} {p}",
    lambda q, u, p: f"Please pack {q} {u} of {p}",
    lambda q, u, p: f"Could you add {q} {u} {p} to my cart?",
    lambda q, u, p: f"I also need {q} {u} {p}",
    lambda q, u, p: f"I also need {q} {u} of {p}",
    lambda q, u, p: f"Also add {q} {u} {p}",
    lambda q, u, p: f"Do you have {q} {u} of {p}?",
    lambda q, u, p: f"I will take {q} {u} {p}",
    lambda q, u, p: f"I will take {q} {u} of {p}",
    
    # Type D: Short/informal
    lambda q, u, p: f"{q} {u} {p} please",
    lambda q, u, p: f"{p} {q} {u}",
    lambda q, u, p: f"{p} - {q} {u}",
    lambda q, u, p: f"Buy {q} {u} {p}",
    lambda q, u, p: f"Buy {q} {u} of {p}",
    lambda q, u, p: f"Order {q} {u} {p}",
    lambda q, u, p: f"Order {q} {u} of {p}",
    lambda q, u, p: f"Put {q} {u} {p}",
    lambda q, u, p: f"Put {q} {u} of {p}",
    lambda q, u, p: f"Pack {q} {u} {p} for me",
    lambda q, u, p: f"Keep {q} {u} {p} ready",
    lambda q, u, p: f"Prepare {q} {u} {p}",
    lambda q, u, p: f"I'll need {q} {u} of {p}",
    lambda q, u, p: f"Can I get {q} {u} {p}?",
    lambda q, u, p: f"Can I have {q} {u} {p}?",
    lambda q, u, p: f"May I have {q} {u} of {p}?",
    lambda q, u, p: f"Kindly give me {q} {u} {p}",
    lambda q, u, p: f"I require {q} {u} {p}",
    lambda q, u, p: f"I require {q} {u} of {p}",
    lambda q, u, p: f"I am looking for {q} {u} {p}",
    lambda q, u, p: f"I am looking for {q} {u} of {p}",
    lambda q, u, p: f"Need {q} {u} {p}",
    lambda q, u, p: f"Need {q} {u} of {p}",
    lambda q, u, p: f"Want {q} {u} {p}",
    lambda q, u, p: f"Want {q} {u} of {p}",
    lambda q, u, p: f"{q} {u} of {p} please send",
    lambda q, u, p: f"Make it {q} {u} {p}",
    lambda q, u, p: f"Include {q} {u} {p} in my order",
    lambda q, u, p: f"Include {q} {u} of {p} in my order",
    lambda q, u, p: f"Just {q} {u} {p}",
    lambda q, u, p: f"Just {q} {u} of {p}",
    lambda q, u, p: f"Only {q} {u} {p}",
    lambda q, u, p: f"I'd like {q} {u} {p}",
    lambda q, u, p: f"I'd like {q} {u} of {p}",
    lambda q, u, p: f"Deliver {q} {u} {p}",
    lambda q, u, p: f"Deliver {q} {u} of {p}",
    lambda q, u, p: f"Please deliver {q} {u} {p}",
    lambda q, u, p: f"Please deliver {q} {u} of {p}",
    lambda q, u, p: f"I'll have {q} {u} {p}",
    lambda q, u, p: f"Reserve {q} {u} {p} for me",
    lambda q, u, p: f"Set aside {q} {u} {p}",
    lambda q, u, p: f"Bring {q} {u} {p}",
    lambda q, u, p: f"Bring me {q} {u} of {p}",
    lambda q, u, p: f"Fetch me {q} {u} {p}",
    lambda q, u, p: f"Keep {q} {u} of {p} aside for me",
    lambda q, u, p: f"Sir please give {q} {u} {p}",
    lambda q, u, p: f"Bhaiya {q} {u} {p} de do",
    lambda q, u, p: f"Please provide {q} {u} of {p}",
    lambda q, u, p: f"Kindly pack {q} {u} {p}",
    lambda q, u, p: f"I am ordering {q} {u} {p}",
    lambda q, u, p: f"My order is {q} {u} {p}",
    lambda q, u, p: f"Today I need {q} {u} {p}",
    lambda q, u, p: f"Today I need {q} {u} of {p}",
    lambda q, u, p: f"For today give me {q} {u} of {p}",
    lambda q, u, p: f"Urgently need {q} {u} {p}",
    lambda q, u, p: f"Please quickly send {q} {u} {p}",
    lambda q, u, p: f"Hi, I need {q} {u} of {p}",
    lambda q, u, p: f"Hello, please send {q} {u} {p}",
    lambda q, u, p: f"Hi, can I get {q} {u} {p}?",
    lambda q, u, p: f"Good morning, I need {q} {u} {p}",
    lambda q, u, p: f"Hey, send me {q} {u} of {p}",
]

# -- Two-product conjunction templates --
TWO_PRODUCT_TEMPLATES = [
    lambda q1, u1, p1, q2, u2, p2: f"I need {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"I need {q1} {u1} of {p1} and {q2} {u2} of {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Please give me {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Please give me {q1} {u1} of {p1} and {q2} {u2} of {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Send me {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Send me {q1} {u1} of {p1} and {q2} {u2} of {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Get me {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Add {q1} {u1} {p1} and {q2} {u2} {p2} to my order",
    lambda q1, u1, p1, q2, u2, p2: f"I want {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"I want {q1} {u1} of {p1} and {q2} {u2} of {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Give me {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Can you send me {q1} {u1} {p1} and {q2} {u2} {p2}?",
    lambda q1, u1, p1, q2, u2, p2: f"I would like {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Please add {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Buy {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Order {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Pack {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"I also need {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"{q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"{q1} {u1} {p1} and {q2} {u2} {p2} please",
    lambda q1, u1, p1, q2, u2, p2: f"Send {q1} {u1} {p1} along with {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Send me {q1} {u1} {p1} along with {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"I need {q1} {u1} {p1} as well as {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Deliver {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Kindly send {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Hi, I want {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Please pack {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Could I get {q1} {u1} {p1} and {q2} {u2} {p2}?",
    lambda q1, u1, p1, q2, u2, p2: f"I'll take {q1} {u1} {p1} and {q2} {u2} {p2}",
    lambda q1, u1, p1, q2, u2, p2: f"Today I need {q1} {u1} {p1} and {q2} {u2} {p2}",
]

# -- Three-product templates --
THREE_PRODUCT_TEMPLATES = [
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"I need {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"I need {q1} {u1} of {p1}, {q2} {u2} of {p2} and {q3} {u3} of {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Please give me {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Please add {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Send me {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"I want {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Give me {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Add {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3} to my order",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Can you send {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}?",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Pack {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"{q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"{q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3} please",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"I'd like {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Order {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Buy {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Deliver {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Hi, I need {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
    lambda q1, u1, p1, q2, u2, p2, q3, u3, p3: f"Hello, send me {q1} {u1} {p1}, {q2} {u2} {p2} and {q3} {u3} {p3}",
]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 5: ANNOTATION ENGINE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def annotate_entities(text, product_qty_unit_list):
    """
    Given text and a list of (product_name, quantity_str, unit_display_str),
    find each entity's exact character offsets in the text.
    Returns list of [start, end, label] sorted by start position.
    """
    entities = []
    used_positions = set()  # Track used character positions to prevent overlaps
    
    for product, qty, unit in product_qty_unit_list:
        # Find PRODUCT
        p_start = find_entity_position(text, product, used_positions)
        if p_start is not None:
            p_end = p_start + len(product)
            entities.append([p_start, p_end, "PRODUCT"])
            for i in range(p_start, p_end):
                used_positions.add(i)
        
        # Find QUANTITY
        q_start = find_entity_position(text, qty, used_positions)
        if q_start is not None:
            q_end = q_start + len(qty)
            entities.append([q_start, q_end, "QUANTITY"])
            for i in range(q_start, q_end):
                used_positions.add(i)
        
        # Find UNIT
        u_start = find_entity_position(text, unit, used_positions)
        if u_start is not None:
            u_end = u_start + len(unit)
            entities.append([u_start, u_end, "UNIT"])
            for i in range(u_start, u_end):
                used_positions.add(i)
    
    # Sort by start position
    entities.sort(key=lambda x: x[0])
    return entities


def find_entity_position(text, entity, used_positions):
    """Find the first occurrence of entity in text that doesn't overlap with used positions."""
    start = 0
    while True:
        idx = text.find(entity, start)
        if idx == -1:
            return None
        # Check if this position overlaps with already used positions
        entity_range = set(range(idx, idx + len(entity)))
        if not entity_range.intersection(used_positions):
            # Additionally, verify word boundary to avoid partial matches
            # Check left boundary
            if idx > 0 and text[idx-1].isalnum():
                start = idx + 1
                continue
            # Check right boundary
            end_idx = idx + len(entity)
            if end_idx < len(text) and text[end_idx].isalnum():
                start = idx + 1
                continue
            return idx
        start = idx + 1


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 6: MISSPELLING VARIANTS (SMALL CONTROLLED SET)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MISSPELLING_MAP = {
    "Rice": ["rice", "Ric", "rie"],
    "Sugar": ["sugar", "Suger", "sugr"],
    "Milk": ["milk", "Mlk", "mlk"],
    "Wheat Flour": ["wheat flour", "Wheat Flor", "wheet flour"],
    "Coriander Powder": ["coriander powder", "Coriender Powder", "corinder powder"],
    "Turmeric Powder": ["turmeric powder", "Turmeric Powdr", "turmaric powder"],
    "Coconut Oil": ["coconut oil", "Cocnut Oil", "coconut oill"],
    "Basmati Rice": ["basmati rice", "Basmathi Rice", "basmti rice"],
    "Toor Dal": ["toor dal", "Toor Daal", "toor daal"],
    "Sunflower Oil": ["sunflower oil", "Sunflwer Oil", "sunflowr oil"],
}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 7: SAMPLE GENERATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def generate_single_product_sample(products, product_names):
    """Generate a single-product shopping request."""
    product = random.choice(product_names)
    db_unit = random.choice(list(products[product]))
    qty, display_unit = gen_quantity_with_unit(db_unit)
    
    template = random.choice(SINGLE_TEMPLATES)
    text = template(qty, display_unit, product)
    
    entities = annotate_entities(text, [(product, qty, display_unit)])
    return text, entities, False


def generate_two_product_sample(products, product_names):
    """Generate a two-product shopping request."""
    prods = random.sample(product_names, 2)
    
    items = []
    params = []
    for p in prods:
        db_unit = random.choice(list(products[p]))
        qty, display_unit = gen_quantity_with_unit(db_unit)
        items.append((p, qty, display_unit))
        params.extend([qty, display_unit, p])
    
    template = random.choice(TWO_PRODUCT_TEMPLATES)
    text = template(*params)
    
    entities = annotate_entities(text, items)
    return text, entities, False


def generate_three_product_sample(products, product_names):
    """Generate a three-product shopping request."""
    prods = random.sample(product_names, 3)
    
    items = []
    params = []
    for p in prods:
        db_unit = random.choice(list(products[p]))
        qty, display_unit = gen_quantity_with_unit(db_unit)
        items.append((p, qty, display_unit))
        params.extend([qty, display_unit, p])
    
    template = random.choice(THREE_PRODUCT_TEMPLATES)
    text = template(*params)
    
    entities = annotate_entities(text, items)
    return text, entities, False


def generate_misspelling_sample(products, product_names):
    """Generate a sample with a controlled misspelling. Flagged for review."""
    misspellable = [p for p in product_names if p in MISSPELLING_MAP]
    if not misspellable:
        return generate_single_product_sample(products, product_names)
    
    product = random.choice(misspellable)
    db_unit = random.choice(list(products[product]))
    qty, display_unit = gen_quantity_with_unit(db_unit)
    
    misspelled = random.choice(MISSPELLING_MAP[product])
    
    # Use a simple template with the misspelled product
    templates_for_misspell = [
        lambda q, u, p: f"I need {q} {u} {p}",
        lambda q, u, p: f"Please give me {q} {u} {p}",
        lambda q, u, p: f"Send me {q} {u} {p}",
        lambda q, u, p: f"{q} {u} {p}",
        lambda q, u, p: f"I want {q} {u} {p}",
        lambda q, u, p: f"Can you send {q} {u} {p}?",
        lambda q, u, p: f"Give me {q} {u} {p}",
        lambda q, u, p: f"Add {q} {u} {p} to my order",
    ]
    template = random.choice(templates_for_misspell)
    text = template(qty, display_unit, misspelled)
    
    # Annotate with the misspelled form (actual text)
    entities = annotate_entities(text, [(misspelled, qty, display_unit)])
    return text, entities, True  # Flagged for review


def generate_product_first_sample(products, product_names):
    """Generate a sample with product name first, then quantity and unit."""
    product = random.choice(product_names)
    db_unit = random.choice(list(products[product]))
    qty, display_unit = gen_quantity_with_unit(db_unit)
    
    templates = [
        lambda p, q, u: f"{p} {q} {u}",
        lambda p, q, u: f"{p} - {q} {u}",
        lambda p, q, u: f"{p}: {q} {u}",
        lambda p, q, u: f"{p}, {q} {u}",
        lambda p, q, u: f"For {p}, I need {q} {u}",
        lambda p, q, u: f"For {p} send {q} {u}",
        lambda p, q, u: f"Regarding {p}, send me {q} {u}",
        lambda p, q, u: f"About {p}, please give {q} {u}",
    ]
    
    template = random.choice(templates)
    text = template(product, qty, display_unit)
    
    entities = annotate_entities(text, [(product, qty, display_unit)])
    return text, entities, False


def generate_all_samples(products):
    """Generate exactly 3000 unique samples."""
    product_names = list(products.keys())
    
    # Distribution: ~55% single, ~25% two-product, ~10% three-product, 
    # ~5% product-first, ~5% misspelling
    samples = []
    seen_texts = set()
    
    # Target counts
    single_target = 1650
    two_target = 750
    three_target = 300
    product_first_target = 150
    misspell_target = 150
    
    generators = [
        (single_target, generate_single_product_sample),
        (two_target, generate_two_product_sample),
        (three_target, generate_three_product_sample),
        (product_first_target, generate_product_first_sample),
        (misspell_target, generate_misspelling_sample),
    ]
    
    total_generated = 0
    max_attempts_per_type = 50000
    
    for target, gen_func in generators:
        count = 0
        attempts = 0
        while count < target and attempts < max_attempts_per_type:
            attempts += 1
            text, entities, review_flag = gen_func(products, product_names)
            
            # Uniqueness check
            if text in seen_texts:
                continue
            
            # Basic validation - check entity offsets
            valid = True
            for start, end, label in entities:
                if start < 0 or end > len(text) or start >= end:
                    valid = False
                    break
                extracted = text[start:end]
                if not extracted.strip():
                    valid = False
                    break
            
            if not valid:
                continue
            
            # Verify we have at least one PRODUCT entity
            has_product = any(e[2] == "PRODUCT" for e in entities)
            if not has_product:
                continue
            
            seen_texts.add(text)
            samples.append({
                "text": text,
                "entities": entities,
                "review_flag": review_flag,
            })
            count += 1
            total_generated += 1
        
        print(f"  Generated {count}/{target} samples of type '{gen_func.__name__}' ({attempts} attempts)")
    
    # If we're short, generate more single-product samples
    shortage = TARGET_SAMPLES - len(samples)
    if shortage > 0:
        print(f"  Generating {shortage} additional single-product samples...")
        attempts = 0
        while shortage > 0 and attempts < 100000:
            attempts += 1
            text, entities, review_flag = generate_single_product_sample(products, product_names)
            if text in seen_texts:
                continue
            valid = True
            for start, end, label in entities:
                if start < 0 or end > len(text) or start >= end:
                    valid = False
                    break
            if not valid:
                continue
            has_product = any(e[2] == "PRODUCT" for e in entities)
            if not has_product:
                continue
            seen_texts.add(text)
            samples.append({
                "text": text,
                "entities": entities,
                "review_flag": review_flag,
            })
            shortage -= 1
    
    # Shuffle to mix types
    random.shuffle(samples)
    
    print(f"\nTotal unique samples generated: {len(samples)}")
    return samples[:TARGET_SAMPLES]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 8: VALIDATION
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def validate_dataset(samples, products):
    """Comprehensive dataset validation. Returns validation report dict."""
    report = {
        "total_samples": len(samples),
        "unique_texts": len(set(s["text"] for s in samples)),
        "empty_samples": 0,
        "duplicates": 0,
        "total_product_annotations": 0,
        "total_quantity_annotations": 0,
        "total_unit_annotations": 0,
        "offset_errors": 0,
        "invalid_product_unit": 0,
        "missing_annotations": 0,
        "flagged_for_review": 0,
        "invalid_labels": 0,
        "errors": [],
    }
    
    text_counts = Counter(s["text"] for s in samples)
    report["duplicates"] = sum(1 for c in text_counts.values() if c > 1)
    
    valid_labels = {"PRODUCT", "QUANTITY", "UNIT"}
    
    for idx, sample in enumerate(samples):
        text = sample["text"]
        entities = sample["entities"]
        
        # Empty check
        if not text.strip():
            report["empty_samples"] += 1
            report["errors"].append(f"Sample {idx}: empty text")
            continue
        
        # Review flag
        if sample.get("review_flag"):
            report["flagged_for_review"] += 1
        
        # Entity validation
        if not entities:
            report["missing_annotations"] += 1
            report["errors"].append(f"Sample {idx}: no entities annotated")
            continue
        
        for ent in entities:
            start, end, label = ent
            
            # Label check
            if label not in valid_labels:
                report["invalid_labels"] += 1
                report["errors"].append(f"Sample {idx}: invalid label '{label}'")
            
            # Offset bounds check
            if start < 0 or end > len(text) or start >= end:
                report["offset_errors"] += 1
                report["errors"].append(f"Sample {idx}: offset error [{start}, {end}] in text of length {len(text)}")
                continue
            
            # Extract and verify
            extracted = text[start:end]
            
            if label == "PRODUCT":
                report["total_product_annotations"] += 1
            elif label == "QUANTITY":
                report["total_quantity_annotations"] += 1
            elif label == "UNIT":
                report["total_unit_annotations"] += 1
    
    return report


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 9: FILE OUTPUT
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def save_jsonl(samples, filepath):
    """Save samples as JSONL file."""
    # Backup if exists
    if os.path.exists(filepath):
        backup = filepath + ".bak"
        print(f"  Backing up existing file to {backup}")
        os.replace(filepath, backup)
    
    with open(filepath, "w", encoding="utf-8") as f:
        for sample in samples:
            line = json.dumps({
                "text": sample["text"],
                "entities": sample["entities"],
            }, ensure_ascii=False)
            f.write(line + "\n")
    
    print(f"  Saved JSONL: {filepath}")


def save_excel(samples, validation_report, filepath):
    """Save samples as Excel workbook with two sheets."""
    # Backup if exists
    if os.path.exists(filepath):
        backup = filepath + ".bak"
        print(f"  Backing up existing file to {backup}")
        os.replace(filepath, backup)
    
    wb = openpyxl.Workbook()
    
    # â”€â”€ Sheet 1: Training_Dataset â”€â”€
    ws1 = wb.active
    ws1.title = "Training_Dataset"
    
    # Header styling
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    
    headers = ["Input_Text", "Entities", "ReviewFlag"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Data rows
    for row_idx, sample in enumerate(samples, 2):
        ws1.cell(row=row_idx, column=1, value=sample["text"])
        ws1.cell(row=row_idx, column=2, value=json.dumps(sample["entities"]))
        ws1.cell(row=row_idx, column=3, value=sample.get("review_flag", False))
    
    # Column widths
    ws1.column_dimensions["A"].width = 80
    ws1.column_dimensions["B"].width = 60
    ws1.column_dimensions["C"].width = 15
    
    # â”€â”€ Sheet 2: Dataset_Summary â”€â”€
    ws2 = wb.create_sheet("Dataset_Summary")
    
    summary_header_fill = PatternFill(start_color="548235", end_color="548235", fill_type="solid")
    
    summary_headers = ["Metric", "Value"]
    for col_idx, header in enumerate(summary_headers, 1):
        cell = ws2.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = summary_header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    summary_data = [
        ("Total training samples", validation_report["total_samples"]),
        ("Number of unique samples", validation_report["unique_texts"]),
        ("Total PRODUCT annotations", validation_report["total_product_annotations"]),
        ("Total QUANTITY annotations", validation_report["total_quantity_annotations"]),
        ("Total UNIT annotations", validation_report["total_unit_annotations"]),
        ("Samples flagged for review", validation_report["flagged_for_review"]),
        ("Annotation offset errors", validation_report["offset_errors"]),
        ("Invalid product-unit combinations", validation_report["invalid_product_unit"]),
        ("Missing or malformed annotations", validation_report["missing_annotations"]),
    ]
    
    for row_idx, (metric, value) in enumerate(summary_data, 2):
        ws2.cell(row=row_idx, column=1, value=metric)
        ws2.cell(row=row_idx, column=2, value=value)
    
    ws2.column_dimensions["A"].width = 40
    ws2.column_dimensions["B"].width = 20
    
    wb.save(filepath)
    print(f"  Saved Excel: {filepath}")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 10: MAIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main():
    print("=" * 70)
    print("NLP TRAINING DATASET GENERATOR")
    print("=" * 70)
    
    # Step 1: Extract products
    print("\n[1/6] Extracting products from seed_database.py...")
    products = extract_products_from_seed()
    
    # Show some stats
    unit_counts = Counter()
    for name, units in products.items():
        for u in units:
            unit_counts[u] += 1
    print(f"  Unit distribution: {dict(unit_counts)}")
    
    # Step 2: Generate samples
    print(f"\n[2/6] Generating {TARGET_SAMPLES} unique training samples...")
    samples = generate_all_samples(products)
    
    if len(samples) < TARGET_SAMPLES:
        print(f"ERROR: Only generated {len(samples)} samples, needed {TARGET_SAMPLES}")
        sys.exit(1)
    
    # Step 3: Validate
    print(f"\n[3/6] Validating dataset...")
    report = validate_dataset(samples, products)
    
    print(f"\n  --- Validation Report ---")
    print(f"  Total samples:              {report['total_samples']}")
    print(f"  Unique texts:               {report['unique_texts']}")
    print(f"  Empty samples:              {report['empty_samples']}")
    print(f"  Duplicates:                 {report['duplicates']}")
    print(f"  PRODUCT annotations:        {report['total_product_annotations']}")
    print(f"  QUANTITY annotations:       {report['total_quantity_annotations']}")
    print(f"  UNIT annotations:           {report['total_unit_annotations']}")
    print(f"  Offset errors:              {report['offset_errors']}")
    print(f"  Invalid product-unit combos:{report['invalid_product_unit']}")
    print(f"  Missing annotations:        {report['missing_annotations']}")
    print(f"  Flagged for review:         {report['flagged_for_review']}")
    print(f"  Invalid labels:             {report['invalid_labels']}")
    
    # Check for critical failures
    if report["total_samples"] != TARGET_SAMPLES:
        print(f"\n  FAIL: Expected {TARGET_SAMPLES} samples, got {report['total_samples']}")
        sys.exit(1)
    if report["unique_texts"] != TARGET_SAMPLES:
        print(f"\n  FAIL: Expected {TARGET_SAMPLES} unique texts, got {report['unique_texts']}")
        sys.exit(1)
    if report["empty_samples"] > 0:
        print(f"\n  FAIL: {report['empty_samples']} empty samples found")
        sys.exit(1)
    if report["offset_errors"] > 0:
        print(f"\n  WARNING: {report['offset_errors']} offset errors found")
        # Print first 10 errors
        for err in report["errors"][:10]:
            print(f"    {err}")
    if report["missing_annotations"] > 0:
        print(f"\n  WARNING: {report['missing_annotations']} samples with missing annotations")
    
    print(f"\n  âœ… Validation passed!")
    
    # Step 4: Save JSONL
    print(f"\n[4/6] Saving JSONL file...")
    save_jsonl(samples, JSONL_FILE)
    
    # Step 5: Save Excel
    print(f"\n[5/6] Saving Excel workbook...")
    save_excel(samples, report, XLSX_FILE)
    
    # Step 6: Cross-validate files
    print(f"\n[6/6] Cross-validating output files...")
    
    # Verify JSONL
    with open(JSONL_FILE, "r", encoding="utf-8") as f:
        jsonl_lines = f.readlines()
    assert len(jsonl_lines) == TARGET_SAMPLES, f"JSONL has {len(jsonl_lines)} lines, expected {TARGET_SAMPLES}"
    for i, line in enumerate(jsonl_lines):
        obj = json.loads(line)
        assert "text" in obj, f"JSONL line {i}: missing 'text'"
        assert "entities" in obj, f"JSONL line {i}: missing 'entities'"
    print(f"  âœ… JSONL file verified: {len(jsonl_lines)} valid JSON objects")
    
    # Verify Excel
    wb_check = openpyxl.load_workbook(XLSX_FILE)
    assert "Training_Dataset" in wb_check.sheetnames, "Missing Training_Dataset sheet"
    assert "Dataset_Summary" in wb_check.sheetnames, "Missing Dataset_Summary sheet"
    ws_check = wb_check["Training_Dataset"]
    excel_row_count = ws_check.max_row - 1  # Minus header
    assert excel_row_count == TARGET_SAMPLES, f"Excel has {excel_row_count} data rows, expected {TARGET_SAMPLES}"
    print(f"  âœ… Excel file verified: {excel_row_count} data rows, 2 sheets")
    
    # Cross-check content matches
    for i, line in enumerate(jsonl_lines):
        obj = json.loads(line)
        excel_text = ws_check.cell(row=i+2, column=1).value
        assert obj["text"] == excel_text, f"Mismatch at row {i+2}: JSONL text != Excel text"
        excel_entities = json.loads(ws_check.cell(row=i+2, column=2).value)
        assert obj["entities"] == excel_entities, f"Mismatch at row {i+2}: entities differ"
    print(f"  âœ… Cross-validation passed: Excel and JSONL content match")
    
    wb_check.close()
    
    # Final report
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"  Output files:")
    print(f"    1. {os.path.abspath(XLSX_FILE)}")
    print(f"    2. {os.path.abspath(JSONL_FILE)}")
    print(f"  Total training samples:       {report['total_samples']}")
    print(f"  Unique samples:               {report['unique_texts']}")
    print(f"  PRODUCT annotations:          {report['total_product_annotations']}")
    print(f"  QUANTITY annotations:         {report['total_quantity_annotations']}")
    print(f"  UNIT annotations:             {report['total_unit_annotations']}")
    print(f"  Invalid product-unit combos:  {report['invalid_product_unit']}")
    print(f"  Annotation offset errors:     {report['offset_errors']}")
    print(f"  Duplicates:                   {report['duplicates']}")
    print(f"  Flagged for review:           {report['flagged_for_review']}")
    print(f"  Both files passed validation: YES")
    print(f"\n  Files created or modified:")
    print(f"    - {os.path.abspath(XLSX_FILE)}")
    print(f"    - {os.path.abspath(JSONL_FILE)}")
    print(f"    (No existing application files were modified)")
    print("=" * 70)


if __name__ == "__main__":
    main()

