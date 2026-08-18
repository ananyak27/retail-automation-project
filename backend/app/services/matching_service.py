import difflib
from sqlalchemy.orm import Session
from app.models import Product

def find_best_match(product_name: str, db_products: list, cutoff: float = 0.5):
    """
    Finds the closest matching product from the list of database products.
    Uses difflib's get_close_matches to compute similarity ratios.
    """
    product_names_map = {p.name.lower(): p for p in db_products}
    names_list = list(product_names_map.keys())
    
    # 1. Exact match (case insensitive)
    name_lower = product_name.lower()
    if name_lower in product_names_map:
        return product_names_map[name_lower], []
        
    # 2. Fuzzy match
    matches = difflib.get_close_matches(name_lower, names_list, n=3, cutoff=cutoff)
    
    if matches:
        # If the highest match is very high (e.g. > 0.8), we can auto-match it
        best_match_name = matches[0]
        ratio = difflib.SequenceMatcher(None, name_lower, best_match_name).ratio()
        
        # Mapping matched names back to Product objects
        suggested_products = [product_names_map[m] for m in matches]
        
        if ratio >= 0.85:
            # High confidence auto-match, but return suggested options just in case
            return product_names_map[best_match_name], suggested_products
        else:
            # Low confidence match, return None for product, list of suggestions
            return None, suggested_products
            
    return None, []

def match_extracted_items(db: Session, shop_id: int, extracted_items: list) -> list:
    """
    Matches NLP extracted items against the selected shop's catalog.
    
    Returns a list of dictionaries:
    [
        {
            "original_name": "Ric",
            "quantity": 2.0,
            "unit": "kg",
            "matched_product": ProductObj | None,
            "suggestions": [{"id": 1, "name": "Rice", "price": 65}, ...],
            "recognized": bool
        },
        ...
    ]
    """
    # Fetch all products of this shop
    db_products = db.query(Product).filter(Product.shop_id == shop_id).all()
    
    matched_results = []
    
    for item in extracted_items:
        original_name = item["product"]
        quantity = item["quantity"]
        unit = item["unit"]
        
        matched_product, suggestions = find_best_match(original_name, db_products)
        
        suggestions_data = [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "unit": p.unit,
                "stock": p.stock
            } for p in suggestions
        ]
        
        matched_results.append({
            "original_name": original_name,
            "quantity": quantity,
            "unit": unit,
            "matched_product_id": matched_product.id if matched_product else None,
            "matched_product_name": matched_product.name if matched_product else None,
            "matched_product_price": matched_product.price if matched_product else None,
            "suggestions": suggestions_data,
            "recognized": matched_product is not None
        })
        
    return matched_results
