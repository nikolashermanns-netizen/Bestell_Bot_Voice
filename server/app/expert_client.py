"""
Expert Client für komplexe Fachfragen.

Nutzt GPT-5 und O-Serie Modelle für tiefgehende Analyse mit Konfidenz-System.
Nur Antworten mit hoher Konfidenz werden weitergegeben.
"""

import asyncio
import json
import logging
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
DEFAULT_MIN_CONFIDENCE = 0.9

# System-Prompt für Experten-Anfragen
EXPERT_SYSTEM_PROMPT = """Du bist ein erfahrener SHK-Fachexperte (Sanitaer, Heizung, Klima) mit tiefgehendem Wissen ueber Viega-Produkte und Installationstechnik.

DEINE AUFGABE:
- Beantworte technische Fachfragen praezise und korrekt
- Nutze den Produktkatalog wenn du konkrete Produktempfehlungen geben sollst
- Sei ehrlich wenn du dir unsicher bist

WICHTIGE REGELN:
1. Antworte NUR wenn du dir sehr sicher bist (>90% Konfidenz)
2. Bei Unsicherheit: Sage klar "Das kann ich nicht sicher beantworten"
3. Nenne bei Produktempfehlungen IMMER die Artikelnummer
4. Halte deine Antwort kurz und praegnant (max 2-3 Saetze fuer Sprachausgabe)
5. Keine Vermutungen - nur gesichertes Fachwissen

ANTWORT-FORMAT:
Du MUSST immer in diesem JSON-Format antworten:
{
    "antwort": "Deine Antwort fuer den Kunden (kurz, praegnant, fuer Sprachausgabe geeignet)",
    "konfidenz": 0.0-1.0,
    "begruendung": "Kurze Begruendung fuer deine Konfidenz-Einschaetzung",
    "artikelnummern": ["Liste der genannten Artikelnummern falls vorhanden"]
}

KONFIDENZ-SKALA:
- 1.0: Absolut sicher, Fachwissen oder aus Katalog bestaetigt
- 0.9: Sehr sicher, Standardwissen
- 0.8: Ziemlich sicher, aber kleine Unsicherheit
- 0.7: Unsicher, sollte nicht weitergegeben werden
- <0.7: Zu unsicher, verweigere die Antwort

VERFUEGBARE VIEGA-SYSTEME:
- Temponox: Edelstahl-Presssystem fuer Heizung
- Sanpress: Kupfer/Rotguss-Presssystem fuer Trinkwasser
- Sanpress Inox: Edelstahl-Presssystem fuer Trinkwasser

PRODUKTTYPEN: Bogen 45°, Bogen 90°, Kappe, Muffe, Reduzierstueck, Rohr, T-Stueck, Uebergangsstueck, Verschraubung
GROESSEN: 15mm, 18mm, 22mm, 28mm, 35mm, 42mm, 54mm
"""

# Tools für Katalog-Zugriff
EXPERT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "suche_produkt",
            "description": "Sucht Produkte im Viega-Katalog nach Name oder Typ",
            "parameters": {
                "type": "object",
                "properties": {
                    "suchbegriff": {
                        "type": "string",
                        "description": "Suchbegriff (z.B. 'Bogen 90', 'T-Stueck', 'Muffe')"
                    },
                    "system": {
                        "type": "string",
                        "enum": ["temponox", "sanpress", "sanpress-inox"],
                        "description": "Optional: System-Filter"
                    },
                    "groesse": {
                        "type": "string",
                        "description": "Optional: Groessen-Filter (z.B. '22mm')"
                    }
                },
                "required": ["suchbegriff"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lade_system_katalog",
            "description": "Laedt alle Produkte eines Systems",
            "parameters": {
                "type": "object",
                "properties": {
                    "system": {
                        "type": "string",
                        "enum": ["temponox", "sanpress", "sanpress-inox"],
                        "description": "Das System dessen Katalog geladen werden soll"
                    }
                },
                "required": ["system"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "produkt_details",
            "description": "Holt Details zu einem Produkt anhand der Artikelnummer",
            "parameters": {
                "type": "object",
                "properties": {
                    "artikelnummer": {
                        "type": "string",
                        "description": "Die Artikelnummer (Kennung) des Produkts"
                    }
                },
                "required": ["artikelnummer"]
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
        
        # Callbacks
        self.on_expert_start: Optional[Callable[[str, str], None]] = None  # (frage, model)
        self.on_expert_done: Optional[Callable[[dict], None]] = None  # result
        
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
                {"role": "system", "content": EXPERT_SYSTEM_PROMPT}
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
            response = await self._client.chat.completions.create(
                model=selected_model,
                messages=messages,
                tools=EXPERT_TOOLS,
                tool_choice="auto",
                response_format={"type": "json_object"},
                temperature=0.3,  # Niedrig für konsistente Antworten
                max_tokens=1000
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
                    temperature=0.3,
                    max_tokens=1000
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
                if name == "suche_produkt":
                    products = catalog.search_product(
                        query=args.get("suchbegriff", ""),
                        system=args.get("system"),
                        size=args.get("groesse")
                    )
                    result = catalog.format_product_list(products, max_items=15)
                
                elif name == "lade_system_katalog":
                    system = args.get("system", "")
                    products = catalog.get_system_products(system)
                    
                    if not products:
                        result = f"System '{system}' nicht gefunden."
                    else:
                        # Nach Größe gruppieren
                        by_size = {}
                        for p in products:
                            size = p.get("size", "?")
                            if size not in by_size:
                                by_size[size] = []
                            by_size[size].append(p)
                        
                        lines = [f"=== {system.upper()} KATALOG ({len(products)} Produkte) ==="]
                        for size in sorted(by_size.keys()):
                            lines.append(f"\n--- {size} ---")
                            for p in by_size[size]:
                                lines.append(f"- {p['name']} | Artikel Nr: {p['kennung']}")
                        
                        result = "\n".join(lines)
                
                elif name == "produkt_details":
                    kennung = args.get("artikelnummer", "")
                    product = catalog.get_product_by_kennung(kennung)
                    
                    if product:
                        result = json.dumps(product, ensure_ascii=False, indent=2)
                    else:
                        result = f"Produkt mit Artikelnummer {kennung} nicht gefunden."
                
                else:
                    result = f"Unbekannte Funktion: {name}"
                
                logger.info(f"[Expert Tool] Ergebnis: {len(result)} Zeichen")
                
            except Exception as e:
                result = f"Fehler bei {name}: {e}"
                logger.error(f"[Expert Tool] {result}")
            
            results.append(result)
        
        return results
    
    def get_config(self) -> dict:
        """Gibt die aktuelle Konfiguration zurück."""
        return {
            "enabled_models": self._enabled_models,
            "default_model": self._default_model,
            "min_confidence": self._min_confidence,
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
        
        return changed
