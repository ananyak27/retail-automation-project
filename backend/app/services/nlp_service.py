import re
import subprocess
import logging

logger = logging.getLogger(__name__)

nlp = None

def load_spacy_model():
    global nlp
    if nlp is None:
        try:
            import spacy
            try:
                nlp = spacy.load("en_core_web_sm")
                logger.info("spaCy en_core_web_sm model loaded successfully.")
            except OSError:
                logger.info("en_core_web_sm model not found. Downloading...")
                try:
                    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
                    nlp = spacy.load("en_core_web_sm")
                    logger.info("spaCy en_core_web_sm downloaded and loaded successfully.")
                except Exception as e:
                    logger.error(f"Failed to download spaCy model: {e}. Falling back to regex NLP parser.")
                    nlp = False
        except Exception as e:
            logger.warning(f"spaCy/torch library initialization failed ({e}). Falling back to regex NLP parser.")
            nlp = False

    return nlp if nlp is not False else None

def extract_entities(text: str) -> list:
    """
    Extracts (Product, Quantity, Unit) from the given text.
    Handles text inputs like:
      - 2kg Rice
      - 3 Milk
      - 5 piece Soap
      - 1.5 litre Milk
    Returns a list of dicts: [{'product': 'Rice', 'quantity': 2.0, 'unit': 'kg'}, ...]
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    extracted_items = []

    # Try loading spaCy for intelligent POS tags
    nlp_model = load_spacy_model()

    # Predefined units to match
    units_list = ["kg", "kilo", "kilogram", "g", "gm", "gram", "litre", "liter", "l", "ltr", "piece", "pieces", "pc", "packet", "pkt", "box", "bottle", "cup"]
    
    for line in lines:
        # 1. Regex parse: Extract quantity, unit and item
        # Matches formats: '2.5kg rice', '2.5 kg rice', '2 rice', '2 packets rice'
        pattern = r"^\s*([\d\./]+)\s*(" + "|".join(units_list) + r")?\s*(.*)$"
        match = re.match(pattern, line, re.IGNORECASE)
        
        if match:
            raw_qty, raw_unit, raw_prod = match.groups()
            
            # Clean quantity
            try:
                # Handle fractions like 1/2
                if "/" in raw_qty:
                    num, denom = raw_qty.split("/")
                    quantity = float(num) / float(denom)
                else:
                    quantity = float(raw_qty)
            except ValueError:
                quantity = 1.0
                
            # Clean unit
            unit = raw_unit.lower() if raw_unit else "piece"
            # Normalize common units
            if unit in ["kilo", "kilogram"]:
                unit = "kg"
            elif unit in ["liter", "ltr", "l"]:
                unit = "litre"
            elif unit in ["gm", "gram"]:
                unit = "g"
            elif unit in ["pieces", "pc"]:
                unit = "piece"
                
            # Clean product name
            product = raw_prod.strip()
            
            # If spaCy is loaded, let's refine the product name (e.g. lemmatize or extract nouns)
            if nlp_model and product:
                doc = nlp_model(product)
                # Keep noun phrases or nouns for clean product naming
                nouns = [token.text for token in doc if token.pos_ in ["NOUN", "PROPN", "ADJ"]]
                if nouns:
                    refined_product = " ".join(nouns)
                    if len(refined_product) > 1:
                        product = refined_product
            
            # Only add if we found a product name
            if product:
                # Capitalize product name
                product = product.title()
                extracted_items.append({
                    "product": product,
                    "quantity": quantity,
                    "unit": unit
                })
        else:
            # Fallback if no digits were matched (e.g. "Rice", "Sugar and Soap")
            if nlp_model:
                doc = nlp_model(line)
                # Simple extraction of Noun chunks
                for chunk in doc.noun_chunks:
                    extracted_items.append({
                        "product": chunk.text.title(),
                        "quantity": 1.0,
                        "unit": "piece"
                    })
            else:
                # Simple split fallback
                extracted_items.append({
                    "product": line.title(),
                    "quantity": 1.0,
                    "unit": "piece"
                })
                
    return extracted_items
