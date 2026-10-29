from datetime import datetime, timezone
import pytest
from autotuner_api.routes.collections import CreateCollectionRequest
from uuid import uuid4

def test_windows_are_normalized_before_comparison():
    r = CreateCollectionRequest(target_id=uuid4(), requested_window_start_utc="2026-10-01T00:00:00", requested_window_end_utc="2026-10-01T01:00:00Z")
    assert r.requested_window_start_utc.tzinfo == timezone.utc

def test_incomplete_window_is_invalid():
    with pytest.raises(ValueError):
        CreateCollectionRequest(target_id=uuid4(), requested_window_start_utc=datetime.now())


def test_future_historical_window_is_rejected():
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        CreateCollectionRequest(target_id=uuid4(), requested_window_start_utc=now, requested_window_end_utc=now + timedelta(hours=1))
