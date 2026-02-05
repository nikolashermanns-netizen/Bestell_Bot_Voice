# Heinrich Schmidt OnlinePro - Webseiten-Dokumentation

Diese Dokumentation beschreibt, wie man programmatisch auf die Heinrich Schmidt OnlinePro Webseite zugreift, um Produktdaten, Kataloge und Downloads zu erhalten.

## Überblick

- **URL**: `https://onlineprohs.schmidt-mg.de`
- **System**: InterSystems Caché Server Pages (CSP)
- **Authentifizierung**: Session-basiert mit Cookies
- **Zugangsdaten**: Siehe `keys` Datei im Projekt-Root

## Zugangsdaten

Die Zugangsdaten befinden sich in der Datei `keys` im Projekt-Root:

```
user_heinrich_schmidt=NH@PLER01
passwort_heinrich_schmidt=4uDPZs!h7TyH2fW
```

Format der Kundenkennung: `BENUTZER-KÜRZEL@KUNDEN-NR`

---

## 1. Login

### URL
```
POST https://onlineprohs.schmidt-mg.de/hs/login.csp
```

### Formular-Daten
```python
login_data = {
    "KME": "NH@PLER01",           # Kundenkennung
    "Kennwort": "4uDPZs!h7TyH2fW", # Passwort
    "FlagAngemeldetBleiben": "",   # Leer lassen
}
```

### Erfolgreiche Antwort
- Redirect zu `/hs/index.csp` oder `/hs/agbok.csp`
- Session-Cookie wird gesetzt

### AGB-Akzeptierung (falls nötig)
Wenn Redirect zu `agbok.csp`:
```python
agb_data = {"Aktion": "Weiter", "AGB": "on"}
session.post(agb_url, data=agb_data, allow_redirects=True)
```

### Python-Beispiel
```python
import requests

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})

# Login-Seite laden (für Cookies)
session.get("https://onlineprohs.schmidt-mg.de/hs/login.csp")

# Login durchführen
response = session.post(
    "https://onlineprohs.schmidt-mg.de/hs/login.csp",
    data={
        "KME": "NH@PLER01",
        "Kennwort": "4uDPZs!h7TyH2fW",
        "FlagAngemeldetBleiben": "",
    },
    allow_redirects=True
)

# Prüfen ob Login erfolgreich
if "index.csp" in response.url or "agbok.csp" in response.url:
    print("Login erfolgreich!")
    # AGB akzeptieren falls nötig
    if "agbok.csp" in response.url:
        session.post(response.url, data={"Aktion": "Weiter", "AGB": "on"})
```

---

## 2. Artikelsuche

### URL
```
GET https://onlineprohs.schmidt-mg.de/hs/artikelsuche.csp?Suchstring={SUCHBEGRIFF}
```

### Parameter
| Parameter | Beschreibung | Beispiel |
|-----------|--------------|----------|
| `Suchstring` | Suchbegriff (URL-encoded) | `Viega+Profipress` |
| `SuchstringHUSOLR7ID` | Optional, leer lassen | |
| `SuchstringSelect` | Optional, `1` für exakte Suche | `1` |

### Beispiel
```
https://onlineprohs.schmidt-mg.de/hs/artikelsuche.csp?Suchstring=Viega+Profipress
```

### Antwort parsen
Die Antwort enthält:
- Trefferanzahl: `Ihre Suche ergab X Treffer`
- Hinweis bei Limit: `Angezeigt werden nur die ersten 2.000 Treffer`
- SucheID für Export: `SucheID=12345678`

```python
import re

html = response.text

# Treffer extrahieren
hits_match = re.search(r"Ihre Suche ergab (\d+(?:\.\d+)?)\s*Treffer", html)
total_hits = int(hits_match.group(1).replace(".", "")) if hits_match else 0

# SucheID extrahieren
suche_id_match = re.search(r"SucheID=(\d+)", html)
suche_id = suche_id_match.group(1) if suche_id_match else ""
```

---

## 3. Produktdetails (Artikelauskunft)

### URL
```
GET https://onlineprohs.schmidt-mg.de/hs/artikelauskunft.csp?Artikel={ARTIKEL_NR}&Suchstring={ARTIKEL_NR}
```

