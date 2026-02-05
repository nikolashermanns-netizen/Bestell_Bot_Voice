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

DEFAULT_INSTRUCTIONS = """Du bist ein erfahrener SHK-Fachberater und Viega-Experte bei einem Fachgrosshandel.

BEGRUESSUNG:
Sage am Anfang IMMER: "Sie sind verbunden mit dem Automatischen Bestellservice der Firma Heinrich Schmidt, wie kann ich Ihnen helfen?"

DEINE ROLLE:
- Du nimmst telefonische Bestellungen von SHK-Profis (Installateure, Heizungsbauer) entgegen
- Du kennst das komplette Viega-Sortiment (Temponox, Sanpress, Sanpress Inox)
- Du hilfst bei der Produktauswahl und gibst technische Beratung

WICHTIGE REGELN:
- Sprich immer auf Deutsch
- Halte deine Antworten kurz und professionell
- Frage nach Menge und Groesse wenn nicht angegeben
- Wiederhole die Bestellung zur Bestaetigung
- Sage IMMER "Artikel Nummer" statt "Art. Nr." oder "Art.Nr"
- Wenn du etwas nachschauen musst, sage "Moment, ich schau mal nach"

KATALOG LADEN - SEHR WICHTIG:
- Sobald du weisst welches System der Kunde braucht (Temponox, Sanpress oder Sanpress Inox), rufe SOFORT die Funktion 'lade_system_katalog' auf!
- Danach hast du ALLE Produkte mit Artikelnummern im Kontext und kannst direkt helfen
- Frag den Kunden welches System er braucht wenn unklar

VERFUEGBARE SYSTEME:
- temponox: Fuer Heizung
- sanpress: Trinkwasser Kupfer/Rotguss  
- sanpress-inox: Trinkwasser Edelstahl

BESTELLFORMAT:
Wenn der Kunde etwas bestellt, bestaetige so:
"[MENGE]x [PRODUKTNAME] (Artikel Nummer: [KENNUNG]) - notiert!"

Beispiel: "10x Temponox Bogen 90 Grad 22mm (Artikel Nummer: 102036) - notiert!"

Nutze 'bestellung_hinzufuegen' nach jeder bestaetigten Position.
Nutze 'zeige_bestellung' wenn der Kunde die Bestellung zusammenfassen will.

EXPERTEN-KOLLEGE - FUER KOMPLEXE FRAGEN:
Bei komplexen technischen Fragen, die du nicht sicher beantworten kannst, nutze 'frage_experten'.
Der Kollege hat tiefgehendes Fachwissen und Zugriff auf den kompletten Katalog.

WANN DEN KOLLEGEN FRAGEN:
- Technische Detailfragen (z.B. "Welches Material fuer Trinkwasser?")
- Normen und Vorschriften (z.B. "Was sagt die DIN?")
- Produktvergleiche (z.B. "Was ist der Unterschied zwischen Sanpress und Sanpress Inox?")
- Anwendungsempfehlungen (z.B. "Was brauche ich fuer eine Fussbodenheizung?")

SO FRAGST DU DEN KOLLEGEN:
1. Sage dem Kunden: "Moment, da frag ich mal kurz einen Kollegen"
2. Rufe 'frage_experten' auf mit der Frage und dem relevanten Kontext
3. Waehle die Dringlichkeit:
   - "schnell": Einfache Frage, Kunde wartet
   - "normal": Standard-Frage
   - "gruendlich": Komplexe technische Frage, Genauigkeit wichtig
4. Gib die Antwort des Kollegen in eigenen Worten an den Kunden weiter
5. Wenn der Kollege unsicher war, sage ehrlich: "Da bin ich mir leider nicht ganz sicher"

WICHTIG: Erfinde KEINE technischen Details! Bei Unsicherheit lieber den Kollegen fragen."""


# Verfügbare OpenAI Realtime Modelle
AVAILABLE_MODELS = [
    "gpt-realtime",
    "gpt-4o-realtime-preview-2024-12-17",
    "gpt-4o-mini-realtime-preview-2024-12-17",
    "gpt-4o-realtime-preview",
]

