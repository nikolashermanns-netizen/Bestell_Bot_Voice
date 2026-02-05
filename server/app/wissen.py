"""
SHK-Wissensmodul für Experten-AI.

Stellt Funktionen zur Suche in der SHK-Wissensdatenbank bereit.
Enthält Normen, Richtlinien und technische Regeln mit Quellenangaben.
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Pfade zu den Wissensdateien
WISSEN_DIR = os.path.join(os.path.dirname(__file__), "..", "wissen")
NORMEN_INDEX_PATH = os.path.join(WISSEN_DIR, "_normen_index.json")
FACHWISSEN_PATH = os.path.join(WISSEN_DIR, "_shk_fachwissen.json")
DOKUMENTE_DIR = os.path.join(WISSEN_DIR, "dokumente")

# Cache für geladene Daten
_normen_index: Dict = {}
_fachwissen: Dict = {}
_geladen: bool = False


def load_wissen() -> bool:
    """
    Lädt die Wissensdatenbanken in den Cache.
    
    Returns:
        True wenn erfolgreich
    """
    global _normen_index, _fachwissen, _geladen
    
    try:
        # Normen-Index laden
        if os.path.exists(NORMEN_INDEX_PATH):
            with open(NORMEN_INDEX_PATH, "r", encoding="utf-8") as f:
                _normen_index = json.load(f)
            logger.info(f"Normen-Index geladen: {len(_normen_index.get('normen', []))} Normen")
        else:
            logger.warning(f"Normen-Index nicht gefunden: {NORMEN_INDEX_PATH}")
            _normen_index = {"normen": [], "bereiche": {}}
        
        # Fachwissen laden
        if os.path.exists(FACHWISSEN_PATH):
            with open(FACHWISSEN_PATH, "r", encoding="utf-8") as f:
                _fachwissen = json.load(f)
            logger.info(f"Fachwissen geladen: {len(_fachwissen.get('bereiche', {}))} Bereiche")
        else:
            logger.warning(f"Fachwissen nicht gefunden: {FACHWISSEN_PATH}")
            _fachwissen = {"bereiche": {}}
        
        _geladen = True
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON-Fehler beim Laden der Wissensdatenbank: {e}")
        return False
    except Exception as e:
        logger.error(f"Fehler beim Laden der Wissensdatenbank: {e}")
        return False


def _ensure_loaded():
    """Stellt sicher, dass die Daten geladen sind."""
    if not _geladen:
        load_wissen()


def suche_normen(suchbegriff: str, bereich: str = "alle") -> List[Dict]:
    """
    Sucht nach Normen anhand eines Suchbegriffs.
    
    Args:
        suchbegriff: Suchbegriff (z.B. "Legionellen", "3-Liter")
        bereich: Fachbereich ("trinkwasser", "heizung", "gas", "abwasser", "alle")
        
    Returns:
        Liste von passenden Normen mit Regeln
    """
    _ensure_loaded()
    
    suchbegriff_lower = suchbegriff.lower()
    ergebnisse = []
    
    for norm in _normen_index.get("normen", []):
        # Bereich filtern
        if bereich != "alle" and norm.get("bereich") != bereich:
            continue
        
        # In Name, Titel, Beschreibung suchen
        text_gesamt = f"{norm.get('name', '')} {norm.get('titel', '')} {norm.get('beschreibung', '')}".lower()
        
        # In Regeln suchen
        regeln_text = ""
        passende_regeln = []
        
        for regel in norm.get("wichtige_regeln", []):
            regel_text = f"{regel.get('regel', '')} {regel.get('inhalt', '')}".lower()
            regeln_text += " " + regel_text
            
            if suchbegriff_lower in regel_text:
                passende_regeln.append(regel)
        
        # Treffer?
        if suchbegriff_lower in text_gesamt or passende_regeln:
            ergebnis = {
                "norm": norm.get("name"),
                "titel": norm.get("titel"),
                "bereich": norm.get("bereich"),
                "beschreibung": norm.get("beschreibung"),
                "passende_regeln": passende_regeln if passende_regeln else norm.get("wichtige_regeln", [])[:3]
            }
            ergebnisse.append(ergebnis)
    
    return ergebnisse


def suche_fachwissen(suchbegriff: str, bereich: str = "alle") -> Dict:
    """
    Sucht im strukturierten Fachwissen nach einem Thema.
    
    Args:
        suchbegriff: Suchbegriff (z.B. "Warmwasser Temperatur", "pH-Wert")
        bereich: Fachbereich ("trinkwasser", "heizung", "gas", "abwasser", "presssysteme", "alle")
        
    Returns:
        Dict mit gefundenen Informationen und Quellen
    """
    _ensure_loaded()
    
    # Suchbegriff normalisieren: Bindestriche durch Leerzeichen ersetzen
    suchbegriff_normalized = suchbegriff.lower().replace("-", " ").replace("_", " ")
    suchbegriffe = suchbegriff_normalized.split()
    
    # Auch den Originalbegriff für zusammengesetzte Wörter behalten
    suchbegriff_komplett = suchbegriff.lower().replace("-", "").replace("_", "").replace(" ", "")
    
    ergebnisse = {
        "suchbegriff": suchbegriff,
        "treffer": [],
        "quellen": []
    }
    
    bereiche = _fachwissen.get("bereiche", {})
    
    # Bereiche durchsuchen
    for bereich_key, bereich_data in bereiche.items():
        if bereich != "alle" and bereich_key != bereich:
            continue
        
        bereich_name = bereich_data.get("name", bereich_key)
        
        # Themen durchsuchen
        for thema_key, thema_data in bereich_data.get("themen", {}).items():
            # Thema als String serialisieren für Suche, auch normalisieren
            thema_json_raw = json.dumps(thema_data, ensure_ascii=False).lower()
            thema_json = thema_json_raw.replace("-", " ").replace("_", " ")
            
            # Auch Thema-Key durchsuchen
            thema_key_normalized = thema_key.lower().replace("-", " ").replace("_", " ")
            thema_json += " " + thema_key_normalized
            
            # Prüfen ob Suchbegriffe vorkommen
            matches = sum(1 for sb in suchbegriffe if sb in thema_json)
            
            # Bonus für zusammengesetzten Begriff
            if suchbegriff_komplett and len(suchbegriff_komplett) > 5:
                thema_json_kompakt = thema_json.replace(" ", "")
                if suchbegriff_komplett in thema_json_kompakt:
                    matches += 2  # Bonus für exakten Match
            
            if matches > 0:
                # Relevante Daten extrahieren
                treffer = {
                    "bereich": bereich_name,
                    "thema": thema_key,
                    "relevanz": matches / len(suchbegriffe),
                    "daten": thema_data
                }
                
                # Quellen extrahieren
                quellen = _extrahiere_quellen(thema_data)
                for quelle in quellen:
                    if quelle not in ergebnisse["quellen"]:
                        ergebnisse["quellen"].append(quelle)
                
                ergebnisse["treffer"].append(treffer)
    
    # Nach Relevanz sortieren
    ergebnisse["treffer"].sort(key=lambda x: x["relevanz"], reverse=True)
    
    return ergebnisse


def _extrahiere_quellen(data: Any, quellen: List[str] = None) -> List[str]:
    """Extrahiert alle Quellenangaben aus verschachtelten Daten."""
    if quellen is None:
        quellen = []
    
    if isinstance(data, dict):
        if "quelle" in data:
            quelle = data["quelle"]
            if quelle and quelle not in quellen:
                quellen.append(quelle)
        
        for value in data.values():
            _extrahiere_quellen(value, quellen)
    
    elif isinstance(data, list):
        for item in data:
            _extrahiere_quellen(item, quellen)
    
    return quellen


def get_regel_details(norm_id: str, regel_name: str = None) -> Optional[Dict]:
    """
    Holt Details zu einer spezifischen Norm oder Regel.
    
    Args:
        norm_id: ID der Norm (z.B. "din_1988_200", "dvgw_w551")
        regel_name: Optional - Name der Regel (z.B. "3-Liter-Regel")
        
    Returns:
        Dict mit Norm-/Regel-Details oder None
    """
    _ensure_loaded()
    
    norm_id_lower = norm_id.lower().replace("-", "_").replace(" ", "_")
    
    for norm in _normen_index.get("normen", []):
        if norm.get("id", "").lower() == norm_id_lower:
            if regel_name:
                # Spezifische Regel suchen
                for regel in norm.get("wichtige_regeln", []):
                    if regel_name.lower() in regel.get("regel", "").lower():
                        return {
                            "norm": norm.get("name"),
                            "titel": norm.get("titel"),
                            "regel": regel
                        }
            else:
                # Ganze Norm zurückgeben
                return norm
    
    return None


def get_werkstoff_info(werkstoff: str) -> Optional[Dict]:
    """
    Holt Informationen zu einem Werkstoff oder Presssystem.
    
    Args:
        werkstoff: Name des Werkstoffs oder Systems (z.B. "Temponox", "Edelstahl 1.4521")
        
    Returns:
        Dict mit Werkstoff-Informationen
    """
    _ensure_loaded()
    
    werkstoff_lower = werkstoff.lower()
    
    # In Fachwissen nach Werkstoffen suchen
    presssysteme = _fachwissen.get("bereiche", {}).get("presssysteme", {}).get("themen", {})
    
    # Viega Systeme
    for system_key, system_data in presssysteme.get("viega_systeme", {}).items():
        if werkstoff_lower in system_key or werkstoff_lower in str(system_data).lower():
            return {
                "hersteller": "Viega",
                "system": system_key,
                **system_data
            }
    
    # Geberit Systeme
    for system_key, system_data in presssysteme.get("geberit_systeme", {}).items():
        if werkstoff_lower in system_key or werkstoff_lower in str(system_data).lower():
            return {
                "hersteller": "Geberit",
                "system": system_key,
                **system_data
            }
    
    # Allgemeine Werkstoff-Suche in Trinkwasser-Werkstoffen
    tw_werkstoffe = _fachwissen.get("bereiche", {}).get("trinkwasser", {}).get("themen", {}).get("werkstoffe_trinkwasser", {})
    
    for werkstoff_data in tw_werkstoffe.get("zugelassen", []):
        if werkstoff_lower in werkstoff_data.get("werkstoff", "").lower():
            return {
                "typ": "zugelassen",
                **werkstoff_data
            }
    
    for werkstoff_data in tw_werkstoffe.get("nicht_fuer_trinkwasser", []):
        if werkstoff_lower in werkstoff_data.get("werkstoff", "").lower():
            return {
                "typ": "nicht_trinkwasser",
                **werkstoff_data
            }
    
    return None


def get_dokument_liste() -> List[Dict]:
    """
    Gibt eine Liste aller verfügbaren Wissensdokumente zurück.
    
    Returns:
        Liste von Dokumenten mit ID, Name und Pfad
    """
    dokumente = []
    
    # Aus Fachwissen-Index
    for dok in _fachwissen.get("dokumente", []):
        local_path = os.path.join(DOKUMENTE_DIR, f"{dok['id']}.pdf")
        dokumente.append({
            "id": dok["id"],
            "name": dok["name"],
            "kategorie": dok.get("kategorie", "allgemein"),
            "themen": dok.get("themen", []),
            "verfuegbar": os.path.exists(local_path),
            "local_path": local_path if os.path.exists(local_path) else None
        })
    
    return dokumente


def get_dokument_pfad(dokument_id: str) -> Optional[str]:
    """
    Gibt den lokalen Pfad zu einem Dokument zurück.
    
    Args:
        dokument_id: ID des Dokuments (z.B. "viega_temperaturhaltung")
        
    Returns:
        Pfad zur PDF-Datei oder None
    """
    pfad = os.path.join(DOKUMENTE_DIR, f"{dokument_id}.pdf")
    
    if os.path.exists(pfad):
        return pfad
    
    return None


def formatiere_fuer_ai(ergebnisse: Dict) -> str:
    """
    Formatiert Suchergebnisse für die AI-Ausgabe.
    
    Args:
        ergebnisse: Dict mit Sucherergebnissen
        
    Returns:
        Formatierter String
    """
    lines = []
    
    suchbegriff = ergebnisse.get("suchbegriff", "")
    treffer = ergebnisse.get("treffer", [])
    quellen = ergebnisse.get("quellen", [])
    
    if not treffer:
        return f"Keine Ergebnisse für '{suchbegriff}' gefunden."
    
    lines.append(f"=== SHK-WISSEN: {suchbegriff} ===\n")
    
    for t in treffer[:5]:  # Max 5 Treffer
        lines.append(f"BEREICH: {t['bereich']} - {t['thema']}")
        
        daten = t.get("daten", {})
        
        # Wichtigste Daten extrahieren
        if isinstance(daten, dict):
            for key, value in daten.items():
                if key in ["beschreibung", "wert", "regel"]:
                    lines.append(f"  {key}: {value}")
                elif isinstance(value, dict) and "wert" in value:
                    lines.append(f"  {key}: {value['wert']}")
                    if "quelle" in value:
                        lines.append(f"    Quelle: {value['quelle']}")
        
        lines.append("")
    
    if quellen:
        lines.append("QUELLEN:")
        for quelle in quellen[:5]:
            lines.append(f"  - {quelle}")
    
    return "\n".join(lines)


def formatiere_normen_fuer_ai(normen: List[Dict]) -> str:
    """
    Formatiert Normen-Suchergebnisse für die AI.
    
    Args:
        normen: Liste von Norm-Ergebnissen
        
    Returns:
        Formatierter String
    """
    if not normen:
        return "Keine passenden Normen gefunden."
    
    lines = ["=== RELEVANTE NORMEN ===\n"]
    
    for norm in normen[:5]:
        lines.append(f"{norm['norm']}: {norm['titel']}")
        lines.append(f"  Bereich: {norm['bereich']}")
        
        for regel in norm.get("passende_regeln", [])[:3]:
            lines.append(f"  - {regel['regel']}: {regel['inhalt']}")
            lines.append(f"    ({regel.get('abschnitt', 'k.A.')})")
        
        lines.append("")
    
    return "\n".join(lines)


# Beim Import automatisch laden
load_wissen()
