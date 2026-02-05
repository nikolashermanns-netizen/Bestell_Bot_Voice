"""Test: Produktgruppen-Name direkt von der Seite holen"""
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

# Test mit einer unbekannten Produktgruppe (Code = S00800040)
url = 'https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp?Produktgruppe1=S&Produktgruppe2=S0080&Produktgruppe3=S00800040'
response = session.get(url, timeout=20)
soup = BeautifulSoup(response.text, 'html.parser')

print('=== Produktgruppen-Seite: S00800040 (Badkeramik) ===')
print()

# Suche nach Elementen die den Code enthalten
print('--- Elemente mit S00800040 ---')
for elem in soup.find_all(string=re.compile('S00800040')):
    parent = elem.parent
    if parent:
        print(f'  {parent.name}: {parent.get_text(strip=True)[:100]}')

# Suche nach Links mit dem aktuellen Produktgruppe3-Wert
print()
print('--- Links mit Produktgruppe3=S00800040 ---')
for link in soup.find_all('a', href=re.compile('Produktgruppe3=S00800040')):
    text = link.get_text(strip=True)
    print(f'  {text}: {link.get("href")[:80]}')

# Alternative: Artikelsuche-Seite statt Sortiment-Seite
print()
print('=== Versuche Artikelsuche-Seite ===')
url2 = 'https://onlineprohs.schmidt-mg.de/hs/artikelsuche.csp?Produktgruppe1=S&Produktgruppe2=S0080&Produktgruppe3=S00800040'
response2 = session.get(url2, timeout=20)
soup2 = BeautifulSoup(response2.text, 'html.parser')

# Suche nach dem Gruppen-Namen in der Artikelsuche
print('--- Überschriften auf Artikelsuche ---')
for h in soup2.find_all(['h1', 'h2', 'h3', 'h4']):
    text = h.get_text(strip=True)
    if text:
        print(f'  {h.name}: {text[:80]}')

# Suche nach Breadcrumb/Filter-Anzeige
print()
print('--- Filter/Breadcrumb Bereich ---')
for elem in soup2.find_all(class_=re.compile(r'filter|bread|crumb|path|kategorie', re.I)):
    text = elem.get_text(strip=True)
    if text and len(text) < 200:
        print(f'  {text[:150]}')
