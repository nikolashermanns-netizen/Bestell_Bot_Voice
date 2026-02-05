"""
Erstellt einen Such-Index für die Kategorien.
Format: Keyword -> Kategorie-Pfad -> Such-URL
"""
import json
import re
import time

def normalize_keyword(text: str) -> list:
    """Extrahiert suchbare Keywords aus einem Text"""
    # Lowercase und Sonderzeichen entfernen
    text = text.lower()
    text = re.sub(r'[^\wäöüß\s-]', ' ', text)
    
    # In Wörter splitten
    words = text.split()
    
    # Kurze Wörter und Stopwords entfernen
    stopwords = {'und', 'für', 'mit', 'der', 'die', 'das', 'ein', 'eine', 'oder', 'zur', 'zum'}
    keywords = [w for w in words if len(w) > 2 and w not in stopwords]
    
    return keywords


def main():
    print('=== Such-Index erstellen ===')
    print()
    
    # Struktur laden
    with open('../system_katalog/_sortiment_struktur.json', 'r', encoding='utf-8') as f:
        struktur = json.load(f)
    
    BASE_URL = "https://onlineprohs.schmidt-mg.de/hs"
    
    # Index aufbauen
    # 1. Flache Liste aller Kategorien mit Such-URLs
    kategorien = []
    
    # 2. Keyword -> Kategorie-Mapping
    keyword_index = {}
    
    for sort_code, sortiment in struktur['sortimente'].items():
        sort_name = sortiment['name']
        
        # Sortiment-Ebene
        kategorien.append({
            'typ': 'sortiment',
            'name': sort_name,
            'code': sort_code,
            'pfad': sort_name,
            'suche_url': f'{BASE_URL}/artikelsuche.csp?Produktgruppe1={sort_code}',
        })
        
        # Keywords für Sortiment
        for kw in normalize_keyword(sort_name):
            if kw not in keyword_index:
                keyword_index[kw] = []
            keyword_index[kw].append({
                'pfad': sort_name,
                'code': sort_code,
                'typ': 'sortiment'
            })
        
        for og_code, obergruppe in sortiment['obergruppen'].items():
            og_name = obergruppe['name']
            og_pfad = f'{sort_name} > {og_name}'
            
            # Obergruppe-Ebene
            kategorien.append({
                'typ': 'obergruppe',
                'name': og_name,
                'code': og_code,
                'pfad': og_pfad,
                'sortiment': sort_name,
                'suche_url': f'{BASE_URL}/artikelsuche.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}',
            })
            
            # Keywords für Obergruppe
            for kw in normalize_keyword(og_name):
                if kw not in keyword_index:
                    keyword_index[kw] = []
                keyword_index[kw].append({
                    'pfad': og_pfad,
                    'code': og_code,
                    'typ': 'obergruppe'
                })
            
            for pg_code, produktgruppe in obergruppe['produktgruppen'].items():
                pg_name = produktgruppe['name']
                
                # Nur Produktgruppen mit echtem Namen (nicht nur Code)
                if pg_name == pg_code:
                    continue
                
                pg_pfad = f'{sort_name} > {og_name} > {pg_name}'
                
                # Produktgruppe-Ebene
                kategorien.append({
                    'typ': 'produktgruppe',
                    'name': pg_name,
                    'code': pg_code,
                    'pfad': pg_pfad,
                    'sortiment': sort_name,
                    'obergruppe': og_name,
                    'suche_url': f'{BASE_URL}/artikelsuche.csp?Produktgruppe1={sort_code}&Produktgruppe2={og_code}&Produktgruppe3={pg_code}',
                })
                
                # Keywords für Produktgruppe
                for kw in normalize_keyword(pg_name):
                    if kw not in keyword_index:
                        keyword_index[kw] = []
                    keyword_index[kw].append({
                        'pfad': pg_pfad,
                        'code': pg_code,
                        'typ': 'produktgruppe'
                    })
    
    # Such-Index speichern
    such_index = {
        'meta': {
            'source': 'Heinrich Schmidt OnlinePro',
            'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'description': 'Such-Index für Kategorien-Navigation',
            'statistics': {
                'kategorien': len(kategorien),
                'keywords': len(keyword_index),
            }
        },
        'kategorien': kategorien,
        'keywords': keyword_index,
    }
    
    output_path = '../system_katalog/_such_index.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(such_index, f, ensure_ascii=False, indent=2)
    
    print(f'Kategorien: {len(kategorien)}')
    print(f'Keywords: {len(keyword_index)}')
    print(f'Gespeichert: {output_path}')
    
    # Beispiel-Ausgabe
    print()
    print('=== Beispiel: Suche nach "waschtisch" ===')
    if 'waschtisch' in keyword_index:
        for match in keyword_index['waschtisch'][:5]:
            print(f'  {match["pfad"]}')
    
    print()
    print('=== Beispiel: Suche nach "heizung" ===')
    if 'heizung' in keyword_index:
        for match in keyword_index['heizung'][:5]:
            print(f'  {match["pfad"]}')


if __name__ == '__main__':
    main()
