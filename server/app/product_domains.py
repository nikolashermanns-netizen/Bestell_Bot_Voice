"""
Produktbereiche mit spezifischem SHK-Fachwissen.

Jeder Bereich hat:
- name: Anzeigename
- keywords: Schluesselwoerter zur Erkennung
- catalogs: Zugehoerige Katalog-Keys
- instructions: Bereichsspezifisches Fachwissen fuer die AI

ABDECKUNG: 109 Kataloge / 157.520 Produkte (100%)
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
            "t-stueck", "tstueck", "kupplung",
            # Material
            "kupfer", "edelstahl", "rotguss", "stahl", "verbundrohr", "mehrschicht",
            # Hersteller
            "viega", "geberit", "uponor", "rehau", "wavin", "aquatherm", "comap",
        ],
        "catalogs": [
            "edelstahl_press", "cu_press", "viega", "viega_profipress", 
            "viega_sanpress", "viega_megapress", "geberit_mapress", "geberit_mepla",
            "uponor", "rehau", "wavin", "aquatherm", "comap"
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
- Uponor/Rehau = Mehrschicht-Verbundrohre

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
            "bodengleich", "ablaufrinne", "duschrinne",
            # Spuelkasten
            "spuelkasten", "druckerplatte", "betaetigungsplatte",
            # Hersteller
            "duravit", "villeroy", "ideal", "keramag", "laufen", "kaldewei", "bette",
            "hoesch", "koralle", "hsk",
        ],
        "catalogs": [
            "duravit", "villeroy_boch", "ideal_standard", "keramag", 
            "laufen", "kaldewei", "bette", "geberit", "tece", "koralle", "hoesch",
            "hsk", "sanitaer_komplett"
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
    
    "wc_technik": {
        "name": "WC-Technik und Vorwandinstallation",
        "keywords": [
            # Produkte
            "vorwand", "installationselement", "spuelkasten", "unterputz",
            "betaetigungsplatte", "druckerplatte", "sigma", "omega",
            "geberit duofix", "tece", "sanit", "mepa", "schwab", "wisa", "friatec",
            # Teile
            "fuellventil", "ablaufventil", "heberglocke", "druckerspuelung",
        ],
        "catalogs": [
            "geberit", "tece", "sanit", "friatec", "mepa", "schwab", "wisa"
        ],
        "instructions": """=== FACHWISSEN: WC-TECHNIK UND VORWANDINSTALLATION ===

VORWANDSYSTEME:
- Geberit Duofix: Marktfuehrer, viele Varianten
- TECE: Alternative, modernes Design
- Sanit: Guenstigere Alternative
- Mepa/Schwab/Wisa: Weitere Hersteller

INSTALLATIONSELEMENTE:
- WC-Element: Fuer Wand-WC mit Spuelkasten
- Waschtisch-Element: Fuer Waschtisch-Montage
- Urinal-Element: Fuer Urinal
- Bidet-Element: Fuer Bidet

SPUELKASTEN-TYPEN:
- UP320: Geberit Universal (8cm Tiefe)
- UP720: Geberit fuer geringe Tiefen
- Omega: Geberit mit anderem Betaetigungssystem
- Sigma: Geberit Standard-System

BETAETIGUNGSPLATTEN:
- 1-Mengen: Nur eine Taste
- 2-Mengen: Kleine und grosse Spuelung
- Pneumatisch: Druckknopf mit Schlauch
- Elektrisch: Beruehrungslos/Sensor

ERSATZTEILE (haeufig gefragt):
- Fuellventil: Laesst Wasser einlaufen
- Ablaufventil/Heberglocke: Spuelvorgang
- Dichtungen: Fuer Spuelkasten
- Druckerplatte: Ausloesung

SUCHSTRATEGIE:
1. Hersteller + Element-Typ
2. Beispiel: "geberit duofix wc element"
3. Ersatzteile: Spuelkasten-Typ erfragen (UP320, etc.)"""
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
            "weishaupt", "broetje", "rotex", "bosch",
        ],
        "catalogs": [
            "viessmann", "buderus", "vaillant", "wolf_heizung", "wolf", "junkers",
            "weishaupt", "broetje", "rotex", "bosch", "heizung_komplett"
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
            "arbonia", "bemm", "cosmo", "schulte",
        ],
        "catalogs": [
            "kermi", "purmo", "zehnder", "oventrop", "danfoss", "heimeier",
            "arbonia", "bemm", "cosmo", "schulte", "heizung_komplett"
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
    
    "klima": {
        "name": "Klimaanlagen und Waermepumpen",
        "keywords": [
            # Produkte
            "klimaanlage", "klima", "split", "multisplit", "monoblock",
            "kaeltemittel", "r32", "r410a",
            # Waermepumpe
            "waermepumpe", "luft-luft", "luft-wasser", "inverter",
            # Hersteller
            "daikin", "mitsubishi", "panasonic", "lg", "samsung",
        ],
        "catalogs": [
            "daikin", "mitsubishi", "panasonic", "lg"
        ],
        "instructions": """=== FACHWISSEN: KLIMAANLAGEN UND WAERMEPUMPEN ===

