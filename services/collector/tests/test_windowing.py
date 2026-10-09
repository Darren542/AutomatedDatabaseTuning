from datetime import datetime, timedelta

from collector.collection.windowing import metadata_is_due, resolve_effective_window

def test_first_auto_window_is_bounded():
    now = datetime(2026, 10, 9, 2, 0, 0)
    result = resolve_effective_window(
        requested_start_utc=None,
        requested_end_utc=None,
        previous_watermark_utc=None,
        now_utc=now,
        initial_lookback_minutes=60,
    )
    assert result.source == "InitialLookback"
    assert result.start_utc == datetime(2026, 10, 9, 1, 0, 0)
    assert result.end_utc == now

def test_incremental_window_uses_watermark():
    now = datetime(2026, 10, 9, 2, 0, 0)
    watermark = datetime(2026, 10, 9, 1, 45, 0)
    result = resolve_effective_window(
        requested_start_utc=None,
        requested_end_utc=None,
        previous_watermark_utc=watermark,
        now_utc=now,
        initial_lookback_minutes=60,
    )
    assert result.source == "Incremental"
    assert result.start_utc == watermark
    assert result.end_utc == now

def test_explicit_window_wins():
    result = resolve_effective_window(
        requested_start_utc=datetime(2026, 10, 8, 10, 0, 0),
        requested_end_utc=datetime(2026, 10, 8, 11, 0, 0),
        previous_watermark_utc=datetime(2026, 10, 9, 1, 0, 0),
        now_utc=datetime(2026, 10, 9, 2, 0, 0),
        initial_lookback_minutes=60,
    )
    assert result.source == "Explicit"

def test_metadata_cadence_and_force():
    now = datetime(2026, 10, 9, 2, 0, 0)
    assert not metadata_is_due(
        last_metadata_collected_at_utc=now - timedelta(minutes=10),
        now_utc=now,
        refresh_minutes=60,
        force_metadata=False,
    )
    assert metadata_is_due(
        last_metadata_collected_at_utc=now - timedelta(minutes=61),
        now_utc=now,
        refresh_minutes=60,
        force_metadata=False,
    )
    assert metadata_is_due(
        last_metadata_collected_at_utc=now,
        now_utc=now,
        refresh_minutes=60,
        force_metadata=True,
    )
