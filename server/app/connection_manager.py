"""
WebSocket Connection Manager für GUI Clients.
"""

import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Verwaltet WebSocket-Verbindungen zu GUI Clients."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Neue Verbindung akzeptieren."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"GUI Client verbunden. Aktive Verbindungen: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Verbindung entfernen."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"GUI Client getrennt. Aktive Verbindungen: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Nachricht an alle verbundenen Clients senden."""
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.debug(f"Broadcast Fehler: {e}")
                disconnected.append(connection)
        
        # Disconnected Clients entfernen
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_to(self, websocket: WebSocket, message: dict):
        """Nachricht an spezifischen Client senden."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.debug(f"Send Fehler: {e}")
            self.disconnect(websocket)
