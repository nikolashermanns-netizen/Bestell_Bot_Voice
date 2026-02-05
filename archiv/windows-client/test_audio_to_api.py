"""
Test-Script: WAV-Datei an OpenAI Realtime API streamen.

Simuliert einen SIP-Client Stream und testet die Transkription.
"""

import sys
import os
import time
import wave
import asyncio
import json
import base64
from pathlib import Path

# UTF-8 Output für Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

try:
    import websockets
    import numpy as np
except ImportError as e:
    print(f"Fehlende Dependency: {e}")
    print("Bitte installieren: pip install websockets numpy")
    sys.exit(1)

from config import load_config


def load_wav_file(filepath: Path) -> tuple[bytes, int]:
    """
    Laedt eine WAV-Datei.
    
    Returns:
        Tuple aus (PCM-Daten, Sample-Rate)
    """
    with wave.open(str(filepath), 'rb') as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
        
        print(f"WAV-Datei geladen:")
        print(f"  - Channels: {channels}")
        print(f"  - Sample Width: {sample_width} bytes")
        print(f"  - Sample Rate: {sample_rate} Hz")
        print(f"  - Frames: {len(frames)} bytes")
        print(f"  - Dauer: {len(frames) / (sample_rate * sample_width * channels):.2f}s")
        
        return frames, sample_rate


