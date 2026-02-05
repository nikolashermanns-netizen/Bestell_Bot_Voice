"""
SIP/RTP Modul für Call Control und Audio I/O.
"""

from .audio_bridge import AudioBridge
from .events import IncomingCallEvent, CallStateChangedEvent, RegistrationStateEvent

# SIPClient wird nicht hier importiert um zirkuläre Imports zu vermeiden
# Import direkt: from sip.client import SIPClient

__all__ = [
    "AudioBridge",
    "IncomingCallEvent",
    "CallStateChangedEvent",
    "RegistrationStateEvent",
]
