import hashlib
import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SchemaCache:
    """
    Thread-safe in-memory cache for database schema DDL context and table metadata.
    Provides sub-millisecond lookup speeds with automated TTL expiry.
    """

    def __init__(self, default_ttl_seconds: int = 3600):
        self.default_ttl = default_ttl_seconds
        self._schema_text: Optional[str] = None
        self._tables_metadata: Optional[Dict[str, Any]] = None
        self._last_updated: float = 0.0
        self._lock = threading.Lock()

    def get_schema(self) -> Optional[str]:
        """Returns cached schema text if within TTL, else None."""
        with self._lock:
            if not self._schema_text:
                return None
            if time.time() - self._last_updated > self.default_ttl:
                logger.info("SchemaCache TTL expired.")
                return None
            return self._schema_text

    def set_schema(self, schema_text: str, tables_metadata: Optional[Dict[str, Any]] = None) -> None:
        """Sets schema text and optional metadata with current timestamp."""
        with self._lock:
            self._schema_text = schema_text
            self._tables_metadata = tables_metadata or {}
            self._last_updated = time.time()
            logger.info("SchemaCache updated successfully.")

    def get_tables_metadata(self) -> Optional[Dict[str, Any]]:
        """Returns cached table metadata if within TTL, else None."""
        with self._lock:
            if not self._tables_metadata:
                return None
            if time.time() - self._last_updated > self.default_ttl:
                return None
            return self._tables_metadata

    def invalidate(self) -> None:
        """Explicitly clears the schema cache."""
        with self._lock:
            self._schema_text = None
            self._tables_metadata = None
            self._last_updated = 0.0
            logger.info("SchemaCache invalidated.")

    @property
    def is_cached(self) -> bool:
        """Checks if active valid schema is available in cache."""
        with self._lock:
            if not self._schema_text:
                return False
            return (time.time() - self._last_updated) <= self.default_ttl


class QueryCache:
    """
    In-memory LRU cache for exact or normalized query answers.
    Enables instant 10ms responses for identical recurring queries.
    """

    def __init__(self, max_entries: int = 200, ttl_seconds: int = 300):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _normalize_key(query: str) -> str:
        """Normalizes and hashes a user query string."""
        clean = " ".join(query.strip().lower().split())
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached response dict for a query if valid."""
        key = self._normalize_key(query)
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time.time() - entry["timestamp"] > self.ttl_seconds:
                del self._cache[key]
                return None
            return entry["data"]

    def set(self, query: str, data: Dict[str, Any]) -> None:
        """Stores a response dict for a query with timestamp and LRU eviction."""
        key = self._normalize_key(query)
        with self._lock:
            if len(self._cache) >= self.max_entries:
                # Evict oldest entry
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
                del self._cache[oldest_key]

            self._cache[key] = {
                "timestamp": time.time(),
                "data": data,
            }

    def clear(self) -> None:
        """Clears all cached queries."""
        with self._lock:
            self._cache.clear()


# Global Singleton Cache Instances
schema_cache = SchemaCache(default_ttl_seconds=3600)
query_cache = QueryCache(max_entries=200, ttl_seconds=300)
