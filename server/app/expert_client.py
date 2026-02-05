"""
Expert Client für komplexe Fachfragen.

Nutzt GPT-5 und O-Serie Modelle für tiefgehende Analyse mit Konfidenz-System.
Nur Antworten mit hoher Konfidenz werden weitergegeben.
"""

import asyncio
import json
import logging
import os
from typing import Optional, Callable
from openai import AsyncOpenAI

import catalog

logger = logging.getLogger(__name__)


# Verfügbare Experten-Modelle (Stand Februar 2026)
EXPERT_MODELS = {
    # GPT-5 Familie (Basis: GPT-5, August 2025)
    "gpt-5-mini": {"base": "GPT-5", "speed": "fast", "type": "standard", "latency_sec": 10},
    "gpt-5-nano": {"base": "GPT-5", "speed": "fast", "type": "standard", "latency_sec": 24},
    "gpt-5": {"base": "GPT-5", "speed": "medium", "type": "standard", "latency_sec": 27},
    "gpt-5.2": {"base": "GPT-5", "speed": "medium", "type": "standard", "latency_sec": 30},
    # O-Serie Reasoning (Neueste Generation, April 2025)
    "o4-mini": {"base": "O-Serie", "speed": "fast", "type": "reasoning", "latency_sec": 15},
    "o3": {"base": "O-Serie", "speed": "slow", "type": "reasoning", "latency_sec": 30},
    "o3-pro": {"base": "O-Serie", "speed": "slow", "type": "reasoning", "latency_sec": 45},
}

# Default-Einstellungen
DEFAULT_MODEL = "o4-mini"
DEFAULT_MIN_CONFIDENCE = 0.6  # Niedriger, damit Empfehlungen durchkommen

# Default System-Prompt für Experten-Anfragen
DEFAULT_EXPERT_INSTRUCTIONS = """Du bist ein erfahrener SHK-Fachexperte bei Heinrich Schmidt, einem Fachgrosshandel.

=== DEIN STIL ===
- Verhalte dich menschlich und natuerlich, nicht wie eine Maschine
- Antworte warmherzig und kollegial
- Du bist ein erfahrener, hilfsbereiter Kollege - so sollst du auch klingen
- Nutze natuerliche Sprache, keine roboterhaften Formulierungen

=== DEIN ZUGRIFF ===
Du hast Zugriff auf 63 Hersteller im SHK-Bereich:
SANITAER: Grohe, Hansgrohe, Geberit, Duravit, Villeroy & Boch
HEIZUNG: Viessmann, Buderus, Vaillant, Wolf, Junkers
ROHRSYSTEME: Viega (Profipress, Sanpress, Megapress), Geberit (Mapress, Mepla)
PUMPEN: Grundfos, Wilo, Oventrop, Danfoss
WERKZEUGE: Rothenberger, REMS, Knipex, Makita

=== ABLAUF BEI PRODUKTFRAGEN ===
1. Nutze IMMER "suche_produkte" um passende Produkte zu finden!
2. Beispiel: Frage "Welcher Siphon passt zu Duravit?" -> suche_produkte("duravit siphon")
3. Gib konkrete Produktempfehlungen aus den Suchergebnissen
4. WICHTIG: Suche zuerst, antworte nicht ohne Suche!

=== SHK-WISSEN (Normen & Regeln) ===
Du hast Zugriff auf eine Wissensdatenbank mit SHK-Normen und technischen Richtlinien:
- Nutze "suche_shk_wissen" fuer Vorschriften, Grenzwerte, Normen (DIN, DVGW, VDI)
- Nutze "lade_norm_dokument" fuer die Originalquelle bei komplexen Fragen
- Bei Quellen-Nachfrage: Nenne exakten Norm-Abschnitt (z.B. "DIN 1988-200, Abschnitt 9.3")

=== WICHTIGE REGELN ===
- Bei Produktfragen: IMMER erst suchen mit "suche_produkte"!
- Nenne gefundene Produkte mit Namen (OHNE Artikelnummer - die ist intern)
- Halte Antworten kurz und praegnant (2-3 Saetze)
- Keine Vermutungen - nur gesichertes Fachwissen aus Suche oder Wissensdatenbank
- Gib NIEMALS 0% Konfidenz - nutze die Tools um eine Antwort zu finden!
- Wenn nichts gefunden: Mindestens 0.5 Konfidenz und sage was du empfehlen wuerdest

=== ANTWORT-FORMAT ===
Du MUSST immer in diesem JSON-Format antworten:
{
    "antwort": "Deine Antwort fuer den Kunden (kurz, praegnant, fuer Sprachausgabe)",
    "konfidenz": 0.0-1.0,
    "begruendung": "Kurze Begruendung fuer deine Konfidenz",
    "artikelnummern": ["Heinrich Schmidt Artikelnummern falls vorhanden"]
}

=== KONFIDENZ-SKALA ===
- 1.0: Absolut sicher, aus Produktdokumentation oder Norm bestaetigt
- 0.95: Sehr sicher, Produkt im Katalog gefunden
- 0.9: Sicher, aus SHK-Wissensdatenbank oder Standardwissen
- 0.8: Empfehlung basierend auf Suchergebnissen
- 0.7: Allgemeine Empfehlung ohne exakten Treffer
- 0.5: Beste Vermutung - empfehle Rueckfrage beim Hersteller
- NIEMALS 0%! Nutze IMMER die Tools um eine Antwort zu finden!

=== SHK-FACHWISSEN: ROHRSYSTEME ===
TRINKWASSER-GEEIGNET (DVGW zugelassen):
- Temponox (Viega): Edelstahl 1.4521 (V4A), DVGW W 534, fuer Trinkwasser geeignet
- Sanpress Inox (Viega): Edelstahl 1.4401/1.4521, DVGW zugelassen, Trinkwasser geeignet
- Profipress (Viega): Kupfer/Rotguss, DVGW zugelassen, Trinkwasser geeignet
- Mapress Edelstahl (Geberit): 1.4401/1.4521, DVGW zugelassen, Trinkwasser geeignet
- Mepla (Geberit): Mehrschicht-Verbundrohr, fuer Trinkwasser zugelassen
- Sanfix (Viega): Mehrschicht-Verbundrohr, DVGW zugelassen

NUR HEIZUNG/GAS (NICHT fuer Trinkwasser):
- Megapress (Viega): Stahl verzinkt, NUR Heizung/Gas/Druckluft
- Prestabo (Viega): Stahl verzinkt, NUR Heizung/Gas
- Mapress C-Stahl (Geberit): Kohlenstoffstahl, NUR Heizung

MATERIALIEN:
- 1.4521 / V4A: Edelstahl, korrosionsbestaendig, Trinkwasser OK
- 1.4401 / V2A: Edelstahl, Trinkwasser OK
- Kupfer: Trinkwasser OK, nicht bei pH < 7.0
- Rotguss: Trinkwasser OK, ideal fuer Armaturen
- Verzinkter Stahl: NUR Heizung, korrodiert bei Trinkwasser

=== ABLAUF JE NACH FRAGENTYP ===

PRODUKTFRAGE ("Welcher Siphon passt zu Duravit?"):
1. Nutze "suche_produkte" mit dem Produktnamen/Hersteller
2. Gib konkrete Produktempfehlungen aus den Ergebnissen
3. Konfidenz 0.8-0.95 je nach Trefferqualitaet

TECHNISCHE FRAGE ("Ist Temponox fuer Trinkwasser geeignet?"):
1. Pruefe ob du es mit dem eingebauten Fachwissen beantworten kannst
2. Wenn ja: Antworte mit 0.9+ Konfidenz
3. Wenn nein: Nutze "suche_shk_wissen" oder "lade_produkt_dokumentation"

NORMEN-FRAGE ("Was sagt die DIN dazu?"):
1. Nutze "suche_shk_wissen" mit dem Thema
2. Gib die Antwort mit Quellenangabe
3. Konfidenz 0.9-1.0

Beispiel gute Antwort:
{
    "antwort": "Fuer das Duravit Handwaschbecken empfehle ich die Geberit Ablaufgarnitur mit Stopfen. Die passt perfekt zu den 50cm Becken.",
    "konfidenz": 0.85,
    "begruendung": "Produkt im Katalog gefunden, passend fuer Duravit",
    "artikelnummern": ["GEB+151120211"]
}
"""

