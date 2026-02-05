"""
Exportiert den gesamten Heinrich Schmidt Katalog, aufgeteilt nach Sortimenten/Systemen.

Erstellt eine JSON-Datei pro Produktsystem im Ordner 'system_katalog'.
"""

import json
import logging
import os
import re
import sys
import time
from typing import List, Tuple
from urllib.parse import urljoin, urlencode

sys.path.insert(0, os.path.dirname(__file__))
from schmidt_csv_export import SchmidtCSVExporter, load_credentials

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bekannte Haupt-Sortimente aus der Webseite
# Diese werden als Suchbegriffe verwendet
SORTIMENTE = [
    # Installation/Rohrsysteme
    ("CU-Press", "cu_press"),
    ("Edelstahl-Press", "edelstahl_press"),
    ("Viega Profipress", "viega_profipress"),
    ("Viega Sanpress", "viega_sanpress"),
    ("Viega Megapress", "viega_megapress"),
    ("Geberit Mapress", "geberit_mapress"),
    ("Geberit Mepla", "geberit_mepla"),
    
    # Sanitär
    ("Grohe", "grohe"),
    ("Hansgrohe", "hansgrohe"),
    ("Geberit", "geberit"),
    ("Duravit", "duravit"),
    ("Villeroy Boch", "villeroy_boch"),
    ("Ideal Standard", "ideal_standard"),
    ("Keramag", "keramag"),
    ("TECE", "tece"),
    
    # Heizung
    ("Viessmann", "viessmann"),
    ("Buderus", "buderus"),
    ("Vaillant", "vaillant"),
    ("Wolf", "wolf_heizung"),
    ("Junkers", "junkers"),
    ("Weishaupt", "weishaupt"),
    ("Brötje", "broetje"),
    ("Kermi", "kermi"),
    ("Purmo", "purmo"),
    ("Oventrop", "oventrop"),
    ("Danfoss", "danfoss"),
    ("Honeywell", "honeywell"),
    ("Grundfos", "grundfos"),
    ("Wilo", "wilo"),
    
    # Klima/Lüftung
    ("Zehnder", "zehnder"),
    ("Helios", "helios"),
    ("Maico", "maico"),
    
    # Werkzeug
    ("Rothenberger", "rothenberger"),
    ("REMS", "rems"),
    ("Ridgid", "ridgid"),
    ("Knipex", "knipex"),
    ("Wera", "wera"),
    ("Wiha", "wiha"),
    ("Makita", "makita"),
    ("Bosch", "bosch_werkzeug"),
    ("Milwaukee", "milwaukee"),
    ("Metabo", "metabo"),
    ("Hilti", "hilti"),
    ("Fischer", "fischer"),
    
    # Elektro/PV
    ("SMA", "sma_solar"),
    ("Fronius", "fronius"),
    ("Huawei Solar", "huawei_solar"),
    
    # Sonstige Hersteller
    ("Stiebel Eltron", "stiebel_eltron"),
    ("AEG", "aeg"),
    ("Clage", "clage"),
    ("Caleffi", "caleffi"),
    ("Reflex", "reflex"),
    ("Flamco", "flamco"),
    ("IMI Hydronic", "imi_hydronic"),
    ("Heimeier", "heimeier"),
    ("Resideo", "resideo"),
    ("Afriso", "afriso"),
    ("Watts", "watts"),
    ("Kemper", "kemper"),
    ("Schell", "schell"),
    ("Syr", "syr"),
    ("BWT", "bwt"),
    ("Grünbeck", "gruenbeck"),
    ("Judo", "judo"),
    ("Armacell", "armacell"),
    ("Rockwool", "rockwool"),
]


