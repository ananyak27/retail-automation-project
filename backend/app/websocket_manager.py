from fastapi import WebSocket
from typing import Dict, List
import logging
import json

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps user_id (int) to active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket. Total connections: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected from WebSocket.")

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            # Send message to all tabs/connections of this user
            disconnected_sockets = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"Error sending message to user {user_id}: {e}")
                    disconnected_sockets.append(connection)
            
            # Clean up stale connections
            for stale in disconnected_sockets:
                self.disconnect(user_id, stale)

    async def broadcast(self, message: dict):
        for user_id, connections in list(self.active_connections.items()):
            disconnected_sockets = []
            for connection in connections:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"Error broadcasting to user {user_id}: {e}")
                    disconnected_sockets.append(connection)
            
            for stale in disconnected_sockets:
                self.disconnect(user_id, stale)

# Singleton manager
manager = ConnectionManager()