KLIMAANLAGEN-TYPEN:
- Split-Klimageraet: Innen- und Ausseneinheit getrennt
- Multisplit: Ein Aussengeraet, mehrere Innengeraete
- Monoblock: Alles in einem Geraet
- VRF/VRV: Grossanlagen fuer Gewerbe

INNENGERAETE:
- Wandgeraet: An der Wand montiert (Standard)
- Deckengeraet: In/an der Decke
- Truhengeraet: Am Boden stehend
- Kanalgeraet: In Lueftungskanal

WICHTIGE KENNWERTE:
- Kuehlleistung: in kW (z.B. 2.5kW, 3.5kW)
- SEER: Effizienz Kuehlen (hoeher = besser)
- SCOP: Effizienz Heizen (hoeher = besser)
- Kaeltemittel: R32 (neu), R410A (aelter)

WAERMEPUMPEN:
- Luft-Wasser: Fuer Heizung und Warmwasser
- Luft-Luft: Nur Raumklimatisierung
- Inverter: Variable Leistung (effizienter)

INSTALLATION:
- Kaeltemittelleitung: Verbindung Innen-/Aussen
- Kondensatleitung: Wasserablauf
- Elektrik: Meist 230V, groessere 400V

SUCHSTRATEGIE:
1. Hersteller + Kuehlleistung + Typ
2. Beispiel: "daikin 3.5 kw wandgeraet"
3. Bei Ersatzteilen: Geraetemodell erfragen"""
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
            "grundfos", "wilo", "ksb", "dab", "lowara",
        ],
        "catalogs": [
            "grundfos", "wilo", "oventrop", "danfoss", "honeywell", "resideo",
            "dab", "lowara", "perma"
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
- DAB: Evosta, Evoplus

REGELUNGSTECHNIK:
- Mischer: 3-Wege oder 4-Wege
- Stellantrieb: 230V oder 24V, stromlos auf/zu
- Zonenventil: Fuer einzelne Heizkreise

SUCHSTRATEGIE:
1. Typ + Einbaulaenge + Anschluss
2. Beispiel: "grundfos alpha2 25-60 180"
3. Ersatzteile: Pumpentyp erfragen"""
    },
    
    "regelungstechnik": {
        "name": "Regelungs- und Steuerungstechnik",
        "keywords": [
            # Produkte
            "regler", "steuerung", "thermostat", "raumthermostat",
            "stellantrieb", "stellmotor", "mischer", "mischerventil",
            "dreiwegeventil", "vierwegeventil", "zonenventil", "motorventil",
            # Hersteller
            "siemens", "esbe", "meibes", "paw", "caleffi",
            "honeywell", "resideo", "danfoss", "oventrop",
        ],
        "catalogs": [
            "siemens", "esbe", "meibes", "paw", "caleffi",
            "honeywell", "resideo", "danfoss", "oventrop"
        ],
        "instructions": """=== FACHWISSEN: REGELUNGS- UND STEUERUNGSTECHNIK ===

REGLER:
- Witterungsgefuehrter Regler: Steuert nach Aussentemperatur
- Raumthermostat: Steuert nach Raumtemperatur
- Mischerregler: Steuert Mischventile
- Zonenregler: Steuert einzelne Heizkreise

MISCHER:
- 3-Wege-Mischer: Beimischschaltung
- 4-Wege-Mischer: Umlenkschaltung
- Rotierend oder Hub-Mischer
- Kvs-Wert: Durchflusskennzahl

STELLANTRIEBE:
- Thermisch: Langsam, leise, guenstig
- Motorisch: Schnell, praezise
- 230V AC oder 24V AC/DC
- Stromlos auf oder stromlos zu

ANWENDUNGEN:
- Heizkreisregelung: Vorlauftemperatur steuern
- Fussbodenheizung: Einzelraumregelung
- Pufferspeicher: Be-/Entladung steuern
- Solar: Speicherbeladung

BUSSYSTEME:
- KNX: Gebaeudeautomation
- Modbus: Industriestandard
- 0-10V: Analoge Steuerung
- OpenTherm: Heizungsregelung

SUCHSTRATEGIE:
1. Funktion + Anschluss/Leistung
2. Beispiel: "esbe 3-wege-mischer dn25"
3. Bei Stellantrieben: Spannung und Hub angeben"""
    },
    
    "druckhaltung": {
        "name": "Druckhaltung und Sicherheit",
        "keywords": [
            # Produkte
            "ausdehnungsgefaess", "mag", "druckhaltung", "membranausdehnungsgefaess",
            "sicherheitsventil", "sicherheitsgruppe", "druckminderer",
            "rueckflussverhinderer", "systemtrenner",
            # Hersteller
            "reflex", "flamco", "afriso", "watts", "caleffi",
        ],
        "catalogs": [
            "reflex", "flamco", "afriso", "watts", "caleffi"
        ],
        "instructions": """=== FACHWISSEN: DRUCKHALTUNG UND SICHERHEIT ===

AUSDEHNUNGSGEFAESSE:
- Heizung: Rot, 1.5 bar Vordruck
- Trinkwasser: Weiss/blau, 4 bar Vordruck
- Solar: Orange, hoehere Temperaturbestaendigkeit
- Groesse: Nach Anlageninhalt berechnen

SICHERHEITSVENTILE:
- Heizung: 2.5 oder 3 bar Ansprechdruck
- Trinkwasser: 6 oder 10 bar
- Membrane oder Kolben
- Mit Hebelvorrichtung zur Pruefung

DRUCKMINDERER:
- Reduziert Leitungsdruck auf Haushaltsniveau
- Einstellbar: z.B. 2-6 bar
- Mit Manometer zur Kontrolle
- Regelmassig warten!

SYSTEMTRENNER:
- Schuetzen Trinkwasser vor Rueckfliessen
- BA = Rueckflussverhinderer (einfach)
- CA = Systemtrenner (zertifiziert)
- EA = Freier Auslauf (hoechste Sicherheit)

WEITERE ARMATUREN:
- Entluefter: Automatisch oder manuell
- Schmutzfaenger: Vor empfindlichen Komponenten
- Absperrventile: Kugelhahn, Schieber

SUCHSTRATEGIE:
1. Produkt + Volumen/Druck + Anschluss
2. Beispiel: "reflex ausdehnungsgefaess 50 liter"
3. Bei Sicherheitsventilen: Ansprechdruck angeben"""
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
    
    "befestigung": {
        "name": "Befestigungstechnik",
        "keywords": [
            # Produkte
            "duebel", "anker", "schraube", "stockschraube", "gewindestange",
            "rohrschelle", "rohrhalter", "schallschutz", "schiene",
            "montageschiene", "lochband",
            # Hersteller
            "fischer", "hilti", "wuerth",
        ],
        "catalogs": [
            "fischer", "hilti"
        ],
        "instructions": """=== FACHWISSEN: BEFESTIGUNGSTECHNIK ===

DUEBEL:
- Spreizdübel: Standard für Vollbaustoffe
- Hohlraumdübel: Für Gipskarton, Hohlziegel
- Schwerlastanker: Hohe Traglasten
- Injektionsanker: Chemische Verankerung

ROHRSCHELLEN:
- Zweischraub-Schelle: Standard
- Gelenkschelle: Flexibler Winkel
- Schwingungsdämpfend: Mit Gummi-Einlage
- Schallschutz: Reduziert Körperschall

MONTAGESCHIENEN:
- C-Schiene: Universal
- Lochschiene: Für Rohrhalter
- Halteklemmen: Befestigung an Schiene

TRAGLASTEN:
- Immer auf Untergrund achten!
- Beton: Höchste Traglasten
- Mauerwerk: Mittlere Traglasten
- Gipskarton: Nur leichte Lasten

SUCHSTRATEGIE:
1. Dübeltyp + Durchmesser + Länge
2. Beispiel: "fischer duebel 10x80"
3. Bei Schellen: Rohrdurchmesser angeben"""
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
            "bwt", "gruenbeck", "judo", "syr", "honeywell", "kemper",
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
    
    "lueftung": {
        "name": "Lueftung und Ventilatoren",
        "keywords": [
            # Produkte
            "luefter", "ventilator", "lueftung", "abluft", "zuluft",
            "waermerueckgewinnung", "wrg", "kwl", "kontrollierte wohnraumlueftung",
            "badluefter", "kanalventilator", "axialluefter", "radialluefter",
            # Hersteller
            "helios", "maico", "systemair", "pluggit",
        ],
        "catalogs": [
            "helios", "maico", "systemair", "pluggit"
        ],
        "instructions": """=== FACHWISSEN: LUEFTUNG UND VENTILATOREN ===

LUEFTUNGSSYSTEME:
- Kontrollierte Wohnraumlueftung (KWL): Zentral mit WRG
- Dezentrale Lueftung: Einzelgeraete in jedem Raum
- Abluftanlage: Nur Abluft (Bad, Kueche)
- Zu-/Abluftanlage: Beides mit Waermerueckgewinnung

VENTILATOR-TYPEN:
- Badluefter: Fuer Feuchtraeume
- Kanalventilator: In Lueftungsrohr eingebaut
- Axialluefter: Hoher Volumenstrom, geringer Druck
- Radialluefter: Hoeherer Druck, leiser

WAERMERUECKGEWINNUNG (WRG):
- Plattenwaermetauscher: 70-90% Effizienz
- Rotationswaermetauscher: 80-95% Effizienz
- Kreuzstrom/Gegenstrom: Verschiedene Bauarten

KENNWERTE:
- Volumenstrom: m³/h (Kubikmeter pro Stunde)
- Schallpegel: dB(A) - niedriger ist leiser
- WRG-Grad: Waermerueckgewinnungseffizienz

STEUERUNG:
- Feuchtesensor: Startet bei hoher Luftfeuchte
- CO2-Sensor: Bedarfsgerecht nach Luftqualitaet
- Timer: Zeitgesteuert
- Nachlauf: Laeuft nach Lichtausschalten weiter

SUCHSTRATEGIE:
1. Anwendung + Volumenstrom/Rohr-Durchmesser
2. Beispiel: "helios badluefter 100"
3. Bei KWL: Wohnflaeche erfragen"""
    },
    
    "isolierung": {
        "name": "Isolierung und Daemmung",
        "keywords": [
            # Produkte
            "isolierung", "daemmung", "rohrisolierung", "rohrschale",
            "armaflex", "steinwolle", "mineralwolle", "kaeltebruecke",
            "brandschutz", "schalldaemmung",
            # Hersteller
            "armacell", "rockwool", "isover",
        ],
        "catalogs": [
            "armacell", "rockwool", "isover"
        ],
        "instructions": """=== FACHWISSEN: ISOLIERUNG UND DAEMMUNG ===

ROHRISOLIERUNG:
- Armaflex: Flexibel, fuer Kaelte und Waerme
- Steinwolle: Fuer hohe Temperaturen, Brandschutz
- PU-Schale: Hart, fuer Heizung
- Schlauch vs. Schale: Schlauch bei Montage, Schale nachtraeglich

MATERIALIEN:
- Elastomer (Armaflex): -50 bis +105°C
- Mineralwolle: bis +250°C (Heizung)
- PU-Schaum: gute Daemmung, guenstig
- PE-Schaum: Einfache Anwendung

DICKEN:
- Heizung: mind. 100% der Rohrdicke
- Kaltwasser: je nach Taupunkt
- EnEV/GEG: Mindestdicken vorgeschrieben

BRANDSCHUTZ:
- B1: Schwer entflammbar
- B2: Normal entflammbar
- A1/A2: Nicht brennbar (Mineralwolle)

ANWENDUNGEN:
- Heizungsrohre: Waermeverlust reduzieren
- Kaltwasser: Kondensat verhindern
- Lueftung: Schall und Waerme
- Sanitaer: Schallschutz (Abwasser)

SUCHSTRATEGIE:
1. Material + Rohrdurchmesser + Dicke
2. Beispiel: "armaflex 22mm 13mm"
3. Bei Brandschutz: Klasse angeben"""
    },
    
    "solar": {
        "name": "Solar und Photovoltaik",
        "keywords": [
            # Produkte
            "solar", "photovoltaik", "pv", "wechselrichter", "modul",
            "solarmodul", "solarpanel", "kollektor", "solarthermie",
            "speicher", "batteriespeicher",
            # Hersteller
            "sma", "fronius", "kostal",
        ],
        "catalogs": [
            "sma_solar"
        ],
        "instructions": """=== FACHWISSEN: SOLAR UND PHOTOVOLTAIK ===

PHOTOVOLTAIK:
- Solarmodul: Erzeugt Gleichstrom (DC)
- Wechselrichter: Wandelt DC in Wechselstrom (AC)
- Speicher: Puffert Strom fuer spaeter

WECHSELRICHTER-TYPEN:
- String-Wechselrichter: Mehrere Module in Reihe
- Mikro-Wechselrichter: Pro Modul einer
- Hybrid-Wechselrichter: Mit Speicheranschluss

KENNWERTE:
- kWp: Spitzenleistung der Anlage
- kWh: Erzeugte/gespeicherte Energie
- Wirkungsgrad: Effizienz der Umwandlung

SOLARTHERMIE:
- Flachkollektor: Standard fuer Warmwasser
- Roehrenkollektor: Hoehere Effizienz, teurer
- Speicher: Bivalent (Solar + Heizung)

MONTAGE:
- Aufdach: Auf bestehende Dachziegel
- Indach: In die Dachhaut integriert
- Flachdach: Mit Aufstaenderung

SUCHSTRATEGIE:
1. Produkt + Leistung
2. Beispiel: "sma sunny boy 5.0"
3. Bei Speichern: Kapazitaet in kWh"""
    },
    
    "kueche": {
        "name": "Kueche und Spuelen",
        "keywords": [
            # Produkte
            "spuele", "einbauspuele", "unterbauspuele", "spuelbecken",
            "kuechenarmatur", "spueltischarmatur", "brause",
            "abfallsammler", "abfalltrennung",
            # Hersteller
            "franke", "blanco", "grohe", "hansgrohe",
        ],
        "catalogs": [
            "franke", "blanco"
        ],
        "instructions": """=== FACHWISSEN: KUECHE UND SPUELEN ===

SPUELEN-TYPEN:
- Einbauspuele: Von oben eingesetzt
- Unterbauspuele: Von unten montiert (flächenbündig)
- Auflagespuele: Liegt auf Unterschrank
- Flächenbündig: In Arbeitsplatte integriert

MATERIALIEN:
- Edelstahl: Robust, hygienisch, Standard
- Silgranit/Fragranit: Granit-Verbund, viele Farben
- Keramik: Hochwertig, kratzfest
- Glas: Designvariante

BECKENFORMEN:
- Einzelbecken: Ein grosses Becken
- 1.5-Becken: Haupt- + Nebenbecken
- Doppelbecken: Zwei gleiche Becken
- Mit Abtropfflaeche: Seitlicher Bereich

ARMATUREN:
- Hoher Auslauf: Fuer grosse Toepfe
- Schwenkbar: 180° oder 360°
- Mit Brause: Ausziehbare Brause
- Sensor: Beruehrungslos

MASSE:
- Ausschnitt: Loch in Arbeitsplatte
- Beckentiefe: Meist 150-200mm
- Einbaubreite: z.B. 60cm, 80cm, 100cm

SUCHSTRATEGIE:
1. Hersteller + Beckenzahl + Masse
2. Beispiel: "blanco 1.5 becken 80cm"
3. Bei Armaturen: Mit/ohne Brause"""
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


def get_all_catalogs() -> set:
    """Gibt alle in Domains definierten Kataloge zurueck."""
    all_catalogs = set()
    for domain in PRODUCT_DOMAINS.values():
        all_catalogs.update(domain.get("catalogs", []))
    return all_catalogs


def validate_coverage(index_file: str = None) -> dict:
    """
    Prueft ob alle Kataloge aus dem Index abgedeckt sind.
    
    Returns:
        Dict mit covered, missing, extra Listen
    """
    import json
    import os
    
    if not index_file:
        # Standard-Pfad
        base_dir = os.path.dirname(os.path.dirname(__file__))
        index_file = os.path.join(base_dir, "system_katalog", "_index.json")
    
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    except Exception:
        return {"error": "Could not load index file"}
    
    # Alle Katalog-Keys aus dem Index
    index_catalogs = set()
    for system in index_data.get("systems", []):
        filename = system.get("file", "")
        if filename:
            key = filename.replace(".json", "")
            index_catalogs.add(key)
    
    # Alle Katalog-Keys aus den Domains
    domain_catalogs = get_all_catalogs()
    
    # Vergleich
    covered = index_catalogs & domain_catalogs
    missing = index_catalogs - domain_catalogs
    extra = domain_catalogs - index_catalogs
    
    return {
        "total_in_index": len(index_catalogs),
        "total_in_domains": len(domain_catalogs),
        "covered": len(covered),
        "coverage_percent": round(len(covered) / len(index_catalogs) * 100, 1) if index_catalogs else 0,
        "missing": sorted(list(missing)),
        "extra": sorted(list(extra))
    }
