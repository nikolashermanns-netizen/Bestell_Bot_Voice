"""
Heinrich Schmidt OnlinePro CSV-Export

Exportiert Produktdaten direkt über den CSV-Export-Endpunkt.
Viel schneller als Seite-für-Seite scrapen!
"""

import csv
import io
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
from urllib.parse import urljoin, urlencode

import requests

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchmidtCSVExporter:
    """Exportiert Produkte über die native CSV-Export-Funktion."""
    
    BASE_URL = "https://onlineprohs.schmidt-mg.de"
    LOGIN_URL = "/hs/login.csp"
    SEARCH_URL = "/hs/artikelsuche.csp"
    # Die Broker-URL wird relativ zur aktuellen Seite aufgelöst
    # Von /hs/artikelsuche.csp aus wird das /hs/%CSP.Broker.cls
    BROKER_URL = "/hs/%25CSP.Broker.cls"
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })
        self.logged_in = False
        
        # Tokens werden aus der Seite extrahiert
        self.export_modal_token = None
        self.csv_export_token = None
        
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
    
    def _extract_tokens(self, html: str) -> Tuple[Optional[str], Optional[str]]:
        """Extrahiert die CSP-Tokens aus der HTML-Seite."""
        
        # Token für ArtikelsucheExport (öffnet Modal)
        export_modal_match = re.search(
            r"\$\('\.ArtikelsucheExport'\)\.on\('click'.*?cspHttpServerMethod\('([^']+)'",
            html, re.DOTALL
        )
        
        # Token für Export2CSV
        csv_export_match = re.search(
            r"\$\('\.Export2CSV'\)\.on\('click'.*?cspHttpServerMethod\('([^']+)'",
            html, re.DOTALL
        )
        
        export_modal_token = export_modal_match.group(1) if export_modal_match else None
        csv_export_token = csv_export_match.group(1) if csv_export_match else None
        
        return export_modal_token, csv_export_token
    
    def _call_csp_method(self, method_token: str, *args) -> requests.Response:
        """Ruft eine CSP-Server-Methode auf."""
        
        # Daten für den CSP-Broker aufbauen
        data = f"WARGC={len(args)}&WEVENT={method_token}"
        
        for i, arg in enumerate(args, 1):
            if arg is not None:
                data += f"&WARG_{i}={requests.utils.quote(str(arg))}"
        
        url = urljoin(self.BASE_URL, self.BROKER_URL)
        
        response = self.session.post(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        
        return response
    
    def search_and_get_tokens(self, search_term: str) -> Tuple[str, str, int]:
        """
        Führt eine Suche durch und extrahiert die benötigten IDs und Tokens.
        
        Returns:
            Tuple von (SucheID, ExportModalToken, Treffer)
        """
        if not self.logged_in:
            raise RuntimeError("Nicht eingeloggt")
        
        # Suche durchführen
        params = {
            "Suchstring": search_term,
            "SuchstringHUSOLR7ID": "",
            "SuchstringSelect": "1",
        }
        
        url = urljoin(self.BASE_URL, self.SEARCH_URL) + "?" + urlencode(params)
        response = self.session.get(url)
        html = response.text
        
        # SucheID extrahieren
        suche_id_match = re.search(r"SucheID=(\d+)", html)
        suche_id = suche_id_match.group(1) if suche_id_match else ""
        
        # Treffer extrahieren
        hits_match = re.search(r"Ihre Suche ergab (\d+(?:\.\d+)?)\s*Treffer", html)
        total_hits = int(hits_match.group(1).replace(".", "")) if hits_match else 0
        
        # Tokens extrahieren
        self.export_modal_token, self.csv_export_token = self._extract_tokens(html)
        
        logger.info(f"Suche: '{search_term}' -> {total_hits} Treffer")
        logger.info(f"SucheID: {suche_id}")
        logger.info(f"Export-Modal-Token: {self.export_modal_token[:30]}..." if self.export_modal_token else "Nicht gefunden")
        logger.info(f"CSV-Export-Token: {self.csv_export_token[:30]}..." if self.csv_export_token else "Nicht gefunden")
        
        return suche_id, self.export_modal_token, total_hits
    
    def get_export_id(self, suche_id: str) -> Optional[str]:
        """
        Öffnet das Export-Modal und holt die ExportID.
        
        Die CSP-Methode gibt HTML/JavaScript zurück, das die ExportID enthält.
        """
        if not self.export_modal_token:
            logger.error("Export-Modal-Token nicht verfügbar")
            return None
        
        logger.info(f"Öffne Export-Modal für SucheID: {suche_id}")
        
        response = self._call_csp_method(self.export_modal_token, suche_id)
        
        # Die Antwort enthält JavaScript das die ExportID setzt
        # Format: $('#ExportID').val(23438068); oder $('#ExportID').val('...');
        export_id_match = re.search(r"#ExportID.*?\.val\((['\"]?)(\d+)\1\)", response.text)
        
        if export_id_match:
            export_id = export_id_match.group(2)  # Gruppe 2 enthält die Zahl
            logger.info(f"ExportID erhalten: {export_id}")
            return export_id
        
        # Alternative: ExportID könnte auch als einfacher String zurückgegeben werden
        # Manchmal ist die Antwort einfach die ID selbst
        if response.text and len(response.text) < 100 and response.text.strip():
            # Könnte ein einfacher ID-String sein
            potential_id = response.text.strip().strip('"\'')
            if potential_id and not '<' in potential_id:
                logger.info(f"ExportID (direkt): {potential_id}")
                return potential_id
        
        logger.warning(f"ExportID nicht gefunden. Antwort: {response.text[:500]}")
        return None
    
    def export_csv(self, export_id: str, detailed: bool = True) -> Optional[str]:
        """
        Führt den CSV-Export durch.
        
        Args:
            export_id: Die ExportID aus dem Modal
            detailed: True für CSV detailliert, False für einfaches CSV
            
        Returns:
            CSV-Inhalt als String oder None bei Fehler
        """
        if not self.csv_export_token:
            logger.error("CSV-Export-Token nicht verfügbar")
            return None
        
        typ = "2" if detailed else "1"  # 2 = detailliert, 1 = einfach
        
        logger.info(f"Starte CSV-Export (Typ: {'detailliert' if detailed else 'einfach'})...")
        
        response = self._call_csp_method(self.csv_export_token, export_id, typ)
        
        # Prüfen ob CSV-Daten zurückgegeben wurden
        content_type = response.headers.get('Content-Type', '')
        
        
        # Der Server gibt oft eine Download-URL zurück
        # Format: window.location='Online3.Download.cls?FileId=650808464';
        if 'Download.cls' in response.text:
            download_match = re.search(r"['\"]?(Online3\.Download\.cls\?FileId=\d+)['\"]?", response.text)
            if download_match:
                download_path = download_match.group(1)
                # Die URL ist relativ zum /hs/ Verzeichnis
                download_url = urljoin(self.BASE_URL, f"/hs/{download_path}")
                
                logger.info(f"Lade CSV von: {download_url}")
                csv_response = self.session.get(download_url)
                
                if csv_response.status_code == 200:
                    logger.info(f"CSV heruntergeladen! Größe: {len(csv_response.text)} Bytes")
                    return csv_response.text
                else:
                    logger.warning(f"Download fehlgeschlagen: Status {csv_response.status_code}")
        
        # Fallback: Direkte CSV-Daten in der Antwort
        if 'csv' in content_type.lower() or (';' in response.text[:1000] and 'Artikel' in response.text[:1000]):
            logger.info(f"CSV-Export erfolgreich! Größe: {len(response.text)} Bytes")
            return response.text
        
        logger.warning(f"Unerwartete Antwort: {response.text[:500]}")
        return None
    
    def parse_csv(self, csv_content: str) -> list[dict]:
        """Parst den CSV-Inhalt in eine Liste von Dictionaries."""
        
        if not csv_content:
            return []
        
        # CSV parsen
        products = []
        
        try:
            # Versuche verschiedene Delimiter
            for delimiter in [';', ',', '\t']:
                reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
                rows = list(reader)
                
                if rows and len(rows[0]) > 2:
                    # Erfolgreicher Parse
                    for row in rows:
                        products.append(dict(row))
                    break
        except Exception as e:
            logger.error(f"CSV-Parse-Fehler: {e}")
            
            # Fallback: Manuell parsen
            lines = csv_content.strip().split('\n')
            if len(lines) > 1:
                header = lines[0].split(';')
                for line in lines[1:]:
                    values = line.split(';')
                    if len(values) == len(header):
                        products.append(dict(zip(header, values)))
        
        logger.info(f"CSV geparst: {len(products)} Produkte")
        return products
    
    def export_products(self, search_term: str, detailed: bool = True) -> list[dict]:
        """
        Hauptmethode: Exportiert alle Produkte für einen Suchbegriff.
        
        Args:
            search_term: Suchbegriff (z.B. "VIEGA PROFIPRESS")
            detailed: True für detaillierte Daten
            
        Returns:
            Liste von Produkt-Dictionaries
        """
        if not self.logged_in:
            if not self.login():
                return []
        
        # 1. Suche durchführen und Tokens holen
        suche_id, export_token, total_hits = self.search_and_get_tokens(search_term)
        
        if not suche_id or not export_token:
            logger.error("Suche fehlgeschlagen oder Tokens nicht gefunden")
            return []
        
        # 2. Export-Modal öffnen und ExportID holen
        export_id = self.get_export_id(suche_id)
        
        if not export_id:
            logger.error("ExportID konnte nicht ermittelt werden")
            return []
        
        # 3. CSV exportieren
        csv_content = self.export_csv(export_id, detailed)
        
        if not csv_content:
            logger.error("CSV-Export fehlgeschlagen")
            return []
        
        # 4. CSV parsen
        products = self.parse_csv(csv_content)
        
        return products
    
    def save_to_json(self, products: list[dict], filepath: str):
        """Speichert die Produkte als JSON."""
        
        catalog = {
            "products": products,
            "metadata": {
                "total": len(products),
                "source": "Heinrich Schmidt OnlinePro (CSV Export)",
                "exported_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Gespeichert: {filepath} ({len(products)} Produkte)")


def load_credentials() -> Tuple[str, str]:
    """Lädt Zugangsdaten aus der keys-Datei."""
    keys_path = os.path.join(os.path.dirname(__file__), "..", "..", "keys")
    
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
    # Argumente parsen
    search_term = sys.argv[1] if len(sys.argv) > 1 else "VIEGA PROFIPRESS"
    
    # Zugangsdaten laden
    username, password = load_credentials()
    
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        sys.exit(1)
    
    print(f"Starte CSV-Export für '{search_term}'...")
    
    exporter = SchmidtCSVExporter(username, password)
    products = exporter.export_products(search_term, detailed=True)
    
    if products:
        output_path = os.path.join(os.path.dirname(__file__), "..", "schmidt_csv_export.json")
        exporter.save_to_json(products, output_path)
        
        print(f"\nErfolgreich {len(products)} Produkte exportiert!")
        print(f"Gespeichert unter: {output_path}")
        
        # Beispiele anzeigen
        if products:
            print("\nBeispielprodukt (erste Zeile):")
            for key, value in list(products[0].items())[:10]:
                print(f"  {key}: {value}")
    else:
        print("Export fehlgeschlagen!")
