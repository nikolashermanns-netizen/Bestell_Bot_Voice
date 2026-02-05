"""
Universeller Produktkatalog Manager

Lädt und verwaltet Produktkataloge aller Hersteller für Heinrich Schmidt.
Die Kataloge werden dynamisch von der AI geladen wenn sie gebraucht werden.

FELDSTRUKTUR DER PRODUKTE:
- artikel: Interne Heinrich Schmidt Artikelnummer (Bestellnummer)
- hersteller_nr: Werksnummer/Artikelnummer des Herstellers
- bezeichnung: Vollständiger Produktname (aus Bezeichnung 1 + 2)
- ek_preis: Einkaufspreis für den Kunden (Netto)
- vk_preis: Verkaufspreis (Brutto-Listenpreis)
- ean: EAN-Code (wenn vorhanden)
- einheit: Mengeneinheit (Stück, Meter, etc.)
- pe: Packungseinheit
"""

import json
import logging
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Pfad zum Katalog-Ordner
# Im Docker: /app/system_katalog, lokal: ../system_katalog relativ zur App
_local_path = os.path.join(os.path.dirname(__file__), "..", "system_katalog")
_docker_path = os.path.join(os.path.dirname(__file__), "system_katalog")
CATALOG_DIR = _docker_path if os.path.exists(_docker_path) else _local_path

# Index der verfügbaren Hersteller (wird beim Start geladen)
_hersteller_index: Dict[str, Dict] = {}

# Cache für geladene Kataloge (Key: hersteller_key, Value: Liste von Produkten)
_loaded_catalogs: Dict[str, List[Dict]] = {}

# Aktiv geladene Kataloge für die aktuelle Session (für AI Context)
_active_catalogs: List[str] = []

# Keyword-Index für schnelle Produktsuche (Keyword -> Kataloge)
_keyword_index: Dict[str, Dict] = {}


def load_index() -> bool:
    """
    Lädt den Hersteller-Index beim Serverstart.
    
    Returns:
        True wenn erfolgreich
    """
    global _hersteller_index
    
    index_path = os.path.join(CATALOG_DIR, "_index.json")
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
        
        # Index in handliches Format konvertieren
        _hersteller_index = {}
        for system in index_data.get("systems", []):
            # Key aus Dateiname generieren (ohne .json)
            file_name = system.get("file", "")
            key = file_name.replace(".json", "") if file_name else ""
            
            if key:
                _hersteller_index[key] = {
                    "name": system.get("name", key),
                    "file": system.get("file", ""),
                    "products": system.get("products", 0)
                }
        
        logger.info(f"Katalog-Index geladen: {len(_hersteller_index)} Hersteller, {index_data.get('total_products', 0)} Produkte gesamt")
        
        # Keyword-Index laden
        load_keyword_index()
        
        return True
        
    except FileNotFoundError:
        logger.error(f"Katalog-Index nicht gefunden: {index_path}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Katalog-Index JSON Fehler: {e}")
        return False


