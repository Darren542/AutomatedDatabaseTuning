"""Separate collection -> candidate set -> weighted scoring workflow."""
from hashlib import sha256
import json
from uuid import UUID,uuid4

from collector.repository.connection import repository_connection
from collector.repository.collection_batches import SqlCollectionBatchRepository
from collector.repository.collection_lock import target_collection_lock
from recommender.engine import VERSION, Policy, analyze
from recommender.repository import RecommendationRepository, canonical_json


def generate_candidates(bundle):
    result = analyze(bundle, score=False)
    for row in result['recommendations']:
        row.pop('score', None)
        row.pop('rank', None)
        row.pop('policy', None)
        row['status'] = 'Unscored' if row['action'] == 'CREATE' else row['status']
        row['features'] = {k: v for k, v in row.pop('score_components').items()
            if k not in ('read_benefit', 'write_penalty', 'maintenance_penalty')}
        row['features']['planning_storage_mb']=row.pop('predicted_impact')['storage_estimate_mb']
        if row['action']=='CREATE': row['rationale']='Missing-index evidence suggests a new covering access path. Review keys, includes and existing-index coverage before scoring.'
    result.pop('policy', None)
    return result


class CandidateRepository:
    def save(self, bundle, result):
        inputs = canonical_json(bundle)
        result = dict(result, candidate_set_id=str(uuid4()), batch_id=str(UUID(str(bundle['batch']['batch_id']))),
            target_id=str(UUID(str(bundle['batch']['target_id']))), metadata_batch_id=str(UUID(str(bundle['metadata_batch_id']))),
            observed_at_utc=json.loads(canonical_json(bundle['source']['observed_at_utc'])), input_hash=sha256(inputs.encode('utf-8')).hexdigest())
        with repository_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''INSERT dbo.CandidateSet
                    (CandidateSetId,TargetId,BatchId,MetadataBatchId,EngineVersion,InputHash,InputJson,ResultJson)
                    VALUES (?,?,?,?,?,?,?,?)''', result['candidate_set_id'], result['target_id'], result['batch_id'],
                    result['metadata_batch_id'], VERSION, result['input_hash'], inputs, canonical_json(result))
                conn.commit()
            except Exception:
                conn.rollback(); raise
            finally:
                cursor.close()
        return result

    def get(self, candidate_set_id, *, inputs=False):
        with repository_connection() as conn:
            cursor = conn.cursor()
            try:
                row = cursor.execute('SELECT InputJson,ResultJson FROM dbo.CandidateSet WHERE CandidateSetId=?',str(candidate_set_id)).fetchone()
                if row is None: raise KeyError('Candidate set not found.')
                return (json.loads(row[0]),json.loads(row[1])) if inputs else json.loads(row[1])
            finally: cursor.close()

    def list(self, target_id=None):
        with repository_connection() as conn:
            cursor=conn.cursor()
            try:
                cursor.execute('SELECT TOP(100) CandidateSetId,TargetId,BatchId,CreatedAtUtc FROM dbo.CandidateSet'+
                    (' WHERE TargetId=?' if target_id else '')+' ORDER BY CreatedAtUtc DESC,CandidateSetId',*([str(target_id)] if target_id else []))
                return [dict(candidate_set_id=str(UUID(str(r[0]))),target_id=str(UUID(str(r[1]))),batch_id=str(UUID(str(r[2]))),created_at_utc=r[3].isoformat()+'Z') for r in cursor.fetchall()]
            finally: cursor.close()


class CandidateService:
    def __init__(self, candidates=None, analyses=None):
        self.candidates=candidates or CandidateRepository()
        self.analyses=analyses or RecommendationRepository()

    def generate(self, batch_id):
        batch=SqlCollectionBatchRepository().get(batch_id)
        if not batch: raise KeyError('Collection not found.')
        with target_collection_lock(batch.target_id):
            bundle=self.analyses.load(batch_id)
            return self.candidates.save(bundle,generate_candidates(bundle))

    def from_analysis(self,analysis_id):
        bundle=self.analyses.get_input(analysis_id)
        with target_collection_lock(bundle['batch']['target_id']):
            bundle=self.analyses.get_input(analysis_id)
            return self.candidates.save(bundle,generate_candidates(bundle))

    def score(self, candidate_set_id, candidate_ids, weights):
        bundle, candidates=self.candidates.get(candidate_set_id,inputs=True)
        with target_collection_lock(bundle['batch']['target_id']):
            # Recheck existence under the cleanup lock. Never load fresh target evidence.
            self.candidates.get(candidate_set_id)
            if candidates['engine_version'] != VERSION:
                raise ValueError('Regenerate candidates with the current engine version.')
            known={r['recommendation_id'] for r in candidates['recommendations']}
            selected=set(candidate_ids) if candidate_ids is not None else known
            if not selected or not selected<=known:
                raise ValueError('Select at least one candidate from this saved set.')
            result=analyze(bundle,Policy(**weights))
            result['recommendations']=[r for r in result['recommendations'] if r['recommendation_id'] in selected]
            for rank,row in enumerate(result['recommendations'],1): row['rank']=rank
            result['candidate_set_id']=str(candidate_set_id)
            result['selected_candidate_ids']=sorted(selected)
            return self.analyses.save(bundle,result)
