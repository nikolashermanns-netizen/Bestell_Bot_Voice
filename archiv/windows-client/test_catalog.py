#!/usr/bin/env python3
"""Test Katalog-Suche"""

import sys
sys.path.insert(0, '/app')

import catalog

# Katalog laden
catalog.load_catalog()

# Test 1: Allgemeine Suche
print("=== Test 1: Suche 'Bogen 90' ===")
results = catalog.search_product("Bogen 90")
print(f"Ergebnisse: {len(results)}")
for r in results[:5]:
    print(f"  - {r['name']} ({r['kennung']}) - {r['system']} {r['size']}")

# Test 2: Mit System-Filter
print("\n=== Test 2: Suche 'Bogen 90' in temponox ===")
results = catalog.search_product("Bogen 90", system="temponox")
print(f"Ergebnisse: {len(results)}")
for r in results[:5]:
    print(f"  - {r['name']} ({r['kennung']}) - {r['system']} {r['size']}")

# Test 3: Mit Groesse
print("\n=== Test 3: Suche 'Bogen 90' in temponox 28mm ===")
results = catalog.search_product("Bogen 90", system="temponox", size="28mm")
print(f"Ergebnisse: {len(results)}")
for r in results[:5]:
    print(f"  - {r['name']} ({r['kennung']}) - {r['system']} {r['size']}")

# Test 4: Zeige alle Produkte in temponox mit 28mm
print("\n=== Test 4: Alle temponox 28mm Produkte ===")
products = catalog.get_system_products("temponox", size="28mm")
print(f"Produkte: {len(products)}")
for p in products[:10]:
    print(f"  - {p['name']} ({p['kennung']})")

# Test 5: System-Uebersicht
print("\n=== Test 5: System-Uebersicht ===")
overview = catalog.get_systems_overview()
print(f"Systeme: {len(overview.get('systems', []))}")
for s in overview.get('systems', []):
    print(f"  - {s['id']}: {s['name']} ({s['product_count']} Produkte)")
    print(f"    Groessen: {s['sizes']}")
