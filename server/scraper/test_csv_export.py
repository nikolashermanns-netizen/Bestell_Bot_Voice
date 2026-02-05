"""
Test-Script um den CSV-Export-Endpunkt zu finden.
"""

import os
import re
import sys
from urllib.parse import urljoin, urlencode

import requests

# Pfad für Import anpassen
sys.path.insert(0, os.path.dirname(__file__))
from schmidt_scraper import load_credentials, SchmidtScraper


def test_export_endpoints():
    """Testet verschiedene Export-Endpunkte."""
    
    username, password = load_credentials()
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        return
    
    print(f"Zugangsdaten geladen: {username}")
    
    # Scraper initialisieren und einloggen
    scraper = SchmidtScraper(username, password)
    if not scraper.login():
        print("Login fehlgeschlagen!")
        return
    
    print("Login erfolgreich!")
    
    # Suche initialisieren um SucheLID und SucheID zu bekommen
    search_term = "VIEGA PROFIPRESS"
    suche_lid, suche_id, total_hits = scraper.search_products_init(search_term)
    
    print(f"Suche: '{search_term}' -> {total_hits} Treffer")
    print(f"SucheLID: {suche_lid}, SucheID: {suche_id}")
    
    if not suche_lid or not suche_id:
        print("Fehler: Keine Such-IDs gefunden!")
        return
    
    # Liste möglicher Export-Endpunkte
    base_url = scraper.BASE_URL
    
    export_urls = [
        # GET-Varianten
        f"/hs/export.csp?Format=CSVDetailliert&SucheLID={suche_lid}&SucheID={suche_id}",
        f"/hs/export.csp?Aktion=CSVDetailliert&SucheLID={suche_lid}&SucheID={suche_id}",
        f"/hs/artikelexport.csp?Format=CSVDetailliert&SucheLID={suche_lid}&SucheID={suche_id}",
        f"/hs/artikelsuche.csp?Aktion=Export&Format=CSVDetailliert&SucheLID={suche_lid}&SucheID={suche_id}",
        f"/hs/artikelsuche.csp?Export=CSVDetailliert&SucheLID={suche_lid}&SucheID={suche_id}",
        f"/hs/dateiexport.csp?Typ=CSVDetailliert&SucheLID={suche_lid}&SucheID={suche_id}",
        f"/hs/download.csp?Format=CSVDetailliert&SucheLID={suche_lid}&SucheID={suche_id}",
    ]
    
    print("\n--- Teste GET-Endpunkte ---")
    for url in export_urls:
        full_url = urljoin(base_url, url)
        try:
            response = scraper.session.get(full_url, allow_redirects=False)
            content_type = response.headers.get('Content-Type', '')
            content_disp = response.headers.get('Content-Disposition', '')
            
            print(f"\n{url}")
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {content_type[:50]}")
            if content_disp:
                print(f"  Content-Disposition: {content_disp}")
            
            # Prüfen ob CSV
            if 'csv' in content_type.lower() or 'csv' in content_disp.lower():
                print("  >>> CSV GEFUNDEN! <<<")
                # Erste Zeilen ausgeben
                lines = response.text.split('\n')[:5]
                for line in lines:
                    print(f"    {line[:100]}")
                return full_url
            
            # Prüfen ob Download
            if 'attachment' in content_disp or 'octet-stream' in content_type:
                print("  >>> DOWNLOAD! <<<")
                print(f"    Erste 200 Zeichen: {response.text[:200]}")
                return full_url
                
        except Exception as e:
            print(f"\n{url}")
            print(f"  Fehler: {e}")
    
    # POST-Varianten testen
    print("\n--- Teste POST-Endpunkte ---")
    
    post_endpoints = [
        ("/hs/export.csp", {"Format": "CSVDetailliert", "SucheLID": suche_lid, "SucheID": suche_id}),
        ("/hs/export.csp", {"Aktion": "CSVDetailliert", "SucheLID": suche_lid, "SucheID": suche_id}),
        ("/hs/artikelsuche.csp", {"Aktion": "Export", "Format": "CSVDetailliert", "SucheLID": suche_lid, "SucheID": suche_id}),
        ("/hs/artikelsuche.csp", {"Export": "CSVDetailliert", "SucheLID": suche_lid, "SucheID": suche_id}),
        ("/hs/dateiexport.csp", {"Typ": "CSVDetailliert", "SucheLID": suche_lid, "SucheID": suche_id}),
    ]
    
    for endpoint, data in post_endpoints:
        full_url = urljoin(base_url, endpoint)
        try:
            response = scraper.session.post(full_url, data=data, allow_redirects=False)
            content_type = response.headers.get('Content-Type', '')
            content_disp = response.headers.get('Content-Disposition', '')
            
            print(f"\nPOST {endpoint} mit {list(data.keys())}")
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {content_type[:50]}")
            if content_disp:
                print(f"  Content-Disposition: {content_disp}")
            
            # Prüfen ob CSV
            if 'csv' in content_type.lower() or 'csv' in content_disp.lower():
                print("  >>> CSV GEFUNDEN! <<<")
                lines = response.text.split('\n')[:5]
                for line in lines:
                    print(f"    {line[:100]}")
                return (full_url, data)
            
            # Prüfen ob Download
            if 'attachment' in content_disp or 'octet-stream' in content_type:
                print("  >>> DOWNLOAD! <<<")
                print(f"    Erste 200 Zeichen: {response.text[:200]}")
                return (full_url, data)
                
        except Exception as e:
            print(f"\nPOST {endpoint}")
            print(f"  Fehler: {e}")
    
    print("\n--- Kein CSV-Export-Endpunkt gefunden ---")
    print("Versuche, die Artikelsuche-Seite nach versteckten Export-Links zu durchsuchen...")
    
    # Seite laden und nach Export-Links suchen
    search_url = f"{base_url}/hs/artikelsuche.csp?SucheLID={suche_lid}&SucheID={suche_id}&SucheSeite=1"
    response = scraper.session.get(search_url)
    
    # Nach Export-bezogenen Strings suchen
    patterns = [
        r'href="([^"]*export[^"]*)"',
        r'href="([^"]*csv[^"]*)"',
        r'href="([^"]*download[^"]*)"',
        r'action="([^"]*export[^"]*)"',
        r"exportCSV[^'\"]*['\"]([^'\"]+)['\"]",
        r"Export.*?url.*?['\"]([^'\"]+)['\"]",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response.text, re.IGNORECASE)
        if matches:
            print(f"\nPattern '{pattern[:30]}...' gefunden:")
            for match in matches[:5]:
                print(f"  {match}")
    
    return None


if __name__ == "__main__":
    result = test_export_endpoints()
    if result:
        print(f"\n=== Export-Endpunkt gefunden: {result} ===")
