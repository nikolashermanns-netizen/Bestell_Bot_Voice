"""
Vollständiger Export von Sanitär und Heizung Sortimenten.
Nutzt die Obergruppen-Struktur um das 2000er Limit zu umgehen.
"""

import json
import logging
import os
import re
import sys
import time
from typing import Set, List, Dict, Tuple
from urllib.parse import urljoin, urlencode

sys.path.insert(0, os.path.dirname(__file__))
from schmidt_csv_export import SchmidtCSVExporter, load_credentials

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Alle Obergruppen für Sanitär und Heizung
SORTIMENTE = {
    "sanitaer": {
        "code": "S",
        "name": "Sanitär",
        "obergruppen": [
            "Badkeramik",
            "Armaturen",
            "Brauseprogramme",
            "WC WT Urinal Zubehör",
            "Armaturenanschlusszubehör",
            "Dusch Badewannen",
            "Duschrinnen",
            "Ablaufprogramme",
            "Duschabtrennungen",
            "Wellness",
            "Rückwandverkleidungen",
            "Badmöbel",
            "Spiegel Spiegelschränke",
            "Badaccessoires",
            "Spendersysteme Händetrockner",
            "Barrierefreie Einrichtungen",
            "Einbaumodule",
            "Elektrische Warmwasserbereitung",
            "Spülen Ausgüsse",
            "Sanitär Sets",
            "Sanitärersatzteile",
        ]
    },
    "heizung": {
        "code": "H",
        "name": "Heizung",
        "obergruppen": [
            "Wärmeerzeuger",
            "Gasdurchlauferhitzer",
            "Speicher Trinkwassererwärmung",
            "Abgassysteme",
            "Heizkörper",
            "Heizkörperzubehör",
            "Lufterhitzer",
            "Flächenheizung",
            "Elektrische Heizsysteme",
            "Heizungsarmaturen",
            "Pumpengruppen",
            "Fernwärme",
            "Druckhaltung Abscheider",
            "Pumpen",
            "Messen Anzeigen Erfassen",
            "Brennstofflagerung",
            "Brenner",
            "Heizungswasserbehandlung",
            "Reinigen Pflegen Warten",
            "Heizungsersatzteile",
            "Verteiler Weichen",
            "Regelungen",
        ]
    }
}


def get_article_key(product: Dict) -> str:
    """Generiert einen eindeutigen Schlüssel für ein Produkt."""
    for key in ["Artikel-Nr.", "ArtikelNr", "Artikelnummer", "ArtNr", "Art.-Nr.", "Artikel-Nr"]:
        if key in product and product[key]:
            return str(product[key]).strip()
    
    # Fallback: EAN
    if "EAN" in product and product["EAN"]:
        return f"EAN:{product['EAN']}"
    
    return ""


