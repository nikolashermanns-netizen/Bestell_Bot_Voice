"""
Bestell Bot Voice - POC Einstiegspunkt.

Startet die Qt-Anwendung mit SIP-Client und ChatGPT Realtime Integration.
"""

import sys
import signal
import logging
import atexit
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from config import load_config, AppConfig
from ui.main_window import MainWindow
from core.state import AppState
from core.signals import init_signals
from core.controller import CallController

# Globale Referenzen für Cleanup
_controller: CallController | None = None
_app: QApplication | None = None


def setup_logging(level: str) -> None:
    """Konfiguriert das Logging-System."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduziere Log-Spam von externen Libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def create_application() -> QApplication:
    """Erstellt die Qt-Anwendung."""
    app = QApplication(sys.argv)
    app.setApplicationName("Bestell Bot Voice")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("POC")
    return app


def setup_signal_handlers(app: QApplication) -> None:
    """
    Richtet Signal-Handler für graceful shutdown ein.
    Erlaubt Ctrl+C im Terminal.
    """
    logger = logging.getLogger(__name__)

    def signal_handler(*args):
        logger.info("Shutdown-Signal empfangen, beende Anwendung...")
        graceful_shutdown()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Timer für Signal-Verarbeitung im Qt Event Loop
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)


def graceful_shutdown() -> None:
    """Führt einen sauberen Shutdown aller Komponenten durch."""
    global _controller
    logger = logging.getLogger(__name__)

    logger.info("Führe Graceful Shutdown durch...")

    if _controller:
        try:
            _controller.stop()
            logger.info("Controller gestoppt")
        except Exception as e:
            logger.error(f"Fehler beim Controller-Shutdown: {e}")
        _controller = None

    logger.info("Graceful Shutdown abgeschlossen")


def main() -> int:
    """
    Haupteinstiegspunkt der Anwendung.

    Returns:
        Exit-Code (0 = Erfolg)
    """
    global _controller, _app

    # Konfiguration laden
    try:
        config = load_config()
    except ValueError as e:
        print(f"Konfigurationsfehler: {e}")
        print("Bitte .env.example nach .env kopieren und ausfüllen.")
        return 1

    # Logging einrichten
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starte Bestell Bot Voice POC...")

    # Qt-Anwendung erstellen
    _app = create_application()
    setup_signal_handlers(_app)

    # Cleanup bei Exit registrieren
    atexit.register(graceful_shutdown)

    # Signals initialisieren
    signals = init_signals()

    # App-State initialisieren
    app_state = AppState()

    # Controller erstellen
    _controller = CallController(config, app_state, signals)

    # Hauptfenster erstellen und anzeigen
    window = MainWindow(config, app_state, _controller)
    window.show()

    # Controller starten (SIP Registrierung)
    _controller.start()

    logger.info("Anwendung bereit")

    # Event Loop starten
    exit_code = _app.exec()

    # Cleanup
    logger.info("Räume auf...")
    graceful_shutdown()
    window.cleanup()

    logger.info("Anwendung beendet")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