def load_keyword_index() -> bool:
    """
    Lädt den Keyword-Index für schnelle Produktsuche.
    
    Returns:
        True wenn erfolgreich
    """
    global _keyword_index
    
    keyword_path = os.path.join(CATALOG_DIR, "_keywords.json")
    
    try:
        with open(keyword_path, "r", encoding="utf-8") as f:
            _keyword_index = json.load(f)
        
        logger.info(f"Keyword-Index geladen: {len(_keyword_index)} Schlagwoerter")
        return True
        
    except FileNotFoundError:
        logger.warning(f"Keyword-Index nicht gefunden: {keyword_path}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Keyword-Index JSON Fehler: {e}")
        return False


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Berechnet Levenshtein-Distanz zwischen zwei Strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def find_similar_keywords(keyword: str, max_distance: int = 2, limit: int = 20) -> List[Dict]:
    """
    Findet aehnliche Schlagwoerter im Index.
    
    Args:
        keyword: Suchbegriff
        max_distance: Maximale Levenshtein-Distanz
        limit: Maximale Anzahl Ergebnisse
    
    Returns:
        Liste von Dicts mit keyword, distance, kataloge
    """
    import re
    
    # Normalisieren
    keyword = keyword.lower().strip()
    keyword = keyword.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    keyword = re.sub(r'[^a-z0-9]', '', keyword)
    
    if not keyword or len(keyword) < 3:
        return []
    
    results = []
    
    # Exakter Match zuerst
    if keyword in _keyword_index:
        data = _keyword_index[keyword]
        results.append({
            "keyword": keyword,
            "distance": 0,
            "kataloge": data["kataloge"],
            "count": data["count"]
        })
    
    # Partial Matches (enthält oder ist enthalten)
    for indexed_kw, data in _keyword_index.items():
        if indexed_kw == keyword:
            continue
        
        # Substring-Match (höhere Priorität)
        if keyword in indexed_kw:
            results.append({
                "keyword": indexed_kw,
                "distance": 0.5,  # Pseudo-Distanz für Substring
                "kataloge": data["kataloge"],
                "count": data["count"]
            })
        elif indexed_kw in keyword:
            results.append({
                "keyword": indexed_kw,
                "distance": 0.5,
                "kataloge": data["kataloge"],
                "count": data["count"]
            })
    
    # Levenshtein nur wenn wenige Ergebnisse und Keyword kurz genug
    if len(results) < 5 and len(keyword) <= 15:
        for indexed_kw, data in _keyword_index.items():
            # Nur ähnlich lange Keywords prüfen (Performance)
            if abs(len(indexed_kw) - len(keyword)) > max_distance:
                continue
            if any(r["keyword"] == indexed_kw for r in results):
                continue
            
            distance = _levenshtein_distance(keyword, indexed_kw)
            if distance <= max_distance:
                results.append({
                    "keyword": indexed_kw,
                    "distance": distance,
                    "kataloge": data["kataloge"],
                    "count": data["count"]
                })
    
    # Nach Distanz sortieren, dann nach Count
    results.sort(key=lambda x: (x["distance"], -x["count"]))
    
    return results[:limit]


def find_catalogs_by_keyword(keyword: str) -> Dict:
    """
    Findet welche Kataloge ein bestimmtes Schlagwort enthalten.
    
    Args:
        keyword: Suchbegriff (z.B. "temponox", "waschtisch", "bogen")
    
    Returns:
        Dict mit kataloge und count, oder leeres Dict
    """
    similar = find_similar_keywords(keyword, max_distance=2, limit=10)
    
    if not similar:
        return {"kataloge": [], "count": 0}
    
    # Alle Kataloge aus allen ähnlichen Keywords sammeln
    all_kataloge = {}
    for item in similar:
        for katalog in item["kataloge"]:
            if katalog not in all_kataloge:
                all_kataloge[katalog] = 0
            all_kataloge[katalog] += item["count"]
    
    sorted_kataloge = sorted(all_kataloge.keys(), key=lambda k: all_kataloge[k], reverse=True)
    return {"kataloge": sorted_kataloge[:10], "count": sum(all_kataloge.values())}


