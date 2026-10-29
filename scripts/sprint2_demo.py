"""Prepare an isolated synthetic acceptance repository, or serve it for a UI demo.

Only names prefixed AutoTuner_Sprint2_Demo_ are accepted. Existing databases are
never reseeded or dropped. This script never changes the normal repository or
monitored target. All fixtures are synthetic, not measured production results.
"""
import argparse
from dataclasses import fields, replace
from datetime import datetime
from pathlib import Path
import json
import os
import re

import pyodbc

from collector.collection import records
from collector.repository.collection_batches import SqlCollectionBatchRepository
from collector.repository.component_results import SqlComponentResultRepository
from collector.repository.connection import RepositorySettings
from collector.repository.evidence import SqlEvidenceRepository
from collector.repository.models import CollectionBatchStatus as Status
from collector.repository.targets import SqlTargetRepository
from collector.targets import TargetConfiguration
from recommender.engine import utc
from recommender.fixtures import acceptance_bundle
from recommender.repository import RecommendationRepository
from recommender.service import RecommendationService


def materialize(cls, row):
    values = {}
    for field in fields(cls):
        if field.name in row:
            values[field.name] = row[field.name]
        elif field.name.startswith('is_') or field.name == 'has_filter':
            values[field.name] = False
        elif field.name.endswith('_utc') or field.name in ('filter_definition', 'query_hash', 'query_plan_hash'):
            values[field.name] = None
        elif field.name == 'index_type_desc':
            values[field.name] = 'CLUSTERED' if row.get('index_type') == 1 else 'NONCLUSTERED'
        else:
            values[field.name] = 0
    return cls(**values)