### Parameter
| Parameter | Beschreibung | Beispiel |
|-----------|--------------|----------|
| `Artikel` | Artikelnummer (URL-encoded) | `WT%2BOPS60` |
| `Suchstring` | Gleiche Artikelnummer | `WT%2BOPS60` |

**WICHTIG**: Das `+` Zeichen muss als `%2B` kodiert werden!

### Beispiel
```
https://onlineprohs.schmidt-mg.de/hs/artikelauskunft.csp?Artikel=WT%2BOPS60&Suchstring=WT%2BOPS60
```

### Verfügbare Informationen
Die Seite enthält Tabs mit verschiedenen Informationen:

| Tab | Inhalt |
|-----|--------|
| **Infos** | Produktname, Hersteller, Gewicht, Montagezeit, Kategorie |
| **Bestände** | Lagerbestand, Lieferzeit |
| **Downloads** | PDFs, Bilder, Datenblätter, Montageanleitungen |
| **Weitere Infos** | Zusätzliche technische Daten |

### Downloads extrahieren
Die Downloads sind als Links verfügbar. Typische Typen:

**PDFs (herunterladen):**
- `Montageanleitung` - Einbauanleitung
- `Datenblatt` - Technische Daten
- `Prospekt` - Produktprospekt
- `Zulassung` - Zertifikate, Zulassungen
- `EPD-Nachhaltigkeitszertifikat` - Umweltzertifikat

**Bilder (überspringen):**
- `Farbbild` / `Farbbild2` - Produktfotos
- `SWBild` - Schwarz-Weiß-Bild
- `Strichzeichnung` - Technische Zeichnung
- `Masszeichnung` - Maßzeichnung

### Download-Filter (Python)
```python
# Keywords für Bilder (überspringen)
image_keywords = ['farbbild', 'swbild', 'strichzeichnung', 'masszeichnung', 'zeichnung']
image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    if 'Online3.Download.cls' in href:
        text = link.get_text(strip=True)
        
        # Bild-Extension in URL?
        is_image_ext = any(ext in href.lower() for ext in image_extensions)
        # Bild-Keyword im Text?
        is_image_text = any(kw in text.lower() for kw in image_keywords)
        
        # Überspringe Bilder und leere Links
        if is_image_ext or is_image_text or not text:
            continue
        
        # Dies ist ein PDF-Download
        full_url = f'https://onlineprohs.schmidt-mg.de/hs/{href}'
        downloads.append({'name': text, 'url': full_url})
```

---

## 4. CSV-Export (Massendownload)

Der CSV-Export ermöglicht das Herunterladen von bis zu 2.000 Produkten auf einmal.

### Schritt 1: Suche durchführen
```python
url = "https://onlineprohs.schmidt-mg.de/hs/artikelsuche.csp?Suchstring=Viega"
response = session.get(url)
html = response.text

# SucheID und Tokens extrahieren
suche_id = re.search(r"SucheID=(\d+)", html).group(1)

# Export-Modal-Token (für das Öffnen des Export-Dialogs)
export_modal_token = re.search(
    r"\$\('\.ArtikelsucheExport'\)\.on\('click'.*?cspHttpServerMethod\('([^']+)'",
    html, re.DOTALL
).group(1)

# CSV-Export-Token (für den eigentlichen Export)
csv_export_token = re.search(
    r"\$\('\.Export2CSV'\)\.on\('click'.*?cspHttpServerMethod\('([^']+)'",
    html, re.DOTALL
).group(1)
```

### Schritt 2: Export-Modal öffnen (ExportID holen)
```python
BROKER_URL = "https://onlineprohs.schmidt-mg.de/hs/%25CSP.Broker.cls"

# CSP-Broker aufrufen
data = f"WARGC=1&WEVENT={export_modal_token}&WARG_1={suche_id}"
response = session.post(BROKER_URL, data=data, headers={
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
})

# ExportID extrahieren
export_id = re.search(r"#ExportID.*?\.val\((['\"]?)(\d+)\1\)", response.text).group(2)
```

