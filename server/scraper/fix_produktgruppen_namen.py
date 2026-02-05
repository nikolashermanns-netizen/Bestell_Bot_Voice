"""
Holt die echten Namen für alle Produktgruppen die nur Codes haben.
Besucht dafür jede Obergruppen-Seite.
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


def get_produktgruppen_namen(session: requests.Session, sort_code: str, og_code: str) -> dict:
    """Holt alle Produktgruppen-Namen von einer Obergruppen-Detail-Seite"""
    url = f'{BASE_URL}/sortimenthsa.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}'
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    namen = {}
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if 'sortimenthsa.csp' not in href or not text:
            continue
        if 'weitere' in text.lower():
            continue
        if '?' not in href:
            continue
            
        params = parse_qs(href.split('?')[1])
        pg3 = params.get('Produktgruppe3', [''])[0]
        
        if pg3 and text:
            namen[pg3] = text
    
    return namen


def main():
    print('=== Produktgruppen-Namen korrigieren ===')
    print()
    
    # Struktur laden
    with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
        struktur = json.load(f)
    
    session = login()
    print('Login erfolgreich!')
    print()
    
    # Zähle Produktgruppen mit nur Code als Name
    codes_only = 0
    total_pg = 0
    for sortiment in struktur['sortimente'].values():
        for obergruppe in sortiment['obergruppen'].values():
            for pg_code, pg in obergruppe['produktgruppen'].items():
                total_pg += 1
                if pg['name'] == pg_code:
                    codes_only += 1
    
    print(f'Produktgruppen gesamt: {total_pg}')
    print(f'Davon nur Code als Name: {codes_only}')
    print()
    
    # Für jede Obergruppe die Detail-Seite laden
    fixed = 0
    for sort_code, sortiment in struktur['sortimente'].items():
        sort_name = sortiment['name']
        print(f'[{sort_code}] {sort_name}')
        
        for og_code, obergruppe in sortiment['obergruppen'].items():
            og_name = obergruppe['name']
            
            # Namen von der Detail-Seite holen
            namen = get_produktgruppen_namen(session, sort_code, og_code)
            
            # Namen aktualisieren
            for pg_code in obergruppe['produktgruppen'].keys():
                if pg_code in namen and namen[pg_code] != pg_code:
                    old_name = obergruppe['produktgruppen'][pg_code]['name']
                    if old_name == pg_code:
                        obergruppe['produktgruppen'][pg_code]['name'] = namen[pg_code]
                        fixed += 1
            
            pg_count = len(obergruppe['produktgruppen'])
            named = sum(1 for pg in obergruppe['produktgruppen'].values() if pg['name'] != pg['code'])
            print(f'      {og_name}: {named}/{pg_count} mit Namen')
            
            time.sleep(0.1)
    
    print()
    print(f'Korrigiert: {fixed} Namen')
    
    # Speichern
    struktur['meta']['exported_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    struktur['meta']['namen_korrigiert'] = True
    
    with open('../system_katalog/_sortiment_struktur.json', 'w', encoding='utf-8') as f:
        json.dump(struktur, f, ensure_ascii=False, indent=2)
    
    print('Gespeichert!')


if __name__ == '__main__':
    main()
