"""
Holt ALLE Produktgruppen-Namen von der Artikelsuche-Seite.
Die sortimenthsa.csp Links enthalten die Namen.
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


def get_all_pg_names(session: requests.Session, sort_code: str, og_code: str) -> dict:
    """
    Holt alle Produktgruppen-Namen von der Artikelsuche-Seite.
    """
    # Artikelsuche mit Obergruppen-Filter
    url = f'{BASE_URL}/artikelsuche.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}'
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    pg_names = {}
    
    # Suche nach sortimenthsa.csp Links mit Produktgruppe3
    for link in soup.find_all('a', href=re.compile(r'sortimenthsa\.csp.*Produktgruppe3')):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if '?' in href and text:
            params = parse_qs(href.split('?')[1])
            pg1 = params.get('Produktgruppe1', [''])[0]
            pg2 = params.get('Produktgruppe2', [''])[0]
            pg3 = params.get('Produktgruppe3', [''])[0]
            
            # Nur Links zur aktuellen Obergruppe
            if pg1 == sort_code and pg2 == og_code and pg3:
                # Namen extrahieren (kann "weitere" enthalten)
                if 'weitere' not in text.lower():
                    pg_names[pg3] = text
    
    return pg_names


def main():
    print('=== ALLE Produktgruppen-Namen holen ===')
    print()
    
    # Struktur laden
    with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
        struktur = json.load(f)
    
    session = login()
    print('Login erfolgreich!')
    print()
    
    # Zähle Produktgruppen ohne Namen
    missing_before = sum(
        1 for s in struktur['sortimente'].values()
        for og in s['obergruppen'].values()
        for pg_code, pg in og['produktgruppen'].items()
        if pg['name'] == pg_code
    )
    print(f'Ohne Namen (vorher): {missing_before}')
    print()
    
    fixed = 0
    
    for sort_code, sortiment in struktur['sortimente'].items():
        sort_name = sortiment['name']
        print(f'[{sort_code}] {sort_name}')
        
        for og_code, obergruppe in sortiment['obergruppen'].items():
            og_name = obergruppe['name']
            
            # Namen von Artikelsuche holen
            pg_names = get_all_pg_names(session, sort_code, og_code)
            
            # Namen aktualisieren
            for pg_code, pg in obergruppe['produktgruppen'].items():
                if pg['name'] == pg_code and pg_code in pg_names:
                    pg['name'] = pg_names[pg_code]
                    fixed += 1
            
            named = sum(1 for p in obergruppe['produktgruppen'].values() if p['name'] != p['code'])
            total = len(obergruppe['produktgruppen'])
            print(f'      {og_name}: {named}/{total}')
            
            time.sleep(0.15)
    
    # Statistik danach
    missing_after = sum(
        1 for s in struktur['sortimente'].values()
        for og in s['obergruppen'].values()
        for pg_code, pg in og['produktgruppen'].items()
        if pg['name'] == pg_code
    )
    
    print()
    print('=== Ergebnis ===')
    print(f'Korrigiert: {fixed}')
    print(f'Ohne Namen (vorher): {missing_before}')
    print(f'Ohne Namen (nachher): {missing_after}')
    
    # Speichern
    struktur['meta']['exported_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    struktur['meta']['alle_namen_geholt'] = True
    
    with open('../system_katalog/_sortiment_struktur.json', 'w', encoding='utf-8') as f:
        json.dump(struktur, f, ensure_ascii=False, indent=2)
    
    print('Gespeichert!')


if __name__ == '__main__':
    main()
