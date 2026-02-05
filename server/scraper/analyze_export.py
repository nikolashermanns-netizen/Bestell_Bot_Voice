"""
Analysiert die Export-JavaScript-Funktionen in der Artikelsuche-Seite.
"""

import os
import re
import sys
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))
from schmidt_scraper import load_credentials, SchmidtScraper


def analyze_export():
    """Analysiert die Export-Funktionalität."""
    
    username, password = load_credentials()
    if not username or not password:
        print("Fehler: Zugangsdaten nicht gefunden!")
        return
    
    scraper = SchmidtScraper(username, password)
    if not scraper.login():
        print("Login fehlgeschlagen!")
        return
    
    # Suche initialisieren
    search_term = "VIEGA PROFIPRESS"
    suche_lid, suche_id, total_hits = scraper.search_products_init(search_term)
    
    print(f"Suche: '{search_term}' -> {total_hits} Treffer")
    print(f"SucheLID: {suche_lid}, SucheID: {suche_id}")
    
    # Artikelsuche-Seite laden
    search_url = f"{scraper.BASE_URL}/hs/artikelsuche.csp?SucheLID={suche_lid}&SucheID={suche_id}&SucheSeite=1"
    response = scraper.session.get(search_url)
    html = response.text
    
    # HTML speichern für manuelle Analyse
    with open("artikelsuche_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("\nHTML gespeichert: artikelsuche_page.html")
    
    # Nach Export-bezogenem JavaScript suchen
    print("\n--- Suche nach Export-Funktionen ---")
    
    # Pattern für Export-Funktionen
    patterns = [
        (r"function\s+(\w*[Ee]xport\w*)\s*\([^)]*\)\s*\{([^}]+)\}", "Export-Funktionen"),
        (r"(CSVDetailliert|CSV\s*detailliert)[^}]*\{([^}]+)\}", "CSVDetailliert Handler"),
        (r"(ExportDateien)[^}]*\{([^}]+)\}", "ExportDateien Handler"),
        (r"Download\.cls[^'\"]*", "Download.cls URLs"),
        (r"(exportieren|export)\s*[:=]\s*['\"]([^'\"]+)['\"]", "Export-URLs"),
        (r"data-export[^>]*", "data-export Attribute"),
        (r"onclick=['\"][^'\"]*export[^'\"]*['\"]", "onclick Export Handler"),
    ]
    
    for pattern, description in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
        if matches:
            print(f"\n{description}:")
            for match in matches[:3]:
                if isinstance(match, tuple):
                    print(f"  {match[0][:100]}...")
                else:
                    print(f"  {match[:150]}...")
    
    # Suche nach dem Export-Modal
    print("\n--- Suche nach Export-Modal HTML ---")
    
    # Suche nach dem Modal mit ExportDateien
    modal_match = re.search(r'id="ExportDateien"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
    if modal_match:
        print("ExportDateien Modal gefunden:")
        print(modal_match.group(0)[:500])
    
    # Suche nach allen Buttons im Export-Bereich
    print("\n--- Suche nach Export-Buttons ---")
    buttons = re.findall(r'<button[^>]*class="[^"]*btn[^"]*"[^>]*>([^<]+)</button>', html, re.IGNORECASE)
    export_buttons = [b for b in buttons if 'csv' in b.lower() or 'export' in b.lower() or 'excel' in b.lower()]
    print(f"Export-bezogene Buttons: {export_buttons}")
    
    # Suche nach Form-Actions
    print("\n--- Suche nach Forms ---")
    forms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>', html, re.IGNORECASE)
    for form in forms:
        if 'export' in form.lower() or 'download' in form.lower():
            print(f"  Form action: {form}")
    
    # Suche nach versteckten Inputs
    print("\n--- Suche nach versteckten Inputs mit Export-Bezug ---")
    hidden_inputs = re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]*)"[^>]*value="([^"]*)"', html, re.IGNORECASE)
    for name, value in hidden_inputs:
        if any(x in name.lower() or x in value.lower() for x in ['export', 'csv', 'format', 'typ']):
            print(f"  {name} = {value}")
    
    # Suche nach AJAX-Calls
    print("\n--- Suche nach AJAX-Export-Calls ---")
    ajax_patterns = [
        r'\$\.ajax\([^)]*[Ee]xport[^)]*\)',
        r'\$\.post\([^)]*[Ee]xport[^)]*\)',
        r'\$\.get\([^)]*[Ee]xport[^)]*\)',
        r'fetch\([^)]*[Ee]xport[^)]*\)',
        r'window\.location\s*=\s*[\'"]([^"\']*export[^"\']*)[\'"]',
        r'window\.open\([\'"]([^"\']+)[\'"]',
    ]
    
    for pattern in ajax_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            print(f"Pattern '{pattern[:40]}...' gefunden:")
            for match in matches[:3]:
                print(f"  {match[:200] if isinstance(match, str) else match}")
    
    # Suche nach der konkreten Export-URL im JavaScript
    print("\n--- Suche nach konkreten Export-URLs ---")
    url_patterns = [
        r"['\"]([^'\"]*\.csp\?[^'\"]*[Ee]xport[^'\"]*)['\"]",
        r"['\"]([^'\"]*[Ee]xport[^'\"]*\.csp[^'\"]*)['\"]",
        r"['\"]([^'\"]*[Dd]ownload[^'\"]*\.csp[^'\"]*)['\"]",
        r"['\"]([^'\"]*dateiexport[^'\"]*)['\"]",
        r"url\s*:\s*['\"]([^'\"]+)['\"]",
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            print(f"Pattern gefunden:")
            for match in set(matches[:5]):
                print(f"  {match}")


if __name__ == "__main__":
    analyze_export()
