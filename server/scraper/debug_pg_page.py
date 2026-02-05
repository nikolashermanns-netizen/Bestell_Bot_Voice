"""Debug: Produktgruppen-Seite untersuchen"""
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

# Unbekannte Produktgruppe: S00800040 (Badkeramik)
pg_code = 'S00800040'
url = f'https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp?Produktgruppe1=S&Produktgruppe2=S0080&Produktgruppe3={pg_code}'
response = session.get(url, timeout=20)
soup = BeautifulSoup(response.text, 'html.parser')

print(f'=== Produktgruppen-Seite: {pg_code} ===')
print()

# Suche nach allen Links mit dem pg_code
print('--- Links mit pg_code ---')
for link in soup.find_all('a', href=re.compile(f'Produktgruppe3={pg_code}')):
    text = link.get_text(strip=True)
    parent = link.parent.name if link.parent else ''
    print(f'  [{parent}] "{text}": {link.get("href")[:60]}...')

print()
print('--- Breadcrumb/Navigation ---')
# Suche nach Navigations-Elementen
for nav in soup.find_all(['nav', 'ol', 'ul'], class_=re.compile(r'bread|nav|crumb|path', re.I)):
    print(f'  {nav.name}: {nav.get_text(strip=True)[:100]}')

print()
print('--- Aktive Kategorie-Elemente ---')
for elem in soup.find_all(class_=re.compile(r'active|current|selected', re.I)):
    text = elem.get_text(strip=True)
    if text and len(text) < 80:
        print(f'  {text}')

print()
print('--- Alle Überschriften ---')
for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
    text = h.get_text(strip=True)
    if text and len(text) < 100:
        print(f'  {h.name}: {text}')
