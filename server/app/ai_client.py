"""
OpenAI Realtime API Client für Voice Bot.

Streamt Audio bidirektional zur OpenAI API via WebSocket.
Unterstützt Function Calling für Katalog-Suche, Bestellungen und Experten-Anfragen.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Callable, Optional, TYPE_CHECKING

import catalog
from order_manager import order_manager

if TYPE_CHECKING:
    from expert_client import ExpertClient

logger = logging.getLogger(__name__)

DEFAULT_INSTRUCTIONS = """Du bist der automatische Telefonservice von Heinrich Schmidt, einem Fachgrosshandel fuer SHK.

=== DEIN STIL ===
- Verhalte dich menschlich und natuerlich, nicht wie eine Maschine
- Sei warmherzig, locker und freundlich wie ein echter Kollege am Telefon
- Zeige echtes Interesse am Kunden
- Nutze natuerliche Sprache, keine roboterhaften Formulierungen

=== BEGRUESSUNG ===
"Guten Tag! Sie sind verbunden mit dem Bestellservice von Heinrich Schmidt. Wie kann ich Ihnen helfen?"

=== DEINE ROLLE ===
- Du nimmst Bestellungen von SHK-Profis entgegen (Installateure, Heizungsbauer)
- Du hast Zugriff auf 63 Hersteller mit tausenden Produkten
- DU findest das richtige Produkt - der Kunde muss keine Nummern kennen
- Bei komplexen Fachfragen hast du einen Experten-Kollegen

=== BESTELLABLAUF ===
So laeuft eine typische Bestellung:

1. KUNDE NENNT HERSTELLER UND PRODUKT
   - "Ich brauch eine Grohe Waschtischarmatur" oder "Viega Sanpress Bogen 22mm"
   - Falls Hersteller unklar: Frag freundlich nach

2. DU FINDEST DAS PRODUKT (im Hintergrund, ohne es zu erwaehnen!)
   - Nutze 'lade_hersteller_katalog' OHNE es dem Kunden zu sagen
   - Das geht schnell - kein "Moment" oder "ich schau mal" noetig
   - Durchsuche die Produkte und finde das passende

3. DIREKTE ANTWORT MIT PRODUKT
   - "Die Grohe Eurosmart, Artikel Nummer GR2339210E. Wieviel Stueck brauchen Sie?"
   - Bei mehreren Optionen: "Da haette ich zwei Varianten..."
   - Nach Mengenangabe: Nutze 'bestellung_hinzufuegen'

WICHTIG: Erwähne NIEMALS technische Vorgaenge wie "Katalog laden" oder "System durchsuchen"!
Das passiert im Hintergrund - der Kunde merkt davon nichts.

=== VERFUEGBARE HERSTELLER ===
SANITAER: Grohe, Hansgrohe, Geberit, Duravit, Villeroy & Boch, Ideal Standard
HEIZUNG: Viessmann, Buderus, Vaillant, Wolf, Junkers, Broetje
ROHRSYSTEME: Viega (Profipress, Sanpress, Megapress), Geberit (Mapress, Mepla)
PUMPEN: Grundfos, Wilo, Oventrop, Danfoss, Honeywell
WERKZEUGE: Rothenberger, REMS, Knipex, Makita, Milwaukee

Bei Unsicherheit: Nutze 'zeige_hersteller' fuer die komplette Liste.

=== EXPERTEN-KOLLEGE ===
Bei komplexen Fachfragen die du nicht sicher beantworten kannst:

WANN KOLLEGEN FRAGEN:
- Technische Detailfragen ("Welches Material fuer Trinkwasser?")
- Normen und Vorschriften ("Was sagt die DIN dazu?")
- Produktvergleiche ("Was ist besser, X oder Y?")
- Anwendungsempfehlungen ("Was brauche ich fuer...?")

SO GEHST DU VOR:
1. Sage: "Moment, da frag ich kurz einen Kollegen"
2. Nutze 'frage_experten' mit der Frage und Kontext
3. Gib die Antwort in eigenen Worten weiter