class FullCatalogExporter:
    """Exportiert den gesamten Katalog nach Systemen/Herstellern."""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.exporter = None
        self.stats = {
            "total_products": 0,
            "total_systems": 0,
            "systems": []
        }
        
    def initialize(self, username: str, password: str) -> bool:
        """Initialisiert den Exporter mit Login."""
        self.exporter = SchmidtCSVExporter(username, password)
        return self.exporter.login()
    
    def get_sortiment_list(self) -> List[Tuple[str, str, int]]:
        """
        Holt die Liste aller Sortimente von der Webseite.
        
        Returns:
            Liste von (Name, URL-Slug, Anzahl Artikel)
        """
        if not self.exporter or not self.exporter.logged_in:
            raise RuntimeError("Nicht eingeloggt")
        
        # Sortiment-Seite laden
        url = urljoin(self.exporter.BASE_URL, "/hs/sortimenthsa.csp")
        response = self.exporter.session.get(url)
        
        sortimente = []
        
        # Sortimente aus der Seite extrahieren
        # Format: <a href="artikelsuche.csp?Sortiment=...">Name (Anzahl)</a>
        pattern = r'href="artikelsuche\.csp\?Sortiment=([^"]+)"[^>]*>([^<]+)'
        matches = re.findall(pattern, response.text)
        
        for sortiment_id, name in matches:
            name = name.strip()
            if name and len(name) > 2:
                sortimente.append((name, sortiment_id, 0))
        
        return sortimente
    
    def export_by_search(self, search_term: str, filename: str) -> int:
        """
        Exportiert Produkte für einen Suchbegriff.
        
        Returns:
            Anzahl der exportierten Produkte
        """
        try:
            products = self.exporter.export_products(search_term, detailed=True)
            
            if products:
                filepath = os.path.join(self.output_dir, f"{filename}.json")
                self.exporter.save_to_json(products, filepath)
                return len(products)
            return 0
            
        except Exception as e:
            logger.error(f"Fehler bei Export '{search_term}': {e}")
            return 0
    
    def export_by_sortiment(self, sortiment_id: str, filename: str) -> int:
        """
        Exportiert Produkte für ein Sortiment.
        
        Returns:
            Anzahl der exportierten Produkte
        """
        try:
            # Sortiment-Suche durchführen
            params = {
                "Sortiment": sortiment_id,
                "SuchstringSelect": "1",
            }
            
            url = urljoin(self.exporter.BASE_URL, "/hs/artikelsuche.csp") + "?" + urlencode(params)
            response = self.exporter.session.get(url)
            
            # SucheID und Tokens extrahieren
            suche_id_match = re.search(r"SucheID=(\d+)", response.text)
            if not suche_id_match:
                logger.warning(f"Keine SucheID für Sortiment {sortiment_id}")
                return 0
            
            suche_id = suche_id_match.group(1)
            
            # Tokens extrahieren
            export_modal_token, csv_export_token = self.exporter._extract_tokens(response.text)
            
            if not export_modal_token or not csv_export_token:
                logger.warning(f"Keine Tokens für Sortiment {sortiment_id}")
                return 0
            
            self.exporter.export_modal_token = export_modal_token
            self.exporter.csv_export_token = csv_export_token
            
            # ExportID holen
            export_id = self.exporter.get_export_id(suche_id)
            if not export_id:
                return 0
            
            # CSV exportieren
            csv_content = self.exporter.export_csv(export_id, detailed=True)
            if not csv_content:
                return 0
            
            products = self.exporter.parse_csv(csv_content)
            
            if products:
                filepath = os.path.join(self.output_dir, f"{filename}.json")
                self.exporter.save_to_json(products, filepath)
                return len(products)
            
            return 0
            
        except Exception as e:
            logger.error(f"Fehler bei Sortiment-Export '{sortiment_id}': {e}")
            return 0
    
    def export_all_systems(self) -> dict:
        """
        Exportiert alle bekannten Systeme/Hersteller.
        
        Returns:
            Statistik-Dictionary
        """
        logger.info(f"Starte Export von {len(SORTIMENTE)} Systemen...")
        
        for i, (search_term, filename) in enumerate(SORTIMENTE, 1):
            logger.info(f"\n[{i}/{len(SORTIMENTE)}] Exportiere: {search_term}")
            
            count = self.export_by_search(search_term, filename)
            
            if count > 0:
                self.stats["total_products"] += count
                self.stats["total_systems"] += 1
                self.stats["systems"].append({
                    "name": search_term,
                    "file": f"{filename}.json",
                    "products": count
                })
                logger.info(f"  -> {count} Produkte exportiert")
            else:
                logger.info(f"  -> Keine Produkte gefunden")
            
            # Kurze Pause zwischen Requests
            time.sleep(0.5)
        
        # Statistik speichern
        stats_path = os.path.join(self.output_dir, "_index.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"Export abgeschlossen!")
        logger.info(f"Systeme: {self.stats['total_systems']}")
        logger.info(f"Produkte gesamt: {self.stats['total_products']}")
        logger.info(f"Index: {stats_path}")
        
        return self.stats


def main():
    """Hauptfunktion."""
    
    # Output-Verzeichnis
    output_dir = os.path.join(os.path.dirname(__file__), "..", "system_katalog")
    os.makedirs(output_dir, exist_ok=True)
    
    # Zugangsdaten laden
    username, password = load_credentials()
    
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        sys.exit(1)
    
    print(f"Starte Katalog-Export nach: {output_dir}")
    print(f"Anzahl Systeme: {len(SORTIMENTE)}")
    print()
    
    # Exporter initialisieren
    exporter = FullCatalogExporter(output_dir)
    
    if not exporter.initialize(username, password):
        print("Login fehlgeschlagen!")
        sys.exit(1)
    
    # Alle Systeme exportieren
    stats = exporter.export_all_systems()
    
    print(f"\n{'='*50}")
    print(f"FERTIG!")
    print(f"Exportierte Systeme: {stats['total_systems']}")
    print(f"Exportierte Produkte: {stats['total_products']}")
    print(f"Ausgabeverzeichnis: {output_dir}")


if __name__ == "__main__":
    main()
