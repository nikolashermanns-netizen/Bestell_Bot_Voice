"""
State Management für Call und App Zustand.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


class CallState(Enum):
    """Mögliche Zustände eines Anrufs."""

    IDLE = "idle"
    RINGING = "ringing"
    ACTIVE = "active"
    ENDED = "ended"


class RegistrationState(Enum):
    """SIP Registrierungsstatus."""

    UNREGISTERED = "unregistered"
    REGISTERING = "registering"
    REGISTERED = "registered"
    FAILED = "failed"


@dataclass
class CallInfo:
    """Informationen über den aktuellen Anruf."""

    caller_id: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Anrufdauer in Sekunden."""
        if not self.start_time:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()


@dataclass
class DebugInfo:
    """Debug-Informationen für das Status-Panel."""

    latency_ms: float = 0.0
    audio_in_queue_size: int = 0
    audio_out_queue_size: int = 0
    last_error: str = ""
    last_error_time: Optional[datetime] = None


@dataclass
class AppState:
    """
    Gesamtzustand der Anwendung.

    Thread-safe Zugriff über Qt Signals.
    """

    # SIP Status
    registration_state: RegistrationState = RegistrationState.UNREGISTERED
    registration_error: str = ""

    # Call Status
    call_state: CallState = CallState.IDLE
    call_info: CallInfo = field(default_factory=CallInfo)

    # AI Status
    ai_muted: bool = False
    ai_connected: bool = False

    # Debug
    debug: DebugInfo = field(default_factory=DebugInfo)

    def reset_call(self) -> None:
        """Setzt Call-bezogene Daten zurück."""
        self.call_state = CallState.IDLE
        self.call_info = CallInfo()

    def start_call(self, caller_id: str) -> None:
        """Startet einen neuen Anruf."""
        self.call_state = CallState.RINGING
        self.call_info = CallInfo(caller_id=caller_id)

    def accept_call(self) -> None:
        """Nimmt den Anruf an."""
        self.call_state = CallState.ACTIVE
        self.call_info.start_time = datetime.now()

    def end_call(self) -> None:
        """Beendet den Anruf."""
        self.call_state = CallState.ENDED
        self.call_info.end_time = datetime.now()

    def set_error(self, error: str) -> None:
        """Setzt einen Fehler."""
        self.debug.last_error = error
        self.debug.last_error_time = datetime.now()


# Demo/Test
if __name__ == "__main__":
    state = AppState()
    print(f"Initial: {state.call_state.value}")

    state.start_call("+49 123 456789")
    print(f"Nach start_call: {state.call_state.value}, Caller: {state.call_info.caller_id}")

    state.accept_call()
    print(f"Nach accept_call: {state.call_state.value}")

    import time

    time.sleep(1)

    state.end_call()
    print(f"Nach end_call: {state.call_state.value}, Dauer: {state.call_info.duration_seconds:.1f}s")
