"""
Exportiert die komplette Sortiment-Struktur von der Schmidt-Webseite.
Parst alle Links von der Sortiment-Hauptseite.
"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import parse_qs
from collections import defaultdict

REQUEST_TIMEOUT = 30
BASE_URL = "https://onlineprohs.schmidt-mg.de/hs"

# Sortimente mit ihren Codes
SORTIMENTE = {
    "S": "Sanitär",
    "H": "Heizung",
    "I": "Installation",
    "L": "Klima/Lüftung",
    "E": "Elektro",
    "C": "Werkzeug",
    "P": "Photovoltaik",
    "G": "Hausgeräte",
    "M": "Befestigungstechnik",
}


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


def parse_sortiment_links(html: str) -> dict:
    """Parst alle Sortiment-Links und baut die Struktur auf"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Struktur: sortiment -> obergruppe -> produktgruppe
    struktur = defaultdict(lambda: {'obergruppen': defaultdict(lambda: {'produktgruppen': {}})})
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if 'sortimenthsa.csp' not in href or not text or 'weitere' in text.lower():
            continue
        
        if '?' not in href:
            continue
            
        params = parse_qs(href.split('?')[1])
        
        pg1 = params.get('Produktgruppe1', [''])[0]
        pg2 = params.get('Produktgruppe2', [''])[0]
        pg3 = params.get('Produktgruppe3', [''])[0]
        
        if pg1 and not pg2:
            # Sortiment selbst - ignorieren, haben wir schon
            pass
        elif pg1 and pg2 and not pg3:
            # Obergruppe
            if pg2 not in struktur[pg1]['obergruppen']:
                struktur[pg1]['obergruppen'][pg2] = {
                    'code': pg2,
                    'name': text,
                    'produktgruppen': {}
                }
        elif pg1 and pg2 and pg3:
            # Produktgruppe
            if pg2 in struktur[pg1]['obergruppen']:
                struktur[pg1]['obergruppen'][pg2]['produktgruppen'][pg3] = {
                    'code': pg3,
                    'name': text,
                }
            else:
                # Obergruppe noch nicht bekannt - erstellen
                struktur[pg1]['obergruppen'][pg2] = {
                    'code': pg2,
                    'name': 'Unbekannt',
                    'produktgruppen': {
                        pg3: {'code': pg3, 'name': text}
                    }
                }
    
    return struktur


def main():
    print('=== Schmidt Sortiment-Struktur Export ===')
    print()
    
    session = login()
    print('Login erfolgreich!')
    print()
    
    # Alle Sortimente durchgehen und deren Seiten laden
    all_links_html = ""
    
    for sort_code, sort_name in SORTIMENTE.items():
        print(f'Lade [{sort_code}] {sort_name}...', end=' ', flush=True)
        
        try:
            # Sortiment-Seite laden
            url = f'{BASE_URL}/sortimenthsa.csp?Produktgruppe1={sort_code}'
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            all_links_html += response.text
            print('OK')
            time.sleep(0.2)
        except Exception as e:
            print(f'Fehler: {e}')
    
    print()
    print('Parse Struktur...')
    
    # Alle Links parsen
    raw_struktur = parse_sortiment_links(all_links_html)
    
    # In finale Struktur umwandeln
    struktur = {
        'meta': {
            'source': 'Heinrich Schmidt OnlinePro',
            'url': 'https://onlineprohs.schmidt-mg.de',
            'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        },
        'sortimente': {}
    }
    
    total_obergruppen = 0
    total_produktgruppen = 0
    
    for sort_code, sort_name in SORTIMENTE.items():
        sortiment_data = {
            'code': sort_code,
            'name': sort_name,
            'obergruppen': {}
        }
        
        if sort_code in raw_struktur:
            for og_code, og_data in raw_struktur[sort_code]['obergruppen'].items():
                sortiment_data['obergruppen'][og_code] = {
                    'code': og_data['code'],
                    'name': og_data['name'],
                    'produktgruppen': og_data['produktgruppen']
                }
                total_obergruppen += 1
                total_produktgruppen += len(og_data['produktgruppen'])
        
        struktur['sortimente'][sort_code] = sortiment_data
        print(f'  [{sort_code}] {sort_name}: {len(sortiment_data["obergruppen"])} Obergruppen')
    
    # Statistiken
    struktur['meta']['statistics'] = {
        'sortimente': len(SORTIMENTE),
        'obergruppen': total_obergruppen,
        'produktgruppen': total_produktgruppen,
    }
    
    # Speichern
    output_path = '../system_katalog/_sortiment_struktur.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(struktur, f, ensure_ascii=False, indent=2)
    
    print()
    print('=== Ergebnis ===')
    print(f'Sortimente: {len(SORTIMENTE)}')
    print(f'Obergruppen: {total_obergruppen}')
    print(f'Produktgruppen: {total_produktgruppen}')
    print(f'Gespeichert: {output_path}')


if __name__ == '__main__':
    main()
