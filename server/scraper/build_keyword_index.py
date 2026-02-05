#!/usr/bin/env python3
"""
Build Keyword Index - Extrahiert Schlagwoerter aus allen Katalogen.

Erstellt _keywords.json mit Zuordnung: Schlagwort -> welche Kataloge enthalten es.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path

# Pfad zum Katalog-Ordner
CATALOG_DIR = Path(__file__).parent.parent / "system_katalog"

# Stoppwoerter die nicht indexiert werden
STOPWORDS = {
    "und", "oder", "mit", "aus", "fuer", "von", "zur", "zum", "der", "die", "das",
    "ein", "eine", "einer", "eines", "einem", "einen",
    "ist", "sind", "wird", "werden", "hat", "haben",
    "mm", "cm", "m", "kg", "g", "l", "ml", "bar", "grad",
    "stueck", "stk", "stück", "set", "pack", "pck",
    "dn", "da", "ag", "ig", "zoll",
    "x", "bis", "ca", "inkl", "incl", "ohne", "nur",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
}

# Mindestlaenge fuer Schlagwoerter
MIN_KEYWORD_LENGTH = 3


def extract_keywords(text: str) -> set:
    """Extrahiert relevante Schlagwoerter aus einem Text."""
    if not text:
        return set()
    
    # Lowercase und Umlaute normalisieren
    text = text.lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    
    # Nur Buchstaben und Zahlen behalten, Rest durch Leerzeichen ersetzen
    text = re.sub(r'[^a-z0-9äöüß]', ' ', text)
    
    # In Woerter splitten
    words = text.split()
    
    # Filtern
    keywords = set()
    for word in words:
        # Mindestlaenge
        if len(word) < MIN_KEYWORD_LENGTH:
            continue
        # Keine reinen Zahlen
        if word.isdigit():
            continue
        # Keine Stoppwoerter
        if word in STOPWORDS:
            continue
        keywords.add(word)
    
    return keywords


def build_index():
    """Baut den Keyword-Index aus allen Katalogen."""
    
    # Index: keyword -> {kataloge: set, count: int}
    keyword_index = defaultdict(lambda: {"kataloge": set(), "count": 0})
    
    # Hersteller-Keywords separat tracken (fuer bessere Zuordnung)
    hersteller_keywords = {}
    
    # Index-Datei laden
    index_path = CATALOG_DIR / "_index.json"
    if not index_path.exists():
        print(f"Error: {index_path} nicht gefunden!")
        return
    
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)
    
    systems = index_data.get("systems", [])
    print(f"Verarbeite {len(systems)} Kataloge...")
    
    total_products = 0
    total_keywords = 0
    
    for system in systems:
        name = system["name"]
        filename = system["file"]
        catalog_key = filename.replace(".json", "")
        
        filepath = CATALOG_DIR / filename
        if not filepath.exists():
            print(f"  Warnung: {filename} nicht gefunden")
            continue
        
        print(f"  {name} ({filename})...", end=" ", flush=True)
        
        # Hersteller-Name als Keyword
        hersteller_keywords[catalog_key] = extract_keywords(name)
        for kw in hersteller_keywords[catalog_key]:
            keyword_index[kw]["kataloge"].add(catalog_key)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except Exception as e:
            print(f"Fehler: {e}")
            continue
        
        products = catalog.get("products", [])
        product_count = len(products)
        total_products += product_count
        
        catalog_keywords = set()
        
        for product in products:
            # Bezeichnung 1 und 2 extrahieren
            bez1 = product.get("Bezeichnung 1", "")
            bez2 = product.get("Bezeichnung 2", "")
            
            # Keywords extrahieren
            kw1 = extract_keywords(bez1)
            kw2 = extract_keywords(bez2)
            
            all_kw = kw1 | kw2
            catalog_keywords.update(all_kw)
            
            for kw in all_kw:
                keyword_index[kw]["kataloge"].add(catalog_key)
                keyword_index[kw]["count"] += 1
        
        total_keywords += len(catalog_keywords)
        print(f"{product_count} Produkte, {len(catalog_keywords)} Keywords")
    
    # Sets zu Listen konvertieren fuer JSON
    final_index = {}
    for keyword, data in keyword_index.items():
        final_index[keyword] = {
            "kataloge": sorted(list(data["kataloge"])),
            "count": data["count"]
        }
    
    # Nach Haeufigkeit sortieren (haeufigste zuerst)
    sorted_index = dict(sorted(
        final_index.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    ))
    
    # Speichern
    output_path = CATALOG_DIR / "_keywords.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sorted_index, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== Fertig ===")
    print(f"Produkte gesamt: {total_products:,}")
    print(f"Unique Keywords: {len(sorted_index):,}")
    print(f"Index gespeichert: {output_path}")
    
    # Top 20 Keywords anzeigen
    print(f"\nTop 20 Keywords:")
    for i, (kw, data) in enumerate(list(sorted_index.items())[:20]):
        print(f"  {i+1}. {kw}: {data['count']} Treffer in {len(data['kataloge'])} Katalogen")


if __name__ == "__main__":
    build_index()
