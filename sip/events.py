"""
SIP Event-Typen für Kommunikation zwischen SIP Client und App.
"""

from dataclasses import dataclass
from typing import Optional
from core.state import CallState, RegistrationState


@dataclass
class RegistrationStateEvent:
    """Event für Änderung des SIP Registrierungsstatus."""

    state: RegistrationState
    error: str = ""

    @property
    def is_registered(self) -> bool:
        return self.state == RegistrationState.REGISTERED

    @property
    def is_failed(self) -> bool:
        return self.state == RegistrationState.FAILED


@dataclass
class IncomingCallEvent:
    """Event für eingehenden Anruf."""

    call_id: str
    caller_id: str
    caller_name: str = ""
    caller_uri: str = ""

    @property
    def display_name(self) -> str:
        """Anzeigename für UI."""
        if self.caller_name:
            return f"{self.caller_name} ({self.caller_id})"
        return self.caller_id or "Unbekannt"


@dataclass
class CallStateChangedEvent:
    """Event für Änderung des Anrufstatus."""

    call_id: str
    state: CallState
    reason: str = ""


@dataclass
class AudioFrameEvent:
    """Event für eingehendes Audio-Frame."""

    call_id: str
    data: bytes  # PCM Audio-Daten
    timestamp_ms: float


@dataclass
class CallEndedEvent:
    """Event für beendeten Anruf."""

    call_id: str
    reason: str
    duration_seconds: float = 0.0
    was_answered: bool = False


@dataclass
class DTMFEvent:
    """Event für DTMF-Töne (Tastendrücke)."""

    call_id: str
    digit: str  # 0-9, *, #