def resample_audio(data: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resampled Audio zwischen Sample-Raten."""
    if from_rate == to_rate:
        return data
    
    samples = np.frombuffer(data, dtype=np.int16)
    ratio = to_rate / from_rate
    new_length = int(len(samples) * ratio)
    indices = np.linspace(0, len(samples) - 1, new_length)
    resampled = np.interp(indices, np.arange(len(samples)), samples)
    
    print(f"Resampled: {from_rate}Hz -> {to_rate}Hz ({len(samples)} -> {len(resampled)} samples)")
    return resampled.astype(np.int16).tobytes()


def simulate_sip_stream(audio_data: bytes, sample_rate: int, frame_duration_ms: int = 20):
    """
    Simuliert einen SIP-Client Audio-Stream.
    
    Teilt das Audio in kleine Frames (wie von RTP/SIP kommend).
    
    Yields:
        Audio-Frames in der Groesse wie sie von SIP kaemen
    """
    # Frame-Groesse berechnen (20ms Frames sind typisch fuer SIP)
    samples_per_frame = int(sample_rate * frame_duration_ms / 1000)
    bytes_per_frame = samples_per_frame * 2  # 16-bit = 2 bytes
    
    print(f"\nSimuliere SIP-Stream:")
    print(f"  - Frame Duration: {frame_duration_ms}ms")
    print(f"  - Samples/Frame: {samples_per_frame}")
    print(f"  - Bytes/Frame: {bytes_per_frame}")
    print(f"  - Total Frames: {len(audio_data) // bytes_per_frame}")
    
    for i in range(0, len(audio_data), bytes_per_frame):
        yield audio_data[i:i + bytes_per_frame]


async def test_realtime_api(audio_data: bytes, api_key: str, model: str) -> dict:
    """
    Testet die OpenAI Realtime API mit simuliertem SIP-Stream.
    
    Returns:
        Dict mit Testergebnissen
    """
    url = f"wss://api.openai.com/v1/realtime?model={model}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }
    
    print(f"\n[CONNECT] Verbinde mit OpenAI Realtime API...")
    print(f"[CONNECT] Model: {model}")
    
    results = {
        "connected": False,
        "input_transcript": "",
        "output_transcript": "",
        "response_audio": b"",
        "errors": [],
    }
    
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            print("[OK] Verbunden!")
            results["connected"] = True
            
            # Session konfigurieren
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": "alloy",
                    "instructions": "Du bist ein freundlicher Assistent. Antworte kurz und praezise auf Deutsch.",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 700,
                    },
                },
            }
            
            await ws.send(json.dumps(session_config))
            print("[OK] Session konfiguriert")
            
            # Simuliere SIP-Stream: Audio in kleinen Chunks senden
            # Erst zu 24kHz resampling (API erwartet 24kHz)
            audio_24k = resample_audio(audio_data, 16000, 24000)
            
            # In 20ms Frames aufteilen (wie SIP)
            frames = list(simulate_sip_stream(audio_24k, 24000, frame_duration_ms=20))
            
            print(f"\n[STREAM] Sende {len(frames)} Audio-Frames...")
            
            for i, frame in enumerate(frames):
                audio_b64 = base64.b64encode(frame).decode("utf-8")
                
                event = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64,
                }
                await ws.send(json.dumps(event))
                
                # Simuliere Echtzeit-Streaming (20ms pro Frame)
                await asyncio.sleep(0.015)  # Etwas schneller als Echtzeit
                
                if (i + 1) % 50 == 0:
                    print(f"[STREAM] {i + 1}/{len(frames)} Frames gesendet...")
            
            print(f"[OK] Alle {len(frames)} Frames gesendet!")
            
            # Audio-Buffer committen
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            print("[COMMIT] Buffer committed")
            
            # Warte kurz und dann Response explizit anfordern
            await asyncio.sleep(1.0)
            
            # Response erstellen (triggert die AI Antwort)
            response_create = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                }
            }
            await ws.send(json.dumps(response_create))
            print("[WAIT] Response angefordert, warte auf Antwort...")
            
            # Auf Antwort warten
            response_audio_chunks = []
            timeout = time.time() + 30
            
            while time.time() < timeout:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    event = json.loads(message)
                    event_type = event.get("type", "")
                    
                    if event_type == "session.created":
                        print(f"[EVENT] Session erstellt")
                    
                    elif event_type == "input_audio_buffer.speech_started":
                        print("[EVENT] >>> Sprache erkannt!")
                    
                    elif event_type == "input_audio_buffer.speech_stopped":
                        print("[EVENT] >>> Sprache beendet")
                    
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        results["input_transcript"] = event.get("transcript", "")
                        print(f"\n[TRANSKRIPT INPUT]: {results['input_transcript']}")
                    
                    elif event_type == "response.audio.delta":
                        audio_b64 = event.get("delta", "")
                        if audio_b64:
                            chunk = base64.b64decode(audio_b64)
                            response_audio_chunks.append(chunk)
                    
                    elif event_type == "response.audio_transcript.delta":
                        delta = event.get("delta", "")
                        results["output_transcript"] += delta
                        print(delta, end="", flush=True)
                    
                    elif event_type == "response.audio_transcript.done":
                        results["output_transcript"] = event.get("transcript", results["output_transcript"])
                        print(f"\n\n[TRANSKRIPT OUTPUT]: {results['output_transcript']}")
                    
                    elif event_type == "response.done":
                        print("\n[OK] Antwort abgeschlossen!")
                        break
                    
                    elif event_type == "error":
                        error = event.get("error", {})
                        error_msg = error.get("message", str(error))
                        print(f"\n[ERROR]: {error_msg}")
                        results["errors"].append(error_msg)
                        break
                
                except asyncio.TimeoutError:
                    continue
            
            # Audio zusammenfuegen
            if response_audio_chunks:
                results["response_audio"] = b"".join(response_audio_chunks)
            
            return results
    
    except Exception as e:
        print(f"\n[ERROR] Verbindungsfehler: {e}")
        results["errors"].append(str(e))
        return results


def save_wav(data: bytes, filepath: Path, sample_rate: int = 24000):
    """Speichert Audio als WAV-Datei."""
    with wave.open(str(filepath), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(data)
    print(f"[SAVE] Gespeichert: {filepath} ({len(data)} bytes)")


async def transcribe_audio_via_api(audio_data: bytes, api_key: str, model: str) -> str:
    """
    Sendet Audio zur Transkription an die API.
    Nur Transkription, keine Antwort.
    """
    url = f"wss://api.openai.com/v1/realtime?model={model}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }
    
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            # Session ohne Audio-Antwort konfigurieren
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text"],  # Nur Text, kein Audio-Output
                    "instructions": "Transkribiere nur, antworte nicht.",
                    "input_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "silence_duration_ms": 500,
                    },
                },
            }
            
            await ws.send(json.dumps(session_config))
            
            # Audio senden
            chunk_size = 24000 * 2 // 10  # 100ms chunks
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                audio_b64 = base64.b64encode(chunk).decode("utf-8")
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64,
                }))
                await asyncio.sleep(0.05)
            
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            
            # Auf Transkription warten
            transcript = ""
            timeout = time.time() + 15
            
            while time.time() < timeout:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    event = json.loads(message)
                    
                    if event.get("type") == "conversation.item.input_audio_transcription.completed":
                        transcript = event.get("transcript", "")
                        break
                    elif event.get("type") == "response.done":
                        break
                    elif event.get("type") == "error":
                        print(f"[ERROR] {event.get('error', {}).get('message', '')}")
                        break
                        
                except asyncio.TimeoutError:
                    continue
            
            return transcript
            
    except Exception as e:
        print(f"[ERROR] Transkription fehlgeschlagen: {e}")
        return ""


def main():
    """Hauptfunktion - Vollstaendiger Test."""
    print("=" * 70)
    print("  AUDIO STREAM TEST - Simuliert SIP-Client -> OpenAI Realtime API")
    print("=" * 70)
    
    # Config laden
    try:
        config = load_config()
        print(f"\n[OK] Config geladen")
        print(f"     API Key: {config.openai.api_key[:20]}...")
        print(f"     Model: {config.openai.model}")
    except Exception as e:
        print(f"[ERROR] Config-Fehler: {e}")
        return 1
    
    # Aufnahme laden
    input_file = Path("recordings/recording_20260204_162554.wav")
    
    if not input_file.exists():
        # Fallback: neueste Datei
        recordings_dir = Path("recordings")
        if recordings_dir.exists():
            wav_files = sorted(recordings_dir.glob("recording_*.wav"), reverse=True)
            if wav_files:
                input_file = wav_files[0]
    
    if not input_file.exists():
        print(f"[ERROR] Datei nicht gefunden: {input_file}")
        return 1
    
    print(f"\n[FILE] Lade: {input_file}")
    
    # WAV laden
    audio_data, sample_rate = load_wav_file(input_file)
    
    # Erwarteter Text
    expected_text = "hallo liebes chatgpt kannst du mir sagen wieviel uhr wir haben"
    print(f"\n[EXPECTED] Erwarteter Text: '{expected_text}'")
    
    # === TEST 1: Audio an API senden und Transkription + Antwort erhalten ===
    print("\n" + "=" * 70)
    print("  TEST 1: Audio streamen -> Transkription + Antwort")
    print("=" * 70)
    
    # Zu 16kHz konvertieren falls noetig (SIP typisch 16kHz)
    if sample_rate != 16000:
        audio_16k = resample_audio(audio_data, sample_rate, 16000)
    else:
        audio_16k = audio_data
    
    results = asyncio.run(test_realtime_api(
        audio_16k,
        config.openai.api_key,
        config.openai.model,
    ))
    
    # Ergebnisse anzeigen
    print("\n" + "-" * 70)
    print("  TEST 1 ERGEBNIS:")
    print("-" * 70)
    print(f"  Verbunden:          {results['connected']}")
    print(f"  Input Transkript:   '{results['input_transcript']}'")
    print(f"  Erwartet:           '{expected_text}'")
    print(f"  Output Transkript:  '{results['output_transcript']}'")
    print(f"  Response Audio:     {len(results['response_audio'])} bytes")
    print(f"  Fehler:             {results['errors']}")
    
    # Input-Transkription pruefen
    input_match = expected_text.lower() in results['input_transcript'].lower() or \
                  results['input_transcript'].lower() in expected_text.lower()
    print(f"\n  Input Match:        {'JA' if input_match else 'NEIN'}")
    
    if not results['response_audio']:
        print("\n[WARNING] Kein Antwort-Audio erhalten!")
        return 1
    
    # === Antwort-Audio speichern ===
    response_file = Path("recordings/api_response.wav")
    save_wav(results['response_audio'], response_file, sample_rate=24000)
    
    # === TEST 2: Antwort-Audio nochmal transkribieren ===
    print("\n" + "=" * 70)
    print("  TEST 2: Antwort-Audio -> Transkription (Verifikation)")
    print("=" * 70)
    
    print("[TRANSCRIBE] Sende Antwort-Audio zur Transkription...")
    
    verification_transcript = asyncio.run(transcribe_audio_via_api(
        results['response_audio'],
        config.openai.api_key,
        config.openai.model,
    ))
    
    print(f"\n[VERIFICATION] Transkription des Antwort-Audios:")
    print(f"  '{verification_transcript}'")
    
    # Vergleich
    print("\n" + "-" * 70)
    print("  TEST 2 ERGEBNIS:")
    print("-" * 70)
    print(f"  Output Transkript (original):    '{results['output_transcript']}'")
    print(f"  Output Transkript (verifiziert): '{verification_transcript}'")
    
    # Aehnlichkeit pruefen
    orig_words = set(results['output_transcript'].lower().split())
    verif_words = set(verification_transcript.lower().split())
    
    if orig_words and verif_words:
        overlap = len(orig_words & verif_words) / max(len(orig_words), len(verif_words))
        print(f"  Uebereinstimmung:                {overlap * 100:.1f}%")
    
    # === ZUSAMMENFASSUNG ===
    print("\n" + "=" * 70)
    print("  ZUSAMMENFASSUNG")
    print("=" * 70)
    print(f"  1. Audio geladen:           {input_file.name}")
    print(f"  2. API Verbindung:          {'OK' if results['connected'] else 'FEHLER'}")
    print(f"  3. Input erkannt:           {'OK' if results['input_transcript'] else 'FEHLER'}")
    print(f"  4. Antwort erhalten:        {'OK' if results['output_transcript'] else 'FEHLER'}")
    print(f"  5. Audio-Antwort:           {'OK' if results['response_audio'] else 'FEHLER'}")
    print(f"  6. Verifikation:            {'OK' if verification_transcript else 'FEHLER'}")
    print(f"\n  Gespeicherte Dateien:")
    print(f"     - {response_file}")
    
    all_ok = all([
        results['connected'],
        results['input_transcript'],
        results['output_transcript'],
        results['response_audio'],
    ])
    
    print(f"\n  GESAMTERGEBNIS: {'ALLE TESTS BESTANDEN' if all_ok else 'TESTS FEHLGESCHLAGEN'}")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