def search_keyword_index(query: str) -> str:
    """
    Sucht im Keyword-Index nach einem Begriff und gibt formatierte Ergebnisse zurück.
    Zeigt auch aehnliche Schlagwoerter, damit die AI entscheiden kann.
    
    Args:
        query: Suchbegriff (kann mehrere Woerter enthalten)
    
    Returns:
        Formatierter String mit gefundenen Schlagwoertern und Katalogen
    """
    words = query.lower().split()
    all_similar = []
    all_kataloge = {}
    
    for word in words:
        # Alle ähnlichen Keywords für dieses Wort finden
        similar = find_similar_keywords(word, max_distance=2, limit=15)
        
        for item in similar:
            # Ähnliche Keywords zur Ausgabe hinzufügen
            existing = next((s for s in all_similar if s["keyword"] == item["keyword"]), None)
            if not existing:
                all_similar.append({
                    "keyword": item["keyword"],
                    "distance": item["distance"],
                    "search_word": word,
                    "kataloge": item["kataloge"]
                })
            
            # Kataloge sammeln
            for katalog in item["kataloge"]:
                if katalog not in all_kataloge:
                    all_kataloge[katalog] = {"count": 0, "keywords": set()}
                all_kataloge[katalog]["count"] += 1
                all_kataloge[katalog]["keywords"].add(item["keyword"])
    
    if not all_similar:
        return f"Kein Schlagwort gefunden fuer '{query}'. Versuche eine Internet-Recherche."
    
    lines = [f"=== Keyword-Suche: '{query}' ==="]
    
    # KATALOGE ZUERST anzeigen (wichtigste Info!)
    sorted_kataloge = sorted(all_kataloge.items(), key=lambda x: x[1]["count"], reverse=True)
    
    lines.append("\nPASSENDE KATALOGE (lade einen davon):")
    for katalog, data in sorted_kataloge[:5]:
        info = _hersteller_index.get(katalog, {})
        name = info.get("name", katalog)
        products = info.get("products", 0)
        keywords = ", ".join(list(data["keywords"])[:3])
        lines.append(f"  -> {katalog}: {name} ({products} Produkte) - Match: {keywords}")
    
    # Exakte Treffer anzeigen (nur die wichtigsten)
    exact_matches = [s for s in all_similar if s["distance"] == 0]
    if exact_matches:
        lines.append(f"\nEXAKTE TREFFER: {', '.join([s['keyword'] for s in exact_matches[:5]])}")
    
    # Ähnliche nur kurz erwähnen
    similar_matches = [s for s in all_similar if s["distance"] > 0][:5]
    if similar_matches:
        lines.append(f"AEHNLICH: {', '.join([s['keyword'] for s in similar_matches])}")
    
    lines.append("\nNutze 'lade_hersteller_katalog' mit dem Katalog-Key (z.B. edelstahl_press, viega).")
    return "\n".join(lines)


def get_available_manufacturers() -> List[Dict]:
    """
    Gibt alle verfügbaren Hersteller zurück.
    
    Returns:
        Liste von Herstellern mit Name und Produktanzahl
    """
    return [
        {
            "key": key,
            "name": info["name"],
            "produkte": info["products"]
        }
        for key, info in sorted(_hersteller_index.items(), key=lambda x: x[1]["name"])
    ]


def get_manufacturer_key(search: str) -> Optional[str]:
    """
    Findet den Katalog-Key für einen Hersteller.
    Sucht nach Name oder Key (case-insensitive).
    
    Args:
        search: Herstellername oder Key (z.B. "Grohe", "villeroy_boch", "V&B")
    
    Returns:
        Katalog-Key oder None
    """
    search_lower = search.lower().strip()
    
    # Aliase für häufige Schreibweisen
    aliases = {
        "v&b": "villeroy_boch",
        "villeroy": "villeroy_boch",
        "villeroy und boch": "villeroy_boch",
        "broetje": "broetje",
        "brötje": "broetje",
        "gruenbeck": "gruenbeck",
        "grünbeck": "gruenbeck",
        "bosch": "bosch_werkzeug",
        "wolf": "wolf_heizung",
        "geberit mapress": "geberit_mapress",
        "geberit mepla": "geberit_mepla",
        "viega profipress": "viega_profipress",
        "viega sanpress": "viega_sanpress",
        "viega megapress": "viega_megapress",
        "profipress": "viega_profipress",
        "sanpress": "viega_sanpress",
        "megapress": "viega_megapress",
        "sma": "sma_solar",
        "edelstahl press": "edelstahl_press",
        "cu press": "cu_press",
        "kupfer press": "cu_press",
    }
    
    # Erst in Aliase suchen
    if search_lower in aliases:
        return aliases[search_lower]
    
    # Dann exakt nach Key suchen
    if search_lower.replace(" ", "_") in _hersteller_index:
        return search_lower.replace(" ", "_")
    
    # Nach Name suchen (enthält)
    for key, info in _hersteller_index.items():
        if search_lower in info["name"].lower():
            return key
        if search_lower in key.lower():
            return key
    
    return None


