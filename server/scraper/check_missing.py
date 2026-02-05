"""Zeige welche Produktgruppen noch fehlende Namen haben"""
import json

with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
    struktur = json.load(f)

missing = []
total = 0

for sort_code, sortiment in struktur['sortimente'].items():
    for og_code, obergruppe in sortiment['obergruppen'].items():
        for pg_code, pg_data in obergruppe['produktgruppen'].items():
            total += 1
            if pg_data['name'] == pg_code:
                missing.append({
                    'sort': sortiment['name'],
                    'og': obergruppe['name'],
                    'pg_code': pg_code,
                    'name': pg_data['name']
                })

print(f'Gesamt: {total} Produktgruppen')
print(f'Fehlend: {len(missing)}')
print()
for m in missing:
    print(f'  {m["sort"]} > {m["og"]} > {m["pg_code"]}')
