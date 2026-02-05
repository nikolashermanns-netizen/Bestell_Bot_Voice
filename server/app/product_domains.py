"""
Produktbereiche mit spezifischem SHK-Fachwissen.

Jeder Bereich hat:
- name: Anzeigename
- keywords: Schluesselwoerter zur Erkennung
- catalogs: Zugehoerige Katalog-Keys
- instructions: Bereichsspezifisches Fachwissen fuer die AI
"""

PRODUCT_DOMAINS = {
    "rohrsysteme": {
        "name": "Rohrsysteme und Pressfittings",
        "keywords": [
            # Systeme
            "pressfitting", "press", "temponox", "sanpress", "profipress", "megapress",
            "prestabo", "mapress", "mepla", "sanfix", "sanha",
            # Produkttypen
            "bogen", "muffe", "rohr", "fitting", "verschraubung", "uebergangsstueck",
            "uebergangsmuffe", "reduzierstueck", "kappe", "flansch", "winkel",
            "t-stueck", "tstueck",
            # Material
            "kupfer", "edelstahl", "rotguss", "stahl",
            # Hersteller
            "viega", "geberit",
        ],
        "catalogs": [
            "edelstahl_press", "cu_press", "viega", "viega_profipress", 
            "viega_sanpress", "viega_megapress", "geberit_mapress", "geberit_mepla"
        ],
        "instructions": """=== FACHWISSEN: ROHRSYSTEME UND PRESSFITTINGS ===

GEWINDE-BEZEICHNUNGEN (WICHTIG!):
- Rp = Innengewinde (zylindrisch) -> Kunde sagt "Innengewinde"
- R = Aussengewinde (konisch) -> Kunde sagt "Aussengewinde"
- G = Flachdichtend (mit Dichtring)

Beispiele:
- "1 Zoll Innengewinde" -> suche "Rp1"
- "3/4 Zoll Aussengewinde" -> suche "R3/4"
- "22mm auf 1 Zoll Innengewinde" -> suche "22 Rp1"

ZOLL-SCHREIBWEISE IN KATALOGEN:
- 1/2, 3/4, 1, 11/4 (=1 1/4), 11/2 (=1 1/2), 2

ROHRDIMENSIONEN (mm):
- Standard: 15, 18, 22, 28, 35, 42, 54
- XL-Bereich: 64, 76.1, 88.9, 108

PRESSSYSTEME:
- Temponox = Edelstahl fuer Heizung (nicht Trinkwasser!)
- Sanpress = Kupfer/Rotguss fuer Trinkwasser
- Profipress = Kupfer fuer Heizung
- Megapress = Stahl mit Gewinde (fuer Altbausanierung)
- Mapress/Mepla = Geberit Systeme

PRODUKTTYPEN:
- Bogen: 45 oder 90 Grad, IxI oder IxA
- T-Stueck: gleich oder reduziert (z.B. 22x15x22)
- Muffe: Verbindung zweier Rohre
- Verschraubung: loesbarer Anschluss an Gewinde
- Uebergangsstueck: Press auf Aussengewinde (R)
- Uebergangsmuffe: Press auf Innengewinde (Rp)
- Reduzierstueck: Dimensionswechsel (z.B. 28 auf 22)

OPTIONEN IN BEZEICHNUNGEN:
- SC = Sicherheitscontur (Standard bei Pressfittings)
- IxA = Innen x Aussen (Pressende innen, Gewinde aussen)
- IxI = beidseitig Press-Innen

SUCHSTRATEGIE:
1. Immer System + Produkttyp + Dimension + Gewinde
2. Beispiel: "temponox verschraubung 22 Rp1"
3. Bei vielen Treffern: Nach Gewindeart fragen (Innen/Aussen)"""
    },
    
    "armaturen": {
        "name": "Sanitaerarmaturen",
        "keywords": [
            # Produkttypen
            "armatur", "wasserhahn", "mischer", "einhebel", "zweigriff",
            "thermostat", "brause", "handbrause", "kopfbrause",
            # Bereiche
            "waschtischarmatur", "kuechenarmatur", "duscharmatur", "badewannenarmatur",
            "bidetarmatur", "spueltischarmatur",
            # Teile
            "kartusche", "strahlregler", "brauseschlauch", "brausestange",
            # Hersteller
            "grohe", "hansgrohe", "hansa", "kludi", "dornbracht", "keuco",
        ],
        "catalogs": [
            "grohe", "hansgrohe", "hansa", "kludi", "dornbracht", "keuco", "schell"
        ],
        "instructions": """=== FACHWISSEN: SANITAERARMATUREN ===

ARMATURTYPEN:
- Einhebelmischer: Ein Hebel fuer Temperatur und Menge
- Zweigriffarmatur: Getrennte Griffe fuer Warm/Kalt
- Thermostat: Automatische Temperaturregelung
- Selbstschluss: Schliesst automatisch (oeffentliche Bereiche)
- Sensor/Elektronik: Beruehrungslos

MONTAGEARTEN:
- Aufputz (AP): Sichtbar auf der Wand
- Unterputz (UP): Technik in der Wand, nur Bedienelemente sichtbar
- Standarmatur: Auf Waschtisch/Badewannenrand montiert
- Wandarmatur: An der Wand montiert

WICHTIGE MASSE:
- Ausladung: Wie weit ragt der Auslauf hervor
- Auslaufhoehe: Hoehe des Wasseraustritts
- Anschluss: meist 3/8 Zoll oder 1/2 Zoll

ERSATZTEILE:
- Kartusche: Mischeinheit im Inneren (35mm, 40mm, 46mm)
- Strahlregler/Perlator: Am Auslauf, M22/M24 Gewinde
- Griff/Hebel: Oft separat bestellbar

WICHTIGE UNTERSCHEIDUNG:
- "Waschtischarmatur" = Wasserhahn fuer Waschtisch
- "Waschtisch" allein = meist das Keramik-Becken!
-> Bei "Waschtisch" IMMER nachfragen: Armatur oder Becken?

SUCHSTRATEGIE:
1. Hersteller + Typ + Montage
2. Beispiel: "grohe eurosmart waschtisch"
3. Bei Ersatzteilen: Artikelnummer oder Serienname fragen"""
    },
    
    "keramik": {
        "name": "Sanitaerkeramik und Bad",
        "keywords": [
            # WC
            "wc", "toilette", "klosett", "tiefspueler", "flachspueler",
            "wandhaengend", "stand-wc", "wc-sitz", "wc-deckel",
            # Waschtisch
            "waschtisch", "waschbecken", "handwaschbecken", "aufsatzwaschtisch",
            "einbauwaschtisch", "unterschrank", "waschtischunterschrank",
            # Badewanne/Dusche
            "badewanne", "wanne", "duschwanne", "dusche", "duschtasse",
            "bodengleich", "ablaufrinne",
            # Spuelkasten
            "spuelkasten", "druckerplatte", "betaetigungsplatte",
            # Hersteller
            "duravit", "villeroy", "ideal", "keramag", "laufen", "kaldewei", "bette",
        ],
        "catalogs": [
            "duravit", "villeroy_boch", "ideal_standard", "keramag", 
            "laufen", "kaldewei", "bette", "geberit", "tece", "koralle", "hoesch"
        ],
        "instructions": """=== FACHWISSEN: SANITAERKERAMIK UND BAD ===

WC-TYPEN:
- Wandhaengend: An der Wand montiert, Spuelkasten in Vorwand
- Stand-WC: Auf dem Boden stehend
- Tiefspueler: Standard in Deutschland (hygienischer)
- Flachspueler: Mit Auflageplatte (veraltet)
- Spuelrandlos: Ohne Spuelrand, leichter zu reinigen

WASCHTISCH-TYPEN:
- Moebel-Waschtisch: Mit passendem Unterschrank
- Aufsatzwaschtisch: Liegt auf einer Platte auf
- Einbauwaschtisch: In Platte eingelassen
- Handwaschbecken: Kleiner, fuer Gaeste-WC
- Doppelwaschtisch: Zwei Becken

BADEWANNEN:
- Einbauwanne: In Wannentraeger eingebaut
- Freistehend: Steht frei im Raum
- Eckwanne: Fuer Raumecken
- Raumsparwanne: Asymmetrisch, platzsparend
- Whirlpool: Mit Duesenystem

DUSCHEN:
- Duschwanne: Klassisch mit Rand
- Bodengleich/bodennah: Fast ebenerdig
- Ablaufrinne: Laenglicher Ablauf
- Punktablauf: Runder Ablauf in der Mitte

SPUELKASTEN-SYSTEME:
- Unterputz (UP): In Vorwandinstallation (Geberit, TECE)
- Aufputz (AP): Sichtbar an der Wand
- 2-Mengen-Spuelung: Kleine/Grosse Taste
- Betaetigungsplatte: Design-Element, separat

WICHTIGE MASSE:
- WC: Ausladung (Tiefe), Sitzbefestigung
- Waschtisch: Breite, Tiefe, Hahnloch-Abstand
- Wanne: Laenge x Breite x Hoehe

SUCHSTRATEGIE:
1. Hersteller + Typ + eventuell Serie
2. Beispiel: "duravit starck 3 waschtisch 60"
3. Bei Ersatzteilen: WC-Sitz oft separat"""
    },
    
    "heizung": {
        "name": "Heizung und Kessel",
        "keywords": [
            # Kesseltypen
            "kessel", "heizkessel", "brennwert", "therme", "kombitherme",
            "gaskessel", "oelkessel", "pelletkessel",
            # Waermepumpe
            "waermepumpe", "luft-wasser", "sole-wasser", "erdwaerme",
            # Teile
            "brenner", "zuendung", "platine", "steuerung", "regelung",
            "ausdehnungsgefaess", "sicherheitsventil",
            # Hersteller
            "viessmann", "buderus", "vaillant", "wolf", "junkers", 
            "weishaupt", "broetje",
        ],
        "catalogs": [
            "viessmann", "buderus", "vaillant", "wolf_heizung", "junkers",
            "weishaupt", "broetje", "heizung_komplett"
        ],
        "instructions": """=== FACHWISSEN: HEIZUNG UND KESSEL ===

KESSELTYPEN:
- Brennwertkessel: Hoechste Effizienz, nutzt Abgaswaerme
- Niedertemperaturkessel: Aeltere Technik, weniger effizient
- Kombitherme: Heizung + Warmwasser in einem Geraet
- Systemkessel: Nur Heizung, Speicher separat

BRENNSTOFFE:
- Gas: Erdgas (H-Gas, L-Gas), Fluessiggas (Propan)
- Oel: Heizoel EL (Extra Leicht)
- Pellet: Holzpellets, automatische Beschickung
- Scheitholz: Manuell beschickt
- Strom: Waermepumpe, Elektrokessel

WAERMEPUMPEN:
- Luft-Wasser: Aussenluft als Quelle, am guenstigsten
- Sole-Wasser: Erdwaerme (Sonden oder Kollektor)
- Wasser-Wasser: Grundwasser als Quelle
- COP/JAZ: Effizienz-Kennzahl (hoeher = besser)

LEISTUNG:
- Angabe in kW (Kilowatt)
- Einfamilienhaus: ca. 10-20 kW
- Mehrfamilienhaus: entsprechend mehr
- Modulierend: Leistung passt sich an

REGELUNG:
- Witterungsgefuehrt: Aussentemperatur-Sensor
- Raumtemperaturregelung: Innentemperatur-Sensor
- Fernbedienung/App: Steuerung per Smartphone

ERSATZTEILE (haeufig gefragt):
- Zuendelektrode, Zuendtrafo
- Brennerdichtung, Flammrohr
- Umwaelzpumpe (intern)
- Platine/Steuerung
- Ausdehnungsgefaess, Sicherheitsventil

SUCHSTRATEGIE:
1. Bei Ersatzteilen: Geraetetyp/Artikelnummer erfragen
2. Bei Neugeraeten: Leistung und Brennstoff klaeren
3. Beispiel: "viessmann vitodens 200 ersatzteil pumpe" """
    },
    
    "heizkoerper": {
        "name": "Heizkoerper und Flaechenheizung",
        "keywords": [
            # Typen
            "heizkoerper", "radiator", "kompaktheizkoerper", "ventilheizkoerper",
            "roehrenheizkoerper", "designheizkoerper", "badheizkoerper",
            "handtuchheizkoerper", "plattenheizkoper",
            # Flaechenheizung
            "fussbodenheizung", "wandheizung", "deckenheizung", "flaechenheizung",
            # Ventile
            "thermostatventil", "thermostat", "thermostatkopf", "ventileinsatz",
            "ruecklaufverschraubung",
            # Hersteller
            "kermi", "purmo", "zehnder", "buderus", "viessmann",
        ],
        "catalogs": [
            "kermi", "purmo", "zehnder", "oventrop", "danfoss", "heimeier",
            "heizung_komplett"
        ],
        "instructions": """=== FACHWISSEN: HEIZKOERPER UND FLAECHENHEIZUNG ===

HEIZKOERPER-TYPEN:
- Kompaktheizkoerper: Standard-Flachheizkoerper
- Ventilheizkoerper: Mit integriertem Ventil (unten)
- Roehrenheizkoerper: Designvariante, auch als Handtuchhalter
- Konvektor: Schnelle Waermeabgabe
- Niedertemperatur: Fuer Waermepumpe geeignet

TYP-BEZEICHNUNG (Bautiefe):
- Typ 10: Einreihig ohne Konvektor
- Typ 11: Einreihig mit Konvektor
- Typ 20: Zweireihig ohne Konvektor
- Typ 21: Zweireihig mit 1 Konvektor
- Typ 22: Zweireihig mit 2 Konvektoren
- Typ 33: Dreireihig mit 3 Konvektoren

MASSE:
- Bauhoehe: z.B. 300, 400, 500, 600, 900mm
- Baulaenge: z.B. 400 bis 3000mm
- Angabe oft als "Hoehe x Laenge x Typ"

ANSCHLUSS:
- Seitlich links/rechts
- Unten mittig (Mittelanschluss)
- Ventil unten rechts/links
- Anschlussgewinde: meist 1/2 Zoll

THERMOSTATVENTILE:
- Voreinstellbar: Hydraulischer Abgleich moeglich
- Kv-Wert: Durchflusskennzahl
- Fuehler: Eingebaut oder Fernfuehler
- M30x1.5: Standard-Gewinde fuer Koepfe

FUSSBODENHEIZUNG:
- Heizkreisverteiler, Stellantriebe
- Rohr: PE-RT, PE-X (Dimension 14-20mm)
- Tackersystem, Noppensystem

SUCHSTRATEGIE:
1. Typ + Hoehe + Laenge
2. Beispiel: "kermi typ 22 600 1000"
3. Bei Ventilen: Hersteller beachten (nicht kompatibel)"""
    },
    
    "pumpen": {
        "name": "Pumpen und Regelungstechnik",
        "keywords": [
            # Pumpentypen
            "pumpe", "umwaelzpumpe", "heizungspumpe", "zirkulationspumpe",
            "druckerhoehungspumpe", "brauchwasserpumpe", "tauchpumpe",
            # Serien
            "magna", "alpha", "stratos", "calio",
            # Regelung
            "stellantrieb", "mischer", "dreiwegeventil", "zonenventil",
            # Hersteller
            "grundfos", "wilo", "ksb",
        ],
        "catalogs": [
            "grundfos", "wilo", "oventrop", "danfoss", "honeywell", "resideo"
        ],
        "instructions": """=== FACHWISSEN: PUMPEN UND REGELUNGSTECHNIK ===

PUMPENTYPEN:
- Umwaelzpumpe/Heizungspumpe: Bewegt Heizwasser im Kreislauf
- Zirkulationspumpe: Fuer Warmwasser-Zirkulation (klein)
- Druckerhoehungspumpe: Erhoet Wasserdruck
- Tauchpumpe: Fuer Brunnen/Schaechte

KENNWERTE:
- Foerderhoehe: in Meter (m) - Widerstand den Pumpe ueberwindet
- Volumenstrom: in m3/h oder l/min
- Leistung: in Watt (W)
- Effizienzklasse: A (beste) bis G

REGELUNGSARTEN:
- Konstant: Feste Drehzahl
- Proportionaldruck: Passt sich Bedarf an
- Differenzdruck konstant: Haelt Druck konstant
- Autoadapt: Lernt automatisch

EINBAU:
- Einbaulaenge: 130mm oder 180mm (Standard)
- Flansch: DN25, DN32, DN40, DN50
- Verschraubung: 1", 1 1/4", 1 1/2", 2"

BELIEBTE SERIEN:
- Grundfos: Alpha, Magna, UPS
- Wilo: Stratos, Yonos, Star-Z

REGELUNGSTECHNIK:
- Mischer: 3-Wege oder 4-Wege
- Stellantrieb: 230V oder 24V, stromlos auf/zu
- Zonenventil: Fuer einzelne Heizkreise

SUCHSTRATEGIE:
1. Typ + Einbaulaenge + Anschluss
2. Beispiel: "grundfos alpha2 25-60 180"
3. Ersatzteile: Pumpentyp erfragen"""
    },
    
    "werkzeuge": {
        "name": "Werkzeuge und Maschinen",
        "keywords": [
            # Presswerkzeug
            "presse", "pressmaschine", "pressbacke", "presszange",
            # Rohrwerkzeug
            "rohrzange", "rohrabschneider", "rohrbieger", "entgrater",
            "gewindeschneider", "gewindekluppe",
            # Elektrowerkzeug
            "akkuschrauber", "bohrhammer", "bohrer", "schlagbohrer",
            "winkelschleifer", "flex", "saebelsaege",
            # Handwerkzeug
            "zange", "schraubendreher", "schraubenschluessel", "ratsche",
            # Hersteller
            "rothenberger", "rems", "ridgid", "knipex", "wera", 
            "makita", "milwaukee", "bosch", "metabo", "hilti",
        ],
        "catalogs": [
            "rothenberger", "rems", "ridgid", "knipex", "wera", "wiha",
            "makita", "milwaukee", "bosch_werkzeug", "metabo", "hilti"
        ],
        "instructions": """=== FACHWISSEN: WERKZEUGE UND MASCHINEN ===

PRESSWERKZEUGE:
- Pressmaschine: Akkubetrieben, verschiedene Systeme
- Pressbacke: MUSS zum System passen!
  - V-Kontur: Viega, Geberit Mapress
  - M-Kontur: Geberit Mepla
  - TH-Kontur: Verschiedene Hersteller
- Pressring: Fuer groessere Dimensionen

ROHRWERKZEUGE:
- Rohrabschneider: Fuer saubere Schnitte
- Entgrater: Innen und Aussen
- Rohrbieger: Fuer Kupfer/Weichrohr
- Rohrwaage: Zum Ausrichten

GEWINDEWERKZEUGE:
- Gewindeschneider: Fuer Innengewinde
- Gewindekluppe: Fuer Aussengewinde (Rohr)
- Schneidoel: Zum Schmieren

AKKUWERKZEUGE:
- Spannung: 12V, 18V, 36V
- Kapazitaet: 2.0Ah, 4.0Ah, 5.0Ah, etc.
- Brushless: Buerstenlose Motoren (effizienter)
- Akku-System: Meist herstellergebunden!

HANDWERKZEUGE:
- Wasserpumpenzange: Verschiedene Groessen
- Rohrzange: Fuer Rohrverschraubungen
- Kombizange, Seitenschneider
- Schraubendreher: Schlitz, Kreuz (PH/PZ), Torx

SICHERHEIT:
- VDE-isoliert: Fuer Elektroarbeiten
- Schutzbrille, Handschuhe

SUCHSTRATEGIE:
1. Bei Pressbacken: System und Dimension erfragen!
2. Beispiel: "rothenberger pressbacke v 22"
3. Bei Akkuwerkzeug: Spannung/System erfragen"""
    },
    
    "wasseraufbereitung": {
        "name": "Wasseraufbereitung und Filter",
        "keywords": [
            # Produkte
            "filter", "wasserfilter", "hauswasserfilter", "rueckspuelfilter",
            "enthaertung", "enthaerter", "wasserenthaerter", "enthaertungsanlage",
            "dosierung", "dosieranlage", "mineralstoffe",
            "enthaeertung", "kalkschutz", "kalk",
            # Hersteller
            "bwt", "gruenbeck", "judo", "syr", "honeywell",
        ],
        "catalogs": [
            "bwt", "gruenbeck", "judo", "syr", "kemper", "honeywell"
        ],
        "instructions": """=== FACHWISSEN: WASSERAUFBEREITUNG ===

FILTERTYPEN:
- Rueckspuelfilter: Automatisch oder manuell rueckspuelbar
- Wechselfilter: Filtereinsatz wird getauscht
- Feinheit: 90-100 Mikrometer (Standard)
- Anschluss: 3/4", 1", 1 1/4"

ENTHAERTUNG:
- Ionenaustauscher: Tauscht Kalk gegen Natrium
- Kapazitaet: in °dH x Liter oder m3
- Regeneration: Mit Salz (Tabletten)
- Haertebereich: Einstellbar (meist 0-8°dH Ziel)

DOSIERUNG:
- Phosphat/Silikat: Korrosionsschutz
- Mineralstoffe: Nach Enthaertung
- Automatisch oder manuell

WARTUNG:
- Filter: Regelmaessig rueckspuelen/wechseln
- Enthaerter: Salz nachfuellen
- Jaehrliche Inspektion empfohlen

NORMEN:
- DIN 1988: Trinkwasserinstallation
- DIN EN 806: Technische Regeln
- Trinkwasserverordnung

SUCHSTRATEGIE:
1. Anwendung und Anschlussgroesse klaeren
2. Beispiel: "gruenbeck boxer 1 zoll"
3. Ersatzteile: Geraetetyp erfragen"""
    },
    
    "warmwasser": {
        "name": "Warmwasserbereitung",
        "keywords": [
            # Speicher
            "speicher", "warmwasserspeicher", "boiler", "standspeicher",
            "pufferspeicher", "kombispeicher",
            # Durchlauferhitzer
            "durchlauferhitzer", "dle", "elektronisch", "hydraulisch",
            # Elektro
            "kleinspeicher", "untertisch", "uebertisch",
            # Hersteller
            "stiebel", "eltron", "aeg", "vaillant", "clage",
        ],
        "catalogs": [
            "stiebel_eltron", "aeg", "clage", "vaillant", "buderus"
        ],
        "instructions": """=== FACHWISSEN: WARMWASSERBEREITUNG ===

DURCHLAUFERHITZER:
- Elektronisch: Genaue Temperatur, komfortabel
- Hydraulisch: Aeltere Technik, guenstiger
- Leistung: 18kW, 21kW, 24kW, 27kW
- Anschluss: 400V Drehstrom (Elektriker!)

ELEKTROSPEICHER:
- Kleinspeicher: 5-15 Liter (unter Waschbecken)
- Wandspeicher: 30-150 Liter
- Standspeicher: 150-500+ Liter
- Druckfest: Fuer mehrere Zapfstellen
- Drucklos: Nur eine Zapfstelle

INDIREKT BEHEIZTE SPEICHER:
- Erwaermung durch Heizkessel
- Waermetauscher (Rohrschlange)
- Solarspeicher: Mit Solar-Waermetauscher
- Frischwasserstation: Hygienischer

KOMBISPEICHER:
- Heizung + Warmwasser in einem
- Schichtenspeicher: Effizienter

WICHTIGE KENNWERTE:
- Liter: Speicherinhalt
- kW: Heizleistung
- NL-Zahl: Warmwasser-Komfort (hoeher = besser)
- Standby-Verlust: in kWh/24h

SUCHSTRATEGIE:
1. Elektrisch oder mit Heizung?
2. Speicher oder Durchlauferhitzer?
3. Beispiel: "stiebel eltron dhe 21" """
    },
}


