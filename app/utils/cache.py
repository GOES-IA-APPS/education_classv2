from __future__ import annotations

import hashlib
import json
import time
from threading import RLock
from typing import Any


DEFAULT_CACHE_TTL_SECONDS = 3600

_CACHE: dict[str, tuple[float, Any]] = {}
_LOCK = RLock()


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return sorted(_normalize(item) for item in value)
    return value


def build_cache_key(namespace: str, *, scope: dict[str, Any] | None = None) -> str:
    payload = json.dumps(_normalize(scope or {}), sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def _purge_expired_locked(now: float | None = None) -> None:
    current = now or time.time()
    expired = [key for key, (expires_at, _) in _CACHE.items() if expires_at <= current]
    for key in expired:
        _CACHE.pop(key, None)


def get_cache(key: str) -> Any | None:
    with _LOCK:
        _purge_expired_locked()
        item = _CACHE.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= time.time():
            _CACHE.pop(key, None)
            return None
        return value


def set_cache(key: str, value: Any, *, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS) -> Any:
    with _LOCK:
        _purge_expired_locked()
        _CACHE[key] = (time.time() + ttl_seconds, value)
    return value


def invalidate_namespace(namespace: str) -> None:
    prefix = f"{namespace}:"
    with _LOCK:
        for key in [cache_key for cache_key in _CACHE if cache_key.startswith(prefix)]:
            _CACHE.pop(key, None)


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
