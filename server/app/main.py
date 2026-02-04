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
from ai_client import AIClient
from connection_manager import ConnectionManager

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
manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    global sip_client, ai_client
    
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
    
    # Gespeicherte Instructions laden
    try:
        import json
        with open("/app/instructions.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if "instructions" in data:
                ai_client.set_instructions(data["instructions"])
                logger.info("Gespeicherte Instructions geladen")
    except FileNotFoundError:
        logger.info("Keine gespeicherten Instructions gefunden, verwende Default")
    except Exception as e:
        logger.warning(f"Fehler beim Laden der Instructions: {e}")
    
    # Event Handler verbinden
    sip_client.on_incoming_call = on_incoming_call
    sip_client.on_audio_received = on_audio_from_caller
    sip_client.on_call_ended = on_call_ended
    
    ai_client.on_audio_response = on_audio_from_ai
    ai_client.on_transcript = on_transcript
    
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

async def on_incoming_call(caller_id: str):
    """Wird aufgerufen wenn ein Anruf eingeht."""
    logger.info(f"Eingehender Anruf von: {caller_id}")
    
    # Alle GUI Clients benachrichtigen
    await manager.broadcast({
        "type": "call_incoming",
        "caller_id": caller_id
    })
    
    # Auto-Accept: Anruf annehmen und AI verbinden
    await sip_client.accept_call()
    await ai_client.connect()
    
    await manager.broadcast({
        "type": "call_active",
        "caller_id": caller_id
    })


async def on_audio_from_caller(audio_data: bytes):
    """Audio vom Anrufer empfangen (48kHz) - an AI weiterleiten (16kHz)."""
    if ai_client and ai_client.is_connected:
        # Resample 48kHz -> 16kHz für AI Input
        try:
            resampled = resample_audio(audio_data, 48000, 16000)
            await ai_client.send_audio(resampled)
        except Exception as e:
            logger.debug(f"Audio Resample Fehler: {e}")


async def on_audio_from_ai(audio_data: bytes):
    """Audio von AI empfangen (24kHz) - an Anrufer weiterleiten (48kHz)."""
    if sip_client and sip_client.is_in_call:
        # Resample 24kHz -> 48kHz für SIP/Opus
        try:
            resampled = resample_audio(audio_data, 24000, 48000)
            await sip_client.send_audio(resampled)
        except Exception as e:
            logger.debug(f"Audio Resample Fehler: {e}")


async def on_transcript(role: str, text: str, is_final: bool):
    """Transkript-Update von AI."""
    await manager.broadcast({
        "type": "transcript",
        "role": role,
        "text": text,
        "is_final": is_final
    })


async def on_call_ended(reason: str):
    """Anruf beendet."""
    logger.info(f"Anruf beendet: {reason}")
    
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
        
        # Persistieren in Datei
        try:
            import json
            with open("/app/instructions.json", "w", encoding="utf-8") as f:
                json.dump({"instructions": instructions}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Konnte Instructions nicht speichern: {e}")
        
        return {"status": "ok", "length": len(instructions)}
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
