from datetime import datetime, timezone

import pytest

from app.services.exchange_rate import _extract_rate_from_payload


def test_extract_rate_from_payload_accepts_valid_response() -> None:
    payload = {
        "result": "success",
        "rates": {
            "VND": 26236.346503,
        },
        "time_last_update_unix": 1760000000,
        "time_next_update_unix": 1760086400,
    }

    entry = _extract_rate_from_payload(payload)

    assert entry.rate == 26236.346503
    assert entry.source_updated_at == datetime.fromtimestamp(1760000000, tz=timezone.utc)
    assert entry.next_update_at == datetime.fromtimestamp(1760086400, tz=timezone.utc)


@pytest.mark.parametrize(
    "payload",
    [
        {"result": "error", "rates": {"VND": 26236.346503}},
        {"result": "success", "rates": {}},
        {"result": "success", "rates": {"VND": 0}},
        {"result": "success", "rates": {"VND": "nan"}},
    ],
)
def test_extract_rate_from_payload_rejects_invalid_response(payload: dict) -> None:
    with pytest.raises(ValueError):
        _extract_rate_from_payload(payload)
