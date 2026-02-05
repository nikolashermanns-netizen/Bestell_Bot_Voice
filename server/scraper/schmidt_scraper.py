"""
Heinrich Schmidt OnlinePro Web Scraper

Scrapt Produktdaten von der Heinrich Schmidt OnlinePro Webseite.
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urljoin, urlencode, quote

import requests
from bs4 import BeautifulSoup

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Product:
    """Repräsentiert ein Produkt aus dem Schmidt-Katalog."""
    artikel_nr: str
    name: str
    hersteller: str
    werks_nr: str
    ean: str = ""
    typ: str = ""
    gewicht: str = ""
    einheit: str = "Stück"
    ek_preis: str = ""
    vk_preis: str = ""
    obergruppe: str = ""
    produktgruppe: str = ""
    kategorie: str = ""
    verfuegbarkeit: str = ""
    
    def to_catalog_format(self) -> dict:
        """Konvertiert zu dem Format, das der Katalog erwartet."""
        return {
            "id": self.artikel_nr.lower().replace("+", "-").replace(" ", "-"),
            "name": self.name,
            "kennung": self.artikel_nr,
            "werks_nr": self.werks_nr,
            "ean": self.ean,
            "typ": self.typ or "ARTIKEL",
            "einheit": self.einheit,
            "zulieferer": self.hersteller,
            "thema": self.kategorie or self.obergruppe,
            "ek_preis": self.ek_preis,
            "vk_preis": self.vk_preis,
            "produktgruppe": self.produktgruppe,
            "obergruppe": self.obergruppe
        }


class SchmidtScraper:
    """Web Scraper für Heinrich Schmidt OnlinePro."""
    
    BASE_URL = "https://onlineprohs.schmidt-mg.de"
    LOGIN_URL = "/hs/login.csp"
    SEARCH_URL = "/hs/artikelsuche.csp"
    PRODUCT_URL = "/hs/artikelauskunft.csp"
    SORTIMENT_URL = "/hs/sortimenthsa.csp"
    
    def __init__(self, username: str, password: str):
        """
        Initialisiert den Scraper.
        
        Args:
            username: Benutzerkennung (z.B. "NH@PLER01")
            password: Passwort
        """
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })
        self.logged_in = False
        self.products: list[Product] = []
        
    def login(self) -> bool:
        """
        Führt den Login durch.
        
        Returns:
            True wenn erfolgreich
        """
        try:
            # Login-Seite laden um Session-Cookies zu bekommen
            login_page = self.session.get(urljoin(self.BASE_URL, self.LOGIN_URL))
            login_page.raise_for_status()
            
            # Login-Formular absenden
            login_data = {
                "Benutzer": self.username,
                "Kennwort": self.password,
                "Dauerhaft": "",
                "Aktion": "Anmelden"
            }
            
            response = self.session.post(
                urljoin(self.BASE_URL, self.LOGIN_URL),
                data=login_data,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Prüfen ob Login erfolgreich war (AGB-Seite oder Index)
            if "agbok.csp" in response.url or "index.csp" in response.url:
                logger.info("Login erfolgreich!")
                
                # Falls AGB-Seite, akzeptieren
                if "agbok.csp" in response.url:
                    agb_data = {
                        "Aktion": "Weiter",
                        "AGB": "on"
                    }
                    agb_response = self.session.post(response.url, data=agb_data, allow_redirects=True)
                    logger.info("AGB akzeptiert")
                
                self.logged_in = True
                return True
            else:
                logger.error(f"Login fehlgeschlagen. URL: {response.url}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Login-Fehler: {e}")
            return False
    
    def search_products(self, search_term: str = "", page: int = 1, items_per_page: int = 100) -> tuple[list[dict], int]:
        """
        Sucht Produkte.
        
        Args:
            search_term: Suchbegriff (leer = alle)
            page: Seitennummer (1-basiert)
            items_per_page: Artikel pro Seite
            
        Returns:
            Tuple von (Liste von Produkt-Grunddaten, Gesamtanzahl Treffer)
        """
        if not self.logged_in:
            raise RuntimeError("Nicht eingeloggt")
        
        # Suchanfrage
        params = {
            "Suchstring": search_term,
            "SuchstringHUSOLR7ID": "",
            "SuchstringSelect": "1",
            "Seite": str(page),
            "ArtikelJeSeite": str(items_per_page)
        }
        
        url = urljoin(self.BASE_URL, self.SEARCH_URL) + "?" + urlencode(params)
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Gesamtanzahl Treffer extrahieren
            total_hits = 0
            hits_text = soup.find(string=re.compile(r"Ihre Suche ergab \d+ Treffer"))
            if hits_text:
                match = re.search(r"(\d+(?:\.\d+)?)\s*Treffer", hits_text)
                if match:
                    total_hits = int(match.group(1).replace(".", ""))
            
            # Produkte aus der Liste extrahieren
            products = []
            
            # Artikel-Karten finden
            article_cards = soup.find_all("div", class_=re.compile(r"artikel-card|product-card|article-item"))
            
            # Fallback: Links zu Artikelauskunft finden
            if not article_cards:
                article_links = soup.find_all("a", href=re.compile(r"artikelauskunft\.csp\?Artikel="))
                for link in article_links:
                    href = link.get("href", "")
                    artikel_match = re.search(r"Artikel=([^&]+)", href)
                    if artikel_match:
                        artikel_nr = artikel_match.group(1).replace("%2B", "+")
                        name = link.get_text(strip=True)
                        if name and artikel_nr and len(name) > 3:
                            products.append({
                                "artikel_nr": artikel_nr,
                                "name": name,
                                "url": urljoin(self.BASE_URL, href)
                            })
            
            # Duplikate entfernen
            seen = set()
            unique_products = []
            for p in products:
                if p["artikel_nr"] not in seen:
                    seen.add(p["artikel_nr"])
                    unique_products.append(p)
            
            logger.info(f"Seite {page}: {len(unique_products)} Produkte gefunden (Gesamt: {total_hits})")
            return unique_products, total_hits
            
        except requests.RequestException as e:
            logger.error(f"Suchfehler: {e}")
            return [], 0
    
    def get_product_details(self, artikel_nr: str) -> Optional[Product]:
        """
        Holt detaillierte Produktinformationen.
        
        Args:
            artikel_nr: Artikelnummer (z.B. "PP+B1590")
            
        Returns:
            Product-Objekt oder None
        """
        if not self.logged_in:
            raise RuntimeError("Nicht eingeloggt")
        
        params = {"Artikel": artikel_nr}
        url = urljoin(self.BASE_URL, self.PRODUCT_URL) + "?" + urlencode(params)
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Produktname aus Überschrift
            name = ""
            h1 = soup.find(["h1", "h2"], string=re.compile(r".+"))
            if h1:
                name = h1.get_text(strip=True)
            
            # Alternativ: Aus dem Titel
            if not name:
                title_elem = soup.find(class_=re.compile(r"artikel-titel|product-title"))
                if title_elem:
                    name = title_elem.get_text(strip=True)
            
            # Tabellen-Daten parsen
            data = {}
            
            # Alle Tabellen durchsuchen
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True).lower().replace(":", "").replace("-", "")
                        value = cells[1].get_text(strip=True)
                        data[key] = value
            
            # Alternativ: Definition Lists
            for dl in soup.find_all("dl"):
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                for dt, dd in zip(dts, dds):
                    key = dt.get_text(strip=True).lower().replace(":", "").replace("-", "")
                    value = dd.get_text(strip=True)
                    data[key] = value
            
            # Alternativ: Key-Value Paare in divs
            for div in soup.find_all("div", class_=re.compile(r"info|detail|property")):
                text = div.get_text(strip=True)
                if ":" in text:
                    parts = text.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip().lower()
                        value = parts[1].strip()
                        data[key] = value
            
            # Preise extrahieren
            ek_preis = ""
            vk_preis = ""
            
            ek_match = soup.find(string=re.compile(r"EK.?Preis", re.IGNORECASE))
            if ek_match:
                parent = ek_match.find_parent()
                if parent:
                    price_text = parent.get_text()
                    price_match = re.search(r"(\d+[,\.]\d+)\s*€", price_text)
                    if price_match:
                        ek_preis = price_match.group(1).replace(",", ".") + " €"
            
            vk_match = soup.find(string=re.compile(r"VK.?Preis", re.IGNORECASE))
            if vk_match:
                parent = vk_match.find_parent()
                if parent:
                    price_text = parent.get_text()
                    price_match = re.search(r"(\d+[,\.]\d+)\s*€", price_text)
                    if price_match:
                        vk_preis = price_match.group(1).replace(",", ".") + " €"
            
            # Product-Objekt erstellen
            product = Product(
                artikel_nr=artikel_nr,
                name=name or data.get("bezeichnung", ""),
                hersteller=data.get("hersteller", ""),
                werks_nr=data.get("werksnr", data.get("werksnummer", "")),
                ean=data.get("ean", ""),
                typ=data.get("type", data.get("typ", "")),
                gewicht=data.get("gewicht", ""),
                einheit=data.get("preiseinheit", "Stück").replace("je ", ""),
                ek_preis=ek_preis or data.get("ekpreis", ""),
                vk_preis=vk_preis or data.get("vkpreis", ""),
                obergruppe=data.get("obergruppe", ""),
                produktgruppe=data.get("produktgruppe", ""),
                kategorie=data.get("kategorie", data.get("sortiment", ""))
            )
            
            return product
            
        except requests.RequestException as e:
            logger.error(f"Produktdetails-Fehler für {artikel_nr}: {e}")
            return None
    
    def scrape_products(self, search_term: str = "", max_products: int = 1000, 
                       delay: float = 0.5, fetch_details: bool = False) -> list[Product]:
        """
        Scrapt Produkte mit Paginierung.
        
        Args:
            search_term: Suchbegriff
            max_products: Maximale Anzahl zu scrapender Produkte
            delay: Verzögerung zwischen Requests (in Sekunden)
            fetch_details: Ob Detailseiten geladen werden sollen
            
        Returns:
            Liste von Product-Objekten
        """
        if not self.logged_in:
            if not self.login():
                return []
        
        self.products = []
        page = 1
        items_per_page = 100  # Maximale Anzahl pro Seite
        
        while len(self.products) < max_products:
            products_basic, total_hits = self.search_products(search_term, page, items_per_page)
            
            if not products_basic:
                logger.info("Keine weiteren Produkte gefunden")
                break
            
            for p in products_basic:
                if len(self.products) >= max_products:
                    break
                
                if fetch_details:
                    # Detailseite laden
                    time.sleep(delay)
                    product = self.get_product_details(p["artikel_nr"])
                    if product:
                        self.products.append(product)
                else:
                    # Nur Grunddaten
                    product = Product(
                        artikel_nr=p["artikel_nr"],
                        name=p["name"],
                        hersteller="",
                        werks_nr=""
                    )
                    self.products.append(product)
                
                if len(self.products) % 50 == 0:
                    logger.info(f"Fortschritt: {len(self.products)}/{max_products} Produkte")
            
            # Prüfen ob es noch mehr Seiten gibt
            if len(products_basic) < items_per_page:
                break
            if page * items_per_page >= total_hits:
                break
                
            page += 1
            time.sleep(delay)
        
        logger.info(f"Scraping abgeschlossen: {len(self.products)} Produkte")
        return self.products
    
    def save_to_json(self, filepath: str, group_by: str = "hersteller"):
        """
        Speichert Produkte als JSON im Katalog-Format.
        
        Args:
            filepath: Ziel-Dateipfad
            group_by: Gruppierung ("hersteller" oder "produktgruppe")
        """
        # Nach Gruppierung sortieren
        groups = {}
        for product in self.products:
            if group_by == "hersteller":
                group_key = product.hersteller or "Sonstige"
            else:
                group_key = product.produktgruppe or product.obergruppe or "Sonstige"
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(product.to_catalog_format())
        
        # Katalog-Struktur erstellen
        catalog = {
            "groups": [
                {
                    "id": key.lower().replace(" ", "-"),
                    "name": key,
                    "subgroups": [
                        {
                            "id": "alle",
                            "name": "Alle Produkte",
                            "items": items
                        }
                    ]
                }
                for key, items in sorted(groups.items())
            ],
            "metadata": {
                "total_products": len(self.products),
                "source": "Heinrich Schmidt OnlinePro",
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        # Speichern
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Katalog gespeichert: {filepath} ({len(self.products)} Produkte in {len(groups)} Gruppen)")


def load_credentials() -> tuple[str, str]:
    """Lädt Zugangsdaten aus der keys-Datei."""
    # Pfad zur keys-Datei im Root-Verzeichnis des Projekts
    keys_path = os.path.join(os.path.dirname(__file__), "..", "..", "keys")
    
    # Fallback: Absoluter Pfad
    if not os.path.exists(keys_path):
        keys_path = r"c:\Users\Nikolas\workspace\Bestell Bot Voice\keys"
    
    username = ""
    password = ""
    
    try:
        with open(keys_path, "r") as f:
            for line in f:
                if line.startswith("user_heinrich_schmidt="):
                    username = line.split("=", 1)[1].strip()
                elif line.startswith("passwort_heinrich_schmidt="):
                    password = line.split("=", 1)[1].strip()
    except FileNotFoundError:
        logger.error(f"Keys-Datei nicht gefunden: {keys_path}")
    
    return username, password


if __name__ == "__main__":
    # Test: Erste 1000 Produkte scrapen
    username, password = load_credentials()
    
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        exit(1)
    
    scraper = SchmidtScraper(username, password)
    
    # Login
    if not scraper.login():
        print("Login fehlgeschlagen!")
        exit(1)
    
    # Produkte scrapen (ohne Details für schnelleren Test)
    products = scraper.scrape_products(
        search_term="",  # Alle Produkte
        max_products=1000,
        delay=0.3,
        fetch_details=False  # Nur Grunddaten für schnelleren Test
    )
    
    # Speichern
    output_path = os.path.join(os.path.dirname(__file__), "..", "schmidt_katalog.json")
    scraper.save_to_json(output_path)
    
    print(f"\nErfolgreich {len(products)} Produkte gescrapet!")
    print(f"Gespeichert unter: {output_path}")
