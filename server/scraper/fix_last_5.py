"""Versuche die letzten 5 fehlenden Produktgruppen-Namen zu finden"""
import requests
import re
import json
from bs4 import BeautifulSoup

BASE_URL = 'https://onlineprohs.schmidt-mg.de/hs'

# Login
with open('../../keys', 'r') as f:
    content = f.read()
username = re.search(r'user_heinrich_schmidt=(.+)', content).group(1).strip()
password = re.search(r'passwort_heinrich_schmidt=(.+)', content).group(1).strip()

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})
session.get(f'{BASE_URL}/login.csp', timeout=20)
session.post(f'{BASE_URL}/login.csp',
    data={'KME': username, 'Kennwort': password, 'FlagAngemeldetBleiben': ''},
    allow_redirects=True, timeout=20)

missing = [
    {'sort': 'S', 'og': 'S0090', 'pg': 'S00900040'},
    {'sort': 'S', 'og': 'S0150', 'pg': 'S01500070'},
    {'sort': 'S', 'og': 'S0310', 'pg': 'S00310041'},
    {'sort': 'L', 'og': 'L0140', 'pg': 'L01400100'},
    {'sort': 'C', 'og': 'C_W01', 'pg': '(W01_EZ)'},
]

for m in missing:
    pg_code = m['pg']
    # URL-encode für Klammern
    pg_encoded = pg_code.replace('(', '%28').replace(')', '%29')
    
    print(f'\n=== {pg_code} ===')
    
    # Versuche Artikelsuche mit diesem Produktgruppe-Filter
    url = f'{BASE_URL}/artikelsuche.csp?Produktgruppe1={m["sort"]}&Produktgruppe2={m["og"]}&Produktgruppe3={pg_encoded}'
    print(f'URL: {url}')
    
    try:
        response = session.get(url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Suche nach H1, H2, Breadcrumbs
        for tag in ['h1', 'h2', 'h3']:
            elem = soup.find(tag)
            if elem:
                text = elem.get_text(strip=True)
                print(f'  {tag}: {text}')
        
        # Suche nach title
        title = soup.find('title')
        if title:
            print(f'  title: {title.get_text(strip=True)}')
        
        # Suche nach dem Produktgruppen-Code in Links
        for link in soup.find_all('a', href=re.compile(pg_encoded)):
            text = link.get_text(strip=True)
            if text and text != pg_code and 'weitere' not in text.lower():
                print(f'  Link mit Code: "{text}"')
                
        # Suche Anzahl gefundene Artikel
        results = soup.find(string=re.compile(r'Artikel gefunden'))
        if results:
            print(f'  Ergebnis: {results.strip()[:60]}')
            
    except Exception as e:
        print(f'  Fehler: {e}')
