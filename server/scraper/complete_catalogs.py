"""
Vervollständigt Kataloge die durch das 2000er Limit abgeschnitten wurden.
Führt verfeinerte Suchen durch und fügt neue Produkte hinzu (keine Duplikate).
"""

import json
import logging
import os
import sys
import time
from typing import Set, List, Dict

sys.path.insert(0, os.path.dirname(__file__))
from schmidt_csv_export import SchmidtCSVExporter, load_credentials

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Systeme die das 2000er Limit erreicht haben, mit verfeinerten Suchbegriffen
INCOMPLETE_SYSTEMS = {
    "cu_press": {
        "main_file": "cu_press.json",
        "total_expected": 2692,
        "sub_searches": [
            # Nach Größen suchen
            "CU-Press 12",
            "CU-Press 15",
            "CU-Press 18",
            "CU-Press 22",
            "CU-Press 28",
            "CU-Press 35",
            "CU-Press 42",
            "CU-Press 54",
            "CU-Press 64",
            "CU-Press 76",
            "CU-Press 88",
            "CU-Press 108",
            # Nach Typen suchen
            "CU-Press Bogen",
            "CU-Press T-Stück",
            "CU-Press Muffe",
            "CU-Press Reduktion",
            "CU-Press Winkel",
            "CU-Press Kappe",
            "CU-Press Übergang",
        ]
    },
    "helios": {
        "main_file": "helios.json",
        "total_expected": 3010,
        "sub_searches": [
            # Nach Produktkategorien
            "Helios ELS",
            "Helios KWL",
            "Helios M1",
            "Helios MiniVent",
            "Helios Rohrventilator",
            "Helios Kanalventilator",
            "Helios Dachventilator",
            "Helios Wandventilator",
            "Helios Deckenlüfter",
            "Helios Lüftungsgerät",
            "Helios Filter",
            "Helios Schalldämpfer",
            "Helios Brandschutz",
            "Helios Zubehör",
            "Helios Steuerung",
            "Helios Regelung",
        ]
    },
    "ridgid": {
        "main_file": "ridgid.json", 
        "total_expected": 2087,
        "sub_searches": [
            # Nach Produktkategorien
            "Ridgid Rohrabschneider",
            "Ridgid Rohrzange",
            "Ridgid Rohrschneider",
            "Ridgid Gewindeschneider",
            "Ridgid Presszange",
            "Ridgid Inspektionskamera",
            "Ridgid Rohreinigung",
            "Ridgid Entgrater",
            "Ridgid Rohrbieger",
            "Ridgid Werkzeug",
            "Ridgid Ersatzteil",
            "Ridgid Schneidrad",
        ]
    }
}


def get_article_key(product: Dict) -> str:
    """Generiert einen eindeutigen Schlüssel für ein Produkt."""
    # Versuche verschiedene Felder für die Artikelnummer
    for key in ["Artikel-Nr.", "ArtikelNr", "Artikelnummer", "ArtNr", "Art.-Nr."]:
        if key in product and product[key]:
            return str(product[key]).strip()
    
    # Fallback: Kombination aus mehreren Feldern
    parts = []
    for key in ["Bezeichnung", "Hersteller", "EAN"]:
        if key in product and product[key]:
            parts.append(str(product[key]).strip())
    
    return "|".join(parts) if parts else ""


def load_existing_catalog(filepath: str) -> tuple[List[Dict], Set[str]]:
    """Lädt bestehenden Katalog und extrahiert Artikelnummern."""
    products = []
    article_keys = set()
    
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            products = data.get("products", [])
            
            for product in products:
                key = get_article_key(product)
                if key:
                    article_keys.add(key)
    
    return products, article_keys


