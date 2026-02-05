"""
Holt ALLE Produktgruppen-Namen von der Artikelsuche-Seite OHNE Filter.
Der Produktgruppen-Filter zeigt ALLE Namen.
"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import parse_qs

REQUEST_TIMEOUT = 60
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


def main():
    print('=== Produktgruppen-Namen aus globalem Filter ===')
    print()
    
    session = login()
    print('Login erfolgreich!')
    print()
    
    # Artikelsuche ohne Filter - zeigt ALLE Produktgruppen
    print('Lade Artikelsuche (kann lange dauern)...')
    url = f'{BASE_URL}/artikelsuche.csp'
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(response.text, 'html.parser')
    print(f'Seite geladen ({len(response.text)} bytes)')
    print()
    
    # Sammle alle Produktgruppen-Namen aus sortimenthsa.csp Links
    pg_names = {}
    
    for link in soup.find_all('a', href=re.compile(r'sortimenthsa\.csp.*Produktgruppe3')):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if '?' in href and text and 'weitere' not in text.lower():
            params = parse_qs(href.split('?')[1])
            pg3 = params.get('Produktgruppe3', [''])[0]
            
            if pg3 and text:
                pg_names[pg3] = text
    
    print(f'Produktgruppen-Namen gefunden: {len(pg_names)}')
    
    # Zeige einige Beispiele
    print()
    print('=== Beispiele ===')
    for i, (code, name) in enumerate(list(pg_names.items())[:20]):
        print(f'  {code}: {name}')
    
    # Struktur laden und aktualisieren
    print()
    print('Aktualisiere Struktur...')
    
    with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
        struktur = json.load(f)
    
    fixed = 0
    for sortiment in struktur['sortimente'].values():
        for obergruppe in sortiment['obergruppen'].values():
            for pg_code, pg in obergruppe['produktgruppen'].items():
                if pg['name'] == pg_code and pg_code in pg_names:
                    pg['name'] = pg_names[pg_code]
                    fixed += 1
    
    # Statistik
    missing_after = sum(
        1 for s in struktur['sortimente'].values()
        for og in s['obergruppen'].values()
        for pg_code, pg in og['produktgruppen'].items()
        if pg['name'] == pg_code
    )
    
    print(f'Korrigiert: {fixed}')
    print(f'Noch ohne Namen: {missing_after}')
    
    # Speichern
    struktur['meta']['exported_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    
    with open('../system_katalog/_sortiment_struktur.json', 'w', encoding='utf-8') as f:
        json.dump(struktur, f, ensure_ascii=False, indent=2)
    
    print('Gespeichert!')


if __name__ == '__main__':
    main()
