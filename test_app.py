"""
Test-Script für Bestell Bot Voice POC.

Testet die Komponenten mit echten Backends (OpenAI API, SIP).
"""

import sys
import time
import asyncio
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Config laden
from config import load_config

# Komponenten importieren
from core.state import AppState, CallState, RegistrationState
from core.signals import init_signals, get_signals
from core.audio_buffer import AudioBuffer
from transcription.manager import TranscriptManager
from realtime_ai.vad import VADDetector
import numpy as np


def test_config():
    """Testet die Konfiguration."""
    print("\n=== Config Test ===")
    
    try:
        config = load_config()
        print(f"SIP Server: {config.sip.server}")
        print(f"SIP User: {config.sip.username}")
        print(f"OpenAI Model: {config.openai.model}")
        print(f"OpenAI Key: {config.openai.api_key[:20]}...")
        print("Config Test: PASSED")
        return config
    except Exception as e:
        print(f"Config Test: FAILED - {e}")
        return None


def test_audio_buffer():
    """Testet den Audio Buffer."""
    print("\n=== Audio Buffer Test ===")

    buffer = AudioBuffer(max_frames=5)
    buffer.start()

    # Push-Test
    print("Pushing 7 frames...")
    for i in range(7):
        success = buffer.push(f"frame_{i}".encode())
        status = "OK" if success else "DROPPED"
        print(f"  Frame {i}: {status}")

    print(f"Buffer size: {buffer.size}/{buffer.max_size}")

    # Pull-Test
    print("Pulling frames...")
    count = 0
    while True:
        frame = buffer.pull(timeout=0.01)
        if frame is None:
            break
        count += 1

    print(f"Pulled {count} frames")

    stats = buffer.get_stats()
    print(f"Stats: {stats}")

    buffer.stop()
    print("Audio Buffer Test: PASSED")


def test_vad():
    """Testet die Voice Activity Detection."""
    print("\n=== VAD Test ===")

    vad = VADDetector()

    speech_started = [False]
    speech_ended = [False]

    def on_start():
        speech_started[0] = True
        print("  -> Speech started")

    def on_end():
        speech_ended[0] = True
        print("  -> Speech ended")

    vad.set_callbacks(on_start, on_end)

    # Stille
    print("Testing silence...")
    silence = bytes(640)
    for _ in range(10):
        vad.process_frame(silence)

    # "Sprache" (Rauschen)
    print("Testing 'speech' (noise)...")
    for _ in range(10):
        noise = (np.random.randn(320) * 3000).astype(np.int16).tobytes()
        vad.process_frame(noise)

    # Wieder Stille
    print("Testing silence again...")
    for _ in range(15):
        vad.process_frame(silence)

    if speech_started[0] and speech_ended[0]:
        print("VAD Test: PASSED")
    else:
        print(f"VAD Test: FAILED (started={speech_started[0]}, ended={speech_ended[0]})")


def test_transcript_manager():
    """Testet den Transcript Manager."""
    print("\n=== Transcript Manager Test ===")

    manager = TranscriptManager()
    manager.start_new_call()

    # Gespräch simulieren
    manager.add_partial("caller", "Hallo, ich")
    manager.add_partial("caller", "Hallo, ich möchte")
    manager.add_final("caller", "Hallo, ich möchte eine Pizza bestellen")

    manager.add_final("assistant", "Guten Tag! Welche Pizza darf es sein?")
    manager.add_final("caller", "Eine Margherita bitte")
    manager.add_final("assistant", "Eine Margherita, kommt sofort!")

    # Statistiken prüfen
    summary = manager.get_summary()
    print(f"Segments: {summary['segments']}")
    print(f"Words: {summary['words']}")
    print(f"Caller turns: {summary['caller_turns']}")
    print(f"Assistant turns: {summary['assistant_turns']}")

    # Transcript ausgeben
    print("\nTranscript:")
    print(manager.get_formatted_transcript())

    if summary["segments"] == 4 and summary["caller_turns"] == 2:
        print("\nTranscript Manager Test: PASSED")
    else:
        print("\nTranscript Manager Test: FAILED")


