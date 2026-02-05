"""Finde alle Produktgruppen-Links und ihre Attribute"""
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

print(f'=== Produktgruppen-Links in Obergruppe S0080 ===')
print()

# Finde ALLE Links die auf sortimenthsa.csp mit Produktgruppe3 zeigen
for link in soup.find_all('a', href=re.compile(r'Produktgruppe3=S0080')):
    href = link.get('href', '')
    text = link.get_text(strip=True)
    title = link.get('title', '')
    
    # Extrahiere Produktgruppe3
    pg3_match = re.search(r'Produktgruppe3=(\w+)', href)
    pg3 = pg3_match.group(1) if pg3_match else ''
    
    # Zeige alle Attribute
    attrs = dict(link.attrs)
    del attrs['href']  # href schon bekannt
    
    print(f'Code: {pg3}')
    print(f'  Text: "{text}"')
    print(f'  Title: "{title}"')
    print(f'  Attrs: {attrs}')
    print(f'  Parent: {link.parent.name if link.parent else ""}')
    print()
