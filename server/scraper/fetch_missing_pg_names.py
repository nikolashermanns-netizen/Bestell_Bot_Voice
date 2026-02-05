"""
Ruft jede fehlende Produktgruppen-Seite auf und holt den Namen.
"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup

REQUEST_TIMEOUT = 20
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


def get_pg_name_from_page(session: requests.Session, sort_code: str, og_code: str, pg_code: str) -> str:
    """
    Ruft die Produktgruppen-Seite auf und extrahiert den Namen.
    """
    url = f'{BASE_URL}/sortimenthsa.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}&Produktgruppe3={pg_code}'
    
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Suche nach aktiven/selected Links mit dem pg_code
        for link in soup.find_all('a', href=re.compile(f'Produktgruppe3={pg_code}')):
            text = link.get_text(strip=True)
            if text and text != pg_code and 'weitere' not in text.lower():
                # Entferne führende Zahlen (Produktanzahl)
                name_match = re.match(r'^[\d.]+\s*(.+)$', text)
                if name_match:
                    return name_match.group(1).strip()
                return text
        
        # Alternative: Suche nach h4/h3 mit "Produktgruppe"
        for h in soup.find_all(['h3', 'h4']):
            text = h.get_text(strip=True)
            if pg_code in text or (len(text) > 3 and len(text) < 80):
                # Könnte der Name sein
                pass
                
    except Exception as e:
        print(f'      Fehler bei {pg_code}: {e}')
    
    return None


def main():
    print('=== Fehlende Produktgruppen-Namen holen ===')
    print()
    
    # Struktur laden
    with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
        struktur = json.load(f)
    
    # Sammle alle fehlenden Produktgruppen
    missing = []
    for sort_code, sortiment in struktur['sortimente'].items():
        for og_code, obergruppe in sortiment['obergruppen'].items():
            for pg_code, pg in obergruppe['produktgruppen'].items():
                if pg['name'] == pg_code:
                    missing.append({
                        'sort_code': sort_code,
                        'og_code': og_code,
                        'pg_code': pg_code,
                        'pg': pg,
                    })
    
    print(f'Fehlende Namen: {len(missing)}')
    print()
    
    session = login()
    print('Login erfolgreich!')
    print()
    
    fixed = 0
    for i, item in enumerate(missing):
        pg_code = item['pg_code']
        sort_code = item['sort_code']
        og_code = item['og_code']
        
        name = get_pg_name_from_page(session, sort_code, og_code, pg_code)
        
        if name:
            item['pg']['name'] = name
            fixed += 1
            print(f'[{i+1}/{len(missing)}] {pg_code} -> {name}')
        else:
            print(f'[{i+1}/{len(missing)}] {pg_code} -> (nicht gefunden)')
        
        # Rate limiting
        time.sleep(0.2)
        
        # Zwischenspeichern alle 50 Requests
        if (i + 1) % 50 == 0:
            with open('../system_katalog/_sortiment_struktur.json', 'w', encoding='utf-8') as f:
                json.dump(struktur, f, ensure_ascii=False, indent=2)
            print(f'  ... Zwischengespeichert ({fixed} korrigiert)')
    
    # Final speichern
    struktur['meta']['exported_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    
    with open('../system_katalog/_sortiment_struktur.json', 'w', encoding='utf-8') as f:
        json.dump(struktur, f, ensure_ascii=False, indent=2)
    
    print()
    print('=== Ergebnis ===')
    print(f'Korrigiert: {fixed}/{len(missing)}')


if __name__ == '__main__':
    main()
