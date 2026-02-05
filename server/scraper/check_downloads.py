import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import quote

# Login
with open('../../keys', 'r') as f:
    content = f.read()
username = re.search(r'user_heinrich_schmidt=(.+)', content).group(1).strip()
password = re.search(r'passwort_heinrich_schmidt=(.+)', content).group(1).strip()

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})
session.get('https://onlineprohs.schmidt-mg.de/hs/login.csp')
session.post('https://onlineprohs.schmidt-mg.de/hs/login.csp',
    data={'KME': username, 'Kennwort': password, 'FlagAngemeldetBleiben': ''},
    allow_redirects=True)

# Produkt SP+RED5435
article = 'SP+RED5435'
encoded = quote(article, safe='')
url = f'https://onlineprohs.schmidt-mg.de/hs/artikelauskunft.csp?Artikel={encoded}&Suchstring={encoded}'
response = session.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

print(f'=== Alle Download-Links fuer {article} ===')
print()
for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    if 'Online3.Download.cls' in href:
        text = link.get_text(strip=True)
        # Extension pruefen
        ext = ''
        if 'Extension=' in href:
            ext = href.split('Extension=')[-1][:5]
        is_image = ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        marker = '[BILD]' if is_image else '[PDF?]'
        print(f'  {marker} "{text}": {href[:70]}...')