# Tools für Katalog-Zugriff (Multi-Hersteller)
# Der Experte lädt den Katalog und sucht dann SELBST durch die Daten
EXPERT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "zeige_hersteller",
            "description": "Zeigt alle verfuegbaren Hersteller im Katalog mit Produktanzahl. Nutze diese Funktion um herauszufinden welche Hersteller verfuegbar sind.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suche_produkte",
            "description": "Sucht Produkte im Katalog. Nutze dies um passende Produkte zu finden! Beispiele: 'duravit ablaufgarnitur', 'grohe siphon', 'viega t-stueck 22mm'. Gibt passende Produkte mit Artikelnummern zurueck.",
            "parameters": {
                "type": "object",
                "properties": {
                    "suchbegriff": {
                        "type": "string",
                        "description": "Wonach suchst du? (Produktname, Hersteller, Groesse, etc.)"
                    }
                },
                "required": ["suchbegriff"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lade_hersteller_katalog",
            "description": "Laedt den GESAMTEN Katalog eines Herstellers in deinen Kontext. Danach hast du alle Produkte mit Artikelnummern und Preisen und kannst selbst durchsuchen. Beispiele: 'grohe', 'viega_sanpress', 'buderus', 'villeroy_boch'",
            "parameters": {
                "type": "object",
                "properties": {
                    "hersteller": {
                        "type": "string",
                        "description": "Name oder Key des Herstellers (z.B. 'Grohe', 'Viega Sanpress', 'Buderus')"
                    }
                },
                "required": ["hersteller"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lade_produkt_dokumentation",
            "description": "Laedt technische Dokumentation (Datenblaetter, Montageanleitungen, PDFs) fuer ein Produkt und analysiert sie. Nutze dies wenn du 100% sichere technische Informationen brauchst (Material, Zulassungen, Einsatzbereiche). WICHTIG: Du brauchst die konkrete Artikelnummer!",
            "parameters": {
                "type": "object",
                "properties": {
                    "artikelnummer": {
                        "type": "string",
                        "description": "Heinrich Schmidt Artikelnummer (z.B. 'TEM+VS4240I', 'VIE+SA2815')"
                    }
                },
                "required": ["artikelnummer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suche_shk_wissen",
            "description": "Durchsucht die SHK-Wissensdatenbank nach Normen, Richtlinien und technischen Regeln. Gibt Quellen mit Paragraph/Abschnitt an. Nutze dies fuer Fragen zu Vorschriften, Grenzwerten, Temperaturen, DIN/VDI/DVGW Normen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thema": {
                        "type": "string",
                        "description": "Suchbegriff (z.B. 'Legionellen', '3-Liter-Regel', 'Warmwasser Temperatur', 'Heizungswasser pH')"
                    },
                    "bereich": {
                        "type": "string",
                        "enum": ["trinkwasser", "heizung", "gas", "abwasser", "presssysteme", "alle"],
                        "description": "Fachbereich einschraenken (optional, default: alle)"
                    }
                },
                "required": ["thema"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lade_norm_dokument",
            "description": "Laedt ein spezifisches Norm-/Richtlinien-Dokument (PDF) und analysiert es fuer detaillierte Informationen. Nutze dies wenn die Wissensdatenbank nicht ausreicht und du die Originalquelle brauchst.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dokument_id": {
                        "type": "string",
                        "description": "ID des Dokuments (z.B. 'viega_planungswissen', 'viega_temperaturhaltung', 'geberit_handbuch')"
                    }
                },
                "required": ["dokument_id"]
            }
        }
    }
]


class ExpertClient:
    """
    Client für Experten-Anfragen an GPT-5 und O-Serie Modelle.
    
    Implementiert ein Konfidenz-System, bei dem nur sichere Antworten
    an den Kunden weitergegeben werden.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = AsyncOpenAI(api_key=api_key)
        
        # Konfiguration
        self._enabled_models = list(EXPERT_MODELS.keys())
        self._min_confidence = DEFAULT_MIN_CONFIDENCE
        self._default_model = DEFAULT_MODEL
        self._instructions = DEFAULT_EXPERT_INSTRUCTIONS
        
        # Callbacks
        self.on_expert_start: Optional[Callable[[str, str], None]] = None  # (frage, model)
        self.on_expert_done: Optional[Callable[[dict], None]] = None  # result
        self.on_download_status: Optional[Callable[[dict], None]] = None  # Download-Status für GUI
        
        # Statistiken
        self._stats = {
            "total_requests": 0,
            "successful": 0,
            "low_confidence": 0,
            "errors": 0,
            "avg_latency_ms": 0
        }
    
    @property
    def enabled_models(self) -> list:
        """Liste der aktivierten Modelle."""
        return self._enabled_models.copy()
    
    @property
    def available_models(self) -> dict:
        """Alle verfügbaren Modelle mit Infos."""
        return EXPERT_MODELS.copy()
    
    @property
    def min_confidence(self) -> float:
        """Minimale Konfidenz für Antworten."""
        return self._min_confidence
    
    @property
    def stats(self) -> dict:
        """Statistiken."""
        return self._stats.copy()
    
    @property
    def instructions(self) -> str:
        """Aktuelle Experten-Instruktionen."""
        return self._instructions
    
    def set_instructions(self, instructions: str) -> bool:
        """Setzt die Experten-Instruktionen."""
        if instructions and len(instructions) > 10:
            self._instructions = instructions
            logger.info(f"Experten-Instruktionen aktualisiert ({len(instructions)} Zeichen)")
            return True
        return False
    
    def set_enabled_models(self, models: list) -> bool:
        """Setzt die aktivierten Modelle."""
        valid_models = [m for m in models if m in EXPERT_MODELS]
        if not valid_models:
            logger.warning("Keine gültigen Modelle angegeben")
            return False
        self._enabled_models = valid_models
        logger.info(f"Aktivierte Modelle: {valid_models}")
        return True
    
    def set_min_confidence(self, confidence: float) -> bool:
        """Setzt die minimale Konfidenz (0.5-1.0)."""
        if 0.5 <= confidence <= 1.0:
            self._min_confidence = confidence
            logger.info(f"Minimale Konfidenz: {confidence}")
            return True
        return False
    
    def set_default_model(self, model: str) -> bool:
        """Setzt das Standard-Modell."""
        if model in EXPERT_MODELS:
            self._default_model = model
            logger.info(f"Standard-Modell: {model}")
            return True
        return False
    
    def select_model(self, urgency: str) -> str:
        """
        Wählt das beste Modell basierend auf Dringlichkeit.
        
        Args:
            urgency: "schnell", "normal", oder "gruendlich"
        
        Returns:
            Modell-Name
        """
        enabled = self._enabled_models
        
        if urgency == "schnell":
            # Bevorzuge schnelle Modelle
            for model in ["gpt-5-mini", "o4-mini", "gpt-5-nano"]:
                if model in enabled:
                    return model
        elif urgency == "gruendlich":
            # Bevorzuge gründliche Modelle
            for model in ["o3-pro", "o3", "gpt-5.2", "gpt-5"]:
                if model in enabled:
                    return model
        else:  # normal
            # Balance zwischen Geschwindigkeit und Qualität
            for model in ["o4-mini", "gpt-5", "o3", "gpt-5-mini"]:
                if model in enabled:
                    return model
        
        # Fallback: erstes aktiviertes Modell
        return enabled[0] if enabled else self._default_model
    
    async def ask_expert(
        self,
        question: str,
        context: str = "",
        urgency: str = "normal",
        model: str = None
    ) -> dict:
        """
        Stellt eine Frage an das Experten-Modell.
        
        Args:
            question: Die Kundenfrage
            context: Zusätzlicher Kontext (z.B. bisheriges Gespräch)
            urgency: "schnell", "normal", oder "gruendlich"
            model: Optional: Spezifisches Modell (sonst automatische Auswahl)
        
        Returns:
            Dict mit Antwort, Konfidenz, etc.
        """
        import time
        start_time = time.time()
        
        # Modell auswählen
        selected_model = model if model and model in self._enabled_models else self.select_model(urgency)
        model_info = EXPERT_MODELS.get(selected_model, {})
        
        self._stats["total_requests"] += 1
        
        logger.info(f"[Expert] Frage an {selected_model} ({model_info.get('base', '?')}): {question[:100]}...")
        
        # Callback: Start
        if self.on_expert_start:
            try:
                await self.on_expert_start(question, selected_model)
            except Exception as e:
                logger.warning(f"on_expert_start callback error: {e}")
        
        try:
            # Nachrichten aufbauen
            messages = [
                {"role": "system", "content": self._instructions}
            ]
            
            if context:
                messages.append({
                    "role": "user",
                    "content": f"KONTEXT:\n{context}"
                })
            
            messages.append({
                "role": "user",
                "content": f"KUNDENFRAGE:\n{question}"
            })
            
            # API-Aufruf mit Tool-Unterstützung
            # HINWEIS: temperature wird nicht gesetzt, da GPT-5 Modelle nur temperature=1 unterstützen
            response = await self._client.chat.completions.create(
                model=selected_model,
                messages=messages,
                tools=EXPERT_TOOLS,
                tool_choice="auto",
                response_format={"type": "json_object"},
                max_completion_tokens=1000  # GPT-5/O-Serie benötigt diesen Parameter
            )
            
            # Tool Calls verarbeiten
            message = response.choices[0].message
            
            while message.tool_calls:
                # Tools ausführen
                tool_results = await self._execute_tools(message.tool_calls)
                
                # Ergebnisse hinzufügen
                messages.append(message)
                for tool_call, result in zip(message.tool_calls, tool_results):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
                
                # Nächste Antwort holen
                response = await self._client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    tools=EXPERT_TOOLS,
                    tool_choice="auto",
                    response_format={"type": "json_object"},
                    max_completion_tokens=1000  # GPT-5/O-Serie benötigt diesen Parameter
                )
                message = response.choices[0].message
            
            # Antwort parsen
            content = message.content or "{}"
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: Rohantwort verwenden
                result = {
                    "antwort": content,
                    "konfidenz": 0.5,
                    "begruendung": "Konnte JSON nicht parsen",
                    "artikelnummern": []
                }
            
            # Latenz berechnen
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Konfidenz prüfen
            confidence = result.get("konfidenz", 0.0)
            
            if confidence >= self._min_confidence:
                self._stats["successful"] += 1
                final_result = {
                    "success": True,
                    "antwort": result.get("antwort", ""),
                    "konfidenz": confidence,
                    "begruendung": result.get("begruendung", ""),
                    "artikelnummern": result.get("artikelnummern", []),
                    "model": selected_model,
                    "model_base": model_info.get("base", "?"),
                    "latency_ms": latency_ms
                }
            else:
                self._stats["low_confidence"] += 1
                final_result = {
                    "success": False,
                    "antwort": "Das kann ich leider nicht sicher beantworten. Da sollten Sie besser einen Fachberater kontaktieren.",
                    "konfidenz": confidence,
                    "begruendung": f"Konfidenz {confidence:.0%} unter Minimum {self._min_confidence:.0%}",
                    "artikelnummern": [],
                    "model": selected_model,
                    "model_base": model_info.get("base", "?"),
                    "latency_ms": latency_ms
                }
            
            # Durchschnittliche Latenz aktualisieren
            total = self._stats["total_requests"]
            old_avg = self._stats["avg_latency_ms"]
            self._stats["avg_latency_ms"] = int((old_avg * (total - 1) + latency_ms) / total)
            
            logger.info(f"[Expert] Antwort: konfidenz={confidence:.0%}, latency={latency_ms}ms")
            
            # Callback: Done
            if self.on_expert_done:
                try:
                    await self.on_expert_done(final_result)
                except Exception as e:
                    logger.warning(f"on_expert_done callback error: {e}")
            
            return final_result
            
        except Exception as e:
            self._stats["errors"] += 1
            latency_ms = int((time.time() - start_time) * 1000)
            
            logger.error(f"[Expert] Fehler: {e}")
            
            error_result = {
                "success": False,
                "antwort": "Entschuldigung, ich konnte die Frage gerade nicht bearbeiten. Versuchen Sie es bitte nochmal.",
                "konfidenz": 0.0,
                "begruendung": str(e),
                "artikelnummern": [],
                "model": selected_model,
                "model_base": model_info.get("base", "?"),
                "latency_ms": latency_ms,
                "error": str(e)
            }
            
            if self.on_expert_done:
                try:
                    await self.on_expert_done(error_result)
                except Exception as e2:
                    logger.warning(f"on_expert_done callback error: {e2}")
            
            return error_result
    
    async def _execute_tools(self, tool_calls: list) -> list:
        """Führt Tool-Aufrufe aus und gibt Ergebnisse zurück."""
        results = []
        
        for tool_call in tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            
            logger.info(f"[Expert Tool] {name}({args})")
            
            try:
                if name == "suche_produkte":
                    suchbegriff = args.get("suchbegriff", "")
                    
                    if not suchbegriff:
                        result = "Fehler: Kein Suchbegriff angegeben."
                    else:
                        logger.info(f"[Expert Tool] Suche Produkte: '{suchbegriff}'")
                        
                        # Erst im Keyword-Index suchen um passende Kataloge zu finden
                        keyword_result = catalog.search_keyword_index(suchbegriff)
                        
                        # Dann in den besten Katalogen suchen
                        kataloge = catalog.find_catalogs_by_keyword(suchbegriff.split()[0] if suchbegriff else "")
                        best_catalogs = kataloge.get("kataloge", [])[:5]
                        
                        all_results = []
                        for katalog_key in best_catalogs:
                            if catalog.activate_catalog(katalog_key):
                                results = catalog.search_products(
                                    query=suchbegriff,
                                    hersteller_key=katalog_key,
                                    nur_aktive=True
                                )
                                for p in results[:10]:
                                    all_results.append(p)
                        
                        if all_results:
                            lines = [f"=== {len(all_results)} Treffer fuer '{suchbegriff}' ===\n"]
                            for p in all_results[:20]:
                                bezeichnung = p.get("bezeichnung", "")
                                artikel = p.get("artikel", "")
                                hersteller = p.get("hersteller", "")
                                lines.append(f"- {bezeichnung} | Hersteller: {hersteller} | Art: {artikel}")
                            
                            if len(all_results) > 20:
                                lines.append(f"\n... und {len(all_results) - 20} weitere. Verfeinere die Suche.")
                            
                            result = "\n".join(lines)
                        else:
                            # Kein direkter Treffer - zeige Keyword-Ergebnis
                            result = f"Keine direkten Treffer fuer '{suchbegriff}'.\n\n{keyword_result}"
                
                elif name == "zeige_hersteller":
                    manufacturers = catalog.get_available_manufacturers()
                    
                    if not manufacturers:
                        result = "Fehler: Keine Hersteller verfuegbar."
                    else:
                        # Nach Kategorien gruppieren für bessere Übersicht
                        kategorien = {
                            "Sanitaer": ["grohe", "hansgrohe", "geberit", "duravit", "villeroy_boch", "ideal_standard", "keramag", "tece", "schell"],
                            "Heizung": ["viessmann", "buderus", "vaillant", "wolf_heizung", "junkers", "weishaupt", "broetje"],
                            "Rohrsysteme": ["viega_profipress", "viega_sanpress", "viega_megapress", "geberit_mapress", "geberit_mepla", "cu_press", "edelstahl_press"],
                            "Pumpen & Regelung": ["grundfos", "wilo", "oventrop", "danfoss", "honeywell", "heimeier", "caleffi"],
                            "Wasseraufbereitung": ["bwt", "gruenbeck", "judo", "syr", "kemper"],
                            "Werkzeuge": ["rothenberger", "rems", "ridgid", "knipex", "wera", "wiha", "makita", "milwaukee", "bosch_werkzeug", "hilti", "fischer"],
                        }
                        
                        lines = ["=== VERFUEGBARE HERSTELLER ===\n"]
                        
                        zugeordnet = set()
                        for kat, keys in kategorien.items():
                            kat_hersteller = [m for m in manufacturers if m["key"] in keys]
                            if kat_hersteller:
                                lines.append(f"\n{kat}:")
                                for m in kat_hersteller:
                                    lines.append(f"  - {m['name']} ({m['produkte']} Produkte)")
                                    zugeordnet.add(m["key"])
                        
                        # Restliche Hersteller
                        sonstige = [m for m in manufacturers if m["key"] not in zugeordnet]
                        if sonstige:
                            lines.append("\nSonstige:")
                            for m in sonstige:
                                lines.append(f"  - {m['name']} ({m['produkte']} Produkte)")
                        
                        lines.append(f"\nGesamt: {len(manufacturers)} Hersteller")
                        lines.append("\nNutze 'lade_hersteller_katalog' mit dem Herstellernamen.")
                        result = "\n".join(lines)
                
                elif name == "lade_hersteller_katalog":
                    hersteller = args.get("hersteller", "")
                    
                    # Key ermitteln
                    key = catalog.get_manufacturer_key(hersteller)
                    if not key:
                        # Verfügbare Hersteller vorschlagen
                        manufacturers = catalog.get_available_manufacturers()
                        vorschlaege = [m["name"] for m in manufacturers[:10]]
                        result = f"Hersteller '{hersteller}' nicht gefunden. Verfuegbare Hersteller (Auszug): {', '.join(vorschlaege)}. Nutze 'zeige_hersteller' fuer die komplette Liste."
                    else:
                        # Katalog laden und aktivieren
                        if catalog.activate_catalog(key):
                            # Gesamter Katalog für AI (mehr Produkte für Experte)
                            result = catalog.get_catalog_for_ai(key, max_products=500)
                        else:
                            result = f"Fehler beim Laden des Katalogs '{hersteller}'."
                
                elif name == "suche_shk_wissen":
                    # SHK-Wissensdatenbank durchsuchen
                    try:
                        from app.wissen import suche_normen, suche_fachwissen, formatiere_fuer_ai, formatiere_normen_fuer_ai
                        
                        thema = args.get("thema", "")
                        bereich = args.get("bereich", "alle")
                        
                        if not thema:
                            result = "Fehler: Kein Suchbegriff angegeben."
                        else:
                            logger.info(f"[Expert Tool] Suche SHK-Wissen: '{thema}' in '{bereich}'")
                            
                            # Sowohl Normen als auch Fachwissen durchsuchen
                            normen = suche_normen(thema, bereich)
                            fachwissen = suche_fachwissen(thema, bereich)
                            
                            lines = []
                            
                            # Normen-Ergebnisse
                            if normen:
                                lines.append(formatiere_normen_fuer_ai(normen))
                            
                            # Fachwissen-Ergebnisse
                            if fachwissen.get("treffer"):
                                lines.append("\n" + formatiere_fuer_ai(fachwissen))
                            
                            if lines:
                                result = "\n".join(lines)
                            else:
                                result = f"Keine Ergebnisse fuer '{thema}' in der Wissensdatenbank gefunden."
                            
                    except ImportError as ie:
                        logger.error(f"[Expert Tool] Wissen-Modul nicht verfuegbar: {ie}")
                        result = f"Fehler: Wissensmodul nicht verfuegbar ({ie})"
                    except Exception as e:
                        logger.error(f"[Expert Tool] Fehler bei SHK-Wissen-Suche: {e}")
                        result = f"Fehler bei der Suche: {e}"
                
                elif name == "lade_norm_dokument":
                    import time as time_module
                    # Norm-Dokument laden und analysieren
                    try:
                        from app.wissen import get_dokument_pfad, get_dokument_liste
                        
                        dokument_id = args.get("dokument_id", "")
                        
                        if not dokument_id:
                            # Verfügbare Dokumente auflisten
                            dokumente = get_dokument_liste()
                            if dokumente:
                                lines = ["Verfuegbare Dokumente:"]
                                for dok in dokumente:
                                    status = "verfuegbar" if dok.get("verfuegbar") else "nicht heruntergeladen"
                                    lines.append(f"  - {dok['id']}: {dok['name']} ({status})")
                                result = "\n".join(lines)
                            else:
                                result = "Keine Dokumente in der Wissensdatenbank."
                        else:
                            # Dokument laden
                            pfad = get_dokument_pfad(dokument_id)
                            
                            if not pfad:
                                # Dokument nicht vorhanden - Versuch herunterzuladen
                                dokumente = get_dokument_liste()
                                verfuegbar = [d["id"] for d in dokumente if d.get("verfuegbar")]
                                nicht_verfuegbar = [d["id"] for d in dokumente if not d.get("verfuegbar")]
                                
                                if dokument_id in nicht_verfuegbar:
                                    result = f"Dokument '{dokument_id}' ist bekannt aber noch nicht heruntergeladen. Verfuegbare Dokumente: {', '.join(verfuegbar) if verfuegbar else 'keine'}"
                                else:
                                    result = f"Dokument '{dokument_id}' nicht gefunden. Verfuegbare Dokumente: {', '.join(verfuegbar) if verfuegbar else 'keine'}"
                            else:
                                # PDF analysieren
                                logger.info(f"[Expert Tool] Lade Norm-Dokument: {dokument_id}")
                                
                                # Status: Analyse startet
                                if self.on_download_status:
                                    try:
                                        await self.on_download_status({
                                            "status": "analyzing_norm",
                                            "dokument_id": dokument_id,
                                            "message": f"Analysiere Norm-Dokument: {dokument_id}..."
                                        })
                                    except Exception as cb_err:
                                        logger.warning(f"on_download_status callback error: {cb_err}")
                                
                                # PDF analysieren
                                try:
                                    analysis_start = time_module.time()
                                    
                                    pdf_files = [{
                                        "name": f"{dokument_id}.pdf",
                                        "local_path": pfad
                                    }]
                                    
                                    analysis = await self._analyze_pdfs(pdf_files, dokument_id)
                                    analysis_duration = time_module.time() - analysis_start
                                    
                                    result = f"=== DOKUMENT: {dokument_id} ===\n\n{analysis}"
                                    
                                    # Status: Analyse abgeschlossen
                                    if self.on_download_status:
                                        try:
                                            await self.on_download_status({
                                                "status": "norm_analyzed",
                                                "dokument_id": dokument_id,
                                                "duration_sec": round(analysis_duration, 1),
                                                "message": f"Analyse abgeschlossen in {analysis_duration:.1f}s"
                                            })
                                        except Exception as cb_err:
                                            logger.warning(f"on_download_status callback error: {cb_err}")
                                            
                                except Exception as pdf_error:
                                    logger.error(f"[Expert Tool] PDF-Analyse fehlgeschlagen: {pdf_error}")
                                    result = f"Fehler bei der Analyse von {dokument_id}: {pdf_error}"
                                    
                    except ImportError as ie:
                        logger.error(f"[Expert Tool] Wissen-Modul nicht verfuegbar: {ie}")
                        result = f"Fehler: Wissensmodul nicht verfuegbar ({ie})"
                    except Exception as e:
                        logger.error(f"[Expert Tool] Fehler beim Laden des Norm-Dokuments: {e}")
                        result = f"Fehler: {e}"
                
                elif name == "lade_produkt_dokumentation":
                    import time as time_module
                    artikelnummer = args.get("artikelnummer", "")
                    
                    if not artikelnummer:
                        result = "Fehler: Keine Artikelnummer angegeben. Frage den Kunden nach der genauen Artikelnummer."
                    else:
                        logger.info(f"[Expert Tool] Lade Dokumentation fuer: {artikelnummer}")
                        
                        # Status: Download startet
                        if self.on_download_status:
                            try:
                                await self.on_download_status({
                                    "status": "start",
                                    "artikelnummer": artikelnummer,
                                    "message": f"Lade Dokumentation für {artikelnummer}..."
                                })
                            except Exception as cb_err:
                                logger.warning(f"on_download_status callback error: {cb_err}")
                        
                        try:
                            # ProductDownloader importieren und verwenden
                            import sys
                            scraper_path = os.path.join(os.path.dirname(__file__), "..", "scraper")
                            if scraper_path not in sys.path:
                                sys.path.insert(0, scraper_path)
                            
                            from product_downloads import ProductDownloader
                            
                            download_start = time_module.time()
                            downloader = ProductDownloader()
                            product_data = downloader.get_downloads_for_expert_ai(artikelnummer)
                            download_duration = time_module.time() - download_start
                            
                            if "error" in product_data:
                                result = f"Fehler: {product_data['error']}"
                                
                                # Status: Download fehlgeschlagen
                                if self.on_download_status:
                                    try:
                                        await self.on_download_status({
                                            "status": "error",
                                            "artikelnummer": artikelnummer,
                                            "message": f"Fehler: {product_data['error']}",
                                            "duration_sec": round(download_duration, 1)
                                        })
                                    except Exception as cb_err:
                                        logger.warning(f"on_download_status callback error: {cb_err}")
                            else:
                                # Alle Downloads sammeln
                                all_downloads = product_data.get("downloads", [])
                                pdf_files = [d for d in all_downloads if d.get("type") == "pdf" and d.get("local_path")]
                                
                                # Status: Download abgeschlossen
                                if self.on_download_status:
                                    try:
                                        await self.on_download_status({
                                            "status": "downloaded",
                                            "artikelnummer": artikelnummer,
                                            "product_name": product_data.get('name', 'Unbekannt'),
                                            "files": [d.get("name", "?") for d in all_downloads if d.get("local_path")],
                                            "pdf_count": len(pdf_files),
                                            "total_count": len(all_downloads),
                                            "duration_sec": round(download_duration, 1),
                                            "message": f"{len(all_downloads)} Dateien heruntergeladen in {download_duration:.1f}s"
                                        })
                                    except Exception as cb_err:
                                        logger.warning(f"on_download_status callback error: {cb_err}")
                                
                                # Produktinfo sammeln
                                lines = [
                                    f"=== PRODUKTDOKUMENTATION: {artikelnummer} ===",
                                    f"Name: {product_data.get('name', 'Unbekannt')}",
                                    f"Hersteller: {product_data.get('manufacturer', 'Unbekannt')}",
                                    f"Kategorie: {product_data.get('category', '-')} / {product_data.get('subcategory', '-')}",
                                ]
                                
                                if product_data.get('description'):
                                    lines.append(f"Beschreibung: {product_data['description']}")
                                if product_data.get('weight'):
                                    lines.append(f"Gewicht: {product_data['weight']}")
                                
                                # PDFs analysieren
                                if pdf_files:
                                    lines.append(f"\n{len(pdf_files)} PDF-Dokumente gefunden. Analysiere...")
                                    
                                    # Status: PDF-Analyse startet
                                    if self.on_download_status:
                                        try:
                                            await self.on_download_status({
                                                "status": "analyzing",
                                                "artikelnummer": artikelnummer,
                                                "pdf_count": len(pdf_files),
                                                "message": f"Analysiere {len(pdf_files)} PDFs mit GPT-5..."
                                            })
                                        except Exception as cb_err:
                                            logger.warning(f"on_download_status callback error: {cb_err}")
                                    
                                    # PDFs an GPT-5 zur Analyse senden
                                    try:
                                        analysis_start = time_module.time()
                                        analysis = await self._analyze_pdfs(pdf_files, artikelnummer)
                                        analysis_duration = time_module.time() - analysis_start
                                        
                                        lines.append("\n=== ANALYSE DER TECHNISCHEN DOKUMENTE ===")
                                        lines.append(analysis)
                                        
                                        # Status: Analyse abgeschlossen
                                        if self.on_download_status:
                                            try:
                                                await self.on_download_status({
                                                    "status": "complete",
                                                    "artikelnummer": artikelnummer,
                                                    "pdf_count": len(pdf_files),
                                                    "analysis_duration_sec": round(analysis_duration, 1),
                                                    "total_duration_sec": round(download_duration + analysis_duration, 1),
                                                    "message": f"Analyse abgeschlossen in {analysis_duration:.1f}s (Gesamt: {download_duration + analysis_duration:.1f}s)"
                                                })
                                            except Exception as cb_err:
                                                logger.warning(f"on_download_status callback error: {cb_err}")
                                                
                                    except Exception as pdf_error:
                                        logger.error(f"[Expert Tool] PDF-Analyse fehlgeschlagen: {pdf_error}")
                                        lines.append(f"\nPDF-Analyse fehlgeschlagen: {pdf_error}")
                                        # Zumindest die Dateinamen auflisten
                                        lines.append("Verfuegbare Dokumente:")
                                        for pdf in pdf_files:
                                            lines.append(f"  - {pdf.get('name', 'Unbekannt')}")
                                        
                                        # Status: Analyse fehlgeschlagen
                                        if self.on_download_status:
                                            try:
                                                await self.on_download_status({
                                                    "status": "analysis_error",
                                                    "artikelnummer": artikelnummer,
                                                    "message": f"PDF-Analyse fehlgeschlagen: {pdf_error}"
                                                })
                                            except Exception as cb_err:
                                                logger.warning(f"on_download_status callback error: {cb_err}")
                                else:
                                    lines.append("\nKeine PDF-Dokumente verfuegbar.")
                                
                                result = "\n".join(lines)
                                
                        except ImportError as ie:
                            logger.error(f"[Expert Tool] Import-Fehler: {ie}")
                            result = f"Fehler: ProductDownloader nicht verfuegbar ({ie})"
                        except Exception as e:
                            logger.error(f"[Expert Tool] Fehler bei Dokumentation: {e}")
                            result = f"Fehler beim Laden der Dokumentation: {e}"
                
                else:
                    result = f"Unbekannte Funktion: {name}"
                
                logger.info(f"[Expert Tool] Ergebnis: {len(result)} Zeichen")
                
            except Exception as e:
                result = f"Fehler bei {name}: {e}"
                logger.error(f"[Expert Tool] {result}")
            
            results.append(result)
        
        return results
    
    async def _analyze_pdfs(self, pdf_files: list, artikelnummer: str) -> str:
        """
        Analysiert PDF-Dokumente mit GPT-5 File-Upload.
        
        Args:
            pdf_files: Liste von Dicts mit 'name' und 'local_path'
            artikelnummer: Artikelnummer für Kontext
            
        Returns:
            Analyse-Text aus den Dokumenten
        """
        import base64
        
        logger.info(f"[Expert PDF] Analysiere {len(pdf_files)} PDFs fuer {artikelnummer}")
        
        # PDF-Inhalte laden und als Base64 kodieren (max 3 PDFs)
        pdf_contents = []
        for pdf in pdf_files[:3]:
            try:
                local_path = pdf.get("local_path", "")
                if local_path and os.path.exists(local_path):
                    with open(local_path, "rb") as f:
                        content = base64.b64encode(f.read()).decode()
                        pdf_contents.append({
                            "name": pdf.get("name", "Dokument"),
                            "content": content
                        })
                        logger.info(f"[Expert PDF] Geladen: {pdf.get('name')} ({len(content)} Bytes base64)")
            except Exception as e:
                logger.warning(f"[Expert PDF] Konnte PDF nicht laden: {e}")
        
        if not pdf_contents:
            return "Keine PDFs konnten geladen werden."
        
        # An GPT-5 mit File-Input senden
        try:
            # Multimodal-Nachricht mit PDFs erstellen
            user_content = [
                {
                    "type": "text", 
                    "text": f"""Analysiere die technischen Dokumente fuer Artikel {artikelnummer}.

Extrahiere folgende Informationen (falls vorhanden):
1. MATERIAL: Aus welchem Material ist das Produkt? (z.B. Edelstahl 1.4521, Kupfer, etc.)
2. ZULASSUNGEN: Welche Zulassungen hat es? (DVGW, KTW, WRAS, etc.)
3. EINSATZBEREICHE: Wofuer ist es geeignet? (Trinkwasser, Heizung, Gas, etc.)
4. TECHNISCHE DATEN: Temperatur, Druck, Abmessungen
5. WICHTIGE HINWEISE: Besondere Einschraenkungen oder Anforderungen

Antworte praegnant und strukturiert."""
                }
            ]
            
            # PDFs als File-Attachments hinzufügen
            for pdf in pdf_contents:
                user_content.append({
                    "type": "file",
                    "file": {
                        "filename": pdf["name"],
                        "file_data": f"data:application/pdf;base64,{pdf['content']}"
                    }
                })
            
            messages = [
                {
                    "role": "system", 
                    "content": "Du bist ein technischer Dokumenten-Analyst fuer SHK-Produkte. Extrahiere relevante technische Informationen aus den Dokumenten."
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
            
            # GPT-5 für Dokumentenanalyse verwenden (besser für multimodal)
            # HINWEIS: temperature wird nicht gesetzt, da GPT-5 Modelle nur temperature=1 unterstützen
            response = await self._client.chat.completions.create(
                model="gpt-5",
                messages=messages,
                max_completion_tokens=1500
            )
            
            analysis = response.choices[0].message.content
            logger.info(f"[Expert PDF] Analyse erhalten: {len(analysis)} Zeichen")
            
            return analysis
            
        except Exception as e:
            logger.error(f"[Expert PDF] API-Fehler: {e}")
            
            # Fallback: Nur Dateinamen auflisten
            return f"PDF-Analyse fehlgeschlagen ({e}). Dokumente: {', '.join([p['name'] for p in pdf_contents])}"
    
    def get_config(self) -> dict:
        """Gibt die aktuelle Konfiguration zurück."""
        return {
            "enabled_models": self._enabled_models,
            "default_model": self._default_model,
            "min_confidence": self._min_confidence,
            "instructions": self._instructions,
            "available_models": {
                name: {
                    "base": info["base"],
                    "speed": info["speed"],
                    "type": info["type"],
                    "latency_sec": info["latency_sec"],
                    "enabled": name in self._enabled_models
                }
                for name, info in EXPERT_MODELS.items()
            }
        }
    
    def set_config(self, config: dict) -> bool:
        """Setzt die Konfiguration."""
        changed = False
        
        if "enabled_models" in config:
            if self.set_enabled_models(config["enabled_models"]):
                changed = True
        
        if "default_model" in config:
            if self.set_default_model(config["default_model"]):
                changed = True
        
        if "min_confidence" in config:
            if self.set_min_confidence(config["min_confidence"]):
                changed = True
        
        if "instructions" in config:
            if self.set_instructions(config["instructions"]):
                changed = True
        
        return changed
