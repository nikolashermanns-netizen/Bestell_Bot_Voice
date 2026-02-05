"""Analysiere die Obergruppen-Seite um alle Produktgruppen-Namen zu extrahieren"""
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

# Badkeramik Obergruppe - DIREKT aufrufen (wie bei Klick auf "weitere...")
url = 'https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp?Produktgruppe1=S&Produktgruppe2=S0080'
print(f'Rufe auf: {url}')
response = session.get(url, timeout=30)
soup = BeautifulSoup(response.text, 'html.parser')

# Suche nach li Elementen mit class text-full (das sind die Kategorien)
print()
print('=== Alle li.text-full Elemente ===')
for li in soup.find_all('li', class_='text-full'):
    # Suche den Link mit text-dark text-mm (das ist der Produktgruppenname-Link)
    link = li.find('a', class_='text-dark')
    if link:
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        # Nur Produktgruppen3-Links
        if 'Produktgruppe3=' in href:
            pg3_match = re.search(r'Produktgruppe3=(\w+)', href)
            pg3 = pg3_match.group(1) if pg3_match else ''
            print(f'{pg3}: {text}')

print()
print('=== Analyse der HTML-Struktur für eine Produktgruppe ===')
# Zeige die komplette HTML-Struktur eines li.text-full Elements
for li in soup.find_all('li', class_='text-full')[:3]:
    print(li.prettify()[:500])
    print('---')