def save_catalog(filepath: str, products: List[Dict], source_info: str = ""):
    """Speichert Katalog."""
    catalog = {
        "products": products,
        "metadata": {
            "total": len(products),
            "source": f"Heinrich Schmidt OnlinePro (CSV Export) - {source_info}",
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)


def complete_catalog(exporter: SchmidtCSVExporter, system_key: str, system_config: dict, output_dir: str) -> dict:
    """Vervollständigt einen Katalog mit zusätzlichen Suchen."""
    
    main_file = os.path.join(output_dir, system_config["main_file"])
    sub_searches = system_config["sub_searches"]
    expected_total = system_config["total_expected"]
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Vervollständige: {system_key}")
    logger.info(f"Erwartet: {expected_total} Produkte")
    logger.info(f"{'='*60}")
    
    # Bestehenden Katalog laden
    existing_products, existing_keys = load_existing_catalog(main_file)
    initial_count = len(existing_products)
    
    logger.info(f"Bestehende Produkte: {initial_count}")
    logger.info(f"Eindeutige Artikelnummern: {len(existing_keys)}")
    
    # Zusätzliche Suchen durchführen
    new_products_added = 0
    
    for i, search_term in enumerate(sub_searches, 1):
        logger.info(f"\n[{i}/{len(sub_searches)}] Suche: '{search_term}'")
        
        try:
            products = exporter.export_products(search_term, detailed=True)
            
            if not products:
                logger.info(f"  -> Keine Produkte gefunden")
                continue
            
            # Neue Produkte filtern
            new_count = 0
            for product in products:
                key = get_article_key(product)
                
                if key and key not in existing_keys:
                    existing_products.append(product)
                    existing_keys.add(key)
                    new_count += 1
            
            logger.info(f"  -> {len(products)} gefunden, {new_count} neu hinzugefügt")
            new_products_added += new_count
            
        except Exception as e:
            logger.error(f"  -> Fehler: {e}")
        
        # Kleine Pause zwischen Anfragen
        time.sleep(0.3)
    
    # Katalog speichern
    save_catalog(main_file, existing_products, "vervollständigt")
    
    final_count = len(existing_products)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Ergebnis für {system_key}:")
    logger.info(f"  Vorher: {initial_count}")
    logger.info(f"  Nachher: {final_count}")
    logger.info(f"  Neu hinzugefügt: {new_products_added}")
    logger.info(f"  Erwartet: {expected_total}")
    logger.info(f"  Abdeckung: {final_count/expected_total*100:.1f}%")
    logger.info(f"{'='*60}")
    
    return {
        "system": system_key,
        "initial": initial_count,
        "final": final_count,
        "added": new_products_added,
        "expected": expected_total,
        "coverage": round(final_count/expected_total*100, 1)
    }


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "system_katalog")
    
    # Login
    username, password = load_credentials()
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        sys.exit(1)
    
    exporter = SchmidtCSVExporter(username, password)
    if not exporter.login():
        print("Login fehlgeschlagen!")
        sys.exit(1)
    
    print(f"\nVervollständige Kataloge mit 2000er Limit...")
    print(f"Systeme: {list(INCOMPLETE_SYSTEMS.keys())}\n")
    
    results = []
    
    for system_key, system_config in INCOMPLETE_SYSTEMS.items():
        result = complete_catalog(exporter, system_key, system_config, output_dir)
        results.append(result)
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("ZUSAMMENFASSUNG")
    print("="*60)
    
    total_added = 0
    for r in results:
        print(f"\n{r['system']}:")
        print(f"  {r['initial']} -> {r['final']} Produkte (+{r['added']})")
        print(f"  Abdeckung: {r['coverage']}% von {r['expected']}")
        total_added += r['added']
    
    print(f"\nGesamt neu hinzugefügt: {total_added} Produkte")
    
    # Index aktualisieren
    index_path = os.path.join(output_dir, "_index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        # Produktzahlen aktualisieren
        for r in results:
            for system in index.get("systems", []):
                if system["file"] == f"{r['system']}.json":
                    system["products"] = r["final"]
                    break
        
        # Gesamtzahl neu berechnen
        index["total_products"] = sum(s["products"] for s in index.get("systems", []))
        
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"\nIndex aktualisiert: {index['total_products']} Produkte gesamt")


if __name__ == "__main__":
    main()
