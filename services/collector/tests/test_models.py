from datetime import datetime, timezone
from uuid import uuid4
import pytest
from services.collector.models import CollectionBatchCreate

def test_collection_window_accepts_valid_range():
    x = CollectionBatchCreate(
        target_id=uuid4(),
        requested_window_start_utc=datetime(2026, 10, 8, 10, tzinfo=timezone.utc),
        requested_window_end_utc=datetime(2026, 10, 8, 11, tzinfo=timezone.utc),
    )
    assert x.requested_window_start_utc < x.requested_window_end_utc

def test_collection_window_rejects_reverse_range():
    with pytest.raises(ValueError):
        CollectionBatchCreate(
            target_id=uuid4(),
            requested_window_start_utc=datetime(2026, 10, 8, 12, tzinfo=timezone.utc),
            requested_window_end_utc=datetime(2026, 10, 8, 11, tzinfo=timezone.utc),
        )
