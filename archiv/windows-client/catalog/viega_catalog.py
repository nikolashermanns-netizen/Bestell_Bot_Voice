"""
Viega Katalog - Lädt und verwaltet den Produktkatalog.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ViegaProduct:
    """Ein Viega-Produkt aus dem Katalog."""
    
    id: str
    name: str
    kennung: str
    typ: str
    werkstoff: str
    einheit: str
    thema: str
    groesse: str = ""
    gruppe: str = ""


class ViegaCatalog:
    """
    Viega Produktkatalog.
    
    Lädt den Katalog aus JSON und stellt Suchmethoden bereit.
    """
    
    def __init__(self, catalog_path: Optional[Path] = None):
        """
        Lädt den Viega-Katalog.
        
        Args:
            catalog_path: Pfad zur JSON-Datei. Standard: viega_katalog.json
        """
        if catalog_path is None:
            catalog_path = Path(__file__).parent.parent / "viega_katalog.json"
        
        self._products: dict[str, ViegaProduct] = {}
        self._products_by_kennung: dict[str, ViegaProduct] = {}
        self._load_catalog(catalog_path)
    
    def _load_catalog(self, path: Path) -> None:
        """Lädt den Katalog aus der JSON-Datei."""
        if not path.exists():
            logger.error(f"Katalog nicht gefunden: {path}")
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for group in data.get("groups", []):
                group_name = group.get("name", "")
                
                for subgroup in group.get("subgroups", []):
                    groesse = subgroup.get("name", "")
                    
                    for item in subgroup.get("items", []):
                        product = ViegaProduct(
                            id=item.get("id", ""),
                            name=item.get("name", ""),
                            kennung=item.get("kennung", ""),
                            typ=item.get("typ", ""),
                            werkstoff=item.get("werkstoff", ""),
                            einheit=item.get("einheit", "Stück"),
                            thema=item.get("thema", ""),
                            groesse=groesse,
                            gruppe=group_name,
                        )
                        
                        self._products[product.id] = product
                        if product.kennung:
                            self._products_by_kennung[product.kennung] = product
            
            logger.info(f"Viega-Katalog geladen: {len(self._products)} Produkte")
            
        except Exception as e:
            logger.error(f"Fehler beim Laden des Katalogs: {e}")
    
    def find_by_kennung(self, kennung: str) -> Optional[ViegaProduct]:
        """Findet ein Produkt anhand der Kennung (Artikelnummer)."""
        return self._products_by_kennung.get(kennung)
    
    def find_by_id(self, product_id: str) -> Optional[ViegaProduct]:
        """Findet ein Produkt anhand der ID."""
        return self._products.get(product_id)
    
    def search(self, query: str) -> list[ViegaProduct]:
        """
        Sucht Produkte nach Name, Kennung oder Werkstoff.
        
        Args:
            query: Suchbegriff
            
        Returns:
            Liste passender Produkte
        """
        # Normalisiere Suchbegriff (Umlaute, Sonderzeichen)
        query_normalized = self._normalize_search(query.lower())
        results = []
        
        for product in self._products.values():
            name_normalized = self._normalize_search(product.name.lower())
            if (query_normalized in name_normalized or
                query_normalized in product.kennung.lower() or
                query_normalized in product.werkstoff.lower() or
                query_normalized in product.gruppe.lower()):
                results.append(product)
        
        return results[:50]  # Maximal 50 Ergebnisse
    
    @staticmethod
    def _normalize_search(text: str) -> str:
        """Normalisiert Text für Suche (Umlaute, Sonderzeichen)."""
        replacements = {
            "ü": "ue", "ö": "oe", "ä": "ae", "ß": "ss",
            "Ü": "Ue", "Ö": "Oe", "Ä": "Ae",
            "-": "", "°": "", " ": "",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    def get_all_products(self) -> list[ViegaProduct]:
        """Gibt alle Produkte zurück."""
        return list(self._products.values())
    
    def get_catalog_summary(self) -> str:
        """
        Erstellt eine Zusammenfassung des Katalogs für die AI.
        
        Returns:
            Kompakte Beschreibung aller Produkte
        """
        lines = ["VIEGA PRODUKTKATALOG:", ""]
        
        # Nach Gruppen sortieren
        groups: dict[str, list[ViegaProduct]] = {}
        for product in self._products.values():
            if product.gruppe not in groups:
                groups[product.gruppe] = []
            groups[product.gruppe].append(product)
        
        for gruppe_name, products in sorted(groups.items()):
            lines.append(f"## {gruppe_name}")
            
            # Nach Größe gruppieren
            by_size: dict[str, list[ViegaProduct]] = {}
            for p in products:
                if p.groesse not in by_size:
                    by_size[p.groesse] = []
                by_size[p.groesse].append(p)
            
            for size, prods in sorted(by_size.items()):
                lines.append(f"  {size}:")
                for p in prods[:10]:  # Max 10 pro Größe für Kürze
                    lines.append(f"    - {p.name} (Art.Nr: {p.kennung})")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def get_compact_product_list(self) -> str:
        """
        Erstellt eine kompakte Produktliste für den AI-Kontext.
        Enthält ALLE Produkte mit Name und Artikelnummer.
        
        Returns:
            Kompakte Liste: Name (Kennung)
        """
        lines = []
        
        # Gruppiert nach Werkstoff/System
        systems: dict[str, list[ViegaProduct]] = {}
        for product in self._products.values():
            key = product.werkstoff or product.gruppe
            if key not in systems:
                systems[key] = []
            systems[key].append(product)
        
        for system_name in sorted(systems.keys()):
            lines.append(f"\n{system_name}:")
            products = sorted(systems[system_name], key=lambda p: (p.groesse, p.name))
            
            # ALLE Produkte auflisten
            for p in products:
                lines.append(f"  - {p.name} (Art.Nr: {p.kennung})")
        
        return "\n".join(lines)
    
    def get_full_product_list(self) -> str:
        """
        Erstellt eine vollständige Produktliste mit allen Details.
        Optimiert für AI-Kontext.
        
        Returns:
            Vollständige Liste aller Produkte
        """
        lines = ["VIEGA PRODUKTKATALOG - VOLLSTÄNDIG", "=" * 50, ""]
        
        # Gruppiert nach Werkstoff/System
        systems: dict[str, list[ViegaProduct]] = {}
        for product in self._products.values():
            key = product.werkstoff or product.gruppe
            if key not in systems:
                systems[key] = []
            systems[key].append(product)
        
        for system_name in sorted(systems.keys()):
            lines.append(f"\n### {system_name} ###")
            products = sorted(systems[system_name], key=lambda p: (p.groesse, p.name))
            
            current_size = ""
            for p in products:
                if p.groesse != current_size:
                    current_size = p.groesse
                    lines.append(f"\n  [{current_size}]")
                
                lines.append(f"    {p.name} | Art.Nr: {p.kennung} | {p.einheit}")
        
        lines.append("")
        lines.append(f"GESAMT: {len(self._products)} Produkte")
        
        return "\n".join(lines)
    
    @property
    def product_count(self) -> int:
        """Anzahl der Produkte im Katalog."""
        return len(self._products)
    
    def get_product_types(self) -> list[str]:
        """
        Gibt alle eindeutigen Produkttypen zurück.
        Z.B. Bogen, Muffe, T-Stück, Doppelnippel, etc.
        """
        types = set()
        for product in self._products.values():
            # Produkttyp aus Namen extrahieren (erstes/zweites Wort nach System)
            parts = product.name.split()
            if len(parts) >= 2:
                # Skip system name (Temponox, Sanpress, etc.)
                type_name = parts[1] if len(parts) > 1 else parts[0]
                # Kombiniere mit Winkel wenn vorhanden
                if len(parts) > 2 and "°" in parts[2]:
                    type_name = f"{parts[1]} {parts[2]}"
                types.add(type_name)
        return sorted(types)
    
    def get_available_sizes(self) -> list[str]:
        """Gibt alle verfügbaren Größen zurück."""
        sizes = set()
        for product in self._products.values():
            if product.groesse:
                sizes.add(product.groesse)
        return sorted(sizes, key=lambda x: int(x.replace("mm", "")) if x.replace("mm", "").isdigit() else 0)
    
    def get_systems(self) -> list[str]:
        """Gibt alle Systeme/Werkstoffe zurück."""
        systems = set()
        for product in self._products.values():
            if product.werkstoff:
                systems.add(product.werkstoff)
            elif product.gruppe:
                # Extrahiere Systemname aus Gruppe
                parts = product.gruppe.split()
                if parts:
                    systems.add(parts[1] if len(parts) > 1 else parts[0])
        return sorted(systems)
    
    def get_context_summary(self) -> str:
        """
        Erstellt eine kompakte Zusammenfassung für den AI-Kontext.
        Enthält nur Produkttypen, Größen und Systeme - nicht alle Produkte.
        """
        systems = self.get_systems()
        sizes = self.get_available_sizes()
        types = self.get_product_types()
        
        return f"""VIEGA SORTIMENT ÜBERSICHT:

SYSTEME/WERKSTOFFE:
{', '.join(systems)}

PRODUKTTYPEN:
{', '.join(types)}

VERFÜGBARE GRÖSSEN:
{', '.join(sizes)}

GESAMT: {self.product_count} Produkte im Katalog

WICHTIG: Nutze die Funktion 'suche_produkt' um konkrete Produkte mit Artikelnummern zu finden!
Beispiel: Kunde sagt "Doppelnippel 28mm" -> suche_produkt("Doppelnippel", "28mm")
"""


# Demo/Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    catalog = ViegaCatalog()
    print(f"Produkte geladen: {catalog.product_count}")
    
    # Suche testen
    results = catalog.search("Bogen 90")
    print(f"\nSuche 'Bogen 90': {len(results)} Treffer")
    for r in results[:5]:
        print(f"  - {r.name} ({r.kennung})")
    
    # Kompakte Liste
    print("\n" + "=" * 50)
    print(catalog.get_compact_product_list()[:2000])
