"""
Order Panel - Zeigt die aktuelle Bestellung an.

Analysiert das Transkript und extrahiert Bestellpositionen.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


@dataclass
class OrderItem:
    """Eine Bestellposition."""
    
    menge: int
    produkt: str
    kennung: str
    einheit: str = "Stück"
    
    def __str__(self) -> str:
        return f"{self.menge}x {self.produkt} ({self.kennung})"


@dataclass
class Order:
    """Eine komplette Bestellung."""
    
    items: list[OrderItem] = field(default_factory=list)
    
    def add_item(self, item: OrderItem) -> None:
        """Fügt eine Position hinzu oder erhöht die Menge."""
        # Prüfen ob Produkt schon existiert
        for existing in self.items:
            if existing.kennung == item.kennung:
                existing.menge += item.menge
                return
        
        self.items.append(item)
    
    def remove_item(self, index: int) -> None:
        """Entfernt eine Position."""
        if 0 <= index < len(self.items):
            del self.items[index]
    
    def clear(self) -> None:
        """Löscht alle Positionen."""
        self.items.clear()
    
    @property
    def total_items(self) -> int:
        """Gesamtzahl der Artikel."""
        return sum(item.menge for item in self.items)
    
    @property
    def position_count(self) -> int:
        """Anzahl der Positionen."""
        return len(self.items)


class OrderPanel(QWidget):
    """
    Panel zur Anzeige der Bestellung.
    
    Features:
    - Automatische Erkennung von Bestellungen aus dem Transkript
    - Tabelle mit Menge, Produkt, Artikelnummer
    - Löschen einzelner Positionen
    - Gesamtübersicht
    """
    
    # Signals
    order_updated = Signal(Order)
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._order = Order()
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Erstellt die UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("📋 Bestellung")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self._clear_btn = QPushButton("🗑️ Leeren")
        self._clear_btn.clicked.connect(self._on_clear)
        header_layout.addWidget(self._clear_btn)
        
        layout.addLayout(header_layout)
        
        # Tabelle
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Menge", "Produkt", "Art.Nr.", ""])
        
        # Spaltenbreiten
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Zeilen-Höhe
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        
        layout.addWidget(self._table, stretch=1)
        
        # Zusammenfassung
        self._summary_frame = QFrame()
        self._summary_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        summary_layout = QHBoxLayout(self._summary_frame)
        
        self._summary_label = QLabel("Keine Bestellung")
        self._summary_label.setStyleSheet("font-weight: bold; color: #666;")
        summary_layout.addWidget(self._summary_label)
        
        layout.addWidget(self._summary_frame)
    
    def _on_clear(self) -> None:
        """Löscht die Bestellung."""
        self._order.clear()
        self._update_table()
        self.order_updated.emit(self._order)
    
    def _on_remove_item(self, index: int) -> None:
        """Entfernt eine Position."""
        self._order.remove_item(index)
        self._update_table()
        self.order_updated.emit(self._order)
    
    def _update_table(self) -> None:
        """Aktualisiert die Tabelle."""
        self._table.setRowCount(len(self._order.items))
        
        for row, item in enumerate(self._order.items):
            # Menge
            menge_item = QTableWidgetItem(str(item.menge))
            menge_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, menge_item)
            
            # Produkt
            produkt_item = QTableWidgetItem(item.produkt)
            self._table.setItem(row, 1, produkt_item)
            
            # Artikelnummer
            kennung_item = QTableWidgetItem(item.kennung)
            kennung_item.setForeground(QColor("#666"))
            self._table.setItem(row, 2, kennung_item)
            
            # Löschen-Button
            delete_btn = QPushButton("❌")
            delete_btn.setMaximumWidth(30)
            delete_btn.clicked.connect(lambda checked, r=row: self._on_remove_item(r))
            self._table.setCellWidget(row, 3, delete_btn)
        
        # Zusammenfassung aktualisieren
        if self._order.items:
            self._summary_label.setText(
                f"📦 {self._order.position_count} Position(en), "
                f"{self._order.total_items} Artikel gesamt"
            )
            self._summary_label.setStyleSheet("font-weight: bold; color: #28a745;")
        else:
            self._summary_label.setText("Keine Bestellung")
            self._summary_label.setStyleSheet("font-weight: bold; color: #666;")
    
    def add_item(self, item: OrderItem) -> None:
        """Fügt eine Bestellposition hinzu."""
        self._order.add_item(item)
        self._update_table()
        self.order_updated.emit(self._order)
        logger.info(f"Bestellung hinzugefügt: {item}")
    
    def parse_transcript_for_orders(self, text: str) -> list[OrderItem]:
        """
        Analysiert Transkript-Text auf Bestellungen.
        
        Erkennt Muster wie:
        - "10x Profipress Bogen 90° 22mm (Art.Nr: 294540)"
        - "5 Stück Temponox Muffe 15mm"
        
        Args:
            text: Der zu analysierende Text
            
        Returns:
            Liste der erkannten Bestellpositionen
        """
        items = []
        
        # Muster: [MENGE]x [PRODUKT] (Art.Nr: [KENNUNG])
        pattern1 = r"(\d+)\s*x\s+(.+?)\s*\(Art\.?Nr\.?:?\s*(\d+)\)"
        matches1 = re.findall(pattern1, text, re.IGNORECASE)
        
        for match in matches1:
            menge = int(match[0])
            produkt = match[1].strip()
            kennung = match[2].strip()
            items.append(OrderItem(menge=menge, produkt=produkt, kennung=kennung))
        
        # Muster: [MENGE] Stück [PRODUKT] (mit optionaler Kennung)
        pattern2 = r"(\d+)\s*(?:Stück|stück|St\.?)\s+(.+?)(?:\s*\((\d{6})\))?(?:\s*[-–—]|\s*$)"
        matches2 = re.findall(pattern2, text, re.IGNORECASE)
        
        for match in matches2:
            menge = int(match[0])
            produkt = match[1].strip()
            kennung = match[2].strip() if match[2] else ""
            
            # Nur hinzufügen wenn nicht schon durch pattern1 erfasst
            already_exists = any(
                item.kennung == kennung and kennung != "" 
                for item in items
            )
            if not already_exists and produkt:
                items.append(OrderItem(menge=menge, produkt=produkt, kennung=kennung))
        
        return items
    
    @Slot(str, str, bool)
    def on_transcript_update(self, role: str, text: str, is_final: bool) -> None:
        """
        Slot für Transkript-Updates.
        
        Analysiert nur finale Assistant-Texte auf Bestellungen.
        """
        # Nur finale Assistant-Antworten analysieren (Bestellbestätigungen)
        if role == "assistant" and is_final:
            items = self.parse_transcript_for_orders(text)
            for item in items:
                if item.kennung:  # Nur mit gültiger Artikelnummer
                    self.add_item(item)
    
    def get_order(self) -> Order:
        """Gibt die aktuelle Bestellung zurück."""
        return self._order
    
    def get_order_text(self) -> str:
        """Gibt die Bestellung als Text zurück."""
        if not self._order.items:
            return "Keine Bestellung"
        
        lines = ["BESTELLUNG:", ""]
        for i, item in enumerate(self._order.items, 1):
            lines.append(f"{i}. {item.menge}x {item.produkt}")
            if item.kennung:
                lines.append(f"   Art.Nr: {item.kennung}")
        
        lines.append("")
        lines.append(f"Gesamt: {self._order.total_items} Artikel")
        
        return "\n".join(lines)


# Demo/Test
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    panel = OrderPanel()
    panel.setWindowTitle("Bestellung")
    panel.resize(400, 500)
    
    # Test-Daten
    panel.add_item(OrderItem(10, "Profipress Bogen 90° 22mm", "294540"))
    panel.add_item(OrderItem(5, "Temponox Muffe 15mm", "104306"))
    panel.add_item(OrderItem(20, "Sanpress T-Stück 28mm", "223878"))
    
    # Test Parser
    test_text = "10x Profipress Bogen 90° 22mm (Art.Nr: 294540) - notiert!"
    items = panel.parse_transcript_for_orders(test_text)
    print(f"Parsed: {items}")
    
    panel.show()
    sys.exit(app.exec())
