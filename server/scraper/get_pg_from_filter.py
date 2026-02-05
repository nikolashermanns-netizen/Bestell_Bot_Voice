"""
Holt alle Produktgruppen-Namen aus dem Filter der Artikelsuche.
Die Filter-Sidebar zeigt alle Produktgruppen mit Namen UND Codes.
"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import parse_qs

REQUEST_TIMEOUT = 30
BASE_URL = "https://onlineprohs.schmidt-mg.de/hs"


def login() -> requests.Session:
    with open('../../keys', 'r') as f:
        content = f.read()
    username = re.search(r'user_heinrich_schmidt=(.+)', content).group(1).strip()
    password = re.search(r'passwort_heinrich_schmidt=(.+)', content).group(1).strip()

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    session.get(f'{BASE_URL}/login.csp', timeout=REQUEST_TIMEOUT)
    
    response = session.post(
        f'{BASE_URL}/login.csp',
        data={'KME': username, 'Kennwort': password, 'FlagAngemeldetBleiben': ''},
        allow_redirects=True, timeout=REQUEST_TIMEOUT
    )
    
    if 'agbok.csp' in response.url:
        session.post(response.url, data={'Aktion': 'Weiter', 'AGB': 'on'}, timeout=REQUEST_TIMEOUT)
    
    return session


def get_produktgruppen_from_filter(session: requests.Session, sort_code: str, og_code: str) -> dict:
    """
    Holt alle Produktgruppen einer Obergruppe aus dem Artikelsuche-Filter.
    """
    url = f'{BASE_URL}/artikelsuche.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}'
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    produktgruppen = {}
    
    # Suche nach Links mit Produktgruppe3 im href
    for link in soup.find_all('a', href=re.compile(r'Produktgruppe3=')):
        href = link.get('href', '')
        
        # Code aus URL extrahieren
        if '?' in href:
            params = parse_qs(href.split('?')[1])
            pg3 = params.get('Produktgruppe3', [''])[0]
            
            if pg3:
                # Name aus Link-Text - Format ist "1.234Name" oder "12Name"
                text = link.get_text(strip=True)
                # Entferne führende Zahlen und Punkte
                name_match = re.match(r'^[\d.]+(.+)$', text)
                if name_match:
                    name = name_match.group(1).strip()
                    if name and name != pg3:
                        produktgruppen[pg3] = name
    
    return produktgruppen


def main():
    print('=== Produktgruppen-Namen aus Filter holen ===')
    print()
    
    # Struktur laden
    with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
        struktur = json.load(f)
    
    session = login()
    print('Login erfolgreich!')
    print()
    
    # Zähle wie viele Namen fehlen
    missing_before = 0
    total_pg = 0
    for sortiment in struktur['sortimente'].values():
        for obergruppe in sortiment['obergruppen'].values():
            for pg_code, pg in obergruppe['produktgruppen'].items():
                total_pg += 1
                if pg['name'] == pg_code:
                    missing_before += 1
    
    print(f'Produktgruppen gesamt: {total_pg}')
    print(f'Ohne Namen (vor): {missing_before}')
    print()
    
    # Für jede Obergruppe die Filter-Namen holen
    fixed = 0
    for sort_code, sortiment in struktur['sortimente'].items():
        sort_name = sortiment['name']
        print(f'[{sort_code}] {sort_name}')
        
        for og_code, obergruppe in sortiment['obergruppen'].items():
            og_name = obergruppe['name']
            
            # Filter-Namen holen
            filter_names = get_produktgruppen_from_filter(session, sort_code, og_code)
            
            # Namen aktualisieren
            for pg_code, pg in obergruppe['produktgruppen'].items():
                if pg['name'] == pg_code and pg_code in filter_names:
                    pg['name'] = filter_names[pg_code]
                    fixed += 1
            
            # Fortschritt
            total_in_og = len(obergruppe['produktgruppen'])
            named = sum(1 for p in obergruppe['produktgruppen'].values() if p['name'] != p['code'])
            print(f'      {og_name}: {named}/{total_in_og}')
            
            time.sleep(0.15)
    
    # Statistik danach
    missing_after = 0
    for sortiment in struktur['sortimente'].values():
        for obergruppe in sortiment['obergruppen'].values():
            for pg_code, pg in obergruppe['produktgruppen'].items():
                if pg['name'] == pg_code:
                    missing_after += 1
    
    print()
    print(f'=== Ergebnis ===')
    print(f'Korrigiert: {fixed}')
    print(f'Ohne Namen (vorher): {missing_before}')
    print(f'Ohne Namen (nachher): {missing_after}')
    
    # Speichern
    struktur['meta']['exported_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    struktur['meta']['namen_aus_filter'] = True
    
    with open('../system_katalog/_sortiment_struktur.json', 'w', encoding='utf-8') as f:
        json.dump(struktur, f, ensure_ascii=False, indent=2)
    
    print('Gespeichert!')


if __name__ == '__main__':
    main()
