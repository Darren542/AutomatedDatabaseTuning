"""Repository-only reads and append-only analysis persistence; no target connection."""
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import re
from uuid import UUID, uuid4

from collector.repository.connection import RepositorySettings, repository_connection


def _name(value):
    return re.sub(r'(?<!^)(?=[A-Z][a-z]|(?<=[a-z0-9])[A-Z])', '_', value).lower()


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if isinstance(value, UUID):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(type(value).__name__)


def canonical_json(value):
    return json.dumps(value, default=json_default, ensure_ascii=False, sort_keys=True, allow_nan=False)


class AnalysisInputError(ValueError):
    pass


class RecommendationRepository:
    def __init__(self, settings: RepositorySettings | None = None):
        self.settings = settings

    def load(self, batch_id):
        with repository_connection(self.settings) as conn:
            cursor = conn.cursor()
            try:
                def rows(sql, *parameters):
                    cursor.execute(sql, *parameters)
                    names = [_name(c[0]) for c in cursor.description]
                    return [dict(zip(names, row)) for row in cursor.fetchall()]
                def one(sql, *parameters):
                    result = rows(sql, *parameters)
                    return result[0] if result else None
                batch = one('SELECT * FROM dbo.CollectionBatch WHERE BatchId=?;', str(batch_id))
                if not batch:
                    raise KeyError('Collection not found.')
                if batch['status'] not in ('Completed', 'Partial'):
                    raise AnalysisInputError('Analyze a completed collection with successful required components.')
                statuses = {r['component_name']: r['status'] for r in rows('SELECT ComponentName, Status FROM dbo.CollectionComponentResult WHERE BatchId=?;', str(batch_id))}
                required = ('SOURCE_STATE', 'QUERY_RUNTIME', 'INDEX_USAGE', 'INDEX_OPERATIONAL', 'MISSING_INDEX')
                if any(statuses.get(name) != 'Completed' for name in required):
                    raise AnalysisInputError('Required evidence components are incomplete. Collect the target again.')
                source = one('SELECT * FROM dbo.CollectionSourceState WHERE BatchId=?;', str(batch_id))
                if not source:
                    raise AnalysisInputError('Source/reset context is missing.')
                def metadata_for(source_row):
                    return one('''SELECT TOP (1) c.BatchId, s.ObservedAtUtc
                        FROM dbo.CollectionComponentResult c
                        JOIN dbo.CollectionSourceState s ON s.BatchId=c.BatchId
                        WHERE s.TargetId=? AND c.ComponentName='METADATA' AND c.Status='Completed'
                          AND s.ObservedAtUtc<=? AND s.DatabaseId=? AND s.DatabaseCreateDateUtc=?
                        ORDER BY s.ObservedAtUtc DESC, c.BatchId;''',
                        str(batch['target_id']), source_row['observed_at_utc'], source_row['database_id'], source_row['database_create_date_utc'])
                metadata = metadata_for(source)
                if not metadata:
                    raise AnalysisInputError('No successful metadata snapshot exists for this database epoch. Force metadata refresh.')
                metadata_id = str(metadata['batch_id'])
                baseline = one('''SELECT TOP (1) s.* FROM dbo.CollectionSourceState s
                    JOIN dbo.CollectionComponentResult c ON c.BatchId=s.BatchId AND c.ComponentName='INDEX_USAGE' AND c.Status='Completed'
                    WHERE s.TargetId=? AND s.ObservedAtUtc<? AND s.SqlServerStartTimeUtc=?
                      AND s.DatabaseId=? AND s.DatabaseCreateDateUtc=?
                    ORDER BY s.ObservedAtUtc, s.BatchId;''', str(batch['target_id']), source['observed_at_utc'],
                    source['sql_server_start_time_utc'], source['database_id'], source['database_create_date_utc'])
                old = None
                if baseline:
                    old_metadata = metadata_for(baseline)
                    old = dict(batch_id=baseline['batch_id'], source=baseline,
                        usage=rows('SELECT * FROM dbo.IndexUsageObservation WHERE BatchId=?;', str(baseline['batch_id'])),
                        operational=rows('SELECT * FROM dbo.IndexOperationalObservation WHERE BatchId=?;', str(baseline['batch_id'])),
                        indexes=rows('SELECT * FROM dbo.IndexMetadataSnapshot WHERE BatchId=?;', str(old_metadata['batch_id'])) if old_metadata else [],
                        index_columns=rows('SELECT * FROM dbo.IndexColumnMetadataSnapshot WHERE BatchId=?;', str(old_metadata['batch_id'])) if old_metadata else [])
                bundle = dict(batch=batch, source=source, metadata_batch_id=metadata['batch_id'], metadata_observed_at_utc=metadata['observed_at_utc'], baseline=old)
                # Fixed table names only. All identifiers from callers remain parameters.
                for name, table in [('tables', 'TableMetadataSnapshot'), ('columns', 'ColumnMetadataSnapshot'), ('indexes', 'IndexMetadataSnapshot'), ('index_columns', 'IndexColumnMetadataSnapshot'), ('constraints', 'ConstraintMetadataSnapshot')]:
                    bundle[name] = rows(f'SELECT * FROM dbo.{table} WHERE BatchId=?;', metadata_id)
                for name, table in [('usage', 'IndexUsageObservation'), ('operational', 'IndexOperationalObservation'), ('missing', 'MissingIndexObservation')]:
                    bundle[name] = rows(f'SELECT * FROM dbo.{table} WHERE BatchId=?;', str(batch_id))
                bundle['queries'] = rows('''SELECT e.EvidenceId, e.QueryId, e.QuerySqlText, e.ExecutionCount,
                    e.AvgDurationMicroseconds, e.AvgCpuTimeMicroseconds, e.AvgLogicalIoReads
                    FROM dbo.QueryStoreRuntimeEvidence e JOIN dbo.CollectionQueryStoreEvidence b ON b.EvidenceId=e.EvidenceId
                    WHERE b.BatchId=? ORDER BY e.EvidenceId;''', str(batch_id))
                # Close the read transaction before later append-only persistence.
                conn.commit()
                return bundle
            finally:
                cursor.close()

    def save(self, bundle, result):
        analysis_id = str(uuid4())
        inputs = canonical_json(bundle)
        result = dict(result, analysis_id=analysis_id, batch_id=str(bundle['batch']['batch_id']),
            target_id=str(bundle['batch']['target_id']), metadata_batch_id=str(bundle['metadata_batch_id']),
            observed_at_utc=json_default(bundle['source']['observed_at_utc']) if isinstance(bundle['source']['observed_at_utc'], datetime) else bundle['source']['observed_at_utc'],
            input_hash=sha256(inputs.encode('utf-8')).hexdigest())
        payload = canonical_json(result)
        with repository_connection(self.settings) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''INSERT INTO dbo.RecommendationAnalysis
                    (AnalysisId, TargetId, BatchId, MetadataBatchId, CandidateSetId, EngineVersion, InputHash, RecommendationCount, InputJson, ResultJson)
                    VALUES (?,?,?,?,?,?,?,?,?,?);''', analysis_id, result['target_id'], result['batch_id'], result['metadata_batch_id'], result.get('candidate_set_id'),
                    result['engine_version'], result['input_hash'], len(result['recommendations']), inputs, payload)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
        return result

    def list(self, target_id=None, limit=50, candidate_set_id=None):
        limit = max(1, min(int(limit), 100))
        with repository_connection(self.settings) as conn:
            cursor = conn.cursor()
            try:
                sql = f'SELECT TOP ({limit}) AnalysisId, TargetId, BatchId, MetadataBatchId, CandidateSetId, EngineVersion, InputHash, RecommendationCount, CreatedAtUtc FROM dbo.RecommendationAnalysis'
                conditions=[]; parameters=[]
                if target_id: conditions.append('TargetId=?'); parameters.append(str(target_id))
                if candidate_set_id: conditions.append('CandidateSetId=?'); parameters.append(str(candidate_set_id))
                cursor.execute(sql + (' WHERE '+ ' AND '.join(conditions) if conditions else '') + ' ORDER BY CreatedAtUtc DESC, AnalysisId;', *parameters)
                names = [_name(c[0]) for c in cursor.description]
                return [dict(zip(names, row)) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def get(self, analysis_id):
        with repository_connection(self.settings) as conn:
            cursor = conn.cursor()
            try:
                row = cursor.execute('SELECT ResultJson FROM dbo.RecommendationAnalysis WHERE AnalysisId=?;', str(analysis_id)).fetchone()
                if not row:
                    raise KeyError('Analysis not found.')
                return json.loads(row[0])
            finally:
                cursor.close()


    def get_input(self, analysis_id):
        with repository_connection(self.settings) as conn:
            cursor=conn.cursor()
            try:
                row=cursor.execute('SELECT InputJson FROM dbo.RecommendationAnalysis WHERE AnalysisId=?',str(analysis_id)).fetchone()
                if row is None: raise KeyError('Analysis not found.')
                return json.loads(row[0])
            finally: cursor.close()