### Schritt 3: CSV herunterladen
```python
# Export auslösen (typ=2 für detailliert, typ=1 für einfach)
data = f"WARGC=2&WEVENT={csv_export_token}&WARG_1={export_id}&WARG_2=2"
response = session.post(BROKER_URL, data=data, headers={
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
})

# Die Antwort enthält einen Redirect zur Download-URL
# Format: window.location='Online3.Download.cls?FileId=650808464';
download_match = re.search(r"Online3\.Download\.cls\?FileId=\d+", response.text)
download_url = f"https://onlineprohs.schmidt-mg.de/hs/{download_match.group(0)}"

# CSV herunterladen
csv_response = session.get(download_url)
csv_content = csv_response.text
```

### CSV-Format
- Trennzeichen: `;` (Semikolon)
- Encoding: UTF-8
- Spalten (detaillierter Export):
  - `Artikel` - Artikelnummer
  - `Menge` - Bestellmenge
  - `Bezeichnung 1` - Produktname
  - `Bezeichnung 2` - Zusatzbezeichnung
  - `Werksnummer` - Hersteller-Artikelnummer
  - `EAN` - EAN-Code
  - `ME` - Mengeneinheit (Stück, Meter, etc.)
  - `PE` - Preiseinheit
  - `EK-Preis` - Einkaufspreis
  - `VK-Preis` - Verkaufspreis
  - und weitere...

---

## 5. Datei-Downloads

### Download-URL-Format
```
https://onlineprohs.schmidt-mg.de/hs/Online3.Download.cls?FileId={FILE_ID}&Extension={.pdf|.jpg|.png}
```

Oder mit CSP-Token:
```
https://onlineprohs.schmidt-mg.de/hs/Online3.Download.cls?CSPToken={TOKEN}
```

### Beispiel
```python
# Download-Link von der Produktseite extrahieren
download_url = "https://onlineprohs.schmidt-mg.de/hs/Online3.Download.cls?FileId=650963642&Extension=.pdf"

response = session.get(download_url)

# Dateiname aus Content-Disposition Header
content_disp = response.headers.get('Content-Disposition', '')
# Beispiel: attachment; filename="Montageanleitung.pdf"

# Datei speichern
with open("Montageanleitung.pdf", "wb") as f:
    f.write(response.content)
```

---

## 6. Sortimente und Kategorien

### Sortiment-Übersicht
```
GET https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp
```

### Sortiment auswählen
```
GET https://onlineprohs.schmidt-mg.de/hs/sortimenthsa.csp?Produktgruppe1={CODE}
```

| Code | Sortiment | Produkte (ca.) |
|------|-----------|----------------|
| `S` | Sanitär | 220.000 |
| `H` | Heizung | 200.000 |
| `I` | Installation | 56.000 |
| `K` | Klima/Lüftung | 34.000 |
| `E` | Elektro | 558.000 |
| `W` | Werkzeug | 69.000 |
| `P` | Photovoltaik | 771 |
| `G` | Hausgeräte | ? |
| `B` | Befestigungstechnik | 4.400 |

---

## 7. Hersteller-Übersicht

### URL
```
GET https://onlineprohs.schmidt-mg.de/hs/hersteller.csp
```

### Paginierung
```
GET https://onlineprohs.schmidt-mg.de/hs/hersteller.csp?HIndex={OFFSET}
```

- 24 Hersteller pro Seite
- 28 Seiten insgesamt
- `HIndex=0` für Seite 1, `HIndex=24` für Seite 2, etc.

---

## 8. Wichtige Limitierungen

| Limit | Wert | Beschreibung |
|-------|------|--------------|
| **Export-Limit** | 2.000 | Maximale Anzahl Produkte pro CSV-Export |
| **Anzeige-Limit** | 2.000 | Maximale angezeigte Treffer in der Suche |
| **Session-Timeout** | ~30 Min | Session läuft ab, erneuter Login nötig |

### Umgehung des 2.000er Limits
Um mehr als 2.000 Produkte zu erhalten:
1. Verfeinerte Suchen durchführen (z.B. nach Größen: "Viega 15", "Viega 22")
2. Nach Herstellern einzeln suchen
3. Nach Produktgruppen/Obergruppen filtern

---

## 9. Vollständiges Python-Modul

Siehe `schmidt_csv_export.py` für den CSV-Export und `product_downloads.py` für Produkt-Downloads.