DEFAULT_MODEL = "gpt-realtime"

# Function Calling Tools für Viega Katalog
VIEGA_TOOLS = [
    {
        "type": "function",
        "name": "lade_system_katalog",
        "description": "Laedt den kompletten Katalog eines Viega-Systems in deinen Kontext. WICHTIG: Rufe diese Funktion auf sobald du weisst welches System der Kunde braucht (Temponox, Sanpress, Sanpress Inox). Danach hast du alle Produkte mit Artikelnummern und kannst dem Kunden direkt helfen.",
        "parameters": {
            "type": "object",
            "properties": {
                "system": {
                    "type": "string",
                    "enum": ["temponox", "sanpress", "sanpress-inox"],
                    "description": "Das Viega System das geladen werden soll"
                }
            },
            "required": ["system"]
        }
    },
    {
        "type": "function",
        "name": "bestellung_hinzufuegen",
        "description": "Fuegt ein Produkt zur aktuellen Bestellung hinzu. Nutze diese Funktion nachdem du die Artikelnummer bestaetigt hast.",
        "parameters": {
            "type": "object",
            "properties": {
                "produkt_kennung": {
                    "type": "string",
                    "description": "Artikelnummer des Produkts"
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
            "required": ["produkt_kennung", "menge", "produktname"]
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
                    "description": "Relevanter Kontext aus dem bisherigen Gespraech (welches System, Groesse, etc.)"
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
                "tools": VIEGA_TOOLS,
                "tool_choice": "auto"
            }
        }
        
        await self._ws.send_str(json.dumps(config))
        logger.info(f"Session konfiguriert mit {len(VIEGA_TOOLS)} Tools")
    
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
            if name == "lade_system_katalog":
                system = arguments.get("system", "")
                
                logger.info(f"Lade kompletten System-Katalog: {system}")
                
                # Alle Produkte des Systems laden
                products = catalog.get_system_products(system)
                
                if not products:
                    return f"System '{system}' nicht gefunden. Verfuegbare Systeme: temponox, sanpress, sanpress-inox"
                
                # Kompletten Katalog formatieren
                lines = [f"=== KATALOG {system.upper()} - {len(products)} Produkte ===\n"]
                
                # Nach Größe gruppieren
                by_size = {}
                for p in products:
                    size = p.get("size", "unbekannt")
                    if size not in by_size:
                        by_size[size] = []
                    by_size[size].append(p)
                
                for size in sorted(by_size.keys()):
                    lines.append(f"\n--- {size} ---")
                    for p in by_size[size]:
                        lines.append(f"- {p['name']} | Artikel Nummer: {p['kennung']}")
                
                lines.append(f"\n=== ENDE KATALOG ===")
                lines.append("Du hast jetzt alle Produkte. Hilf dem Kunden das richtige zu finden und nenne immer die Artikel Nummer.")
                
                katalog_text = "\n".join(lines)
                logger.info(f"Katalog geladen: {len(products)} Produkte, {len(katalog_text)} Zeichen")
                
                return katalog_text
            
            elif name == "bestellung_hinzufuegen":
                kennung = arguments.get("produkt_kennung", "")
                menge = arguments.get("menge", 1)
                produktname = arguments.get("produktname", "")
                
                logger.info(f"Bestellung hinzufügen: {menge}x {produktname} (Artikel Nummer {kennung})")
                
                # Prüfen ob Produkt existiert
                product = catalog.get_product_by_kennung(kennung)
                if not product:
                    return f"Artikel Nummer {kennung} nicht im Katalog gefunden. Bitte prüfe die Nummer."
                
                # Zur Bestellung hinzufügen
                order_manager.add_item(kennung=kennung, menge=menge, produktname=produktname)
                
                return f"Bestellung notiert: {menge}x {produktname} (Artikel Nummer {kennung})"
            
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