def get_domain_by_keyword(text: str) -> str:
    """
    Erkennt den Produktbereich anhand von Keywords im Text.
    
    Args:
        text: Kundenanfrage oder Produktbeschreibung
        
    Returns:
        Domain-Key oder None wenn nicht erkannt
    """
    text_lower = text.lower()
    
    # Zaehle Treffer pro Domain
    scores = {}
    for domain_key, domain in PRODUCT_DOMAINS.items():
        score = 0
        for keyword in domain["keywords"]:
            if keyword in text_lower:
                # Laengere Keywords geben mehr Punkte
                score += len(keyword)
        if score > 0:
            scores[domain_key] = score
    
    if not scores:
        return None
    
    # Beste Domain zurueckgeben
    return max(scores, key=scores.get)


def get_domain_catalogs(domain_key: str) -> list:
    """Gibt die Kataloge fuer einen Bereich zurueck."""
    domain = PRODUCT_DOMAINS.get(domain_key)
    if domain:
        return domain.get("catalogs", [])
    return []


def get_domain_instructions(domain_key: str) -> str:
    """Gibt das Fachwissen fuer einen Bereich zurueck."""
    domain = PRODUCT_DOMAINS.get(domain_key)
    if domain:
        return domain.get("instructions", "")
    return ""


def get_all_domain_names() -> dict:
    """Gibt alle Bereichsnamen zurueck."""
    return {key: domain["name"] for key, domain in PRODUCT_DOMAINS.items()}
