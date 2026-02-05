"""
Erstellt ein Mapping von Produktgruppen zu Produkten.
Für jede Produktgruppe wird eine Suche durchgeführt und die gefundenen
Artikelnummern werden der Kategorie zugeordnet.

Speichert das Ergebnis in system_katalog/_kategorie_mapping.json
"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urlencode

REQUEST_TIMEOUT = 30
BASE_URL = "https://onlineprohs.schmidt-mg.de/hs"


def login() -> requests.Session:
    """Login und Session zurückgeben"""
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


def get_product_count(session: requests.Session, pg1: str, pg2: str, pg3: str) -> int:
    """Holt die Produktanzahl für eine Produktgruppe"""
    params = {
        'Produktgruppe1': pg1,
        'Produktgruppe2': pg2,
        'Produktgruppe3': pg3,
    }
    url = f'{BASE_URL}/artikelsuche.csp?' + urlencode(params)
    
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        # Suche nach "X Treffer"
        match = re.search(r'(\d+(?:\.\d+)?)\s*Treffer', response.text)
        if match:
            return int(match.group(1).replace('.', ''))
    except Exception as e:
        print(f'      Fehler: {e}')
    
    return 0


def main():
    print('=== Kategorie-Mapping erstellen ===')
    print()
    
    # Struktur laden
    with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
        struktur = json.load(f)
    
    session = login()
    print('Login erfolgreich!')
    print()
    
    # Mapping erstellen: Für jede Produktgruppe die Produktanzahl holen
    mapping = {
        'meta': {
            'source': 'Heinrich Schmidt OnlinePro',
            'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'description': 'Mapping von Produktgruppen zu Produktanzahl',
        },
        'kategorien': {}
    }
    
    total_produkte = 0
    
    for sort_code, sortiment in struktur['sortimente'].items():
        sort_name = sortiment['name']
        print(f'[{sort_code}] {sort_name}')
        
        for og_code, obergruppe in sortiment['obergruppen'].items():
            og_name = obergruppe['name']
            
            for pg_code, produktgruppe in obergruppe['produktgruppen'].items():
                pg_name = produktgruppe['name']
                
                # Produktanzahl holen
                count = get_product_count(session, sort_code, og_code, pg_code)
                
                # Kategorie-Pfad erstellen
                kategorie_pfad = f"{sort_name} > {og_name} > {pg_name}"
                
                mapping['kategorien'][pg_code] = {
                    'code': pg_code,
                    'name': pg_name,
                    'pfad': kategorie_pfad,
                    'sortiment': {'code': sort_code, 'name': sort_name},
                    'obergruppe': {'code': og_code, 'name': og_name},
                    'produktanzahl': count,
                    'suche_url': f"{BASE_URL}/artikelsuche.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}&Produktgruppe3={pg_code}"
                }
                
                total_produkte += count
                print(f'      {pg_name}: {count} Produkte')
                
                time.sleep(0.15)  # Rate limiting
    
    # Statistiken
    mapping['meta']['statistics'] = {
        'kategorien': len(mapping['kategorien']),
        'total_produkte': total_produkte,
    }
    
    # Speichern
    output_path = '../system_katalog/_kategorie_mapping.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    print()
    print('=== Ergebnis ===')
    print(f'Kategorien: {len(mapping["kategorien"])}')
    print(f'Gesamtprodukte: {total_produkte:,}')
    print(f'Gespeichert: {output_path}')


if __name__ == '__main__':
    main()
