"""
VitalBand Async WebSocket Manager with Redis Pub/Sub Fallback
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket

from backend.config import settings

logger = logging.getLogger("vitalband.websocket")

# Try importing redis for real-time pubsub synchronization across replicas
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class ConnectionManager:
    """
    Manages client WebSocket connections and propagates updates across replicas using Redis Pub/Sub.
    If Redis is not available, falls back to in-memory broadcast.
    """
    def __init__(self):
        # hospital_id -> list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the Redis subscriber task if Redis is configured."""
        if not REDIS_AVAILABLE or not settings.REDIS_URL:
            logger.info("Redis not configured or client library missing. Operating in single-instance memory mode.")
            return

        try:
            self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            # Test ping
            await self.redis_client.ping()
            logger.info("Connected to Redis for WebSocket Pub/Sub synchronization.")

            # Start subscriber listener
            self.pubsub_task = asyncio.create_task(self._redis_subscriber_loop())
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}. Falling back to single-instance memory mode.")
            self.redis_client = None

    async def stop(self):
        """Clean up tasks and connections."""
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
        if self.redis_client:
            await self.redis_client.aclose()

    async def connect(self, websocket: WebSocket, hospital_id: str = "DEFAULT_HOSP"):
        await websocket.accept()
        if hospital_id not in self.active_connections:
            self.active_connections[hospital_id] = []
        self.active_connections[hospital_id].append(websocket)
        logger.info(f"WebSocket client connected to hospital scope: {hospital_id}")

    def disconnect(self, websocket: WebSocket, hospital_id: str = "DEFAULT_HOSP"):
        if hospital_id in self.active_connections:
            if websocket in self.active_connections[hospital_id]:
                self.active_connections[hospital_id].remove(websocket)
                logger.info(f"WebSocket client disconnected from hospital scope: {hospital_id}")
            if not self.active_connections[hospital_id]:
                del self.active_connections[hospital_id]

    async def broadcast_to_hospital(self, hospital_id: str, event_type: str, data: dict):
        """
        Broadcasts an event to all local connections of a specific hospital.
        If Redis is configured, it publishes to Redis instead (to sync all replicas).
        """
        payload = {
            "hospital_id": hospital_id,
            "event_type": event_type,
            "data": data
        }

        if self.redis_client:
            try:
                await self.redis_client.publish("vitalband_alerts", json.dumps(payload))
                return
            except Exception as e:
                logger.error(f"Redis publish error: {e}. Falling back to local broadcast.")

        # Local fallback broadcast
        await self._local_broadcast(hospital_id, event_type, data)

    async def _local_broadcast(self, hospital_id: str, event_type: str, data: dict):
        """Directly sends the payload to connected clients on this instance."""
        payload = {"event_type": event_type, **data}
        connections = self.active_connections.get(hospital_id, [])
        if not connections:
            return

        dead_connections = []
        for ws in connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead_connections.append(ws)

        for dead_ws in dead_connections:
            self.disconnect(dead_ws, hospital_id)

    async def _redis_subscriber_loop(self):
        """Listens to the Redis channel and triggers local broadcasts for received messages."""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe("vitalband_alerts")
        logger.info("Subscribed to Redis channel 'vitalband_alerts'.")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        hospital_id = payload.get("hospital_id", "DEFAULT_HOSP")
                        event_type = payload.get("event_type")
                        data = payload.get("data", {})
                        # Forward to local connected clients
                        await self._local_broadcast(hospital_id, event_type, data)
                    except Exception as e:
                        logger.error(f"Failed to process Redis pubsub message: {e}")
        except asyncio.CancelledError:
            await pubsub.unsubscribe("vitalband_alerts")
        except Exception as e:
            logger.error(f"Redis subscriber loop error: {e}")


manager = ConnectionManager()
