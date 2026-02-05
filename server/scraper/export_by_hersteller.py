"""
Export aller Produkte nach Hersteller sortiert.
Erstellt eine separate JSON-Datei pro Hersteller.
Keine Duplikate innerhalb jeder Datei.
"""

import json
import logging
import os
import re
import sys
import time
from typing import Set, List, Dict, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from schmidt_csv_export import SchmidtCSVExporter, load_credentials

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HerstellerExporter:
    """Exportiert alle Produkte nach Hersteller sortiert."""
    
    BASE_URL = "https://onlineprohs.schmidt-mg.de"
    HERSTELLER_URL = "/hs/hersteller.csp"
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.exporter = None
        self.session = None
        self.stats = {
            "hersteller_total": 0,
            "hersteller_exported": 0,
            "products_total": 0,
            "files_created": 0,
        }
    
    def initialize(self, username: str, password: str) -> bool:
        """Login durchführen."""
        self.exporter = SchmidtCSVExporter(username, password)
        if self.exporter.login():
            self.session = self.exporter.session
            return True
        return False
    
    def get_all_hersteller(self) -> List[Tuple[str, str]]:
        """
        Holt alle Hersteller von der Webseite.
        Returns: Liste von (Hersteller-Name, Hersteller-ID)
        """
        hersteller_list = []
        page = 1
        max_pages = 50  # Sicherheitslimit
        
        logger.info("Lade Hersteller-Liste...")
        
        while page <= max_pages:
            url = f"{self.BASE_URL}{self.HERSTELLER_URL}?HIndex={(page-1)*24}"
            
            try:
                response = self.session.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Hersteller-Links finden (sie haben meist ein Bild mit alt-Text)
                # Oder sie sind in spezifischen Containern
                
                # Methode 1: Suche nach Links mit Hersteller-Pattern
                links = soup.find_all('a', href=re.compile(r'FilterHersteller='))
                
                if not links:
                    # Methode 2: Suche nach Bild-Alt-Texten in Hersteller-Bereich
                    hersteller_container = soup.find('div', class_=re.compile(r'hersteller', re.I))
                    if hersteller_container:
                        imgs = hersteller_container.find_all('img', alt=True)
                        for img in imgs:
                            name = img.get('alt', '').strip()
                            if name and len(name) > 1:
                                hersteller_list.append((name, name))
                
                # Methode 3: Direktes Parsen der Hersteller-Kacheln
                tiles = soup.find_all('div', class_=re.compile(r'tile|card|item', re.I))
                for tile in tiles:
                    # Suche nach Bild mit alt-Text
                    img = tile.find('img', alt=True)
                    if img:
                        name = img.get('alt', '').strip()
                        if name and len(name) > 1 and name not in ['Logo', 'Bild']:
                            if (name, name) not in hersteller_list:
                                hersteller_list.append((name, name))
                    
                    # Oder nach Link-Text
                    link = tile.find('a')
                    if link:
                        text = link.get_text(strip=True)
                        if text and len(text) > 1:
                            if (text, text) not in hersteller_list:
                                hersteller_list.append((text, text))
                
                # Prüfen ob es eine nächste Seite gibt
                pagination = soup.find(text=re.compile(rf'{page}/{page}|{page}/\d+'))
                next_link = soup.find('a', href=re.compile(r'HIndex='))
                
                # Wenn keine neuen Hersteller gefunden wurden, sind wir durch
                page_hersteller_count = len(hersteller_list)
                
                page += 1
                
                # Kurze Pause
                time.sleep(0.2)
                
                # Wenn wir auf der letzten Seite sind oder keine neuen gefunden
                if page > 28:  # Wir wissen es sind 28 Seiten
                    break
                    
            except Exception as e:
                logger.error(f"Fehler beim Laden der Hersteller-Seite {page}: {e}")
                break
        
        # Deduplizieren
        seen = set()
        unique_hersteller = []
        for name, id in hersteller_list:
            if name.lower() not in seen:
                seen.add(name.lower())
                unique_hersteller.append((name, id))
        
        logger.info(f"Gefunden: {len(unique_hersteller)} Hersteller")
        return unique_hersteller
    
    def get_hersteller_from_filter(self) -> List[str]:
        """
        Alternative Methode: Holt Hersteller aus dem Filter einer Artikelsuche.
        """
        logger.info("Lade Hersteller aus Filter...")
        
        # Suche mit allgemeinem Begriff um Filter zu bekommen
        url = f"{self.BASE_URL}/hs/artikelsuche.csp?Suchstring=a"
        
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Suche nach Hersteller im Filter-Bereich
            hersteller_list = []
            
            # Pattern für Hersteller-Filter-Einträge
            # Sie haben oft ein Format wie "Optima 24.954" (Name + Anzahl)
            filter_items = soup.find_all(text=re.compile(r'^[A-Za-z][\w\s\-&]+\s+[\d\.]+$'))
            
            for item in filter_items:
                # Extrahiere Name (ohne Zahl am Ende)
                match = re.match(r'^([A-Za-z][\w\s\-&]+?)\s+[\d\.]+$', item.strip())
                if match:
                    name = match.group(1).strip()
                    if len(name) > 1:
                        hersteller_list.append(name)
            
            # Alternative: Suche nach Links mit Hersteller-Parameter
            links = soup.find_all('a', href=re.compile(r'FilterHersteller='))
            for link in links:
                text = link.get_text(strip=True)
                # Entferne Zahlen am Ende
                name = re.sub(r'\s*[\d\.]+\s*$', '', text).strip()
                if name and len(name) > 1:
                    hersteller_list.append(name)
            
            # Deduplizieren
            seen = set()
            unique = []
            for name in hersteller_list:
                if name.lower() not in seen:
                    seen.add(name.lower())
                    unique.append(name)
            
            return unique
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Hersteller aus Filter: {e}")
            return []
    
    def get_hersteller_hardcoded(self) -> List[str]:
        """
        Hardcodierte Liste der wichtigsten Hersteller für Sanitär & Heizung.
        Basierend auf der vorherigen Analyse.
        """
        return [
            # Sanitär - Keramik & Badausstattung
            "Duravit", "Villeroy Boch", "Geberit", "Ideal Standard", "Keramag",
            "Laufen", "Kaldewei", "Bette", "Hoesch", "Koralle",
            
            # Sanitär - Armaturen
            "Grohe", "Hansgrohe", "Hansa", "Kludi", "Dornbracht",
            "Keuco", "Schell", "Franke", "Blanco", "Damixa",
            
            # Sanitär - Installation
            "Viega", "Geberit", "TECE", "Sanit", "Friatec",
            "Mepa", "Schwab", "Wisa", "Alcaplast",
            
            # Rohrsysteme
            "Viega Profipress", "Viega Sanpress", "Viega Megapress",
            "Geberit Mapress", "Geberit Mepla", "Uponor", "Rehau",
            "Wavin", "Aquatherm", "Comap",
            
            # Heizung - Wärmeerzeuger
            "Viessmann", "Buderus", "Vaillant", "Wolf", "Junkers",
            "Weishaupt", "Brötje", "Rotex", "Bosch", "Stiebel Eltron",
            "Daikin", "Mitsubishi", "Panasonic", "LG",
            
            # Heizung - Heizkörper
            "Kermi", "Purmo", "Buderus", "Zehnder", "Arbonia",
            "Schulte", "HSK", "Bemm", "Cosmo",
            
            # Heizung - Regelung & Armaturen
            "Oventrop", "Danfoss", "Honeywell", "Heimeier", "Resideo",
            "Caleffi", "IMI Hydronic", "Watts", "Flamco", "Reflex",
            
            # Heizung - Pumpen
            "Grundfos", "Wilo", "DAB", "Lowara",
            
            # Heizung - Wasserbehandlung
            "Syr", "BWT", "Grünbeck", "Judo", "Perma",
            
            # Lüftung & Klima
            "Helios", "Maico", "Systemair", "Zehnder", "Vallox",
            "Pluggit", "Viessmann", "Stiebel Eltron", "Wolf",
            
            # Werkzeuge
            "Rothenberger", "REMS", "Ridgid", "Knipex", "Wera",
            "Wiha", "Makita", "Bosch", "Milwaukee", "Metabo",
            "Hilti", "Fischer",
            
            # Dämmung
            "Armacell", "Rockwool", "Isover", "Kaimann",
            
            # Elektro / Warmwasser
            "AEG", "Clage", "Stiebel Eltron", "Vaillant", "Siemens",
            
            # Weitere wichtige
            "Kemper", "Afriso", "Esbe", "Meibes", "PAW",
        ]
    
    def sanitize_filename(self, name: str) -> str:
        """Erstellt einen sicheren Dateinamen aus dem Hersteller-Namen."""
        # Umlaute ersetzen
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
            ' ': '_', '-': '_', '&': '_', '/': '_',
        }
        result = name.lower()
        for old, new in replacements.items():
            result = result.replace(old, new)
        
        # Nur alphanumerische Zeichen und Unterstriche
        result = re.sub(r'[^a-z0-9_]', '', result)
        
        # Mehrfache Unterstriche entfernen
        result = re.sub(r'_+', '_', result)
        
        return result.strip('_')
    
    def export_hersteller(self, hersteller_name: str) -> Tuple[int, str]:
        """
        Exportiert alle Produkte eines Herstellers.
        Returns: (Anzahl Produkte, Dateipfad)
        """
        logger.info(f"Exportiere: {hersteller_name}")
        
        try:
            products = self.exporter.export_products(hersteller_name, detailed=True)
            
            if not products:
                logger.info(f"  -> Keine Produkte gefunden")
                return 0, ""
            
            # Duplikate entfernen basierend auf Artikel-Nr.
            seen_articles = set()
            unique_products = []
            
            for product in products:
                # Artikel-Nr. extrahieren
                article_nr = None
                for key in ["Artikel-Nr.", "ArtikelNr", "Artikelnummer", "ArtNr", "Art.-Nr.", "Artikel-Nr"]:
                    if key in product and product[key]:
                        article_nr = str(product[key]).strip()
                        break
                
                if article_nr:
                    if article_nr not in seen_articles:
                        seen_articles.add(article_nr)
                        unique_products.append(product)
                else:
                    # Ohne Artikel-Nr. trotzdem hinzufügen
                    unique_products.append(product)
            
            if not unique_products:
                return 0, ""
            
            # Datei speichern
            filename = self.sanitize_filename(hersteller_name) + ".json"
            filepath = os.path.join(self.output_dir, filename)
            
            catalog = {
                "hersteller": hersteller_name,
                "products": unique_products,
                "metadata": {
                    "total": len(unique_products),
                    "source": "Heinrich Schmidt OnlinePro (CSV Export)",
                    "exported_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(catalog, f, ensure_ascii=False, indent=2)
            
            logger.info(f"  -> {len(unique_products)} Produkte (Duplikate entfernt: {len(products) - len(unique_products)})")
            
            return len(unique_products), filepath
            
        except Exception as e:
            logger.error(f"  -> Fehler: {e}")
            return 0, ""
    
    def export_all(self, hersteller_list: List[str] = None) -> dict:
        """Exportiert alle Hersteller."""
        
        if hersteller_list is None:
            # Nutze hardcodierte Liste
            hersteller_list = self.get_hersteller_hardcoded()
            # Deduplizieren
            hersteller_list = list(dict.fromkeys(hersteller_list))
        
        self.stats["hersteller_total"] = len(hersteller_list)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"STARTE EXPORT VON {len(hersteller_list)} HERSTELLERN")
        logger.info(f"{'='*60}\n")
        
        results = []
        
        for i, hersteller in enumerate(hersteller_list, 1):
            logger.info(f"\n[{i}/{len(hersteller_list)}] {hersteller}")
            
            count, filepath = self.export_hersteller(hersteller)
            
            if count > 0:
                self.stats["hersteller_exported"] += 1
                self.stats["products_total"] += count
                self.stats["files_created"] += 1
                
                results.append({
                    "hersteller": hersteller,
                    "products": count,
                    "file": os.path.basename(filepath)
                })
            
            # Rate limiting
            time.sleep(0.3)
        
        # Index erstellen/aktualisieren
        self._update_index(results)
        
        return {
            "stats": self.stats,
            "results": results
        }
    
    def _update_index(self, results: List[dict]):
        """Aktualisiert den Index."""
        index_path = os.path.join(self.output_dir, "_index.json")
        
        # Bestehenden Index laden oder neu erstellen
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        else:
            index = {"total_products": 0, "total_systems": 0, "systems": []}
        
        # Neue/aktualisierte Einträge
        existing_files = {s["file"]: s for s in index.get("systems", [])}
        
        for r in results:
            if r["file"] in existing_files:
                existing_files[r["file"]]["products"] = r["products"]
            else:
                index["systems"].append({
                    "name": r["hersteller"],
                    "file": r["file"],
                    "products": r["products"]
                })
        
        # Totals neu berechnen
        index["total_products"] = sum(s["products"] for s in index["systems"])
        index["total_systems"] = len(index["systems"])
        
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\nIndex aktualisiert: {index['total_products']} Produkte in {index['total_systems']} Dateien")


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "system_katalog")
    os.makedirs(output_dir, exist_ok=True)
    
    # Login
    username, password = load_credentials()
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        sys.exit(1)
    
    print("="*60)
    print("EXPORT NACH HERSTELLER")
    print("="*60)
    print("\nEine JSON-Datei pro Hersteller, keine Duplikate.")
    print("="*60)
    
    exporter = HerstellerExporter(output_dir)
    
    if not exporter.initialize(username, password):
        print("Login fehlgeschlagen!")
        sys.exit(1)
    
    print("\nLogin erfolgreich. Starte Export...\n")
    
    # Export starten
    results = exporter.export_all()
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("EXPORT ABGESCHLOSSEN")
    print("="*60)
    print(f"\nHersteller verarbeitet: {results['stats']['hersteller_total']}")
    print(f"Hersteller mit Produkten: {results['stats']['hersteller_exported']}")
    print(f"Produkte gesamt: {results['stats']['products_total']}")
    print(f"Dateien erstellt: {results['stats']['files_created']}")
    print(f"\nAusgabeverzeichnis: {output_dir}")


if __name__ == "__main__":
    main()
