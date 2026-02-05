"""Extrahiere ALLE Produktgruppen-Namen von den Obergruppen-Seiten"""
import requests
import re
import json
import time
from bs4 import BeautifulSoup

BASE_URL = 'https://onlineprohs.schmidt-mg.de/hs'
REQUEST_TIMEOUT = 30
DELAY = 0.5

# Login
with open('../../keys', 'r') as f:
    content = f.read()
username = re.search(r'user_heinrich_schmidt=(.+)', content).group(1).strip()
password = re.search(r'passwort_heinrich_schmidt=(.+)', content).group(1).strip()

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})
session.get(f'{BASE_URL}/login.csp', timeout=REQUEST_TIMEOUT)
session.post(f'{BASE_URL}/login.csp',
    data={'KME': username, 'Kennwort': password, 'FlagAngemeldetBleiben': ''},
    allow_redirects=True, timeout=REQUEST_TIMEOUT)

# Lade aktuelle Struktur
with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
    struktur = json.load(f)

# Sammle alle Produktgruppen-Namen von allen Obergruppen-Seiten
pg_names = {}  # pg_code -> name
obergruppen_visited = 0

for sort_code, sortiment in struktur['sortimente'].items():
    sort_name = sortiment['name']
    print(f'\n=== {sort_name} ({sort_code}) ===')
    
    for og_code, obergruppe in sortiment['obergruppen'].items():
        og_name = obergruppe['name']
        
        # Besuche die Obergruppen-Seite
        url = f'{BASE_URL}/sortimenthsa.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}'
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Finde alle Links mit class text-dark text-mm (Produktgruppen-Links mit Namen)
            for li in soup.find_all('li', class_='text-full'):
                link = li.find('a', class_='text-dark')
                if link:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Nur Produktgruppen3-Links
                    if 'Produktgruppe3=' in href and text and 'weitere' not in text.lower():
                        pg3_match = re.search(r'Produktgruppe3=(\w+)', href)
                        if pg3_match:
                            pg_code = pg3_match.group(1)
                            # Nur hinzufügen wenn noch nicht vorhanden oder der alte Name == Code ist
                            if pg_code not in pg_names or pg_names[pg_code] == pg_code:
                                pg_names[pg_code] = text
            
            obergruppen_visited += 1
            print(f'  {og_name}: {len([l for l in soup.find_all("a", class_="text-dark") if "Produktgruppe3=" in l.get("href", "")])} PG gefunden')
            
            time.sleep(DELAY)
        except Exception as e:
            print(f'  Fehler bei {og_code}: {e}')

print(f'\n\n=== Ergebnis ===')
print(f'Obergruppen besucht: {obergruppen_visited}')
print(f'Produktgruppen-Namen gefunden: {len(pg_names)}')

# Update die Struktur mit den gefundenen Namen
updated = 0
still_missing = 0

for sort_code, sortiment in struktur['sortimente'].items():
    for og_code, obergruppe in sortiment['obergruppen'].items():
        for pg_code, pg_data in obergruppe['produktgruppen'].items():
            if pg_code in pg_names:
                old_name = pg_data['name']
                new_name = pg_names[pg_code]
                if old_name != new_name:
                    pg_data['name'] = new_name
                    updated += 1
                    print(f'  {pg_code}: "{old_name}" -> "{new_name}"')
            else:
                if pg_data['name'] == pg_code:
                    still_missing += 1

print(f'\nAktualisiert: {updated}')
print(f'Immer noch fehlend: {still_missing}')

# Speichern
with open('../system_katalog/_sortiment_struktur.json', 'w', encoding='utf-8') as f:
    json.dump(struktur, f, ensure_ascii=False, indent=2)

print('\nGespeichert!')
