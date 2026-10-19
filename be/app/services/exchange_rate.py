import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import BASE_DIR, settings


logger = logging.getLogger(__name__)

PRIMARY_CACHE_MAX_AGE = timedelta(hours=1)
FALLBACK_CACHE_MAX_AGE = timedelta(hours=24)


@dataclass
class ExchangeRateCacheEntry:
    rate: float
    fetched_at: datetime
    source_updated_at: datetime | None = None
    next_update_at: datetime | None = None


def _resolve_cache_path() -> Path:
    configured = Path(settings.usd_vnd_rate_cache_file)
    return configured if configured.is_absolute() else (BASE_DIR / configured)


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _from_unix_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(numeric, tz=timezone.utc)


def _load_cache() -> ExchangeRateCacheEntry | None:
    path = _resolve_cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read exchange rate cache: %s", exc)
        return None

    try:
        rate = float(payload["rate"])
    except (KeyError, TypeError, ValueError):
        return None
    if rate <= 0:
        return None

    fetched_at = _parse_datetime(payload.get("fetchedAt"))
    if fetched_at is None:
        return None

    return ExchangeRateCacheEntry(
        rate=rate,
        fetched_at=fetched_at,
        source_updated_at=_parse_datetime(payload.get("sourceUpdatedAt")),
        next_update_at=_parse_datetime(payload.get("nextUpdateAt")),
    )


def _save_cache(entry: ExchangeRateCacheEntry) -> None:
    path = _resolve_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "rate": entry.rate,
                    "fetchedAt": entry.fetched_at.isoformat(),
                    "sourceUpdatedAt": entry.source_updated_at.isoformat() if entry.source_updated_at else None,
                    "nextUpdateAt": entry.next_update_at.isoformat() if entry.next_update_at else None,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not write exchange rate cache: %s", exc)


def _cache_age(now: datetime, entry: ExchangeRateCacheEntry) -> timedelta:
    return now - entry.fetched_at


def _extract_rate_from_payload(payload: dict[str, Any]) -> ExchangeRateCacheEntry:
    if payload.get("result") != "success":
        raise ValueError("Exchange rate API did not return success")

    rates = payload.get("rates")
    if not isinstance(rates, dict) or "VND" not in rates:
        raise ValueError("Exchange rate API payload missing rates.VND")

    rate = float(rates["VND"])
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("Exchange rate API returned invalid VND rate")

    now = datetime.now(timezone.utc)
    return ExchangeRateCacheEntry(
        rate=rate,
        fetched_at=now,
        source_updated_at=_from_unix_timestamp(payload.get("time_last_update_unix")),
        next_update_at=_from_unix_timestamp(payload.get("time_next_update_unix")),
    )


async def _fetch_live_rate() -> ExchangeRateCacheEntry:
    async with httpx.AsyncClient(timeout=settings.usd_vnd_rate_timeout_seconds) as client:
        response = await client.get(settings.usd_vnd_rate_api_url)
    if response.status_code != 200:
        raise ValueError(f"Exchange rate API returned status {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Exchange rate API payload is not a JSON object")
    return _extract_rate_from_payload(payload)


async def get_usd_vnd_rate() -> float:
    now = datetime.now(timezone.utc)
    cached = _load_cache()

    if cached and _cache_age(now, cached) <= PRIMARY_CACHE_MAX_AGE:
        return cached.rate

    try:
        live_entry = await _fetch_live_rate()
        _save_cache(live_entry)
        return live_entry.rate
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Could not refresh USD/VND exchange rate: %s", exc)
        if cached and _cache_age(now, cached) <= FALLBACK_CACHE_MAX_AGE:
            logger.warning("Using cached USD/VND exchange rate fetched at %s", cached.fetched_at.isoformat())
            return cached.rate
        logger.error("Falling back to DEFAULT_USD_VND_RATE=%s", settings.default_usd_vnd_rate)
        return settings.default_usd_vnd_rate