def load_manufacturer_catalog(key: str) -> Optional[List[Dict]]:
    """
    Lädt den Katalog eines Herstellers in den Cache.
    
    Args:
        key: Katalog-Key (z.B. "grohe", "villeroy_boch")
    
    Returns:
        Liste von Produkten oder None bei Fehler
    """
    global _loaded_catalogs
    
    # Prüfen ob bereits geladen
    if key in _loaded_catalogs:
        logger.info(f"Katalog '{key}' bereits im Cache")
        return _loaded_catalogs[key]
    
    # Hersteller-Info holen
    if key not in _hersteller_index:
        logger.warning(f"Unbekannter Hersteller: {key}")
        return None
    
    info = _hersteller_index[key]
    file_path = os.path.join(CATALOG_DIR, info["file"])
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Produkte normalisieren
        products = []
        for raw in data.get("products", []):
            product = _normalize_product(raw, key, info["name"])
            products.append(product)
        
        # In Cache speichern
        _loaded_catalogs[key] = products
        
        logger.info(f"Katalog '{info['name']}' geladen: {len(products)} Produkte")
        return products
        
    except FileNotFoundError:
        logger.error(f"Katalog-Datei nicht gefunden: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Katalog JSON Fehler ({key}): {e}")
        return None


def _normalize_product(raw: Dict, hersteller_key: str, hersteller_name: str) -> Dict:
    """
    Normalisiert ein Produkt aus dem Roh-JSON in unser Standard-Format.
    
    Args:
        raw: Roh-Produktdaten aus JSON
        hersteller_key: Key des Herstellers
        hersteller_name: Name des Herstellers
    
    Returns:
        Normalisiertes Produkt-Dict
    """
    # Bezeichnung zusammenführen (Bezeichnung 1 + 2)
    bez1 = raw.get("Bezeichnung 1", "").strip()
    bez2 = raw.get("Bezeichnung 2", "").strip()
    bezeichnung = f"{bez1} {bez2}".strip() if bez2 else bez1
    
    # Preise normalisieren (String mit Komma -> Float)
    def parse_price(price_str: str) -> float:
        if not price_str:
            return 0.0
        try:
            # "1.234,56" -> 1234.56
            clean = price_str.replace(".", "").replace(",", ".")
            return float(clean)
        except (ValueError, AttributeError):
            return 0.0
    
    ek_preis = parse_price(raw.get("EK-Preis", ""))
    vk_preis = parse_price(raw.get("VK-Preis", ""))
    
    return {
        "artikel": raw.get("Artikel", ""),                    # Heinrich Schmidt Artikelnummer
        "hersteller_nr": raw.get("Werksnummer", ""),          # Hersteller-Artikelnummer
        "bezeichnung": bezeichnung,                            # Produktname komplett
        "ek_preis": ek_preis,                                 # Einkaufspreis (Kundenpreis)
        "vk_preis": vk_preis,                                 # Verkaufspreis
        "ean": raw.get("EAN", ""),                            # EAN-Code
        "einheit": raw.get("ME", "Stück"),                    # Mengeneinheit
        "pe": raw.get("PE", "1"),                             # Packungseinheit
        "hersteller_key": hersteller_key,
        "hersteller": hersteller_name
    }


def activate_catalog(key: str) -> bool:
    """
    Aktiviert einen Katalog für die aktuelle Session.
    Wird von der AI aufgerufen wenn sie einen Hersteller-Katalog braucht.
    
    Args:
        key: Katalog-Key
    
    Returns:
        True wenn erfolgreich
    """
    global _active_catalogs
    
    # Katalog laden falls nicht im Cache
    products = load_manufacturer_catalog(key)
    if products is None:
        return False
    
    # Als aktiv markieren
    if key not in _active_catalogs:
        _active_catalogs.append(key)
    
    return True


def get_active_products() -> List[Dict]:
    """
    Gibt alle Produkte der aktiv geladenen Kataloge zurück.
    
    Returns:
        Liste aller aktiven Produkte
    """
    all_products = []
    for key in _active_catalogs:
        if key in _loaded_catalogs:
            all_products.extend(_loaded_catalogs[key])
    return all_products


def clear_active_catalogs():
    """Setzt die aktiven Kataloge zurück (bei neuem Anruf)."""
    global _active_catalogs
    _active_catalogs = []
    logger.info("Aktive Kataloge zurückgesetzt")


