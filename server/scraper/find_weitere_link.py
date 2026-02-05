"""Finde den 'weitere' Link und dessen Mechanismus"""
import requests
import re
from bs4 import BeautifulSoup

# Login
with open('../../keys', 'r') as f:
    content = f.read()
username = re.search(r'user_heinrich_schmidt=(.+)', content).group(1).strip()
password = re.search(r'passwort_heinrich_schmidt=(.+)', content).group(1).strip()

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})
session.get('https://onlineprohs.schmidt-mg.de/hs/login.csp', timeout=20)
session.post('https://onlineprohs.schmidt-mg.de/hs/login.csp',
    data={'KME': username, 'Kennwort': password, 'FlagAngemeldetBleiben': ''},
    allow_redirects=True, timeout=20)

# Badkeramik Obergruppe
url = 'https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp?Produktgruppe1=S&Produktgruppe2=S0080'
response = session.get(url, timeout=30)
soup = BeautifulSoup(response.text, 'html.parser')

print('=== Suche nach "weitere" Elementen ===')
print()

# Finde alle Elemente mit "weitere" im Text
for elem in soup.find_all(string=re.compile(r'weitere', re.I)):
    parent = elem.parent
    if parent:
        print(f'--- Gefunden in {parent.name} ---')
        print(f'  Text: {elem.strip()[:80]}')
        print(f'  Parent attrs: {dict(parent.attrs)}')
        
        # Großeltern
        if parent.parent:
            print(f'  Großeltern: {parent.parent.name}')
            print(f'  Großeltern attrs: {dict(parent.parent.attrs)}')
        print()

# Suche nach JavaScript das die Produktgruppen lädt
print()
print('=== Suche nach AJAX/CSP-Aufrufen für Produktgruppen ===')
for script in soup.find_all('script'):
    text = script.get_text()
    if 'Produktgruppe' in text or 'cspHttpServer' in text:
        # Zeige relevante Zeilen
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'Produktgruppe' in line or 'weitere' in line.lower():
                print(f'  {line.strip()[:100]}')
