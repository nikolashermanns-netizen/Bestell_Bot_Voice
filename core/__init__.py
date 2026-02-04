"""
Core-Modul mit gemeinsam genutzten Komponenten.
"""

from .state import CallState, AppState, RegistrationState
from .audio_buffer import AudioBuffer
from .signals import AppSignals
from .local_audio import LocalAudioDevice, SOUNDDEVICE_AVAILABLE

# Controller wird nicht hier importiert um zirkuläre Imports zu vermeiden
# Import direkt: from core.controller import CallController

__all__ = [
    "CallState",
    "AppState",
    "RegistrationState",
    "AudioBuffer",
    "AppSignals",
    "LocalAudioDevice",
    "SOUNDDEVICE_AVAILABLE",
]