def get_catalog_for_ai(key: str, max_products: int = 500) -> str:
    """
    Gibt den Katalog in einem Format zurück, das die AI verstehen kann.
    
    Args:
        key: Katalog-Key
        max_products: Maximale Anzahl Produkte (für Context-Limit)
    
    Returns:
        Formatierter String für AI-Context
    """
    if key not in _loaded_catalogs:
        products = load_manufacturer_catalog(key)
        if not products:
            return f"Fehler: Katalog '{key}' konnte nicht geladen werden."
    else:
        products = _loaded_catalogs[key]
    
    hersteller_name = _hersteller_index.get(key, {}).get("name", key)
    
    lines = [
        f"=== KATALOG {hersteller_name.upper()} - {len(products)} Produkte ===",
        "",
        "Format: BEZEICHNUNG | Artikel-Nr (intern) | Hersteller-Nr | EK-Preis | VK-Preis",
        ""
    ]
    
    # Produkte ausgeben (bis max_products)
    for p in products[:max_products]:
        hersteller_nr = p["hersteller_nr"] if p["hersteller_nr"] else "-"
        ek = f"{p['ek_preis']:.2f}€" if p['ek_preis'] else "-"
        vk = f"{p['vk_preis']:.2f}€" if p['vk_preis'] else "-"
        
        lines.append(f"- {p['bezeichnung']} | {p['artikel']} | {hersteller_nr} | EK: {ek} | VK: {vk}")
    
    if len(products) > max_products:
        lines.append(f"\n... und {len(products) - max_products} weitere Produkte")
    
    lines.extend([
        "",
        "=== ENDE KATALOG ===",
        "",
        "HINWEIS: 'Artikel-Nr' ist die Heinrich Schmidt Bestellnummer.",
        "'Hersteller-Nr' ist die Werksnummer des Herstellers.",
        "'EK-Preis' ist der Einkaufspreis/Kundenpreis.",
        "'VK-Preis' ist der Verkaufspreis/Listenpreis."
    ])
    
    return "\n".join(lines)


def search_products(
    query: str,
    hersteller_key: str = None,
    nur_aktive: bool = True,
    max_results: int = 20
) -> List[Dict]:
    """
    Sucht Produkte nach Bezeichnung oder Artikelnummer.
    
    Args:
        query: Suchbegriff
        hersteller_key: Optional - nur in diesem Katalog suchen
        nur_aktive: True = nur in aktiven Katalogen suchen
        max_results: Maximale Ergebnisse
    
    Returns:
        Liste gefundener Produkte
    """
    query_lower = query.lower().strip()
    
    # Suchpool bestimmen
    if hersteller_key and hersteller_key in _loaded_catalogs:
        search_pool = _loaded_catalogs[hersteller_key]
    elif nur_aktive:
        search_pool = get_active_products()
    else:
        # Alle geladenen Kataloge durchsuchen
        search_pool = []
        for products in _loaded_catalogs.values():
            search_pool.extend(products)
    
    results = []
    
    for product in search_pool:
        # Nach Bezeichnung suchen
        if query_lower in product["bezeichnung"].lower():
            results.append(product)
            continue
        
        # Nach Artikelnummer suchen
        if query_lower in product["artikel"].lower():
            results.append(product)
            continue
        
        # Nach Hersteller-Nr suchen
        if product["hersteller_nr"] and query_lower in product["hersteller_nr"].lower():
            results.append(product)
            continue
    
    # Nach Relevanz sortieren (exakte Treffer zuerst, dann nach Bezeichnung)
    results.sort(key=lambda x: (
        0 if query_lower == x["artikel"].lower() else
        1 if query_lower in x["artikel"].lower() else
        2 if query_lower in x["bezeichnung"].lower() else 3,
        x["bezeichnung"]
    ))
    
    return results[:max_results]


def get_product_by_artikel(artikel: str) -> Optional[Dict]:
    """
    Findet ein Produkt anhand der Heinrich Schmidt Artikelnummer.
    
    Args:
        artikel: Artikelnummer (z.B. "WT+VERL80")
    
    Returns:
        Produkt oder None
    """
    artikel_lower = artikel.lower().strip()
    
    # In allen geladenen Katalogen suchen
    for products in _loaded_catalogs.values():
        for product in products:
            if product["artikel"].lower() == artikel_lower:
                return product
    
    return None


