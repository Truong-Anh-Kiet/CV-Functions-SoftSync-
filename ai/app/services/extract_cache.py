"""
Content-hash cache for OpenAI extraction results.

Extracting a CV can cost 1–5 sequential GPT-4o(-mini) calls, so re-running the
SAME document is wasteful. This caches the parsed struct keyed by a hash of the
raw content (PDF bytes or text), so an identical re-run returns instantly with
zero OpenAI calls — the common case when iterating on a demo.

- In-memory dict (per process) + optional JSON persistence under tmp_dir so the
  cache survives restarts (incl. uvicorn --reload).
- Disabled entirely when settings.extraction_cache is False.
- Only exact-content matches hit → zero quality risk.
"""

import hashlib
import json
import logging
import threading
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("app.extract_cache")

_mem: dict[str, dict] = {}
_lock = threading.Lock()


def key_for(kind: str, content: bytes) -> str:
    return f"{kind}_{hashlib.sha1(content).hexdigest()}"


def _disk_path(key: str) -> Path:
    return settings.tmp_dir / "extract_cache" / f"{key}.json"


def get(kind: str, content: bytes) -> dict | None:
    """Return the cached struct for this content, or None on miss/disabled."""
    if not settings.extraction_cache:
        return None
    key = key_for(kind, content)
    with _lock:
        hit = _mem.get(key)
    if hit is not None:
        return hit
    path = _disk_path(key)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            with _lock:
                _mem[key] = data
            return data
        except Exception as exc:  # corrupt/partial file → treat as miss
            logger.warning("extract_cache: failed reading %s: %s", path, exc)
    return None


def put(kind: str, content: bytes, value: dict) -> None:
    """Store the parsed struct for this content (RAM + best-effort disk)."""
    if not settings.extraction_cache or not isinstance(value, dict):
        return
    key = key_for(kind, content)
    with _lock:
        _mem[key] = value
    try:
        path = _disk_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # disk cache is optional; never fail the request
        logger.warning("extract_cache: failed writing %s: %s", key, exc)