def seed(database):
    original = RepositorySettings.load()
    master = replace(original, database='master')
    connection = pyodbc.connect(master.to_connection_string(), autocommit=True, timeout=10)
    try:
        if connection.execute('SELECT DB_ID(?);', database).fetchone()[0] is not None:
            raise ValueError('Demo database already exists. Choose a new name; existing data is never overwritten.')
        root = Path(__file__).resolve().parents[1]
        for migration in sorted((root / 'sql/databases/repository/migrations').glob('*.sql')):
            sql = migration.read_text(encoding='utf-8').replace('AutoTunerRepository', database)
            for batch in re.split(r'^\s*GO\s*$', sql, flags=re.I | re.M):
                if batch.strip():
                    cursor = connection.cursor()
                    try:
                        cursor.execute(batch)
                        while cursor.nextset():
                            pass
                    finally:
                        cursor.close()
        # Migration 005 is explicitly verified as rerunnable in the isolated DB.
        sql = (root / 'sql/databases/repository/migrations/005_recommendation_analysis.sql').read_text(encoding='utf-8').replace('AutoTunerRepository', database)
        for batch in re.split(r'^\s*GO\s*$', sql, flags=re.I | re.M):
            if batch.strip():
                cursor = connection.cursor()
                try:
                    cursor.execute(batch)
                    while cursor.nextset(): pass
                finally:
                    cursor.close()
    finally:
        connection.close()
    settings = replace(original, database=database)
    targets = SqlTargetRepository(settings)
    batches = SqlCollectionBatchRepository(settings)
    evidence = SqlEvidenceRepository(settings)
    components = SqlComponentResultRepository(settings)
    target = targets.create(TargetConfiguration(name='Sprint 2 synthetic acceptance', server=original.server,
        database='SyntheticEvidenceOnly', trust_server_certificate=original.trust_server_certificate), credential_reference=None)
    fixture = acceptance_bundle()
    index_by_key = {(r['object_id'], r['index_id']): r for r in fixture['indexes']}
    table_by_id = {t['object_id']: t for t in fixture['tables']}
    current = None
    for old in (True, False):
        source = fixture['baseline']['source'] if old else fixture['source']
        observed = utc(source['observed_at_utc']).replace(tzinfo=None)
        server_start = utc(source['sql_server_start_time_utc']).replace(tzinfo=None)
        batch = batches.create(target_id=target.target_id, label='Synthetic baseline · 48-hour observation' if old else 'Synthetic acceptance · read/write ranking',
            requested_window_start_utc=None, requested_window_end_utc=None, collector_version='sprint2-demo', force_metadata=True)
        batches.transition(batch.batch_id, Status.COLLECTING)
        batches.set_effective_window(batch.batch_id, start_utc=observed, end_utc=observed, window_source='Explicit')
        state = records.SourceState(observed, server_start, 5, utc(source['database_create_date_utc']).replace(tzinfo=None), 'READ_WRITE', 1 if old else 2, 102, 102)
        evidence.save_source_state(batch_id=batch.batch_id, target_id=target.target_id, state=state)
        metadata = records.MetadataBundle(
            tables=[materialize(records.TableMetadata, r) for r in fixture['tables']],
            columns=[materialize(records.ColumnMetadata, r) for r in fixture['columns']],
            indexes=[materialize(records.IndexMetadata, r) for r in fixture['indexes']],
            index_columns=[materialize(records.IndexColumnMetadata, r) for r in fixture['index_columns']], constraints=[])
        evidence.save_metadata(batch_id=batch.batch_id, target_id=target.target_id, observed_at_utc=observed, metadata=metadata)
        usage = []
        for r in fixture['baseline']['usage'] if old else fixture['usage']:
            table, index = table_by_id[r['object_id']], index_by_key[(r['object_id'], r['index_id'])]
            usage.append(materialize(records.IndexUsageObservation, dict(r, schema_name=table['schema_name'], table_name=table['table_name'], index_name=index['index_name'])))
        evidence.save_index_usage(batch_id=batch.batch_id, target_id=target.target_id, sql_server_start_time_utc=server_start, observed_at_utc=observed, rows=usage)
        missing = [materialize(records.MissingIndexObservation, r) for r in fixture['missing']] if not old else []
        evidence.save_missing_indexes(batch_id=batch.batch_id, target_id=target.target_id, sql_server_start_time_utc=server_start, observed_at_utc=observed, rows=missing)
        runtime = [materialize(records.QueryRuntimeEvidence, dict(r, runtime_stats_interval_id=1, runtime_stats_id=r['query_id'], plan_id=r['query_id'], query_text_id=r['query_id'], object_id=None,
            execution_type=0, execution_type_desc='Regular', interval_start_utc=observed, interval_end_utc=observed)) for r in fixture['queries']] if not old else []
        evidence.save_query_runtime(batch_id=batch.batch_id, target_id=target.target_id, rows=runtime)
        for name, count in [('SOURCE_STATE', 1), ('METADATA', sum(len(x) for x in [metadata.tables, metadata.columns, metadata.indexes, metadata.index_columns, metadata.constraints])), ('QUERY_RUNTIME', len(runtime)), ('INDEX_USAGE', len(usage)), ('INDEX_OPERATIONAL', 0), ('MISSING_INDEX', len(missing))]:
            components.start(batch.batch_id, name)
            components.complete(batch.batch_id, name, count)
        current = batches.transition(batch.batch_id, Status.COMPLETED, completeness_percent=100)
    repository = RecommendationRepository(settings)
    result = RecommendationService(repository).analyze(current.batch_id)
    creates = [r for r in result['recommendations'] if r['action'] == 'CREATE']
    assert [r['table_name'] for r in creates] == ['Orders', 'Events']
    assert any(r['action'] == 'DROP' for r in result['recommendations'])
    assert not any(r['action'] == 'DROP' and r['protected'] for r in result['recommendations'])
    assert repository.get(result['analysis_id']) == result
    assert repository.list(target.target_id)[0]['recommendation_count'] == len(result['recommendations'])
    print(json.dumps(dict(database=database, target_id=str(target.target_id), batch_id=str(current.batch_id), analysis_id=result['analysis_id'], recommendations=len(result['recommendations']), validation='Migration rerun, repository load, ranking, safety, save, and reopen passed.'), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--seed', action='store_true')
    mode.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8093)
    args = parser.parse_args()
    if not re.fullmatch(r'AutoTuner_Sprint2_Demo_[A-Za-z0-9_]{1,80}', args.database):
        parser.error('Database must use the safe AutoTuner_Sprint2_Demo_ prefix and letters/digits/underscores.')
    if args.seed:
        seed(args.database)
    else:
        os.environ['AUTOTUNER_REPO_SQL_DATABASE'] = args.database
        from autotuner_api.app import create_app
        from autotuner_api.config import Settings
        import uvicorn
        uvicorn.run(create_app(Settings(port=args.port)), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
