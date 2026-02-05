"""
Order Manager

Verwaltet Bestellungen während eines Anrufs.
Bestellungen werden nur im Speicher gehalten.
"""

import logging
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class OrderItem:
    """Einzelne Position in einer Bestellung."""
    
    def __init__(self, kennung: str, menge: int, produktname: str):
        self.kennung = kennung
        self.menge = menge
        self.produktname = produktname
        self.timestamp = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "kennung": self.kennung,
            "menge": self.menge,
            "produktname": self.produktname,
            "timestamp": self.timestamp.isoformat()
        }


class OrderManager:
    """
    Verwaltet die aktuelle Bestellung.
    
    Eine Bestellung besteht aus mehreren OrderItems und wird
    pro Anruf gehalten. Bei Anrufende wird sie gelöscht.
    """
    
    def __init__(self):
        self._items: list[OrderItem] = []
        self._caller_id: Optional[str] = None
        self._started_at: Optional[datetime] = None
        
        # Callback für Updates (wird von main.py gesetzt)
        self.on_order_update: Optional[Callable[[dict], None]] = None
    
    def start_order(self, caller_id: str = None):
        """Startet eine neue Bestellung für einen Anruf."""
        self._items = []
        self._caller_id = caller_id
        self._started_at = datetime.now()
        logger.info(f"Neue Bestellung gestartet für: {caller_id}")
        self._notify_update()
    
    def add_item(self, kennung: str, menge: int, produktname: str) -> bool:
        """
        Fügt ein Produkt zur Bestellung hinzu.
        
        Args:
            kennung: Artikelnummer
            menge: Bestellmenge
            produktname: Produktname für Anzeige
        
        Returns:
            True wenn erfolgreich
        """
        # Prüfen ob Produkt bereits in Bestellung
        for item in self._items:
            if item.kennung == kennung:
                # Menge erhöhen
                item.menge += menge
                logger.info(f"Bestellung aktualisiert: {menge}x {produktname} (Artikel Nummer {kennung}) - jetzt {item.menge}x")
                self._notify_update()
                return True
        
        # Neues Item hinzufügen
        item = OrderItem(kennung=kennung, menge=menge, produktname=produktname)
        self._items.append(item)
        logger.info(f"Bestellung hinzugefügt: {menge}x {produktname} (Artikel Nummer {kennung})")
        self._notify_update()
        return True
    
    def remove_item(self, kennung: str) -> bool:
        """Entfernt ein Produkt aus der Bestellung."""
        for i, item in enumerate(self._items):
            if item.kennung == kennung:
                removed = self._items.pop(i)
                logger.info(f"Bestellung entfernt: {removed.produktname}")
                self._notify_update()
                return True
        return False
    
    def get_current_order(self) -> dict:
        """Gibt die aktuelle Bestellung zurück."""
        return {
            "caller_id": self._caller_id,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "items": [item.to_dict() for item in self._items],
            "item_count": len(self._items),
            "total_quantity": sum(item.menge for item in self._items)
        }
    
    def get_order_summary(self) -> str:
        """
        Gibt eine Zusammenfassung der Bestellung als Text zurück.
        Für die AI zum Vorlesen.
        """
        if not self._items:
            return "Die Bestellung ist leer."
        
        lines = ["Aktuelle Bestellung:"]
        for item in self._items:
            lines.append(f"- {item.menge}x {item.produktname} (Artikel Nummer {item.kennung})")
        
        lines.append(f"\nGesamt: {len(self._items)} Positionen, {sum(item.menge for item in self._items)} Stück")
        return "\n".join(lines)
    
    def clear_order(self):
        """Löscht die aktuelle Bestellung."""
        count = len(self._items)
        self._items = []
        self._caller_id = None
        self._started_at = None
        logger.info(f"Bestellung gelöscht ({count} Positionen)")
        self._notify_update()
    
    def _notify_update(self):
        """Benachrichtigt über Änderungen (für GUI)."""
        if self.on_order_update:
            try:
                self.on_order_update(self.get_current_order())
            except Exception as e:
                logger.debug(f"Order update notification error: {e}")


# Globale Instanz
order_manager = OrderManager()
