"""
Bestell Bot Voice Server
========================
FastAPI Backend mit PJSIP SIP Client und OpenAI Realtime API Integration.
"""

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from sip_client import SIPClient
from ai_client import AIClient, AVAILABLE_MODELS
from expert_client import ExpertClient, EXPERT_MODELS
from connection_manager import ConnectionManager
from catalog import load_catalog, get_systems_overview
from order_manager import order_manager
import ipaddress

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Global instances
sip_client: SIPClient = None
ai_client: AIClient = None
expert_client: ExpertClient = None
manager = ConnectionManager()

# ============== IP Whitelist für SIP ==============
# Sipgate (netzquadrat GmbH) IP-Ranges
# Nur Anrufe von diesen IPs werden akzeptiert
ALLOWED_SIP_NETWORKS = [
    ipaddress.ip_network("217.10.0.0/16"),      # Sipgate Hauptnetz (netzquadrat)
    ipaddress.ip_network("212.9.32.0/19"),      # Sipgate Infrastruktur
    ipaddress.ip_network("95.174.128.0/20"),    # Sipgate zusätzlich
    ipaddress.ip_network("2001:ab7::/32"),      # Sipgate IPv6
]


def is_ip_allowed(ip_str: str) -> bool:
    """Prüft ob eine IP-Adresse von einem erlaubten SIP-Provider stammt."""
    if not ip_str:
        logger.warning("Keine Remote-IP verfügbar - Anruf wird abgelehnt")
        return False
    
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in ALLOWED_SIP_NETWORKS:
            if ip in network:
                return True
        return False
    except ValueError as e:
        logger.warning(f"Ungültige IP-Adresse '{ip_str}': {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    global sip_client, ai_client, expert_client
    
    logger.info("=== Bestell Bot Voice Server startet ===")
    
    # SIP Client initialisieren
    sip_client = SIPClient(
        server=settings.SIP_SERVER,
        port=settings.SIP_PORT,
        user=settings.SIP_USER,
        password=settings.SIP_PASSWORD
    )
    
    # AI Client initialisieren
    ai_client = AIClient(api_key=settings.OPENAI_API_KEY)
    
    # Expert Client initialisieren
    expert_client = ExpertClient(api_key=settings.OPENAI_API_KEY)
    ai_client.set_expert_client(expert_client)
    
    # Expert Client Callbacks
    expert_client.on_expert_start = on_expert_start
    expert_client.on_expert_done = on_expert_done
    
    logger.info(f"Expert Client initialisiert mit {len(EXPERT_MODELS)} Modellen")
    
    # Gespeicherte Instructions, Model und Expert-Config laden
    try:
        import json
        with open("/app/config/config.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if "instructions" in data:
                ai_client.set_instructions(data["instructions"])
                logger.info("Gespeicherte Instructions geladen")
            if "model" in data:
                ai_client.set_model(data["model"])
                logger.info(f"Gespeichertes Model geladen: {data['model']}")
            if "expert_config" in data:
                expert_client.set_config(data["expert_config"])
                logger.info("Gespeicherte Expert-Konfiguration geladen")
    except FileNotFoundError:
        logger.info("Keine gespeicherte Konfiguration gefunden, verwende Defaults")
    except Exception as e:
        logger.warning(f"Fehler beim Laden der Konfiguration: {e}")
    
    # Viega Katalog laden
    if load_catalog():
        overview = get_systems_overview()
        logger.info(f"Viega Katalog: {overview.get('total_products', 0)} Produkte geladen")
    else:
        logger.warning("Viega Katalog konnte nicht geladen werden")
    
    # Order Manager Callback für GUI-Updates
    order_manager.on_order_update = on_order_update
    
    # Event Handler verbinden
    sip_client.on_incoming_call = on_incoming_call
    sip_client.on_audio_received = on_audio_from_caller
    sip_client.on_call_ended = on_call_ended
    
    ai_client.on_audio_response = on_audio_from_ai
    ai_client.on_transcript = on_transcript
    ai_client.on_interruption = on_interruption
    ai_client.on_debug_event = on_debug_event
    
    # SIP Client starten
    await sip_client.start()
    logger.info("SIP Client gestartet")
    
    yield
    
    # Cleanup
    logger.info("Server wird heruntergefahren...")
    await sip_client.stop()
    await ai_client.disconnect()


app = FastAPI(
    title="Bestell Bot Voice API",
    description="SIP-basierter Voice Bot mit OpenAI Realtime API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS für lokale GUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Audio Resampling ==============

import numpy as np
from scipy import signal as scipy_signal

def resample_audio(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resampelt PCM16 Audio von einer Sample-Rate zur anderen."""
    if from_rate == to_rate:
        return audio_data
    
    # Bytes zu numpy array (16-bit signed)
    samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
    
    # Resampling
    num_samples = int(len(samples) * to_rate / from_rate)
    resampled = scipy_signal.resample(samples, num_samples)
    
    # Zurück zu 16-bit signed
    resampled = np.clip(resampled, -32768, 32767).astype(np.int16)
    
    return resampled.tobytes()


# ============== Event Handlers ==============

# Audio Statistics
_audio_stats = {
    "caller_to_ai": 0,
    "ai_to_caller": 0,
    "caller_bytes": 0,
    "ai_bytes": 0
}

def on_order_update(order_data: dict):
    """Callback wenn die Bestellung aktualisiert wird."""
    # asyncio broadcast in sync context
    asyncio.create_task(manager.broadcast({
        "type": "order_update",
        "order": order_data
    }))


async def on_expert_start(question: str, model: str):
    """Callback wenn eine Experten-Anfrage gestartet wird."""
    await manager.broadcast({
        "type": "expert_query_start",
        "question": question[:200],
        "model": model
    })


async def on_expert_done(result: dict):
    """Callback wenn eine Experten-Anfrage abgeschlossen ist."""
    await manager.broadcast({
        "type": "expert_query_done",
        "success": result.get("success", False),
        "model": result.get("model", "?"),
        "model_base": result.get("model_base", "?"),
        "confidence": result.get("konfidenz", 0),
        "latency_ms": result.get("latency_ms", 0),
        "answer_preview": result.get("antwort", "")[:100]
    })


async def on_incoming_call(caller_id: str, remote_ip: str = None):
    """Wird aufgerufen wenn ein Anruf eingeht."""
    logger.info(f"Eingehender Anruf von: {caller_id} (Remote-IP: {remote_ip})")
    
    # IP-Whitelist prüfen
    if not is_ip_allowed(remote_ip):
        logger.warning(f"ABGELEHNT: Anruf von nicht autorisierter IP {remote_ip} ({caller_id})")
        await sip_client.reject_call(403)  # 403 Forbidden
        await manager.broadcast({
            "type": "call_rejected",
            "caller_id": caller_id,
            "remote_ip": remote_ip,
            "reason": "IP nicht auf Whitelist"
        })
        return
    
    logger.info(f"IP {remote_ip} ist autorisiert (Sipgate)")
    
    # Reset stats
    _audio_stats["caller_to_ai"] = 0
    _audio_stats["ai_to_caller"] = 0
    _audio_stats["caller_bytes"] = 0
    _audio_stats["ai_bytes"] = 0
    
    # Neue Bestellung starten
    order_manager.start_order(caller_id)
    
    # Alle GUI Clients benachrichtigen
    await manager.broadcast({
        "type": "call_incoming",
        "caller_id": caller_id
    })
    
    # Auto-Accept: Anruf annehmen und AI verbinden
    await sip_client.accept_call()
    await ai_client.connect()
    
    # AI startet nach 1 Sekunde Verzögerung mit der Begrüßung
    async def delayed_greeting():
        await asyncio.sleep(1.0)
        await ai_client.trigger_greeting()
    
    asyncio.create_task(delayed_greeting())
    
    await manager.broadcast({
        "type": "call_active",
        "caller_id": caller_id
    })


async def on_audio_from_caller(audio_data: bytes):
    """Audio vom Anrufer empfangen (48kHz) - an AI weiterleiten (16kHz)."""
    _audio_stats["caller_to_ai"] += 1
    _audio_stats["caller_bytes"] += len(audio_data)
    
    # Log alle 50 Pakete
    if _audio_stats["caller_to_ai"] % 50 == 1:
        logger.info(f"[AUDIO] Caller->AI: {_audio_stats['caller_to_ai']} Pakete, {_audio_stats['caller_bytes']} Bytes")
    
    if ai_client and ai_client.is_connected:
        # Resample 48kHz -> 16kHz für AI Input
        try:
            resampled = resample_audio(audio_data, 48000, 16000)
            await ai_client.send_audio(resampled)
        except Exception as e:
            logger.warning(f"Audio Resample Fehler (Caller->AI): {e}")
    else:
        if _audio_stats["caller_to_ai"] == 1:
            logger.warning("AI nicht verbunden - Audio wird verworfen")


async def on_audio_from_ai(audio_data: bytes):
    """Audio von AI empfangen (24kHz) - an Anrufer weiterleiten (48kHz)."""
    _audio_stats["ai_to_caller"] += 1
    _audio_stats["ai_bytes"] += len(audio_data)
    
    # Log alle 50 Pakete
    if _audio_stats["ai_to_caller"] % 50 == 1:
        logger.info(f"[AUDIO] AI->Caller: {_audio_stats['ai_to_caller']} Pakete, {_audio_stats['ai_bytes']} Bytes")
    
    if sip_client and sip_client.is_in_call:
        # Resample 24kHz -> 48kHz für SIP/Opus
        try:
            resampled = resample_audio(audio_data, 24000, 48000)
            await sip_client.send_audio(resampled)
        except Exception as e:
            logger.warning(f"Audio Resample Fehler (AI->Caller): {e}")
    else:
        if _audio_stats["ai_to_caller"] == 1:
            logger.warning("Kein aktiver Anruf - AI Audio wird verworfen")


async def on_transcript(role: str, text: str, is_final: bool):
    """Transkript-Update von AI."""
    await manager.broadcast({
        "type": "transcript",
        "role": role,
        "text": text,
        "is_final": is_final
    })


async def on_interruption():
    """User hat die AI unterbrochen (Barge-In) - Audio-Queue leeren."""
    if sip_client:
        cleared = sip_client.clear_audio_queue()
        if cleared > 0:
            logger.info(f"[INTERRUPTION] Audio-Queue geleert: {cleared} Frames verworfen")


async def on_debug_event(event_type: str, event_data: dict):
    """Debug-Event von OpenAI - an GUI senden."""
    # Nur bestimmte Events senden (nicht zu viel Traffic)
    if event_type not in ["input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped", 
                          "input_audio_buffer.committed", "response.audio_transcript.delta"]:
        # Event-Daten kürzen für Transport
        debug_data = {
            "type": event_type,
            "data": {}
        }
        
        # Wichtige Felder extrahieren
        for key in ["name", "call_id", "arguments", "transcript", "error", "text", "output"]:
            if key in event_data:
                value = event_data[key]
                if isinstance(value, str) and len(value) > 200:
                    value = value[:200] + "..."
                debug_data["data"][key] = value
        
        await manager.broadcast({
            "type": "debug_event",
            "event": debug_data
        })


async def on_call_ended(reason: str):
    """Anruf beendet."""
    logger.info(f"Anruf beendet: {reason}")
    
    # Bestellung Zusammenfassung loggen
    order = order_manager.get_current_order()
    if order.get("items"):
        logger.info(f"Bestellung bei Anrufende: {len(order['items'])} Positionen")
        for item in order["items"]:
            logger.info(f"  - {item['menge']}x {item['produktname']} ({item['kennung']})")
    
    # Bestellung löschen (wird nur im Speicher gehalten)
    order_manager.clear_order()
    
    await ai_client.disconnect()
    
    await manager.broadcast({
        "type": "call_ended",
        "reason": reason
    })


# ============== REST API Endpoints ==============

@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "running",
        "sip_registered": sip_client.is_registered if sip_client else False,
        "call_active": sip_client.is_in_call if sip_client else False
    }


@app.get("/status")
async def get_status():
    """Detaillierter Status."""
    return {
        "sip": {
            "registered": sip_client.is_registered if sip_client else False,
            "server": settings.SIP_SERVER,
            "user": settings.SIP_USER,
            "in_call": sip_client.is_in_call if sip_client else False,
            "caller_id": sip_client.current_caller_id if sip_client else None
        },
        "ai": {
            "connected": ai_client.is_connected if ai_client else False
        }
    }


@app.post("/call/accept")
async def accept_call():
    """Manuell Anruf annehmen."""
    if sip_client and sip_client.has_incoming_call:
        await sip_client.accept_call()
        return {"status": "accepted"}
    return {"status": "no_incoming_call"}


@app.post("/call/hangup")
async def hangup_call():
    """Anruf beenden."""
    if sip_client and sip_client.is_in_call:
        await sip_client.hangup()
        return {"status": "hungup"}
    return {"status": "no_active_call"}


@app.post("/ai/mute")
async def mute_ai():
    """AI stumm schalten."""
    if ai_client:
        ai_client.muted = True
        return {"status": "muted"}
    return {"status": "error"}


@app.post("/ai/unmute")
async def unmute_ai():
    """AI Stummschaltung aufheben."""
    if ai_client:
        ai_client.muted = False
        return {"status": "unmuted"}
    return {"status": "error"}


@app.get("/instructions")
async def get_instructions():
    """Aktuelle AI-Instruktionen abrufen."""
    if ai_client:
        return {"instructions": ai_client.instructions}
    return {"instructions": ""}


@app.post("/instructions")
async def set_instructions(data: dict):
    """AI-Instruktionen setzen (werden beim nächsten Anruf aktiv)."""
    if ai_client:
        instructions = data.get("instructions", "")
        ai_client.set_instructions(instructions)
        
        # Persistieren in Datei (bestehende Config beibehalten)
        try:
            import json
            import os
            os.makedirs("/app/config", exist_ok=True)
            
            # Lade bestehende Config
            config_data = {}
            try:
                with open("/app/config/config.json", "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except FileNotFoundError:
                pass
            
            config_data["instructions"] = instructions
            
            with open("/app/config/config.json", "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Konnte Instructions nicht speichern: {e}")
        
        return {"status": "ok", "length": len(instructions)}
    return {"status": "error"}


@app.get("/model")
async def get_model():
    """Aktuelles AI-Modell und verfügbare Modelle abrufen."""
    if ai_client:
        return {
            "model": ai_client.model,
            "available_models": AVAILABLE_MODELS
        }
    return {"model": "", "available_models": AVAILABLE_MODELS}


@app.post("/model")
async def set_model(data: dict):
    """AI-Modell setzen (wird beim nächsten Anruf aktiv)."""
    if ai_client:
        model = data.get("model", "")
        if ai_client.set_model(model):
            # Persistieren in Datei
            try:
                import json
                import os
                os.makedirs("/app/config", exist_ok=True)
                
                # Lade bestehende Config
                config_data = {}
                try:
                    with open("/app/config/config.json", "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                except FileNotFoundError:
                    pass
                
                config_data["model"] = model
                
                with open("/app/config/config.json", "w", encoding="utf-8") as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Konnte Model nicht speichern: {e}")
            
            return {"status": "ok", "model": model}
        return {"status": "error", "message": "Unbekanntes Modell"}
    return {"status": "error"}


# ============== Order Endpoints ==============

@app.get("/order")
async def get_current_order():
    """Aktuelle Bestellung abrufen."""
    return order_manager.get_current_order()


@app.delete("/order")
async def clear_current_order():
    """Aktuelle Bestellung löschen."""
    order_manager.clear_order()
    return {"status": "cleared"}


# ============== Expert Endpoints ==============

@app.get("/expert/config")
async def get_expert_config():
    """Experten-Konfiguration abrufen."""
    if expert_client:
        return expert_client.get_config()
    return {"error": "Expert Client nicht verfügbar"}


@app.post("/expert/config")
async def set_expert_config(data: dict):
    """Experten-Konfiguration setzen."""
    if expert_client:
        expert_client.set_config(data)
        
        # Persistieren in Datei
        try:
            import json
            import os
            os.makedirs("/app/config", exist_ok=True)
            
            # Lade bestehende Config
            config_data = {}
            try:
                with open("/app/config/config.json", "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except FileNotFoundError:
                pass
            
            config_data["expert_config"] = expert_client.get_config()
            
            with open("/app/config/config.json", "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Konnte Expert-Config nicht speichern: {e}")
        
        return {"status": "ok", "config": expert_client.get_config()}
    return {"status": "error"}


@app.get("/expert/models")
async def get_expert_models():
    """Verfügbare Experten-Modelle abrufen."""
    if expert_client:
        config = expert_client.get_config()
        return {
            "available_models": config.get("available_models", {}),
            "enabled_models": config.get("enabled_models", []),
            "default_model": config.get("default_model", "")
        }
    return {"available_models": EXPERT_MODELS, "enabled_models": [], "default_model": ""}


@app.post("/expert/models")
async def set_expert_models(data: dict):
    """Experten-Modelle aktivieren/deaktivieren."""
    if expert_client:
        if "enabled_models" in data:
            expert_client.set_enabled_models(data["enabled_models"])
        if "default_model" in data:
            expert_client.set_default_model(data["default_model"])
        
        # Persistieren
        try:
            import json
            import os
            os.makedirs("/app/config", exist_ok=True)
            
            config_data = {}
            try:
                with open("/app/config/config.json", "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except FileNotFoundError:
                pass
            
            config_data["expert_config"] = expert_client.get_config()
            
            with open("/app/config/config.json", "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Konnte Expert-Models nicht speichern: {e}")
        
        return {"status": "ok", "enabled_models": expert_client.enabled_models}
    return {"status": "error"}


@app.get("/expert/stats")
async def get_expert_stats():
    """Experten-Statistiken abrufen."""
    if expert_client:
        return expert_client.stats
    return {"error": "Expert Client nicht verfügbar"}


@app.get("/expert/instructions")
async def get_expert_instructions():
    """Experten-Instruktionen abrufen."""
    if expert_client:
        return {"instructions": expert_client.instructions}
    return {"instructions": ""}


@app.post("/expert/instructions")
async def set_expert_instructions(data: dict):
    """Experten-Instruktionen setzen."""
    if expert_client:
        instructions = data.get("instructions", "")
        if expert_client.set_instructions(instructions):
            # Persistieren
            try:
                import json
                import os
                os.makedirs("/app/config", exist_ok=True)
                
                config_data = {}
                try:
                    with open("/app/config/config.json", "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                except FileNotFoundError:
                    pass
                
                config_data["expert_config"] = expert_client.get_config()
                
                with open("/app/config/config.json", "w", encoding="utf-8") as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                logger.warning(f"Konnte Expert-Instructions nicht speichern: {e}")
            
            return {"status": "ok", "length": len(instructions)}
        return {"status": "error", "message": "Instruktionen zu kurz"}
    return {"status": "error"}


# ============== WebSocket für Live-Updates ==============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket für Live-Updates an die GUI.
    
    Sendet:
    - call_incoming: Neuer eingehender Anruf
    - call_active: Anruf aktiv
    - call_ended: Anruf beendet
    - transcript: Transkript-Updates
    - audio_level: Audio-Pegel (optional)
    """
    await manager.connect(websocket)
    
    # Initial Status senden
    await websocket.send_json({
        "type": "status",
        "sip_registered": sip_client.is_registered if sip_client else False,
        "call_active": sip_client.is_in_call if sip_client else False
    })
    
    try:
        while True:
            # Auf Nachrichten von GUI warten
            data = await websocket.receive_json()
            
            if data.get("type") == "accept_call":
                await accept_call()
            elif data.get("type") == "hangup":
                await hangup_call()
            elif data.get("type") == "mute_ai":
                await mute_ai()
            elif data.get("type") == "unmute_ai":
                await unmute_ai()
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("GUI Client disconnected")


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        log_level="info"
    )