=== WICHTIGE REGELN ===
- Halte Antworten KURZ (2-3 Saetze)
- Frage nach Menge wenn nicht angegeben
- Wiederhole die Bestellung zur Bestaetigung
- Sage IMMER "Artikel Nummer" ausgesprochen (nie "Art.Nr.")
- Erfinde NIEMALS Artikelnummern oder Preise!
- Im Zweifel: Im Katalog nachschauen oder Kollegen fragen"""


# Verfügbare OpenAI Realtime Modelle
AVAILABLE_MODELS = [
    "gpt-realtime",
    "gpt-4o-realtime-preview-2024-12-17",
    "gpt-4o-mini-realtime-preview-2024-12-17",
    "gpt-4o-realtime-preview",
]

DEFAULT_MODEL = "gpt-realtime"

# Function Calling Tools für Multi-Hersteller Katalog
CATALOG_TOOLS = [
    {
        "type": "function",
        "name": "zeige_hersteller",
        "description": "Zeigt alle verfuegbaren Hersteller im Katalog. Nutze diese Funktion wenn der Kunde wissen will welche Hersteller verfuegbar sind oder wenn du nicht weisst welchen Hersteller er braucht.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "lade_hersteller_katalog",
        "description": "Laedt den kompletten Katalog eines Herstellers in deinen Kontext. WICHTIG: Rufe diese Funktion auf sobald du weisst welchen Hersteller der Kunde braucht! Danach hast du alle Produkte mit Artikelnummern und Preisen und kannst direkt helfen. Beispiele: 'grohe', 'villeroy_boch', 'viega_sanpress', 'buderus'",
        "parameters": {
            "type": "object",
            "properties": {
                "hersteller": {
                    "type": "string",
                    "description": "Name oder Key des Herstellers (z.B. 'Grohe', 'Villeroy Boch', 'Viega Sanpress', 'Buderus')"
                }
            },
            "required": ["hersteller"]
        }
    },
    {
        "type": "function",
        "name": "suche_produkt",
        "description": "Sucht nach Produkten in den geladenen Katalogen. Sucht nach Bezeichnung, Artikel-Nummer oder Hersteller-Nummer. WICHTIG: Lade zuerst den passenden Hersteller-Katalog bevor du suchst!",
        "parameters": {
            "type": "object",
            "properties": {
                "suchbegriff": {
                    "type": "string",
                    "description": "Wonach gesucht werden soll (Produktname, Artikelnummer oder Herstellernummer)"
                },
                "hersteller": {
                    "type": "string",
                    "description": "Optional: Nur in diesem Hersteller-Katalog suchen"
                }
            },
            "required": ["suchbegriff"]
        }
    },
    {
        "type": "function",
        "name": "zeige_produkt_details",
        "description": "Zeigt alle Details zu einem Produkt inklusive Preise. Nutze diese Funktion wenn der Kunde nach dem Preis fragt oder mehr Details zu einem Produkt braucht.",
        "parameters": {
            "type": "object",
            "properties": {
                "artikel_nummer": {
                    "type": "string",
                    "description": "Heinrich Schmidt Artikel-Nummer (z.B. 'WT+VERL80')"
                }
            },
            "required": ["artikel_nummer"]
        }
    },
    {
        "type": "function",
        "name": "bestellung_hinzufuegen",
        "description": "Fuegt ein Produkt zur aktuellen Bestellung hinzu. Nutze diese Funktion nachdem du die Artikelnummer bestaetigt hast.",
        "parameters": {
            "type": "object",
            "properties": {
                "artikel_nummer": {
                    "type": "string",
                    "description": "Heinrich Schmidt Artikel-Nummer des Produkts"
                },
                "menge": {
                    "type": "integer",
                    "description": "Bestellmenge"
                },
                "produktname": {
                    "type": "string",
                    "description": "Name des Produkts fuer die Bestaetigung"
                }
            },
            "required": ["artikel_nummer", "menge", "produktname"]
        }
    },
    {
        "type": "function",
        "name": "zeige_bestellung",
        "description": "Zeigt die aktuelle Bestellung an. Nutze diese Funktion wenn der Kunde seine Bestellung sehen oder bestaetigen will.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "frage_experten",
        "description": "Fragt einen Fachkollegen bei komplexen technischen Fragen, die du nicht sicher beantworten kannst. WICHTIG: Sage VOR dem Aufruf 'Moment, da frag ich mal kurz einen Kollegen'. Der Kollege hat Zugriff auf den kompletten Produktkatalog und tiefgehendes Fachwissen.",
        "parameters": {
            "type": "object",
            "properties": {
                "frage": {
                    "type": "string",
                    "description": "Die Frage des Kunden, klar und praezise formuliert"
                },
                "kontext": {
                    "type": "string",
                    "description": "Relevanter Kontext aus dem bisherigen Gespraech (Hersteller, Produkt, etc.)"
                },
                "dringlichkeit": {
                    "type": "string",
                    "enum": ["schnell", "normal", "gruendlich"],
                    "description": "Wie schnell braucht der Kunde die Antwort? 'schnell' fuer einfache Fragen, 'gruendlich' fuer komplexe technische Fragen wo Genauigkeit wichtig ist"
                }
            },
            "required": ["frage", "dringlichkeit"]
        }
    }
]


class AIClient:
    """
    Async Client für OpenAI Realtime API via WebSocket.
    """
    
    # Audio Formate
    INPUT_SAMPLE_RATE = 16000   # AI erwartet 16kHz
    OUTPUT_SAMPLE_RATE = 24000  # AI sendet 24kHz
    
    REALTIME_BASE_URL = "wss://api.openai.com/v1/realtime?model="
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self._ws = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        
        self.muted = False
        self.instructions = DEFAULT_INSTRUCTIONS
        self._model = model if model in AVAILABLE_MODELS else DEFAULT_MODEL
        
        # Expert Client Referenz (wird von main.py gesetzt)
        self._expert_client: Optional["ExpertClient"] = None
        
        # Event Callbacks
        self.on_audio_response: Optional[Callable[[bytes], None]] = None
        self.on_transcript: Optional[Callable[[str, str, bool], None]] = None
        self.on_interruption: Optional[Callable[[], None]] = None  # Barge-in callback
        self.on_debug_event: Optional[Callable[[str, dict], None]] = None  # Debug callback für GUI
        self.on_expert_query: Optional[Callable[[str, str], None]] = None  # Callback wenn Experte gefragt wird (frage, model)
    
    @property
    def model(self) -> str:
        """Aktuelles Modell."""
        return self._model
    
    def set_model(self, model: str) -> bool:
        """Setzt das Modell (wird beim nächsten Anruf aktiv)."""
        if model in AVAILABLE_MODELS:
            self._model = model
            logger.info(f"Modell geändert zu: {model}")
            return True
        logger.warning(f"Unbekanntes Modell: {model}")
        return False
    
    def get_realtime_url(self) -> str:
        """Generiert die Realtime API URL mit aktuellem Modell."""
        return f"{self.REALTIME_BASE_URL}{self._model}"
    
    @property
    def is_connected(self) -> bool:
        """Ist die WebSocket-Verbindung aktiv?"""
        return self._ws is not None and self._running
    
    async def connect(self):
        """Verbindung zur Realtime API aufbauen."""
        try:
            import aiohttp
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            
            realtime_url = self.get_realtime_url()
            logger.info(f"Verbinde zu OpenAI mit Modell: {self._model}")
            
            session = aiohttp.ClientSession()
            self._ws = await session.ws_connect(
                realtime_url,
                headers=headers
            )
            self._session = session
            self._running = True
            
            # Session konfigurieren
            await self._configure_session()
            
            # Receive Loop starten
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            logger.info("OpenAI Realtime API verbunden")
            
        except Exception as e:
            logger.error(f"OpenAI Verbindung fehlgeschlagen: {e}")
            self._running = False
    
    async def _configure_session(self):
        """Session mit Instruktionen und Tools konfigurieren."""
        if not self._ws:
            return
        
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.4,  # Etwas sensibler für schnellere Interruption
                    "prefix_padding_ms": 200,
                    "silence_duration_ms": 400,
                    "create_response": True  # Automatisch neue Antwort nach Interruption
                },
                "tools": CATALOG_TOOLS,
                "tool_choice": "auto"
            }
        }
        
        await self._ws.send_str(json.dumps(config))
        logger.info(f"Session konfiguriert mit {len(CATALOG_TOOLS)} Tools")
    
    async def trigger_greeting(self):
        """Löst die initiale Begrüßung aus, ohne auf Spracheingabe zu warten."""
        if not self._ws or not self._running:
            return
        
        try:
            await self._ws.send_str(json.dumps({
                "type": "response.create"
            }))
            logger.info("[OpenAI] Begrüßung ausgelöst")
        except Exception as e:
            logger.error(f"Fehler beim Auslösen der Begrüßung: {e}")
    
    async def _receive_loop(self):
        """Empfängt Events von der Realtime API."""
        if not self._ws:
            return
        
        try:
            async for msg in self._ws:
                if not self._running:
                    break
                
                if msg.type == 1:  # TEXT
                    try:
                        event = json.loads(msg.data)
                        await self._handle_event(event)
                    except json.JSONDecodeError:
                        logger.warning("Ungültiges JSON von API")
                elif msg.type == 258:  # CLOSED
                    break
                elif msg.type == 256:  # ERROR
                    logger.error(f"WebSocket Fehler: {msg.data}")
                    break
                    
        except Exception as e:
            logger.error(f"Receive Loop Fehler: {e}")
        finally:
            self._running = False
    
    async def _handle_event(self, event: dict):
        """Verarbeitet ein Event von der API."""
        event_type = event.get("type", "")
        
        # Log alle Events (außer audio.delta wegen Menge)
        if event_type not in ["response.audio.delta"]:
            logger.info(f"[OpenAI Event] {event_type}")
            # Bei interessanten Events auch Details loggen
            if "function" in event_type or "tool" in event_type:
                logger.info(f"[OpenAI Event Details] {json.dumps(event, ensure_ascii=False)[:500]}")
            
            # Debug callback für GUI
            if self.on_debug_event:
                await self.on_debug_event(event_type, event)
        
        if event_type == "response.audio.delta":
            # Audio-Chunk empfangen
            audio_b64 = event.get("delta", "")
            if audio_b64 and not self.muted:
                audio_bytes = base64.b64decode(audio_b64)
                
                # Log erstes Audio-Chunk
                if not hasattr(self, '_audio_chunk_count'):
                    self._audio_chunk_count = 0
                self._audio_chunk_count += 1
                if self._audio_chunk_count == 1:
                    logger.info(f"[OpenAI] Erstes Audio-Chunk empfangen, size={len(audio_bytes)}")
                
                if self.on_audio_response:
                    await self.on_audio_response(audio_bytes)
        
        elif event_type == "input_audio_buffer.speech_started":
            logger.info("[OpenAI] Sprache erkannt - VAD gestartet (Interruption)")
            # Bei Barge-In: Audio-Queue leeren damit User nicht auf alte Antwort wartet
            if self.on_interruption:
                await self.on_interruption()
        
        elif event_type == "input_audio_buffer.speech_stopped":
            logger.info("[OpenAI] Sprache beendet - VAD gestoppt")
        
        elif event_type == "conversation.item.input_audio_transcription.completed":
            # Caller Transkript
            text = event.get("transcript", "")
            logger.info(f"[OpenAI] Caller Transkript: {text[:100] if text else '(leer)'}...")
            if text and self.on_transcript:
                await self.on_transcript("caller", text, True)
        
        elif event_type == "response.audio_transcript.delta":
            # AI Transkript (streaming)
            text = event.get("delta", "")
            if text and self.on_transcript:
                await self.on_transcript("assistant", text, False)
        
        elif event_type == "response.audio_transcript.done":
            # AI Transkript fertig
            text = event.get("transcript", "")
            logger.info(f"[OpenAI] AI Antwort: {text[:100] if text else '(leer)'}...")
            if text and self.on_transcript:
                await self.on_transcript("assistant", text, True)
        
        elif event_type == "error":
            error = event.get("error", {})
            logger.error(f"[OpenAI] API Error: {error}")
        
        elif event_type in ["session.created", "session.updated"]:
            logger.info(f"[OpenAI] {event_type}")
        
        elif event_type == "response.created":
            logger.info("[OpenAI] AI beginnt zu antworten...")
        
        elif event_type == "response.done":
            logger.info("[OpenAI] AI Antwort abgeschlossen")
        
        elif event_type == "response.function_call_arguments.done":
            # Function Call abgeschlossen - ausführen und Ergebnis senden
            await self._handle_function_call(event)
    
    async def _handle_function_call(self, event: dict):
        """
        Führt eine Function aus und sendet das Ergebnis zurück.
        
        Args:
            event: Das function_call_arguments.done Event
        """
        call_id = event.get("call_id", "")
        name = event.get("name", "")
        arguments_str = event.get("arguments", "{}")
        
        logger.info(f"[OpenAI] Function Call: {name}({arguments_str})")
        
        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            arguments = {}
        
        # Function ausführen
        result = await self._execute_function(name, arguments)
        
        # Ergebnis an OpenAI senden
        await self._send_function_result(call_id, result)
    
    async def _execute_function(self, name: str, arguments: dict) -> str:
        """
        Führt eine Katalog- oder Bestellfunktion aus.
        
        Args:
            name: Funktionsname
            arguments: Funktionsargumente
        
        Returns:
            Ergebnis als String für AI Context
        """
        try:
            if name == "zeige_hersteller":
                logger.info("Zeige verfügbare Hersteller")
                
                manufacturers = catalog.get_available_manufacturers()
                
                if not manufacturers:
                    return "Fehler: Keine Hersteller verfügbar. Katalog-Index nicht geladen?"
                
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
                lines.append("\nNutze 'lade_hersteller_katalog' mit dem Herstellernamen um den Katalog zu laden.")
                
                return "\n".join(lines)
            
            elif name == "lade_hersteller_katalog":
                hersteller = arguments.get("hersteller", "")
                
                logger.info(f"Lade Hersteller-Katalog: {hersteller}")
                
                # Key ermitteln
                key = catalog.get_manufacturer_key(hersteller)
                if not key:
                    # Verfügbare Hersteller vorschlagen
                    manufacturers = catalog.get_available_manufacturers()
                    vorschlaege = [m["name"] for m in manufacturers[:10]]
                    return f"Hersteller '{hersteller}' nicht gefunden. Verfuegbare Hersteller (Auszug): {', '.join(vorschlaege)}. Nutze 'zeige_hersteller' fuer die komplette Liste."
                
                # Katalog laden und aktivieren
                if not catalog.activate_catalog(key):
                    return f"Fehler beim Laden des Katalogs '{hersteller}'."
                
                # Katalog für AI formatieren
                katalog_text = catalog.get_catalog_for_ai(key)
                
                logger.info(f"Katalog '{key}' geladen, {len(katalog_text)} Zeichen für AI-Context")
                
                return katalog_text
            
            elif name == "suche_produkt":
                suchbegriff = arguments.get("suchbegriff", "")
                hersteller = arguments.get("hersteller", "")
                
                logger.info(f"Suche Produkt: '{suchbegriff}' (Hersteller: {hersteller or 'alle'})")
                
                # Hersteller-Key ermitteln falls angegeben
                hersteller_key = None
                if hersteller:
                    hersteller_key = catalog.get_manufacturer_key(hersteller)
                
                # Suchen
                results = catalog.search_products(
                    query=suchbegriff,
                    hersteller_key=hersteller_key,
                    nur_aktive=True
                )
                
                if not results:
                    # Prüfen ob überhaupt Kataloge geladen sind
                    if not catalog.get_active_products():
                        return "Keine Kataloge geladen! Lade zuerst einen Hersteller-Katalog mit 'lade_hersteller_katalog'."
                    return f"Keine Produkte gefunden fuer '{suchbegriff}'."
                
                return catalog.format_search_results_for_ai(results)
            
            elif name == "zeige_produkt_details":
                artikel_nummer = arguments.get("artikel_nummer", "")
                
                logger.info(f"Zeige Produkt-Details: {artikel_nummer}")
                
                # Produkt suchen
                product = catalog.get_product_by_artikel(artikel_nummer)
                
                if not product:
                    # Vielleicht Hersteller-Nummer?
                    product = catalog.get_product_by_hersteller_nr(artikel_nummer)
                
                if not product:
                    return f"Produkt mit Nummer '{artikel_nummer}' nicht gefunden. Ist der passende Katalog geladen?"
                
                return catalog.format_product_for_ai(product, show_prices=True)
            
            elif name == "bestellung_hinzufuegen":
                artikel_nummer = arguments.get("artikel_nummer", "")
                menge = arguments.get("menge", 1)
                produktname = arguments.get("produktname", "")
                
                logger.info(f"Bestellung hinzufügen: {menge}x {produktname} (Artikel-Nr: {artikel_nummer})")
                
                # Prüfen ob Produkt existiert
                product = catalog.get_product_by_artikel(artikel_nummer)
                if not product:
                    return f"Artikel-Nummer '{artikel_nummer}' nicht im Katalog gefunden. Bitte prüfe die Nummer."
                
                # Zur Bestellung hinzufügen (mit kennung für Kompatibilität)
                order_manager.add_item(kennung=artikel_nummer, menge=menge, produktname=produktname)
                
                return f"Bestellung notiert: {menge}x {produktname} (Artikel Nummer: {artikel_nummer})"
            
            elif name == "zeige_bestellung":
                logger.info("Zeige aktuelle Bestellung")
                return order_manager.get_order_summary()
            
            elif name == "frage_experten":
                frage = arguments.get("frage", "")
                kontext = arguments.get("kontext", "")
                dringlichkeit = arguments.get("dringlichkeit", "normal")
                
                logger.info(f"[Expert] Frage an Kollegen: {frage[:100]}... (Dringlichkeit: {dringlichkeit})")
                
                if not self._expert_client:
                    logger.warning("[Expert] Kein Expert Client konfiguriert")
                    return "Leider ist gerade kein Kollege verfuegbar. Bitte versuchen Sie es spaeter noch einmal."
                
                # Experten fragen (async)
                try:
                    result = await self._expert_client.ask_expert(
                        question=frage,
                        context=kontext,
                        urgency=dringlichkeit
                    )
                    
                    # Callback für GUI
                    if self.on_expert_query:
                        try:
                            await self.on_expert_query(frage, result.get("model", "?"))
                        except Exception as e:
                            logger.warning(f"on_expert_query callback error: {e}")
                    
                    if result.get("success"):
                        antwort = result.get("antwort", "")
                        konfidenz = result.get("konfidenz", 0)
                        model = result.get("model", "?")
                        model_base = result.get("model_base", "?")
                        latency = result.get("latency_ms", 0)
                        
                        logger.info(f"[Expert] Antwort von {model} ({model_base}): {antwort[:100]}... (Konfidenz: {konfidenz:.0%}, {latency}ms)")
                        
                        return f"ANTWORT VOM KOLLEGEN ({model_base}):\n{antwort}\n\n(Konfidenz: {konfidenz:.0%})"
                    else:
                        # Experte war sich nicht sicher
                        logger.info(f"[Expert] Keine sichere Antwort: {result.get('begruendung', '?')}")
                        return result.get("antwort", "Das kann ich leider nicht sicher beantworten.")
                
                except Exception as e:
                    logger.error(f"[Expert] Fehler: {e}")
                    return "Entschuldigung, ich konnte meinen Kollegen gerade nicht erreichen."
            
            # Legacy-Support für alten Funktionsnamen
            elif name == "lade_system_katalog":
                system = arguments.get("system", "")
                logger.info(f"[Legacy] lade_system_katalog aufgerufen mit: {system}")
                
                # Mapping auf neue Katalog-Keys
                system_mapping = {
                    "temponox": "viega_profipress",
                    "sanpress": "viega_sanpress",
                    "sanpress-inox": "viega_sanpress",
                }
                
                key = system_mapping.get(system, system)
                if not catalog.activate_catalog(key):
                    return f"System '{system}' nicht gefunden."
                
                return catalog.get_catalog_for_ai(key)
            
            else:
                logger.warning(f"Unbekannte Funktion: {name}")
                return f"Funktion '{name}' nicht verfügbar."
        
        except Exception as e:
            logger.error(f"Fehler bei Funktionsausführung {name}: {e}")
            return f"Fehler bei der Verarbeitung: {e}"
    
    async def _send_function_result(self, call_id: str, result: str):
        """
        Sendet das Ergebnis einer Function an OpenAI.
        
        Args:
            call_id: ID des Function Calls
            result: Ergebnis als String
        """
        if not self._ws or not self._running:
            return
        
        try:
            # Function Output senden
            output_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result
                }
            }
            await self._ws.send_str(json.dumps(output_event))
            logger.info(f"[OpenAI] Function Ergebnis gesendet für call_id={call_id}")
            
            # AI soll antworten mit dem Ergebnis
            response_event = {
                "type": "response.create"
            }
            await self._ws.send_str(json.dumps(response_event))
            logger.info("[OpenAI] Response angefordert nach Function Call")
            
        except Exception as e:
            logger.error(f"Fehler beim Senden des Function-Ergebnisses: {e}")

    async def send_audio(self, audio_data: bytes):
        """
        Audio an die API senden.
        
        Args:
            audio_data: PCM16 Audio @ 16kHz
        """
        if not self._ws or not self._running:
            return
        
        try:
            # Log erstes Audio-Paket
            if not hasattr(self, '_sent_audio_count'):
                self._sent_audio_count = 0
            self._sent_audio_count += 1
            
            if self._sent_audio_count == 1:
                # Erste paar Bytes für Debug
                import struct
                samples = struct.unpack(f'<{min(10, len(audio_data)//2)}h', audio_data[:min(20, len(audio_data))])
                logger.info(f"[OpenAI] Erstes Audio gesendet: {len(audio_data)} bytes, erste samples: {samples}")
            
            # Audio als Base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            await self._ws.send_str(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }))
            
        except Exception as e:
            logger.warning(f"Audio senden Fehler: {e}")
    
    async def commit_audio(self):
        """Audio Buffer committen (Turn beenden)."""
        if not self._ws or not self._running:
            return
        
        try:
            await self._ws.send_str(json.dumps({
                "type": "input_audio_buffer.commit"
            }))
        except Exception as e:
            logger.debug(f"Commit Fehler: {e}")
    
    def set_instructions(self, instructions: str):
        """Setzt neue Instruktionen (werden beim nächsten Anruf aktiv)."""
        self.instructions = instructions
        logger.info(f"Instruktionen aktualisiert ({len(instructions)} Zeichen)")
    
    def set_expert_client(self, expert_client: "ExpertClient"):
        """Setzt den Expert Client für Fachfragen."""
        self._expert_client = expert_client
        logger.info("Expert Client verbunden")
    
    async def disconnect(self):
        """Verbindung trennen."""
        self._running = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            try:
                await self._ws.close()
            except:
                pass
            self._ws = None
        
        if hasattr(self, '_session') and self._session:
            try:
                await self._session.close()
            except:
                pass
            self._session = None
        
        logger.info("OpenAI Realtime API getrennt")
