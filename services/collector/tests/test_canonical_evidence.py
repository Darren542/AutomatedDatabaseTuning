from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from collector.repository.evidence import SqlEvidenceRepository


def test_evidence_lookup_and_update_include_interval_start(monkeypatch):
    connection=Mock();cursor=connection.cursor.return_value
    cursor.execute.return_value=cursor
    cursor.rowcount=0
    cursor.fetchone.return_value=SimpleNamespace(EvidenceId=7)
    monkeypatch.setattr('collector.repository.evidence.repository_connection',lambda settings:nullcontext(connection))
    now=datetime(2026,10,12)
    attributes=['plan_id','query_id','query_text_id','object_id','query_hash','query_plan_hash','query_sql_text','execution_type','execution_type_desc','interval_start_utc','interval_end_utc','first_execution_time_utc','last_execution_time_utc','execution_count','avg_duration_microseconds','avg_cpu_time_microseconds','avg_logical_io_reads','avg_logical_io_writes','avg_physical_io_reads','avg_row_count','runtime_stats_interval_id','runtime_stats_id']
    item=SimpleNamespace(**{key:1 for key in attributes});item.interval_start_utc=now
    assert SqlEvidenceRepository().save_query_runtime(batch_id=uuid4(),target_id=uuid4(),rows=[item])==1
    for call in cursor.execute.call_args_list:
        sql,*params=call.args
        assert sql.count('?')==len(params)
        if 'WHERE TargetId' in sql:
            assert 'AND IntervalStartUtc = ?' in sql
            assert params[-1]==now
    connection.commit.assert_called_once()
