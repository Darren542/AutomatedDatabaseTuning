"""Synthetic, deterministic acceptance input. Never loaded into normal analyses."""
from copy import deepcopy


def acceptance_bundle():
    columns = []
    tables = []
    indexes = []
    index_columns = []
    usage = []
    missing = []
    queries = []
    for oid, name, payload_width, updates in [(101, 'Orders', 8, 1), (102, 'Events', 4000, 1000000)]:
        tables.append(dict(object_id=oid, schema_name='sales', table_name=name, row_count=100000, data_size_mb=10))
        for cid, col, dtype, width in [(1, 'Id', 'int', 4), (2, 'CustomerId', 'int', 4), (3, 'OrderDate', 'datetime2', 8), (4, 'Payload', 'varchar', payload_width)]:
            columns.append(dict(object_id=oid, column_id=cid, column_name=col, data_type=dtype, max_length=width, is_computed=False))
        for iid, col, primary in [(1, 1, True), (9, 3, False), (10, 3, False)]:
            indexes.append(dict(object_id=oid, index_id=iid, index_name=f'IX_{name}_{iid}', index_type=1 if primary else 2, is_unique=primary, is_primary_key=primary, is_unique_constraint=False, is_disabled=False, has_filter=False, filter_definition=None))
            index_columns.append(dict(object_id=oid, index_id=iid, column_id=col, key_ordinal=1, index_column_id=1, is_included_column=False, is_descending_key=False))
            usage.append(dict(object_id=oid, index_id=iid, user_seeks=10 if iid == 9 else 0, user_scans=0, user_lookups=0, user_updates=updates if iid == 1 else 100))
        missing.append(dict(object_id=oid, schema_name='sales', table_name=name, equality_columns='[CustomerId]', inequality_columns=None, included_columns='[Payload]', group_handle=oid, index_handle=oid, user_seeks=1000, user_scans=0, avg_total_user_cost=100.0, avg_user_impact=80.0))
        queries.append(dict(evidence_id=oid, query_id=oid, query_sql_text=f'SELECT [Payload] FROM [sales].[{name}] WHERE [CustomerId] = @id;', execution_count=1000, avg_duration_microseconds=20000, avg_cpu_time_microseconds=10000, avg_logical_io_reads=100))
    source = dict(observed_at_utc='2026-10-28T12:00:00Z', sql_server_start_time_utc='2026-10-01T00:00:00Z', database_id=5, database_create_date_utc='2026-01-01T00:00:00Z', dmv_reset_detected=False)
    old_usage = [dict(row, user_seeks=0, user_updates=0) for row in usage]
    return dict(batch=dict(batch_id='11111111-1111-1111-1111-111111111111', target_id='22222222-2222-2222-2222-222222222222'), source=source,
        metadata_batch_id='33333333-3333-3333-3333-333333333333', metadata_observed_at_utc='2026-10-28T11:00:00Z',
        tables=tables, columns=columns, indexes=indexes, index_columns=index_columns, constraints=[], usage=usage, operational=[], missing=missing, queries=queries,
        baseline=dict(batch_id='44444444-4444-4444-4444-444444444444', source=dict(source, observed_at_utc='2026-10-26T12:00:00Z'), usage=old_usage, indexes=deepcopy(indexes), index_columns=deepcopy(index_columns)))
