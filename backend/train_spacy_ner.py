"""
train_spacy_ner.py
==================
Trains a custom spaCy NER model for retail order text.
Recognizes entities: PRODUCT, QUANTITY, UNIT

Usage:
    cd backend
    python train_spacy_ner.py

Output:
    models/retail_ner/  ← trained model directory
    
Then update nlp_service.py to load "models/retail_ner" instead of "en_core_web_sm"
"""

import spacy
from spacy.training import Example
from spacy.util import minibatch, compounding
import random
import os

# ─────────────────────────────────────────────────────────────────────────────
# TRAINING DATA
# Format: (text, {"entities": [(start, end, label)]})
# Labels: PRODUCT, QUANTITY, UNIT
# ─────────────────────────────────────────────────────────────────────────────
TRAIN_DATA = [
    # Basic quantity + product
    ("2 kg rice", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 9, "PRODUCT")]}),
    ("3 litres milk", {"entities": [(0, 1, "QUANTITY"), (2, 8, "UNIT"), (9, 13, "PRODUCT")]}),
    ("5 pieces soap", {"entities": [(0, 1, "QUANTITY"), (2, 8, "UNIT"), (9, 13, "PRODUCT")]}),
    ("1 kg sugar", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 10, "PRODUCT")]}),
    ("10 apples", {"entities": [(0, 2, "QUANTITY"), (3, 9, "PRODUCT")]}),
    ("2 dozen eggs", {"entities": [(0, 1, "QUANTITY"), (2, 7, "UNIT"), (8, 12, "PRODUCT")]}),
    ("500 grams wheat flour", {"entities": [(0, 3, "QUANTITY"), (4, 9, "UNIT"), (10, 21, "PRODUCT")]}),
    ("1 litre coconut oil", {"entities": [(0, 1, "QUANTITY"), (2, 7, "UNIT"), (8, 19, "PRODUCT")]}),
    ("3 packets biscuits", {"entities": [(0, 1, "QUANTITY"), (2, 9, "UNIT"), (10, 18, "PRODUCT")]}),
    ("2 bottles water", {"entities": [(0, 1, "QUANTITY"), (2, 9, "UNIT"), (10, 15, "PRODUCT")]}),
    ("4 kg tomatoes", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 13, "PRODUCT")]}),
    ("1.5 kg onions", {"entities": [(0, 3, "QUANTITY"), (4, 6, "UNIT"), (7, 13, "PRODUCT")]}),
    ("250 ml shampoo", {"entities": [(0, 3, "QUANTITY"), (4, 6, "UNIT"), (7, 14, "PRODUCT")]}),
    ("2 bars soap", {"entities": [(0, 1, "QUANTITY"), (2, 6, "UNIT"), (7, 11, "PRODUCT")]}),
    ("6 bananas", {"entities": [(0, 1, "QUANTITY"), (2, 9, "PRODUCT")]}),
    ("1 pack noodles", {"entities": [(0, 1, "QUANTITY"), (2, 6, "UNIT"), (7, 14, "PRODUCT")]}),
    ("3 kg potatoes", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 13, "PRODUCT")]}),
    ("2 litres cooking oil", {"entities": [(0, 1, "QUANTITY"), (2, 8, "UNIT"), (9, 20, "PRODUCT")]}),
    ("500g basmati rice", {"entities": [(0, 4, "QUANTITY"), (12, 17, "PRODUCT")]}),
    ("1 kg basmati rice", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 17, "PRODUCT")]}),
    ("2 kg dal", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 8, "PRODUCT")]}),
    ("3 pieces bread", {"entities": [(0, 1, "QUANTITY"), (2, 8, "UNIT"), (9, 14, "PRODUCT")]}),
    ("1 kg salt", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 9, "PRODUCT")]}),
    ("5 kg atta", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 9, "PRODUCT")]}),
    ("2 kg maida", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 10, "PRODUCT")]}),
    ("4 litres milk", {"entities": [(0, 1, "QUANTITY"), (2, 8, "UNIT"), (9, 13, "PRODUCT")]}),
    ("10 pieces banana", {"entities": [(0, 2, "QUANTITY"), (3, 9, "UNIT"), (10, 16, "PRODUCT")]}),
    ("1 box cornflakes", {"entities": [(0, 1, "QUANTITY"), (2, 5, "UNIT"), (6, 16, "PRODUCT")]}),
    ("3 kg chicken", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 12, "PRODUCT")]}),
    ("2 kg fish", {"entities": [(0, 1, "QUANTITY"), (2, 4, "UNIT"), (5, 9, "PRODUCT")]}),
    ("I need 2 kg of rice", {"entities": [(7, 8, "QUANTITY"), (9, 11, "UNIT"), (15, 19, "PRODUCT")]}),
    ("please give me 3 litres of milk", {"entities": [(15, 16, "QUANTITY"), (17, 23, "UNIT"), (27, 31, "PRODUCT")]}),
    ("I want 500 grams of sugar", {"entities": [(7, 10, "QUANTITY"), (11, 16, "UNIT"), (20, 25, "PRODUCT")]}),
    ("get me 1 dozen eggs", {"entities": [(7, 8, "QUANTITY"), (9, 14, "UNIT"), (15, 19, "PRODUCT")]}),
    ("buy 2 packets of biscuits", {"entities": [(4, 5, "QUANTITY"), (6, 13, "UNIT"), (17, 25, "PRODUCT")]}),
    ("I need rice 2 kg", {"entities": [(7, 11, "PRODUCT"), (12, 13, "QUANTITY"), (14, 16, "UNIT")]}),
    ("milk 1 litre", {"entities": [(0, 4, "PRODUCT"), (5, 6, "QUANTITY"), (7, 12, "UNIT")]}),
    ("soap 3 bars", {"entities": [(0, 4, "PRODUCT"), (5, 6, "QUANTITY"), (7, 11, "UNIT")]}),
    ("rice 5 kg and sugar 2 kg", {"entities": [(0, 4, "PRODUCT"), (5, 6, "QUANTITY"), (7, 9, "UNIT"), (14, 19, "PRODUCT"), (20, 21, "QUANTITY"), (22, 24, "UNIT")]}),
    ("tomatoes 1 kg", {"entities": [(0, 8, "PRODUCT"), (9, 10, "QUANTITY"), (11, 13, "UNIT")]}),
]