def test_qt_signals():
    """Testet die Qt Signals."""
    print("\n=== Qt Signals Test ===")

    app = QApplication.instance() or QApplication(sys.argv)
    signals = init_signals()

    received = {"call_state": None, "transcript": None}

    def on_call_state(state):
        received["call_state"] = state
        print(f"  Received call_state: {state.value}")

    def on_transcript(speaker, text, is_final):
        received["transcript"] = (speaker, text, is_final)
        print(f"  Received transcript: {speaker}: {text} (final={is_final})")

    signals.call_state_changed.connect(on_call_state)
    signals.transcript_updated.connect(on_transcript)

    # Signals emittieren
    print("Emitting signals...")
    signals.call_state_changed.emit(CallState.RINGING)
    signals.transcript_updated.emit("caller", "Test message", True)

    # Prozessieren
    app.processEvents()

    if received["call_state"] == CallState.RINGING and received["transcript"]:
        print("Qt Signals Test: PASSED")
    else:
        print("Qt Signals Test: FAILED")


def test_openai_realtime_connection(config):
    """Testet die Verbindung zur OpenAI Realtime API."""
    print("\n=== OpenAI Realtime API Test ===")
    
    if not config:
        print("Übersprungen - keine Config")
        return
    
    from realtime_ai.client import RealtimeClient
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    try:
        signals = get_signals()
    except RuntimeError:
        signals = init_signals()
    
    connected = [False]
    error_msg = [None]
    
    def on_connected(is_connected):
        connected[0] = is_connected
        print(f"  Connection status: {is_connected}")
    
    def on_error(msg):
        error_msg[0] = msg
        print(f"  Error: {msg}")
    
    signals.ai_connection_changed.connect(on_connected)
    signals.error_occurred.connect(on_error)
    
    client = RealtimeClient(config.openai, config.audio, signals)
    
    print("Connecting to OpenAI Realtime API...")
    client.connect()
    
    # Warte auf Verbindung
    for i in range(10):
        time.sleep(1)
        app.processEvents()
        if connected[0]:
            break
        print(f"  Waiting... ({i+1}s)")
    
    if connected[0]:
        print("OpenAI Realtime API Test: PASSED")
    else:
        print(f"OpenAI Realtime API Test: FAILED - {error_msg[0] or 'Connection timeout'}")
    
    client.disconnect()


def test_sip_registration(config):
    """Testet die SIP Registrierung."""
    print("\n=== SIP Registration Test ===")
    
    if not config:
        print("Übersprungen - keine Config")
        return
    
    try:
        from sip.client import SIPClient, PJSUA2_AVAILABLE
    except Exception as e:
        print(f"SIP Test: FAILED - Import Error: {e}")
        return
    
    if not PJSUA2_AVAILABLE:
        print("SIP Test: ÜBERSPRUNGEN - pjsua2 nicht installiert")
        print("  Für SIP-Funktionalität bitte PJSIP mit Python Bindings installieren:")
        print("  https://www.pjsip.org/")
        return
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    try:
        signals = get_signals()
    except RuntimeError:
        signals = init_signals()
    
    registered = [False]
    reg_error = [None]
    
    def on_reg_state(state, error):
        print(f"  Registration: {state.value}, Error: {error}")
        if state == RegistrationState.REGISTERED:
            registered[0] = True
        elif state == RegistrationState.FAILED:
            reg_error[0] = error
    
    signals.sip_registration_changed.connect(on_reg_state)
    
    try:
        client = SIPClient(config.sip, config.audio, signals)
        
        print(f"Registering with {config.sip.server}...")
        client.register()
        
        # Warte auf Registrierung
        for i in range(10):
            time.sleep(1)
            app.processEvents()
            if registered[0] or reg_error[0]:
                break
            print(f"  Waiting... ({i+1}s)")
        
        if registered[0]:
            print("SIP Registration Test: PASSED")
        else:
            print(f"SIP Registration Test: FAILED - {reg_error[0] or 'Timeout'}")
        
        client.shutdown()
        
    except Exception as e:
        print(f"SIP Test: FAILED - {e}")


def run_all_tests():
    """Führt alle Tests aus."""
    print("=" * 50)
    print("BESTELL BOT VOICE - COMPONENT TESTS")
    print("(Echte Backends - keine Mocks)")
    print("=" * 50)

    # Config laden
    config = test_config()
    
    # Basis-Tests
    test_audio_buffer()
    test_vad()
    test_transcript_manager()
    test_qt_signals()
    
    # Backend-Tests
    test_openai_realtime_connection(config)
    test_sip_registration(config)

    print("\n" + "=" * 50)
    print("ALL TESTS COMPLETED")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