### Schnellstart: CSV-Export
```python
from schmidt_csv_export import SchmidtCSVExporter, load_credentials

username, password = load_credentials()
exporter = SchmidtCSVExporter(username, password)

if exporter.login():
    products = exporter.export_products("Viega Profipress", detailed=True)
    exporter.save_to_json(products, "viega_profipress.json")
```

### Schnellstart: Produkt-Downloads
```python
from product_downloads import ProductDownloader

downloader = ProductDownloader()
if downloader.login():
    # Produktinfo + Downloads holen
    result = downloader.get_downloads_for_expert_ai("WT+OPS60")
    
    # result enthält:
    # - article_nr, name, manufacturer
    # - downloads: Liste mit Pfaden zu PDFs (Montageanleitung, Datenblatt, etc.)
```

---

## 10. CSP-Broker (Fortgeschritten)

Das CSP-Framework nutzt einen Broker für AJAX-Aufrufe:

### URL
```
POST https://onlineprohs.schmidt-mg.de/hs/%25CSP.Broker.cls
```

### Request-Format
```
WARGC={ANZAHL_ARGUMENTE}&WEVENT={TOKEN}&WARG_1={ARG1}&WARG_2={ARG2}...
```

### Header
```
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
```

### Token-Extraktion
Tokens werden aus dem JavaScript der Seite extrahiert:
```javascript
// Beispiel aus dem HTML:
$('.ArtikelsucheExport').on('click', function() {
    cspHttpServerMethod('Fe5i4FqEH$WYDdv1bwN4e36ipOOVWx...', SucheID);
});
```

---

## 11. Tipps für die Implementierung

1. **Session wiederverwenden**: Immer `requests.Session()` nutzen für Cookie-Persistenz
2. **Rate Limiting**: 0.2-0.5 Sekunden Pause zwischen Requests
3. **Fehlerbehandlung**: Bei 404/500 erneut einloggen und wiederholen
4. **URL-Encoding**: `+` als `%2B` kodieren in Artikelnummern
5. **Duplikate vermeiden**: Artikelnummern als eindeutigen Schlüssel nutzen

---

## 12. Kategorie-Struktur

Die Webseite hat eine 3-stufige Kategorien-Hierarchie:

### Hierarchie
```
Sortiment (z.B. Sanitär)
  └── Obergruppe (z.B. Badkeramik)
       └── Produktgruppe (z.B. Waschtische)
```

### Sortimente (Produktgruppe1)
| Code | Name | Produkte |
|------|------|----------|
| S | Sanitär | ~220.000 |
| H | Heizung | ~200.000 |
| I | Installation | ~56.000 |
| L | Klima/Lüftung | ~34.000 |
| E | Elektro | ~558.000 |
| C | Werkzeug | ~69.000 |
| P | Photovoltaik | ~771 |
| G | Hausgeräte | ? |
| M | Befestigungstechnik | ~4.400 |

### Such-URLs
```
# Sortiment
artikelsuche.csp?Produktgruppe1=S

# Obergruppe
artikelsuche.csp?Produktgruppe1=S&Produktgruppe2=S0080

# Produktgruppe
artikelsuche.csp?Produktgruppe1=S&Produktgruppe2=S0080&Produktgruppe3=S00800130
```

### Exportierte Dateien
- `_sortiment_struktur.json` - Vollständige Hierarchie (9 Sortimente, 130 Obergruppen, 798 Produktgruppen)
- `_such_index.json` - Keyword-basierter Such-Index

---

## 13. Verfügbare Scripts

| Script | Funktion |
|--------|----------|
| `schmidt_csv_export.py` | CSV-Export für Produktlisten |
| `product_downloads.py` | Downloads für einzelne Produkte |
| `export_by_hersteller.py` | Export nach Herstellern sortiert |
| `export_all_systems.py` | Export aller Sortimente |
| `complete_catalogs.py` | Vervollständigung bei 2000er Limit |
| `export_sortiment_struktur.py` | Export der Kategorie-Hierarchie |
| `create_such_index.py` | Erstellt Keyword-Such-Index |
| `test_dokumentation.py` | Test: Produkt-Downloads |

---

## Kontakt

Bei Fragen zur Webseite:
- Heinrich Schmidt GmbH & Co. KG
- Mönchengladbach
- https://onlineprohs.schmidt-mg.de
