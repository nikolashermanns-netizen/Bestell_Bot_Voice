"""Suche nach Produktgruppen-Daten im JavaScript"""
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

# Sortiment-Seite mit einer Obergruppe
url = 'https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp?Produktgruppe1=S&Produktgruppe2=S0080'
response = session.get(url, timeout=30)

print(f'=== Suche nach Produktgruppen-Daten ===')
print(f'Seite: {len(response.text)} bytes')
print()

# Suche nach JSON-artigen Strukturen
print('--- JSON-ähnliche Strukturen ---')
json_patterns = re.findall(r'\{[^{}]*"S0080[^{}]*\}', response.text)
for j in json_patterns[:5]:
    print(f'  {j[:150]}...')

# Suche nach Arrays mit Produktgruppen-Codes
print()
print('--- Arrays mit S00800 Codes ---')
array_patterns = re.findall(r'\[[^\[\]]*S00800[^\[\]]*\]', response.text)
for a in array_patterns[:5]:
    print(f'  {a[:150]}...')

# Suche nach data-* Attributen
print()
print('--- data-* Attribute mit Produktgruppen ---')
soup = BeautifulSoup(response.text, 'html.parser')
for elem in soup.find_all(attrs={'data-gruppe': True}):
    print(f'  {elem.get("data-gruppe")}: {elem.get_text(strip=True)[:50]}')

for elem in soup.find_all(attrs={'data-code': True}):
    code = elem.get('data-code')
    if 'S008' in str(code):
        print(f'  {code}: {elem.get_text(strip=True)[:50]}')

# Suche nach versteckten Inputs
print()
print('--- Versteckte Inputs ---')
for inp in soup.find_all('input', type='hidden'):
    name = inp.get('name', '')
    val = inp.get('value', '')
    if 'S0080' in name or 'S0080' in val:
        print(f'  {name}: {val[:80]}')
