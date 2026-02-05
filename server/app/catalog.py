"""
Viega Katalog Modul

Lädt und verwaltet den Viega-Produktkatalog für Function Calling.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Katalog-Daten (global geladen beim Start)
_catalog_data: dict = {}
_all_products: list = []


def load_catalog(catalog_path: str = None) -> bool:
    """
    Lädt den Viega-Katalog aus JSON.
    
    Args:
        catalog_path: Pfad zur JSON-Datei. Default: ../viega_katalog.json
    
    Returns:
        True wenn erfolgreich geladen
    """
    global _catalog_data, _all_products
    
    if catalog_path is None:
        # Pfad im gleichen Ordner wie die Anwendung
        catalog_path = os.path.join(os.path.dirname(__file__), "viega_katalog.json")
    
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            _catalog_data = json.load(f)
        
        # Alle Produkte flach extrahieren für schnelle Suche
        _all_products = []
        for group in _catalog_data.get("groups", []):
            system_id = group.get("id", "")
            system_name = group.get("name", "")
            
            for subgroup in group.get("subgroups", []):
                size = subgroup.get("name", "")
                
                for item in subgroup.get("items", []):
                    product = {
                        **item,
                        "system_id": system_id,
                        "system_name": system_name,
                        "size": size
                    }
                    _all_products.append(product)
        
        logger.info(f"Viega Katalog geladen: {len(_all_products)} Produkte in {len(_catalog_data.get('groups', []))} Systemen")
        return True
        
    except FileNotFoundError:
        logger.error(f"Katalog nicht gefunden: {catalog_path}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Katalog JSON Fehler: {e}")
        return False


def get_systems_overview() -> dict:
    """
    Gibt eine Übersicht aller Systeme mit Produkttypen zurück.
    
    Returns:
        Dict mit System-Infos (für AI Context)
    """
    if not _catalog_data:
        return {"error": "Katalog nicht geladen"}
    
    systems = []
    for group in _catalog_data.get("groups", []):
        # Produkttypen in diesem System sammeln
        product_types = set()
        sizes = set()
        
        for subgroup in group.get("subgroups", []):
            sizes.add(subgroup.get("name", ""))
            for item in subgroup.get("items", []):
                # Produkttyp aus Name extrahieren (z.B. "Bogen 90°", "T-Stueck")
                name = item.get("name", "")
                # System-Prefix entfernen
                for prefix in ["Temponox ", "Sanpress Inox ", "Sanpress "]:
                    if name.startswith(prefix):
                        name = name[len(prefix):]
                        break
                # Größe entfernen
                for size in ["15mm", "18mm", "22mm", "28mm", "35mm", "42mm", "54mm"]:
                    name = name.replace(f" {size}", "")
                product_types.add(name.strip())
        
        systems.append({
            "id": group.get("id"),
            "name": group.get("name"),
            "sizes": sorted(list(sizes)),
            "product_types": sorted(list(product_types)),
            "product_count": sum(len(sg.get("items", [])) for sg in group.get("subgroups", []))
        })
    
    return {
        "systems": systems,
        "total_products": len(_all_products)
    }


def get_system_products(system_id: str, size: str = None) -> list:
    """
    Lädt alle Produkte eines Systems, optional gefiltert nach Größe.
    
    Args:
        system_id: z.B. "temponox", "sanpress", "sanpress-inox"
        size: z.B. "22mm" (optional)
    
    Returns:
        Liste von Produkten mit Artikelnummern
    """
    products = []
    
    for product in _all_products:
        if product.get("system_id") == system_id:
            if size is None or product.get("size") == size:
                products.append({
                    "name": product.get("name"),
                    "kennung": product.get("kennung"),
                    "size": product.get("size"),
                    "einheit": product.get("einheit", "Stueck")
                })
    
    return products


def search_product(query: str, system: str = None, size: str = None) -> list:
    """
    Sucht Produkte nach Name/Typ.
    
    Args:
        query: Suchbegriff (z.B. "Bogen 90", "T-Stück", "Muffe")
        system: System-ID Filter (optional)
        size: Größen-Filter (optional)
    
    Returns:
        Liste von passenden Produkten
    """
    query_lower = query.lower()
    
    # Umlaute normalisieren für Suche
    query_normalized = query_lower.replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
    
    # "Grad" zu "°" konvertieren (AI sagt oft "90 Grad" statt "90°")
    query_lower = query_lower.replace(" grad", "°").replace("grad", "°")
    query_normalized = query_normalized.replace(" grad", "°").replace("grad", "°")
    
    results = []
    
    for product in _all_products:
        # Filter anwenden
        if system and product.get("system_id") != system:
            continue
        if size and product.get("size") != size:
            continue
        
        # Name durchsuchen
        name = product.get("name", "").lower()
        name_normalized = name.replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
        
        # Auch Name mit "°" zu "grad" konvertieren für flexiblere Suche
        name_with_grad = name.replace("°", " grad")
        
        if (query_lower in name or 
            query_normalized in name_normalized or
            query_lower in name_with_grad or
            query_normalized in name_with_grad):
            results.append({
                "name": product.get("name"),
                "kennung": product.get("kennung"),
                "system": product.get("system_name"),
                "size": product.get("size"),
                "einheit": product.get("einheit", "Stueck")
            })
    
    # Nach Relevanz sortieren (exakte Treffer zuerst)
    results.sort(key=lambda x: (
        0 if query_lower in x["name"].lower() else 1,
        x["name"]
    ))
    
    return results[:20]  # Max 20 Ergebnisse


def get_product_by_kennung(kennung: str) -> Optional[dict]:
    """
    Findet ein Produkt anhand der Artikelnummer.
    
    Args:
        kennung: Artikelnummer (z.B. "102036")
    
    Returns:
        Produkt-Dict oder None
    """
    for product in _all_products:
        if product.get("kennung") == kennung:
            return {
                "name": product.get("name"),
                "kennung": product.get("kennung"),
                "system": product.get("system_name"),
                "size": product.get("size"),
                "einheit": product.get("einheit", "Stueck"),
                "werkstoff": product.get("werkstoff"),
                "thema": product.get("thema")
            }
    return None


def format_product_list(products: list, max_items: int = 10) -> str:
    """
    Formatiert eine Produktliste für die AI-Antwort.
    
    Args:
        products: Liste von Produkten
        max_items: Maximale Anzahl anzuzeigender Produkte
    
    Returns:
        Formatierter String für AI Context
    """
    if not products:
        return "Keine Produkte gefunden."
    
    lines = []
    for i, p in enumerate(products[:max_items]):
        lines.append(f"- {p['name']} (Artikel Nummer: {p['kennung']})")
    
    if len(products) > max_items:
        lines.append(f"... und {len(products) - max_items} weitere Produkte")
    
    return "\n".join(lines)
