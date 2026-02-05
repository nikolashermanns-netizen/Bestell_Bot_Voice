"""
Download-Script für SHK-Wissensdokumente.

Lädt frei verfügbare PDFs von Herstellern (Viega, Geberit) herunter
für die Experten-Wissensdatenbank.
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Zielordner für Downloads
WISSEN_DIR = os.path.join(os.path.dirname(__file__), "..", "wissen")
DOKUMENTE_DIR = os.path.join(WISSEN_DIR, "dokumente")


@dataclass
class WissensDokument:
    """Repräsentiert ein heruntergeladenes Wissensdokument."""
    id: str
    name: str
    kategorie: str  # viega, geberit, dvgw
    themen: List[str]
    url: str
    local_path: Optional[str] = None
    groesse_kb: int = 0


# Bekannte Download-URLs für SHK-Dokumente
DOKUMENT_URLS = [
    {
        "id": "viega_temperaturhaltung",
        "name": "Viega Temperaturhaltung und Trinkwasserhygiene",
        "kategorie": "viega",
        "themen": ["Legionellen", "Temperatur", "Zirkulation", "30-Sekunden-Regel"],
        "url": "https://www.viega.de/content/dam/viega/aem_online_assets/download_assets/de/temperaturhaltung_web_12122018.pdf"
    },
    {
        "id": "viega_hygiene_din1988",
        "name": "Viega Hygienebewusste Planung nach DIN 1988-200",
        "kategorie": "viega",
        "themen": ["DIN 1988-200", "Hygiene", "Planung", "3-Liter-Regel"],
        "url": "https://www.viega.de/content/dam/viegadm/en/temp/auto_download_assets/de/hygeinebewussteplanungnachdin1988200ikzsonderhefttrinkwasserhygiene2013.pdf"
    }
]


class SHKWissenDownloader:
    """
    Lädt SHK-Wissensdokumente von Herstellern herunter.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/pdf,text/html,*/*"
        })
        
        # Ordner erstellen falls nicht vorhanden
        os.makedirs(DOKUMENTE_DIR, exist_ok=True)
    
    def download_dokument(self, dok: dict) -> Optional[WissensDokument]:
        """
        Lädt ein einzelnes Dokument herunter.
        
        Args:
            dok: Dict mit id, name, kategorie, themen, url
            
        Returns:
            WissensDokument oder None bei Fehler
        """
        try:
            logger.info(f"Lade: {dok['name']}")
            
            response = self.session.get(dok["url"], timeout=30, allow_redirects=True)
            
            if response.status_code != 200:
                logger.warning(f"  -> HTTP {response.status_code}")
                return None
            
            # Dateiname bestimmen
            content_type = response.headers.get("Content-Type", "")
            
            if "pdf" in content_type.lower():
                ext = ".pdf"
            elif "html" in content_type.lower():
                logger.warning(f"  -> HTML statt PDF erhalten")
                return None
            else:
                ext = ".pdf"  # Default
            
            # Dateiname bereinigen
            filename = f"{dok['id']}{ext}"
            filepath = os.path.join(DOKUMENTE_DIR, filename)
            
            # Speichern
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            groesse_kb = len(response.content) // 1024
            
            logger.info(f"  -> Gespeichert: {filename} ({groesse_kb} KB)")
            
            return WissensDokument(
                id=dok["id"],
                name=dok["name"],
                kategorie=dok["kategorie"],
                themen=dok["themen"],
                url=dok["url"],
                local_path=filepath,
                groesse_kb=groesse_kb
            )
            
        except requests.RequestException as e:
            logger.error(f"  -> Netzwerk-Fehler: {e}")
            return None
        except Exception as e:
            logger.error(f"  -> Fehler: {e}")
            return None
    
    def download_alle(self) -> List[WissensDokument]:
        """
        Lädt alle bekannten Dokumente herunter.
        
        Returns:
            Liste der erfolgreich heruntergeladenen Dokumente
        """
        erfolgreich = []
        
        logger.info(f"Starte Download von {len(DOKUMENT_URLS)} Dokumenten...")
        
        for dok in DOKUMENT_URLS:
            result = self.download_dokument(dok)
            if result:
                erfolgreich.append(result)
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"\nFertig! {len(erfolgreich)}/{len(DOKUMENT_URLS)} Dokumente heruntergeladen.")
        
        return erfolgreich
    
    def suche_viega_downloads(self) -> List[dict]:
        """
        Durchsucht das Viega Downloadcenter nach weiteren PDFs.
        
        Returns:
            Liste von gefundenen Dokument-Dicts
        """
        gefunden = []
        
        try:
            logger.info("Durchsuche Viega Downloadcenter...")
            
            # Downloadcenter Seite laden
            response = self.session.get(
                "https://www.viega.de/de/produkte/downloadcenter.html",
                timeout=30
            )
            
            if response.status_code != 200:
                logger.warning(f"Viega Downloadcenter nicht erreichbar: {response.status_code}")
                return gefunden
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Nach PDF-Links suchen
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                
                if ".pdf" in href.lower():
                    # Nur relevante PDFs (Trinkwasser, Hygiene, Planung)
                    text = link.get_text(strip=True).lower()
                    
                    keywords = ["trinkwasser", "hygiene", "planung", "temperatur", 
                               "legionellen", "din", "dvgw", "rohrdimensionierung"]
                    
                    if any(kw in text or kw in href.lower() for kw in keywords):
                        full_url = urljoin("https://www.viega.de", href)
                        
                        # Duplikate vermeiden
                        if not any(d["url"] == full_url for d in gefunden):
                            gefunden.append({
                                "name": link.get_text(strip=True) or os.path.basename(href),
                                "url": full_url,
                                "kategorie": "viega"
                            })
            
            logger.info(f"  -> {len(gefunden)} PDFs gefunden")
            
        except Exception as e:
            logger.error(f"Fehler beim Durchsuchen: {e}")
        
        return gefunden
    
    def aktualisiere_index(self, dokumente: List[WissensDokument]):
        """
        Aktualisiert den Dokumente-Index.
        
        Args:
            dokumente: Liste der heruntergeladenen Dokumente
        """
        index_path = os.path.join(WISSEN_DIR, "_dokumente_index.json")
        
        index = {
            "version": "1.0",
            "stand": time.strftime("%Y-%m-%d"),
            "anzahl": len(dokumente),
            "dokumente": []
        }
        
        for dok in dokumente:
            index["dokumente"].append({
                "id": dok.id,
                "name": dok.name,
                "kategorie": dok.kategorie,
                "themen": dok.themen,
                "datei": os.path.basename(dok.local_path) if dok.local_path else None,
                "groesse_kb": dok.groesse_kb
            })
        
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Index aktualisiert: {index_path}")


def main():
    """Hauptfunktion zum Herunterladen aller Dokumente."""
    print("=" * 60)
    print("SHK-WISSEN DOWNLOAD")
    print("=" * 60)
    
    downloader = SHKWissenDownloader()
    
    # Bekannte Dokumente herunterladen
    dokumente = downloader.download_alle()
    
    # Index aktualisieren
    if dokumente:
        downloader.aktualisiere_index(dokumente)
    
    # Optional: Weitere Dokumente suchen
    # weitere = downloader.suche_viega_downloads()
    # print(f"\nWeitere verfügbare Dokumente: {len(weitere)}")
    
    print("\n" + "=" * 60)
    print(f"FERTIG! {len(dokumente)} Dokumente in {DOKUMENTE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
