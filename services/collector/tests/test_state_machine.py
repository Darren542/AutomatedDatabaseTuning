from collector.repository.collection_batches import _ALLOWED_TRANSITIONS
from collector.repository.models import CollectionBatchStatus as S

def test_terminal_batches_cannot_be_reopened():
    for state in (S.COMPLETED, S.PARTIAL, S.FAILED, S.CANCELLED):
        assert _ALLOWED_TRANSITIONS[state] == set()

def test_pending_can_start_or_cancel():
    assert S.COLLECTING in _ALLOWED_TRANSITIONS[S.PENDING]
    assert S.CANCELLED in _ALLOWED_TRANSITIONS[S.PENDING]
