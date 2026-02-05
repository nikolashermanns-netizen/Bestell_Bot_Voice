"""
Exportiert die komplette Sortiment-Struktur von der Schmidt-Webseite.
Lädt ALLE Produktgruppen durch Parsen der vollständigen Link-Liste.
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


def get_all_groups_from_page(session: requests.Session, sort_code: str) -> dict:
    """
    Holt alle Obergruppen und Produktgruppen von einer Sortiment-Seite.
    Parst sowohl die sichtbaren Links als auch die versteckten Links am Ende.
    """
    url = f'{BASE_URL}/sortimenthsa.csp?Produktgruppe1={sort_code}'
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Sammle alle Produktgruppen-Links (mit und ohne Text)
    obergruppen = {}  # og_code -> {name, produktgruppen: {pg_code -> name}}
    pg_names = {}     # pg_code -> name (für Links mit Text)
    pg_to_og = {}     # pg_code -> og_code (Zuordnung)
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if 'sortimenthsa.csp' not in href:
            continue
        if 'weitere' in text.lower():
            continue
        if '?' not in href:
            continue
            
        params = parse_qs(href.split('?')[1])
        pg1 = params.get('Produktgruppe1', [''])[0]
        pg2 = params.get('Produktgruppe2', [''])[0]
        pg3 = params.get('Produktgruppe3', [''])[0]
        
        if pg1 != sort_code:
            continue
        
        # Obergruppe (pg1 + pg2, kein pg3)
        if pg2 and not pg3:
            if pg2 not in obergruppen and text:
                obergruppen[pg2] = {'name': text, 'produktgruppen': {}}
        
        # Produktgruppe (pg1 + pg2 + pg3)
        elif pg2 and pg3:
            # Zuordnung speichern
            pg_to_og[pg3] = pg2
            
            # Name speichern wenn vorhanden
            if text:
                pg_names[pg3] = text
            
            # Obergruppe erstellen falls noch nicht vorhanden
            if pg2 not in obergruppen:
                obergruppen[pg2] = {'name': 'Unbekannt', 'produktgruppen': {}}
    
    # Jetzt alle Produktgruppen zu ihren Obergruppen zuordnen
    for pg_code, og_code in pg_to_og.items():
        if og_code in obergruppen:
            name = pg_names.get(pg_code, pg_code)  # Fallback auf Code wenn kein Name
            obergruppen[og_code]['produktgruppen'][pg_code] = name
    
    return obergruppen


def get_produktgruppen_details(session: requests.Session, sort_code: str, og_code: str) -> dict:
    """
    Holt alle Produktgruppen einer Obergruppe mit ihren Namen.
    """
    url = f'{BASE_URL}/sortimenthsa.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}'
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    produktgruppen = {}
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if 'sortimenthsa.csp' not in href:
            continue
        if 'weitere' in text.lower():
            continue
        if '?' not in href:
            continue
            
        params = parse_qs(href.split('?')[1])
        pg1 = params.get('Produktgruppe1', [''])[0]
        pg2 = params.get('Produktgruppe2', [''])[0]
        pg3 = params.get('Produktgruppe3', [''])[0]
        
        # Nur Produktgruppen dieser Obergruppe
        if pg1 == sort_code and pg2 == og_code and pg3:
            if pg3 not in produktgruppen:
                produktgruppen[pg3] = text if text else pg3
    
    return produktgruppen


def main():
    print('=== Schmidt Sortiment-Struktur Export (Vollständig) ===')
    print()
    
    session = login()
    print('Login erfolgreich!')
    print()
    
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
        print(f'[{sort_code}] {sort_name}')
        
        # Erste Übersicht laden
        obergruppen = get_all_groups_from_page(session, sort_code)
        print(f'    {len(obergruppen)} Obergruppen gefunden')
        
        sortiment_data = {
            'code': sort_code,
            'name': sort_name,
            'obergruppen': {}
        }
        
        # Für jede Obergruppe die Detail-Seite laden um alle Produktgruppen-Namen zu bekommen
        for og_code, og_data in obergruppen.items():
            og_name = og_data['name']
            
            # Detail-Seite laden für vollständige Produktgruppen-Liste
            pg_details = get_produktgruppen_details(session, sort_code, og_code)
            
            # Merge mit bereits gefundenen
            for pg_code, pg_name in og_data['produktgruppen'].items():
                if pg_code not in pg_details:
                    pg_details[pg_code] = pg_name
            
            pg_dict = {}
            for pg_code, pg_name in pg_details.items():
                pg_dict[pg_code] = {
                    'code': pg_code,
                    'name': pg_name
                }
            
            sortiment_data['obergruppen'][og_code] = {
                'code': og_code,
                'name': og_name,
                'produktgruppen': pg_dict
            }
            
            total_produktgruppen += len(pg_dict)
            print(f'      - {og_name}: {len(pg_dict)} Produktgruppen')
            
            time.sleep(0.1)
        
        total_obergruppen += len(obergruppen)
        struktur['sortimente'][sort_code] = sortiment_data
    
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