def save_catalog(filepath: str, products: List[Dict], metadata: dict = None):
    """Speichert Katalog."""
    catalog = {
        "products": products,
        "metadata": metadata or {
            "total": len(products),
            "source": "Heinrich Schmidt OnlinePro (CSV Export)",
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)


class FullSortimentExporter:
    """Exportiert vollständige Sortimente mit Duplikat-Erkennung."""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.exporter = None
        self.all_products: Dict[str, Dict] = {}  # key -> product
        self.stats = {
            "searches": 0,
            "products_found": 0,
            "duplicates_skipped": 0,
        }
    
    def initialize(self, username: str, password: str) -> bool:
        """Login durchführen."""
        self.exporter = SchmidtCSVExporter(username, password)
        return self.exporter.login()
    
    def search_and_collect(self, search_term: str) -> Tuple[int, int]:
        """
        Führt Suche durch und sammelt neue Produkte.
        Returns: (gefunden, neu_hinzugefügt)
        """
        try:
            products = self.exporter.export_products(search_term, detailed=True)
            
            if not products:
                return 0, 0
            
            found = len(products)
            added = 0
            
            for product in products:
                key = get_article_key(product)
                if key and key not in self.all_products:
                    self.all_products[key] = product
                    added += 1
                elif key:
                    self.stats["duplicates_skipped"] += 1
            
            self.stats["searches"] += 1
            self.stats["products_found"] += found
            
            return found, added
            
        except Exception as e:
            logger.error(f"Fehler bei Suche '{search_term}': {e}")
            return 0, 0
    
    def export_obergruppe(self, obergruppe: str, sortiment_name: str) -> Tuple[int, int]:
        """
        Exportiert eine Obergruppe.
        Bei > 2000 Treffern werden verfeinerte Suchen durchgeführt.
        """
        logger.info(f"  Exportiere Obergruppe: {obergruppe}")
        
        # Erste Suche mit Obergruppen-Begriff
        found, added = self.search_and_collect(obergruppe)
        logger.info(f"    -> {found} gefunden, {added} neu")
        
        # Wenn genau 2000, ist wahrscheinlich mehr da
        if found >= 2000:
            logger.info(f"    -> Limit erreicht, verfeinere Suche...")
            
            # Kombinierte Suche mit Sortiment
            found2, added2 = self.search_and_collect(f"{sortiment_name} {obergruppe}")
            logger.info(f"    -> Kombiniert: {found2} gefunden, {added2} neu")
            added += added2
            
            # Suche mit häufigen Ergänzungen
            for suffix in ["12", "15", "18", "22", "25", "28", "32", "40", "50", "DN"]:
                f, a = self.search_and_collect(f"{obergruppe} {suffix}")
                if a > 0:
                    logger.info(f"    -> {obergruppe} {suffix}: {a} neu")
                    added += a
                time.sleep(0.2)
        
        time.sleep(0.3)  # Rate limiting
        return found, added
    
    def export_sortiment(self, sortiment_key: str) -> dict:
        """Exportiert ein komplettes Sortiment."""
        config = SORTIMENTE[sortiment_key]
        sortiment_name = config["name"]
        obergruppen = config["obergruppen"]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"EXPORTIERE: {sortiment_name}")
        logger.info(f"Obergruppen: {len(obergruppen)}")
        logger.info(f"{'='*60}")
        
        start_count = len(self.all_products)
        
        for i, og in enumerate(obergruppen, 1):
            logger.info(f"\n[{i}/{len(obergruppen)}] {og}")
            self.export_obergruppe(og, sortiment_name)
        
        # Zusätzliche allgemeine Suchen für das Sortiment
        logger.info(f"\n  Zusätzliche Suchen für {sortiment_name}...")
        
        # Suche nach dem Sortiment selbst mit Zahlen (für Größen etc.)
        for term in [sortiment_name, f"{sortiment_name} Ersatzteil", f"{sortiment_name} Zubehör"]:
            f, a = self.search_and_collect(term)
            if a > 0:
                logger.info(f"    -> '{term}': {a} neu")
            time.sleep(0.3)
        
        added_total = len(self.all_products) - start_count
        
        # Speichern
        filepath = os.path.join(self.output_dir, f"{sortiment_key}_komplett.json")
        
        # Nur Produkte dieses Sortiments speichern
        # (Wir speichern alle gesammelten, da sie nach Obergruppen gefiltert wurden)
        products_list = list(self.all_products.values())
        
        save_catalog(filepath, products_list, {
            "sortiment": sortiment_name,
            "total": len(products_list),
            "source": "Heinrich Schmidt OnlinePro (CSV Export) - Vollständig",
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "obergruppen": obergruppen,
        })
        
        logger.info(f"\n{'='*60}")
        logger.info(f"{sortiment_name} FERTIG:")
        logger.info(f"  Neu hinzugefügt: {added_total}")
        logger.info(f"  Gesamt gesammelt: {len(self.all_products)}")
        logger.info(f"  Gespeichert: {filepath}")
        logger.info(f"{'='*60}")
        
        return {
            "sortiment": sortiment_name,
            "added": added_total,
            "total": len(self.all_products),
            "file": filepath
        }
    
    def export_all(self, sortiment_keys: List[str]) -> dict:
        """Exportiert alle angegebenen Sortimente."""
        results = []
        
        for key in sortiment_keys:
            if key in SORTIMENTE:
                result = self.export_sortiment(key)
                results.append(result)
                
                # Zwischenspeichern nach jedem Sortiment
                self._save_progress()
        
        return {
            "results": results,
            "total_products": len(self.all_products),
            "stats": self.stats
        }
    
    def _save_progress(self):
        """Speichert Zwischenstand."""
        progress_file = os.path.join(self.output_dir, "_progress.json")
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({
                "products_collected": len(self.all_products),
                "stats": self.stats,
                "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
            }, f, indent=2)


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "system_katalog")
    os.makedirs(output_dir, exist_ok=True)
    
    # Login
    username, password = load_credentials()
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        sys.exit(1)
    
    print("="*60)
    print("VOLLSTÄNDIGER EXPORT: SANITÄR & HEIZUNG")
    print("="*60)
    print(f"\nErwartete Produkte:")
    print(f"  Sanitär: ~220.000")
    print(f"  Heizung: ~200.000")
    print(f"  Gesamt: ~420.000")
    print(f"\nDies kann mehrere Stunden dauern!")
    print("="*60)
    
    exporter = FullSortimentExporter(output_dir)
    
    if not exporter.initialize(username, password):
        print("Login fehlgeschlagen!")
        sys.exit(1)
    
    print("\nLogin erfolgreich. Starte Export...\n")
    
    # Beide Sortimente exportieren
    results = exporter.export_all(["sanitaer", "heizung"])
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("EXPORT ABGESCHLOSSEN")
    print("="*60)
    
    for r in results["results"]:
        print(f"\n{r['sortiment']}:")
        print(f"  Produkte: {r['added']}")
        print(f"  Datei: {r['file']}")
    
    print(f"\nGESAMT: {results['total_products']} Produkte")
    print(f"Suchen durchgeführt: {results['stats']['searches']}")
    print(f"Duplikate übersprungen: {results['stats']['duplicates_skipped']}")
    
    # Index aktualisieren
    index_path = os.path.join(output_dir, "_index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        # Neue Einträge hinzufügen
        for r in results["results"]:
            filename = os.path.basename(r["file"])
            # Prüfen ob schon vorhanden
            existing = [s for s in index.get("systems", []) if s["file"] == filename]
            if existing:
                existing[0]["products"] = r["added"]
            else:
                index["systems"].append({
                    "name": r["sortiment"] + " (Komplett)",
                    "file": filename,
                    "products": r["added"]
                })
        
        index["total_products"] = sum(s["products"] for s in index.get("systems", []))
        
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"\nIndex aktualisiert: {index['total_products']} Produkte gesamt")


if __name__ == "__main__":
    main()
