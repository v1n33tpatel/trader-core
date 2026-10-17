import os
import json
import time
import threading
import collections
from typing import Any, Callable, Dict, List, Optional

# Standard Redis Channels
CH_MARKET = "trader:events:market"
CH_SIGNALS = "trader:events:signals"
CH_ORDERS = "trader:events:orders"
CH_TELEMETRY = "trader:events:telemetry"


class EventBus:
    """
    Decoupled Event Pub/Sub Bus supporting Redis Pub/Sub with automatic
    in-memory fallback when Redis is offline or not installed.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = None
        self.pubsub = None
        self.backend = "in_memory"
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = collections.defaultdict(list)
        self._recent_events: collections.deque = collections.deque(maxlen=100)
        self._lock = threading.Lock()
        self._listener_threads: List[threading.Thread] = []
        self._running = True

        self._connect()

    def _connect(self):
        try:
            import redis
            client = redis.Redis.from_url(self.redis_url, decode_responses=True, socket_timeout=1.5)
            # Ping to verify live connection
            client.ping()
            self.client = client
            self.backend = "redis"
        except Exception:
            # Fall back gracefully to thread-safe in-memory pubsub
            self.client = None
            self.backend = "in_memory"

    def is_redis(self) -> bool:
        return self.backend == "redis" and self.client is not None

    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """Publishes an event payload to the specified channel."""
        if not isinstance(message, dict):
            message = {"data": message}

        event_envelope = {
            "channel": channel,
            "timestamp": time.time(),
            "payload": message,
        }

        with self._lock:
            self._recent_events.append(event_envelope)

        if self.is_redis():
            try:
                raw_json = json.dumps(message)
                self.client.publish(channel, raw_json)
                return True
            except Exception:
                # If Redis drops, fallback to in-memory dispatch
                pass

        # In-memory distribution to local subscribers
        handlers = list(self._handlers.get(channel, []))
        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                print(f"[EventBus] Error in subscriber handler for {channel}: {e}")
        return True

    def subscribe(self, channel: str, callback: Callable[[Dict[str, Any]], None]):
        """Subscribes a callback handler to a channel."""
        with self._lock:
            self._handlers[channel].append(callback)

        if self.is_redis():
            def _redis_listener():
                try:
                    pubsub = self.client.pubsub()
                    pubsub.subscribe(channel)
                    for item in pubsub.listen():
                        if not self._running:
                            break
                        if item and item.get("type") == "message":
                            data = item.get("data")
                            try:
                                payload = json.loads(data) if isinstance(data, str) else data
                                callback(payload)
                            except Exception as e:
                                print(f"[EventBus] Listener error on {channel}: {e}")
                except Exception as e:
                    print(f"[EventBus] Redis listener terminated on {channel}: {e}")

            t = threading.Thread(target=_redis_listener, daemon=True)
            t.start()
            self._listener_threads.append(t)

    def get_recent_events(self, channel: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._recent_events)
        if channel:
            events = [e for e in events if e.get("channel") == channel]
        return events[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "connected": self.is_redis(),
            "redis_url": self.redis_url if self.is_redis() else None,
            "subscribed_channels": list(self._handlers.keys()),
            "total_cached_events": len(self._recent_events),
        }

    def close(self):
        self._running = False
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass


# Global singleton instance
_global_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus
