from services.collector.repository import _ALLOWED_TRANSITIONS

def test_completed_is_terminal():
    assert _ALLOWED_TRANSITIONS["Completed"] == set()

def test_pending_can_start():
    assert "Collecting" in _ALLOWED_TRANSITIONS["Pending"]

def test_collecting_can_finish_partial():
    assert "Partial" in _ALLOWED_TRANSITIONS["Collecting"]
