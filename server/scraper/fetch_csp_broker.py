"""
Holt die cspbroker.js und analysiert die cspHttpServerMethod Funktion.
"""

import os
import re
import sys
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))
from schmidt_scraper import load_credentials, SchmidtScraper


def fetch_and_analyze():
    """Holt und analysiert die CSP-Broker-Dateien."""
    
    username, password = load_credentials()
    scraper = SchmidtScraper(username, password)
    if not scraper.login():
        print("Login fehlgeschlagen!")
        return
    
    # CSP-Broker-Dateien herunterladen
    files_to_fetch = [
        "/csp/broker/cspbroker.js",
        "/csp/broker/cspxmlhttp.js",
    ]
    
    for file_path in files_to_fetch:
        url = urljoin(scraper.BASE_URL, file_path)
        print(f"\nLade: {url}")
        
        response = scraper.session.get(url)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        # Speichern
        filename = file_path.split("/")[-1]
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"Gespeichert: {filename}")
        
        # Nach relevanten Funktionen suchen
        print("\n--- Suche nach cspHttpServerMethod ---")
        matches = re.findall(r'function\s+cspHttpServerMethod[^{]*\{[^}]+\}', response.text, re.DOTALL)
        if matches:
            for match in matches:
                print(match[:500])
        
        # Alternative Suche
        if "cspHttpServerMethod" in response.text:
            idx = response.text.find("cspHttpServerMethod")
            print(f"\nKontext um cspHttpServerMethod:")
            print(response.text[max(0, idx-100):idx+500])


if __name__ == "__main__":
    fetch_and_analyze()
