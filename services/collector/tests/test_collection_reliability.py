from contextlib import contextmanager, nullcontext
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from collector.collection.runner import CollectionRunner
from collector.repository.collection_lock import CollectionBusyError, target_collection_lock
from collector.repository.models import CollectionBatchStatus as S


@pytest.mark.parametrize('return_code', [-1, -2, -3, -999])
def test_lock_conflict_never_enters_collection(monkeypatch, return_code):
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.execute.return_value.fetchone.return_value = (return_code,)
    monkeypatch.setattr('collector.repository.collection_lock.repository_connection', lambda: nullcontext(connection))
    with pytest.raises(CollectionBusyError):
        with target_collection_lock(uuid4()):
            pytest.fail('Must not enter critical section')
    assert cursor.execute.call_count == 1
    cursor.close.assert_called_once()


def test_lock_released_when_collection_raises(monkeypatch):
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.execute.return_value.fetchone.return_value = (0,)
    monkeypatch.setattr('collector.repository.collection_lock.repository_connection', lambda: nullcontext(connection))
    with pytest.raises(RuntimeError):
        with target_collection_lock(uuid4()):
            raise RuntimeError('test')
    assert 'sp_releaseapplock' in cursor.execute.call_args.args[0]


@pytest.mark.parametrize('failure', [None, 'SOURCE_STATE', 'QUERY_RUNTIME', 'METADATA'])
def test_component_failures_preserve_correct_source_progress(monkeypatch, failure):
    import collector.collection.runner as module
    now = datetime(2026, 10, 12, 10)
    batch = SimpleNamespace(batch_id=uuid4(), target_id=uuid4(), status=S.PENDING,
        effective_window_start_utc=None, effective_window_end_utc=None, window_source=None,
        requested_window_start_utc=None, requested_window_end_utc=None, force_metadata=True,
        completeness_percent=0)
    batches = Mock()
    batches.get.return_value = batch
    def transition(id, status, **kwargs):
        batch.status=status
        batch.completeness_percent=kwargs.get('completeness_percent', 0)
        return batch
    batches.transition.side_effect=transition
    batches.set_effective_window.return_value=batch
    states=Mock(); states.get.return_value=None
    targets=Mock(); targets.get.return_value=SimpleNamespace(is_enabled=True)
    monkeypatch.setattr(module, 'target_collection_lock', lambda id: nullcontext())
    monkeypatch.setattr(module, 'open_target_connection', lambda target: nullcontext(Mock()))
    monkeypatch.setattr(module, 'utc_now_naive', lambda: now)
    source=SimpleNamespace(observed_at_utc=now, sql_server_start_time_utc=now)
    monkeypatch.setattr(module, 'read_source_state', Mock(return_value=source))
    for name in ['read_query_runtime','read_index_usage','read_index_operational','read_missing_indexes']:
        monkeypatch.setattr(module, name, Mock(return_value=[]))
    monkeypatch.setattr(module, 'read_metadata', Mock(return_value=SimpleNamespace(tables=[],columns=[],indexes=[],index_columns=[],constraints=[])))
    if failure:
        function={'SOURCE_STATE':'read_source_state','QUERY_RUNTIME':'read_query_runtime','METADATA':'read_metadata'}[failure]
        getattr(module,function).side_effect=RuntimeError('sensitive diagnostic')
    runner=CollectionRunner(targets=targets,batches=batches,states=states,evidence=Mock(),components=Mock(),policy=SimpleNamespace(initial_lookback_minutes=60,metadata_refresh_minutes=60))
    result=runner.collect(batch.batch_id)
    assert result.final_status == (S.COMPLETED if failure is None else S.FAILED if failure=='SOURCE_STATE' else S.PARTIAL)
    assert states.advance_query_watermark.call_count == (0 if failure in ['SOURCE_STATE','QUERY_RUNTIME'] else 1)
    assert states.mark_metadata_collected.call_count == (0 if failure in ['SOURCE_STATE','METADATA'] else 1)


def test_collecting_batch_is_not_rerun(monkeypatch):
    batches=Mock();batches.get.return_value=SimpleNamespace(target_id=uuid4(),status=S.COLLECTING)
    monkeypatch.setattr('collector.collection.runner.target_collection_lock', lambda id:nullcontext())
    runner=CollectionRunner(batches=batches,targets=Mock(),states=Mock(),evidence=Mock(),components=Mock(),policy=Mock())
    with pytest.raises(ValueError):runner.collect(uuid4())
    batches.transition.assert_not_called()
