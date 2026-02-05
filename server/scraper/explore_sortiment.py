"""
Erkundet die Sortiment-Struktur auf der Schmidt-Webseite
"""
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
response = session.post(
    'https://onlineprohs.schmidt-mg.de/hs/login.csp',
    data={'KME': username, 'Kennwort': password, 'FlagAngemeldetBleiben': ''},
    allow_redirects=True, timeout=20
)
if 'agbok.csp' in response.url:
    session.post(response.url, data={'Aktion': 'Weiter', 'AGB': 'on'}, timeout=20)

print('Login erfolgreich!')
print()

# Sortiment-Seite laden
url = 'https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp'
response = session.get(url, timeout=20)
soup = BeautifulSoup(response.text, 'html.parser')

print('=== Sortiment-Seite Struktur ===')
print()

# Suche nach Sortiment-Links
for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    text = link.get_text(strip=True)
    if 'sortiment' in href.lower() or 'Produktgruppe' in href:
        print(f'  {text}: {href}')

print()
print('=== Sortiment-Kacheln/Buttons ===')
# Suche nach div/button Elementen die Sortimente darstellen
for elem in soup.find_all(['div', 'button', 'a'], class_=True):
    classes = ' '.join(elem.get('class', []))
    if 'sortiment' in classes.lower() or 'kategorie' in classes.lower() or 'gruppe' in classes.lower():
        text = elem.get_text(strip=True)[:50]
        print(f'  [{elem.name}] {classes}: {text}')

print()
print('=== Alle Links mit Produktgruppe ===')
for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    if 'Produktgruppe' in href:
        text = link.get_text(strip=True)
        print(f'  {text}: {href}')
