"""
Zentrale Konfiguration für Bestell Bot Voice.
Lädt Einstellungen aus .env Datei.
"""

from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os


@dataclass
class SIPConfig:
    """SIP/Aircall Verbindungseinstellungen."""

    server: str
    username: str
    password: str
    port: int = 5060


@dataclass
class OpenAIConfig:
    """OpenAI API Einstellungen."""

    api_key: str
    model: str = "gpt-realtime"


@dataclass
class AudioConfig:
    """Audio-Pipeline Einstellungen."""

    sample_rate: int = 16000
    channels: int = 1
    frame_duration_ms: int = 20

    @property
    def frame_size(self) -> int:
        """Samples pro Frame."""
        return int(self.sample_rate * self.frame_duration_ms / 1000)

    @property
    def bytes_per_frame(self) -> int:
        """Bytes pro Frame (16-bit PCM)."""
        return self.frame_size * 2 * self.channels


@dataclass
class AppConfig:
    """Gesamtkonfiguration der Anwendung."""

    sip: SIPConfig
    openai: OpenAIConfig
    audio: AudioConfig
    log_level: str = "INFO"
    auto_accept_calls: bool = True  # Automatisch Anrufe annehmen


def load_config() -> AppConfig:
    """
    Lädt Konfiguration aus .env Datei.

    Returns:
        AppConfig mit allen Einstellungen.

    Raises:
        ValueError: Wenn erforderliche Einstellungen fehlen.
    """
    # .env aus Projektverzeichnis laden
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    # SIP Konfiguration
    sip_server = os.getenv("SIP_SERVER")
    sip_username = os.getenv("SIP_USERNAME")
    sip_password = os.getenv("SIP_PASSWORD")

    if not all([sip_server, sip_username, sip_password]):
        raise ValueError("SIP_SERVER, SIP_USERNAME und SIP_PASSWORD müssen gesetzt sein")

    sip_config = SIPConfig(
        server=sip_server,
        username=sip_username,
        password=sip_password,
        port=int(os.getenv("SIP_PORT", "5060")),
    )

    # OpenAI Konfiguration
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY muss gesetzt sein")

    openai_config = OpenAIConfig(
        api_key=openai_key,
        model=os.getenv("OPENAI_MODEL", "gpt-realtime"),
    )

    # Audio Konfiguration
    audio_config = AudioConfig(
        sample_rate=int(os.getenv("AUDIO_SAMPLE_RATE", "16000")),
        channels=int(os.getenv("AUDIO_CHANNELS", "1")),
        frame_duration_ms=int(os.getenv("AUDIO_FRAME_DURATION_MS", "20")),
    )

    # Auto-Accept Konfiguration
    auto_accept = os.getenv("AUTO_ACCEPT_CALLS", "true").lower() in ("true", "1", "yes")

    return AppConfig(
        sip=sip_config,
        openai=openai_config,
        audio=audio_config,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        auto_accept_calls=auto_accept,
    )


# Demo/Test
if __name__ == "__main__":
    try:
        config = load_config()
        print(f"SIP Server: {config.sip.server}")
        print(f"OpenAI Model: {config.openai.model}")
        print(f"Audio: {config.audio.sample_rate}Hz, {config.audio.frame_duration_ms}ms frames")
    except ValueError as e:
        print(f"Konfigurationsfehler: {e}")
        print("Bitte .env.example nach .env kopieren und ausfüllen.")
