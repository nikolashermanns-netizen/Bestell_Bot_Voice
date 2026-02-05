"""Debug: Filter-Links untersuchen"""
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
url = 'https://onlineprohs.schmidt-mg.de/hs/artikelsuche.csp?Produktgruppe1=S&Produktgruppe2=S0080'
response = session.get(url, timeout=20)
soup = BeautifulSoup(response.text, 'html.parser')

print('=== Filter-Links für Badkeramik (S0080) ===')
print()

# Suche nach "Produktgruppe" im Filter-Bereich
print('--- Links mit "Produktgruppe" im href ---')
count = 0
for link in soup.find_all('a', href=re.compile(r'Produktgruppe', re.I)):
    href = link.get('href', '')
    text = link.get_text(strip=True)[:50]
    if 'Produktgruppe3' in href:
        count += 1
        if count <= 20:
            print(f'  {text}: {href[:80]}')
print(f'  ... {count} Links gefunden')

print()
print('--- Checkboxen/Inputs für Filter ---')
for inp in soup.find_all('input', attrs={'name': re.compile(r'Produktgruppe', re.I)}):
    print(f'  {inp.get("name")}: {inp.get("value")} - {inp.get("type")}')

print()
print('--- JavaScript mit Produktgruppen-Mapping ---')
# Suche nach JavaScript das die Produktgruppen-Namen enthält
scripts = soup.find_all('script')
for script in scripts:
    text = script.get_text()
    if 'S0080' in text or 'Produktgruppe' in text:
        # Zeige ersten 500 Zeichen
        print(f'  Script gefunden ({len(text)} chars):')
        print(f'  {text[:500]}...')
        break
