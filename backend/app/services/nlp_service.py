"""
nlp_service.py
==============
Extracts (Product, Quantity, Unit) from grocery order text.

Priority:
  1. Custom trained Retail NER model pickle ('Retail_NER_Model.pkl')
  2. Custom trained NER model directory at 'models/retail_ner'
  3. Generic en_core_web_sm (noun-based extraction)
  4. Regex fallback (no spaCy needed)

The custom model uses spacy.blank("en") so it works WITHOUT torch/GPU.
"""

import re
import os
import sys
import pickle
import pathlib
import logging

logger = logging.getLogger(__name__)

# Global model cache
_nlp = None
_model_type = None   # 'custom_ner' | 'generic' | None (regex only)


def _load_pickle_model(pkl_path: str):
    """
    Safely load a pickled spaCy model with cross-platform and cross-version compatibility.
    Handles:
      - Python 3.13+ pathlib._local redirection
      - confection._config module redirection
      - PosixPath to WindowsPath instantiation on Windows
    """
    # 1. Compatibility for pathlib._local (present when pickled under Python 3.13+)
    if "pathlib._local" not in sys.modules:
        sys.modules["pathlib._local"] = pathlib

    # 2. Compatibility for confection._config
    try:
        import confection
        if "confection._config" not in sys.modules:
            sys.modules["confection._config"] = confection
    except ImportError:
        pass

    # 3. Compatibility for PosixPath on Windows
    original_posix = getattr(pathlib, "PosixPath", None)
    if os.name == "nt" and hasattr(pathlib, "WindowsPath"):
        pathlib.PosixPath = pathlib.WindowsPath

    try:
        with open(pkl_path, "rb") as f:
            model = pickle.load(f)
        return model
    finally:
        if original_posix is not None:
            pathlib.PosixPath = original_posix


def load_spacy_model():
    """Load the best available spaCy model. Returns (nlp, model_type)."""
    global _nlp, _model_type

    if _nlp is not None:
        return _nlp, _model_type

    # ── Try 1: Custom trained retail NER model pickle (.pkl) ───────────────────
    possible_pkl_paths = [
        os.path.join(os.path.dirname(__file__), "..", "ml_models", "Retail_NER_Model.pkl"),
        os.path.join(os.path.dirname(__file__), "..", "..", "models", "Retail_NER_Model.pkl"),
        os.path.join(os.path.dirname(__file__), "..", "..", "Retail_NER_Model.pkl"),
    ]

    for pkl_path in possible_pkl_paths:
        pkl_path = os.path.normpath(pkl_path)
        if os.path.isfile(pkl_path):
            try:
                _nlp = _load_pickle_model(pkl_path)
                _model_type = "custom_ner"
                logger.info(f"✅ Loaded custom retail NER model from pickle: {pkl_path}")
                return _nlp, _model_type
            except Exception as e:
                logger.warning(f"Could not load custom NER pickle model from {pkl_path}: {e}")

    # ── Try 2: Custom trained retail NER directory model ──────────────────────
    custom_model_path = os.path.join(os.path.dirname(__file__), "..", "..", "models", "retail_ner")
    custom_model_path = os.path.normpath(custom_model_path)

    if os.path.exists(custom_model_path):
        try:
            import spacy
            _nlp = spacy.load(custom_model_path)
            _model_type = "custom_ner"
            logger.info(f"✅ Loaded custom retail NER model from directory: {custom_model_path}")
            return _nlp, _model_type
        except Exception as e:
            logger.warning(f"Could not load custom NER directory model: {e}")

    # ── Try 3: Generic en_core_web_sm ─────────────────────────────────────────
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        _model_type = "generic"
        logger.info("✅ Loaded generic en_core_web_sm spaCy model.")
        return _nlp, _model_type
    except OSError:
        logger.info("en_core_web_sm not found, trying to download...")
        try:
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
            _nlp = spacy.load("en_core_web_sm")
            _model_type = "generic"
            return _nlp, _model_type
        except Exception as e:
            logger.warning(f"Could not load/download en_core_web_sm: {e}")
    except Exception as e:
        logger.warning(f"spaCy initialization failed ({e}). Using regex fallback.")

    # ── Fallback: No spaCy ────────────────────────────────────────────────────
    _nlp = False
    _model_type = None
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# Unit normalization map
# ─────────────────────────────────────────────────────────────────────────────
UNIT_ALIASES = {
    "kilo": "kg", "kilogram": "kg", "kilograms": "kg", "kgs": "kg",
    "liter": "litre", "liters": "litre", "litres": "litre", "ltr": "litre", "ltrs": "litre", "l": "litre",
    "gm": "g", "gram": "g", "grams": "g",
    "ml": "ml", "milliliter": "ml", "millilitre": "ml",
    "pieces": "piece", "pcs": "piece", "pc": "piece",
    "packet": "packet", "pkt": "packet", "packets": "packet",
    "dozen": "dozen",
    "box": "box", "boxes": "box",
    "bottle": "bottle", "bottles": "bottle",
    "bar": "bar", "bars": "bar",
    "cup": "cup", "cups": "cup",
    "bunch": "bunch",
    "can": "can", "cans": "can",
}