# ─────────────────────────────────────────────────────────────────────────────
# TRAINING FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
def train_retail_ner(output_dir="models/retail_ner", n_iter=60):
    """Train a blank spaCy NER model on retail grocery order text."""

    print("🚀 Starting spaCy NER training for retail orders...")
    print(f"   Training examples : {len(TRAIN_DATA)}")
    print(f"   Iterations        : {n_iter}")
    print(f"   Output directory  : {output_dir}")
    print()

    # Start with blank English model (no pretrained weights — faster, no torch needed)
    nlp = spacy.blank("en")

    # Add NER pipe
    if "ner" not in nlp.pipe_names:
        ner = nlp.add_pipe("ner", last=True)
    else:
        ner = nlp.get_pipe("ner")

    # Add all entity labels
    for _, annotations in TRAIN_DATA:
        for ent in annotations.get("entities", []):
            ner.add_label(ent[2])

    # Convert training data to spaCy Example objects
    examples = []
    for text, annotations in TRAIN_DATA:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)
        examples.append(example)

    # Initialize with training data
    nlp.initialize(lambda: examples)

    # Training loop
    best_loss = float("inf")
    with nlp.select_pipes(enable="ner"):
        for iteration in range(n_iter):
            random.shuffle(examples)
            losses = {}
            batches = minibatch(examples, size=compounding(4.0, 32.0, 1.001))
            for batch in batches:
                nlp.update(batch, losses=losses, drop=0.3)

            loss = losses.get("ner", 0)
            if loss < best_loss:
                best_loss = loss

            if (iteration + 1) % 10 == 0:
                print(f"   Iteration {iteration+1:3d}/{n_iter} | NER Loss: {loss:.4f} | Best: {best_loss:.4f}")

    # Save model
    os.makedirs(output_dir, exist_ok=True)
    nlp.to_disk(output_dir)
    print(f"\n✅ Model saved to: {output_dir}")
    return output_dir


# ─────────────────────────────────────────────────────────────────────────────
# TEST FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
def test_model(model_path="models/retail_ner"):
    """Load the trained model and test it on sample grocery texts."""
    print("\n🧪 Testing trained model...")
    nlp = spacy.load(model_path)

    test_texts = [
        "2 kg rice",
        "3 litres milk",
        "I need 5 pieces soap",
        "please give me 1 dozen eggs",
        "500 grams sugar and 2 kg dal",
        "buy tomatoes 3 kg",
        "I want 2 packets biscuits and 1 litre cooking oil",
        "4 kg atta",
        "10 bananas",
    ]

    print("\n{:<45} {:<12} {:<10} {}".format("TEXT", "PRODUCT", "QUANTITY", "UNIT"))
    print("-" * 85)

    for text in test_texts:
        doc = nlp(text)
        entities = {ent.label_: ent.text for ent in doc.ents}
        print("{:<45} {:<12} {:<10} {}".format(
            text,
            entities.get("PRODUCT", "-"),
            entities.get("QUANTITY", "-"),
            entities.get("UNIT", "-")
        ))


if __name__ == "__main__":
    # Train
    output_dir = train_retail_ner(n_iter=80)

    # Test
    test_model(output_dir)

    print("\n✅ Training complete!")
    print("   Next step: update nlp_service.py to load 'models/retail_ner'")
