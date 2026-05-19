import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Small in-process TTL cache for idempotent LLM tasks.

    This is intentionally simple: it reduces accidental repeated calls during
    UI refreshes/debug runs, but does not attempt to be a cross-process cache.
    """

    def __init__(self, *, ttl_seconds: int, max_items: int = 512) -> None:
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._max_items = max(16, int(max_items))
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        # Simple eviction: drop an arbitrary key when full.
        if len(self._store) >= self._max_items:
            try:
                self._store.pop(next(iter(self._store)))
            except StopIteration:
                pass
        self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + self._ttl_seconds)

