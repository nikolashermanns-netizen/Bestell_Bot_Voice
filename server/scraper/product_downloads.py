"""
Produkt-Downloads von Heinrich Schmidt OnlinePro.

Lädt Dokumente (PDFs, Bilder, Datenblätter) für ein spezifisches Produkt herunter.
Kann in das Gesamtsystem integriert werden um der Experten-AI Zugriff auf
Montageanleitungen und technische Daten zu geben.
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Tuple
from urllib.parse import urljoin, quote_plus, unquote

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from schmidt_csv_export import load_credentials

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ProductDownload:
    """Repräsentiert einen heruntergeladenen Artikel-Download."""
    name: str
    type: str  # pdf, jpg, png, etc.
    size: Optional[str]
    url: str
    local_path: Optional[str] = None
    content: Optional[bytes] = None


@dataclass
class ProductInfo:
    """Produktinformationen."""
    article_nr: str
    name: str
    manufacturer: str
    description: str
    weight: Optional[str] = None
    assembly_time: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    downloads: List[ProductDownload] = None
    
    def __post_init__(self):
        if self.downloads is None:
            self.downloads = []


class ProductDownloader:
    """
    Lädt Produktinformationen und Downloads von Heinrich Schmidt OnlinePro.
    
    Verwendung:
        downloader = ProductDownloader(username, password)
        if downloader.login():
            info = downloader.get_product_info("WT+OPS60")
            downloads = downloader.download_all(info)
    """
    
    BASE_URL = "https://onlineprohs.schmidt-mg.de"
    LOGIN_URL = "/hs/login.csp"
    ARTICLE_URL = "/hs/artikelauskunft.csp"
    
    def __init__(self, username: str = None, password: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })
        self.logged_in = False
        
        # Credentials
        if username and password:
            self.username = username
            self.password = password
        else:
            self.username, self.password = load_credentials()
    
    def login(self) -> bool:
        """Führt den Login durch."""
        try:
            # Login-Seite laden
            self.session.get(urljoin(self.BASE_URL, self.LOGIN_URL))
            
            # Login-Formular absenden
            login_data = {
                "KME": self.username,
                "Kennwort": self.password,
                "FlagAngemeldetBleiben": "",
            }
            
            response = self.session.post(
                urljoin(self.BASE_URL, self.LOGIN_URL),
                data=login_data,
                allow_redirects=True
            )
            
            if "agbok.csp" in response.url or "index.csp" in response.url:
                # AGB akzeptieren falls nötig
                if "agbok.csp" in response.url:
                    agb_data = {"Aktion": "Weiter", "AGB": "on"}
                    self.session.post(response.url, data=agb_data, allow_redirects=True)
                
                self.logged_in = True
                logger.info("Login erfolgreich!")
                return True
            else:
                logger.error(f"Login fehlgeschlagen. URL: {response.url}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Login-Fehler: {e}")
            return False
    
    def get_product_info(self, article_nr: str) -> Optional[ProductInfo]:
        """
        Holt Produktinformationen für eine Artikelnummer.
        
        Args:
            article_nr: Die Artikelnummer (z.B. "WT+OPS60")
            
        Returns:
            ProductInfo mit allen verfügbaren Informationen und Downloads
        """
        if not self.logged_in:
            if not self.login():
                return None
        
        # URL für Artikelauskunft
        encoded_article = quote_plus(article_nr)
        url = f"{self.BASE_URL}{self.ARTICLE_URL}?Artikel={encoded_article}&Suchstring={encoded_article}"
        
        logger.info(f"Lade Produktinfo für: {article_nr}")
        
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Produktname extrahieren
            name = ""
            h1 = soup.find('h1')
            if h1:
                name = h1.get_text(strip=True)
            
            # Hersteller
            manufacturer = ""
            hersteller_row = soup.find(text=re.compile(r'Hersteller', re.I))
            if hersteller_row:
                parent = hersteller_row.find_parent('tr') or hersteller_row.find_parent('div')
                if parent:
                    # Suche nach dem Wert
                    value = parent.find('a') or parent.find(class_=re.compile(r'value|content'))
                    if value:
                        manufacturer = value.get_text(strip=True)
            
            # Alternative: Suche nach Optima/etc. im Bild-Alt oder Text
            if not manufacturer:
                logo = soup.find('img', alt=re.compile(r'^[A-Z][a-z]+'))
                if logo:
                    manufacturer = logo.get('alt', '')
            
            # Beschreibung
            description = ""
            desc_elem = soup.find(text=re.compile(r'Ausschreibungstext', re.I))
            if desc_elem:
                parent = desc_elem.find_parent()
                if parent and parent.find_next_sibling():
                    description = parent.find_next_sibling().get_text(strip=True)
            
            # Gewicht
            weight = None
            weight_row = soup.find(text=re.compile(r'Gewicht', re.I))
            if weight_row:
                parent = weight_row.find_parent('tr') or weight_row.find_parent('div')
                if parent:
                    cells = parent.find_all(['td', 'span', 'a'])
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if 'kg' in text.lower():
                            weight = text
                            break
            
            # Montagezeit
            assembly_time = None
            time_row = soup.find(text=re.compile(r'Montagezeit', re.I))
            if time_row:
                parent = time_row.find_parent('tr') or time_row.find_parent('div')
                if parent:
                    cells = parent.find_all(['td', 'span', 'a'])
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if 'Minuten' in text or re.search(r'\d+,?\d*\s*Min', text):
                            assembly_time = text
                            break
            
            # Kategorie
            category = None
            cat_row = soup.find(text=re.compile(r'Obergruppe', re.I))
            if cat_row:
                parent = cat_row.find_parent('tr') or cat_row.find_parent('div')
                if parent:
                    link = parent.find('a')
                    if link:
                        category = link.get_text(strip=True)
            
            # Unterkategorie
            subcategory = None
            subcat_row = soup.find(text=re.compile(r'Produktgruppe', re.I))
            if subcat_row:
                parent = subcat_row.find_parent('tr') or subcat_row.find_parent('div')
                if parent:
                    link = parent.find('a')
                    if link:
                        subcategory = link.get_text(strip=True)
            
            # Downloads finden
            downloads = self._extract_downloads(soup)
            
            product_info = ProductInfo(
                article_nr=article_nr,
                name=name,
                manufacturer=manufacturer,
                description=description,
                weight=weight,
                assembly_time=assembly_time,
                category=category,
                subcategory=subcategory,
                downloads=downloads
            )
            
            logger.info(f"Produkt gefunden: {name}")
            logger.info(f"  Hersteller: {manufacturer}")
            logger.info(f"  Downloads: {len(downloads)}")
            
            return product_info
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Produktinfo: {e}")
            return None
    
    def _extract_downloads(self, soup: BeautifulSoup) -> List[ProductDownload]:
        """Extrahiert alle Download-Links aus der Seite."""
        downloads = []
        
        # Suche nach Download-Bereich
        # Die Downloads sind oft in einem Tab oder Abschnitt
        
        # Methode 1: Suche nach typischen Download-Links
        download_patterns = [
            r'\.pdf',
            r'\.jpg',
            r'\.png',
            r'\.gif',
            r'download',
            r'Infoblatt',
            r'Stammblatt',
            r'Datenblatt',
            r'Montageanleitung',
            r'Anleitung',
            r'Farbbild',
            r'Bild',
        ]
        
        # Alle Links durchsuchen
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Prüfen ob es ein relevanter Download ist
            is_download = False
            download_type = 'unknown'
            
            for pattern in download_patterns:
                if re.search(pattern, href, re.I) or re.search(pattern, text, re.I):
                    is_download = True
                    break
            
            if not is_download:
                continue
            
            # Typ bestimmen
            if '.pdf' in href.lower() or 'pdf' in text.lower():
                download_type = 'pdf'
            elif any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                download_type = 'image'
            elif 'Infoblatt' in text:
                download_type = 'pdf'
            elif 'Stammblatt' in text:
                download_type = 'pdf'
            elif 'Farbbild' in text or 'Bild' in text:
                download_type = 'image'
            
            # URL normalisieren
            if href.startswith('/'):
                full_url = urljoin(self.BASE_URL, href)
            elif href.startswith('http'):
                full_url = href
            else:
                full_url = urljoin(self.BASE_URL, '/hs/' + href)
            
            # Größe extrahieren falls vorhanden
            size = None
            parent = link.find_parent('tr') or link.find_parent('div')
            if parent:
                size_match = re.search(r'(\d+(?:,\d+)?\s*(?:KB|MB|GB))', parent.get_text())
                if size_match:
                    size = size_match.group(1)
            
            # Nur hinzufügen wenn nicht schon vorhanden
            if not any(d.url == full_url for d in downloads):
                downloads.append(ProductDownload(
                    name=text or os.path.basename(href),
                    type=download_type,
                    size=size,
                    url=full_url
                ))
        
        return downloads
    
    def download_file(self, download: ProductDownload, output_dir: str) -> Optional[str]:
        """
        Lädt eine einzelne Datei herunter.
        
        Args:
            download: ProductDownload Objekt
            output_dir: Zielverzeichnis
            
        Returns:
            Pfad zur heruntergeladenen Datei oder None bei Fehler
        """
        try:
            logger.info(f"  Lade: {download.name}")
            
            response = self.session.get(download.url, allow_redirects=True)
            
            if response.status_code != 200:
                logger.warning(f"    -> Fehler: HTTP {response.status_code}")
                return None
            
            # Dateiname bestimmen
            filename = download.name
            
            # Content-Disposition Header prüfen
            content_disp = response.headers.get('Content-Disposition', '')
            if 'filename=' in content_disp:
                match = re.search(r'filename[*]?=(?:UTF-8\'\')?["\']?([^"\';\n]+)', content_disp)
                if match:
                    filename = unquote(match.group(1))
            
            # Dateierweiterung hinzufügen falls nötig
            if not re.search(r'\.\w{2,4}$', filename):
                content_type = response.headers.get('Content-Type', '')
                if 'pdf' in content_type:
                    filename += '.pdf'
                elif 'jpeg' in content_type or 'jpg' in content_type:
                    filename += '.jpg'
                elif 'png' in content_type:
                    filename += '.png'
            
            # Dateiname bereinigen
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            # Speichern
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            download.local_path = filepath
            download.content = response.content
            
            logger.info(f"    -> Gespeichert: {filename} ({len(response.content)} Bytes)")
            
            return filepath
            
        except Exception as e:
            logger.error(f"    -> Fehler: {e}")
            return None
    
    def download_all(self, product_info: ProductInfo, output_dir: str = None) -> List[str]:
        """
        Lädt alle Downloads für ein Produkt herunter.
        
        Args:
            product_info: ProductInfo Objekt mit Downloads
            output_dir: Zielverzeichnis (default: ./downloads/{article_nr}/)
            
        Returns:
            Liste der heruntergeladenen Dateipfade
        """
        if output_dir is None:
            # Sichere Artikelnummer für Verzeichnisname
            safe_article = re.sub(r'[<>:"/\\|?*+]', '_', product_info.article_nr)
            output_dir = os.path.join(os.path.dirname(__file__), 'downloads', safe_article)
        
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"\nLade {len(product_info.downloads)} Downloads für {product_info.article_nr}...")
        
        downloaded_files = []
        
        for download in product_info.downloads:
            filepath = self.download_file(download, output_dir)
            if filepath:
                downloaded_files.append(filepath)
            
            time.sleep(0.2)  # Rate limiting
        
        # Produktinfo als JSON speichern
        info_path = os.path.join(output_dir, 'product_info.json')
        info_dict = asdict(product_info)
        # Downloads ohne Binärdaten speichern
        for d in info_dict.get('downloads', []):
            d.pop('content', None)
        
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\nFertig! {len(downloaded_files)} Dateien heruntergeladen nach: {output_dir}")
        
        return downloaded_files
    
    def get_downloads_for_expert_ai(self, article_nr: str) -> Dict:
        """
        Hauptmethode für die Integration mit der Experten-AI.
        
        Holt alle Produktinformationen und Downloads und gibt sie in einem
        Format zurück, das für die AI verwendbar ist.
        
        Args:
            article_nr: Artikelnummer
            
        Returns:
            Dict mit Produktinfo und Pfaden zu den Downloads
        """
        product_info = self.get_product_info(article_nr)
        
        if not product_info:
            return {"error": f"Produkt {article_nr} nicht gefunden"}
        
        # Downloads herunterladen
        downloaded_files = self.download_all(product_info)
        
        # Ergebnis zusammenstellen
        result = {
            "article_nr": product_info.article_nr,
            "name": product_info.name,
            "manufacturer": product_info.manufacturer,
            "description": product_info.description,
            "weight": product_info.weight,
            "assembly_time": product_info.assembly_time,
            "category": product_info.category,
            "subcategory": product_info.subcategory,
            "downloads": [
                {
                    "name": d.name,
                    "type": d.type,
                    "size": d.size,
                    "local_path": d.local_path
                }
                for d in product_info.downloads if d.local_path
            ],
            "download_count": len(downloaded_files)
        }
        
        return result


# ============================================================================
# TEST / DEMO
# ============================================================================

def main():
    """Test-Funktion zum Ausprobieren."""
    
    # Artikelnummer aus Argumenten oder Standard
    article_nr = sys.argv[1] if len(sys.argv) > 1 else "WT+OPS60"
    
    print("="*60)
    print("PRODUKT-DOWNLOAD TEST")
    print("="*60)
    print(f"\nArtikel: {article_nr}")
    print("="*60)
    
    # Downloader initialisieren
    downloader = ProductDownloader()
    
    if not downloader.login():
        print("Login fehlgeschlagen!")
        sys.exit(1)
    
    # Produktinfo holen
    product_info = downloader.get_product_info(article_nr)
    
    if not product_info:
        print(f"Produkt {article_nr} nicht gefunden!")
        sys.exit(1)
    
    print(f"\n--- PRODUKTINFO ---")
    print(f"Name: {product_info.name}")
    print(f"Hersteller: {product_info.manufacturer}")
    print(f"Gewicht: {product_info.weight}")
    print(f"Montagezeit: {product_info.assembly_time}")
    print(f"Kategorie: {product_info.category} / {product_info.subcategory}")
    
    print(f"\n--- DOWNLOADS ({len(product_info.downloads)}) ---")
    for d in product_info.downloads:
        print(f"  - {d.name} ({d.type}) {d.size or ''}")
    
    # Downloads herunterladen
    print(f"\n--- DOWNLOADING ---")
    downloaded = downloader.download_all(product_info)
    
    print(f"\n{'='*60}")
    print(f"FERTIG! {len(downloaded)} Dateien heruntergeladen.")
    print(f"{'='*60}")
    
    # Ausgabe für Experten-AI
    print(f"\n--- DATEN FÜR EXPERTEN-AI ---")
    result = {
        "article_nr": product_info.article_nr,
        "name": product_info.name,
        "downloads": [d.local_path for d in product_info.downloads if d.local_path]
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