UNITS_LIST = list(UNIT_ALIASES.keys()) + ["kg", "g", "ml", "litre", "piece", "packet", "dozen", "box", "bottle", "bar", "cup", "bunch", "can"]


def normalize_unit(raw_unit: str) -> str:
    if not raw_unit:
        return "piece"
    u = raw_unit.lower().strip()
    return UNIT_ALIASES.get(u, u)


def regex_extract(text: str) -> list:
    """
    Pure regex extraction — works when spaCy is unavailable.
    Handles: '2kg rice', '2.5 kg rice', '2 rice', '1/2 kg rice'
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    items = []

    units_pattern = "|".join(sorted(UNITS_LIST, key=len, reverse=True))
    pattern = re.compile(
        r"^\s*([\d./]+)\s*(" + units_pattern + r")?\s+(.+)$",
        re.IGNORECASE
    )

    for line in lines:
        m = pattern.match(line)
        if m:
            raw_qty, raw_unit, raw_prod = m.groups()
            try:
                if "/" in raw_qty:
                    num, denom = raw_qty.split("/")
                    quantity = float(num) / float(denom)
                else:
                    quantity = float(raw_qty)
            except ValueError:
                quantity = 1.0

            unit = normalize_unit(raw_unit)
            product = raw_prod.strip().title()

            if product:
                items.append({"product": product, "quantity": quantity, "unit": unit})
        else:
            # Line starts with product name (e.g. "Rice 2 kg")
            m2 = re.match(
                r"^(.+?)\s+([\d./]+)\s*(" + units_pattern + r")?$",
                line, re.IGNORECASE
            )
            if m2:
                raw_prod, raw_qty, raw_unit = m2.groups()
                try:
                    quantity = float(raw_qty)
                except ValueError:
                    quantity = 1.0
                unit = normalize_unit(raw_unit)
                product = raw_prod.strip().title()
                if product:
                    items.append({"product": product, "quantity": quantity, "unit": unit})
            elif line:
                # Just a product name, no quantity
                items.append({"product": line.strip().title(), "quantity": 1.0, "unit": "piece"})

    return items


def custom_ner_extract(nlp_model, text: str) -> list:
    """
    Use the custom trained NER model to extract PRODUCT, QUANTITY, UNIT entities.
    Falls back to regex for lines where NER finds nothing.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    items = []

    for line in lines:
        doc = nlp_model(line)
        entities = {ent.label_: ent.text for ent in doc.ents}

        product = entities.get("PRODUCT", "").strip()
        qty_text = entities.get("QUANTITY", "1").strip()
        unit_text = entities.get("UNIT", "").strip()

        # Parse quantity
        try:
            if "/" in qty_text:
                num, denom = qty_text.split("/")
                quantity = float(num) / float(denom)
            else:
                quantity = float(re.sub(r"[^\d./]", "", qty_text) or "1")
        except ValueError:
            quantity = 1.0

        unit = normalize_unit(unit_text)

        if product:
            items.append({
                "product": product.title(),
                "quantity": quantity,
                "unit": unit,
            })
        else:
            # NER found nothing useful — fall back to regex for this line
            fallback = regex_extract(line)
            items.extend(fallback)

    return items


def generic_spacy_extract(nlp_model, text: str) -> list:
    """
    Use the generic en_core_web_sm model (noun-based POS tagging).
    Combined with regex for quantity/unit extraction.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    items = []

    units_pattern = "|".join(sorted(UNITS_LIST, key=len, reverse=True))
    qty_pattern = re.compile(
        r"([\d./]+)\s*(" + units_pattern + r")?",
        re.IGNORECASE
    )

    for line in lines:
        # Extract quantity+unit via regex
        qty_m = qty_pattern.search(line)
        quantity = 1.0
        unit = "piece"
        if qty_m:
            try:
                raw = qty_m.group(1)
                quantity = float(raw.split("/")[0]) / float(raw.split("/")[1]) if "/" in raw else float(raw)
            except ValueError:
                quantity = 1.0
            unit = normalize_unit(qty_m.group(2))

        # Extract product name via spaCy noun detection
        doc = nlp_model(line)
        nouns = [t.text for t in doc if t.pos_ in ("NOUN", "PROPN", "ADJ") and not t.like_num]
        if nouns:
            product = " ".join(nouns).title()
            items.append({"product": product, "quantity": quantity, "unit": unit})
        else:
            # Fallback: strip numbers from line
            product = re.sub(r"[\d./]+\s*(" + units_pattern + r")?", "", line, flags=re.IGNORECASE).strip().title()
            if product:
                items.append({"product": product, "quantity": quantity, "unit": unit})

    return items


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────
def extract_entities(text: str) -> list:
    """
    Main function: extracts (Product, Quantity, Unit) from grocery order text.

    Returns a list of dicts:
        [{'product': 'Rice', 'quantity': 2.0, 'unit': 'kg'}, ...]
    """
    if not text or not text.strip():
        return []

    nlp_model, model_type = load_spacy_model()

    if model_type == "custom_ner":
        logger.debug("Using custom retail NER model")
        return custom_ner_extract(nlp_model, text)
    elif model_type == "generic":
        logger.debug("Using generic en_core_web_sm model")
        return generic_spacy_extract(nlp_model, text)
    else:
        logger.debug("Using regex-only fallback")
        return regex_extract(text)