def get_product_by_hersteller_nr(hersteller_nr: str) -> Optional[Dict]:
    """
    Findet ein Produkt anhand der Hersteller-Artikelnummer.
    
    Args:
        hersteller_nr: Werksnummer des Herstellers (z.B. "4A128L01")
    
    Returns:
        Produkt oder None
    """
    hersteller_nr_lower = hersteller_nr.lower().strip()
    
    # In allen geladenen Katalogen suchen
    for products in _loaded_catalogs.values():
        for product in products:
            if product["hersteller_nr"] and product["hersteller_nr"].lower() == hersteller_nr_lower:
                return product
    
    return None


def format_product_for_ai(product: Dict, show_prices: bool = True) -> str:
    """
    Formatiert ein Produkt für die AI-Ausgabe.
    
    Args:
        product: Produkt-Dict
        show_prices: Ob Preise angezeigt werden sollen
    
    Returns:
        Formatierter String
    """
    lines = [
        f"Produkt: {product['bezeichnung']}",
        f"Hersteller: {product['hersteller']}",
        f"Artikel-Nr (Heinrich Schmidt): {product['artikel']}",
    ]
    
    if product['hersteller_nr']:
        lines.append(f"Hersteller-Nr: {product['hersteller_nr']}")
    
    if show_prices:
        if product['ek_preis']:
            lines.append(f"Einkaufspreis: {product['ek_preis']:.2f}€")
        if product['vk_preis']:
            lines.append(f"Verkaufspreis: {product['vk_preis']:.2f}€")
    
    lines.append(f"Einheit: {product['einheit']}")
    
    if product.get('ean'):
        lines.append(f"EAN: {product['ean']}")
    
    return "\n".join(lines)


def format_search_results_for_ai(products: List[Dict], show_prices: bool = True) -> str:
    """
    Formatiert Suchergebnisse für die AI.
    
    Args:
        products: Liste von Produkten
        show_prices: Ob Preise angezeigt werden sollen
    
    Returns:
        Formatierter String
    """
    if not products:
        return "Keine Produkte gefunden."
    
    lines = [f"Gefunden: {len(products)} Produkte\n"]
    
    for p in products:
        preis_info = ""
        if show_prices and p['ek_preis']:
            preis_info = f" | EK: {p['ek_preis']:.2f}€"
            if p['vk_preis']:
                preis_info += f" | VK: {p['vk_preis']:.2f}€"
        
        hersteller_nr = f" ({p['hersteller_nr']})" if p['hersteller_nr'] else ""
        
        lines.append(f"- {p['bezeichnung']}{hersteller_nr}")
        lines.append(f"  Artikel-Nr: {p['artikel']}{preis_info}")
    
    return "\n".join(lines)


# Kompatibilitäts-Funktionen für bestehenden Code
# (damit ai_client.py nicht sofort umgebaut werden muss)

def load_catalog(catalog_path: str = None) -> bool:
    """Legacy-Funktion - lädt jetzt den Index."""
    return load_index()


def get_system_products(system_id: str, size: str = None) -> list:
    """
    Legacy-Funktion - unterstützt alte Viega-System-IDs.
    Mappt auf neue Katalog-Keys.
    """
    # Mapping alte System-IDs -> neue Katalog-Keys
    system_mapping = {
        "temponox": "viega_profipress",  # Temponox war Teil von Profipress
        "sanpress": "viega_sanpress",
        "sanpress-inox": "viega_sanpress",  # Inox ist jetzt Teil von Sanpress
    }
    
    key = system_mapping.get(system_id)
    if not key:
        return []
    
    products = load_manufacturer_catalog(key)
    if not products:
        return []
    
    # In altes Format konvertieren für Kompatibilität
    return [
        {
            "name": p["bezeichnung"],
            "kennung": p["artikel"],
            "size": "",  # Nicht mehr verfügbar im neuen Format
            "einheit": p["einheit"]
        }
        for p in products
    ]


def get_product_by_kennung(kennung: str) -> Optional[dict]:
    """Legacy-Funktion - nutzt jetzt get_product_by_artikel."""
    product = get_product_by_artikel(kennung)
    if not product:
        return None
    
    # In altes Format konvertieren
    return {
        "name": product["bezeichnung"],
        "kennung": product["artikel"],
        "system": product["hersteller"],
        "size": "",
        "einheit": product["einheit"]
    }
