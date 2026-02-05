"""
Test: Nur auf Basis der schmidt_webseite.md Dokumentation arbeiten
Laedt ALLE Downloads (ausser Bilder) mit 20 Sekunden Timeout pro Request
"""
import time
import requests
import re
from bs4 import BeautifulSoup
import os
import json
import random
from urllib.parse import quote

# Timeout in Sekunden pro Request
REQUEST_TIMEOUT = 20

start_time = time.time()
print('=== Test: Dokumentation anwenden ===')
print()

# 1. Credentials laden (wie in Doku beschrieben)
with open('../../keys', 'r') as f:
    content = f.read()
username = re.search(r'user_heinrich_schmidt=(.+)', content).group(1).strip()
password = re.search(r'passwort_heinrich_schmidt=(.+)', content).group(1).strip()
print(f'[1] Credentials geladen: {username[:5]}...')

# 2. Session erstellen und Login (wie in Doku)
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
session.get('https://onlineprohs.schmidt-mg.de/hs/login.csp', timeout=REQUEST_TIMEOUT)

response = session.post(
    'https://onlineprohs.schmidt-mg.de/hs/login.csp',
    data={'KME': username, 'Kennwort': password, 'FlagAngemeldetBleiben': ''},
    allow_redirects=True,
    timeout=REQUEST_TIMEOUT
)

if 'agbok.csp' in response.url:
    session.post(response.url, data={'Aktion': 'Weiter', 'AGB': 'on'}, timeout=REQUEST_TIMEOUT)

login_time = time.time() - start_time
print(f'[2] Login erfolgreich ({login_time:.2f}s)')

# 3. Zufaelliges Produkt aus Viega-Katalog
with open('../system_katalog/viega.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
products = data['products'] if isinstance(data, dict) and 'products' in data else data

# Waehle zufaellig
product = random.choice(products)
article_nr = product.get('Artikel', product.get('artikel', ''))
print(f'[3] Zufaelliges Produkt: {article_nr}')

# 4. Produktseite aufrufen (wie in Doku: artikelauskunft.csp)
encoded_article = quote(article_nr, safe='')
url = f'https://onlineprohs.schmidt-mg.de/hs/artikelauskunft.csp?Artikel={encoded_article}&Suchstring={encoded_article}'
response = session.get(url, timeout=REQUEST_TIMEOUT)
soup = BeautifulSoup(response.text, 'html.parser')

# Produktname extrahieren
name_elem = soup.find('h2')
product_name = name_elem.get_text(strip=True) if name_elem else 'Unbekannt'
print(f'[4] Produktname: {product_name[:60]}...')

# 5. Downloads finden - ALLES ausser Bilder
downloads = []
image_keywords = ['farbbild', 'swbild', 'strichzeichnung', 'masszeichnung', 'zeichnung']
image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    if 'Online3.Download.cls' in href:
        text = link.get_text(strip=True)
        
        # Pruefe ob Bild-Extension in URL
        is_image_ext = any(ext in href.lower() for ext in image_extensions)
        
        # Pruefe ob Bild-Keyword im Text
        is_image_text = any(kw in text.lower() for kw in image_keywords)
        
        # Ueberspringe Bilder und leere Links
        if is_image_ext or is_image_text or not text:
            continue
            
        full_url = f'https://onlineprohs.schmidt-mg.de/hs/{href}' if not href.startswith('http') else href
        downloads.append({'name': text, 'url': full_url})

print(f'[5] {len(downloads)} Downloads gefunden (ohne Bilder)')

# 6. ALLE Downloads ausfuehren (mit Timeout)
safe_article = article_nr.replace("+", "_").replace("/", "_").replace("\\", "_")
output_dir = f'downloads/{safe_article}'
os.makedirs(output_dir, exist_ok=True)

downloaded = []
failed = []
for i, dl in enumerate(downloads, 1):
    try:
        print(f'    [{i}/{len(downloads)}] {dl["name"]}...', end=' ')
        resp = session.get(dl['url'], timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            # Dateiname aus Header oder generieren
            cd = resp.headers.get('Content-Disposition', '')
            if 'filename=' in cd:
                match = re.search(r'filename="?([^"]+)"?', cd)
                filename = match.group(1) if match else f"{dl['name']}.pdf"
            else:
                filename = f"{dl['name']}.pdf"
            filename = filename.replace('/', '_').replace('\\', '_')
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            downloaded.append(filename)
            size_kb = len(resp.content) // 1024
            print(f'{size_kb} KB')
        else:
            print(f'HTTP {resp.status_code}')
            failed.append(dl['name'])
    except requests.exceptions.Timeout:
        print(f'TIMEOUT (>{REQUEST_TIMEOUT}s)')
        failed.append(dl['name'])
    except Exception as e:
        print(f'Fehler: {e}')
        failed.append(dl['name'])

total_time = time.time() - start_time
print()
print('=== Ergebnis ===')
print(f'Produkt: {article_nr}')
print(f'Name: {product_name}')
print(f'Downloads: {len(downloaded)}/{len(downloads)} erfolgreich')
if failed:
    print(f'Fehlgeschlagen: {len(failed)} ({", ".join(failed)})')
print(f'Ordner: {output_dir}')
print()
print(f'Gesamtzeit: {total_time:.2f} Sekunden')
print(f'Timeout pro Request: {REQUEST_TIMEOUT} Sekunden')
