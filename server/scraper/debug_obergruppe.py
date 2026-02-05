"""Debug: Zeigt alle Links einer Obergruppen-Seite"""
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

# Badkeramik Obergruppe (hat "12 weitere...")
url = 'https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp?Produktgruppe1=S&Produktgruppe2=S0080'
response = session.get(url, timeout=20)
soup = BeautifulSoup(response.text, 'html.parser')

print('=== Alle Links auf der Badkeramik-Seite ===')
print()
for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    text = link.get_text(strip=True)
    if 'sortimenthsa.csp' in href and 'Produktgruppe3' in href:
        print(f'  {text}: {href}')

print()
print('=== Suche nach "weitere" Links ===')
for link in soup.find_all('a', href=True):
    text = link.get_text(strip=True)
    if 'weitere' in text.lower():
        print(f'  {text}: {link.get("href")}')
