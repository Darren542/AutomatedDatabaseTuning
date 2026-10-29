"""Explicit, previewed repository cleanup. Never opens a target connection."""
from hashlib import sha256
import json
from collector.repository.connection import repository_connection
from collector.repository.collection_lock import target_collection_lock
from collector.repository.activity_lock import simulation_lock

EVIDENCE_TABLES=('CollectionSourceState','CollectionComponentResult','IndexUsageObservation',
    'IndexOperationalObservation','MissingIndexObservation','TableMetadataSnapshot',
    'ColumnMetadataSnapshot','IndexMetadataSnapshot','IndexColumnMetadataSnapshot','ConstraintMetadataSnapshot')

class CleanupRepository:
    def _plan(self,cursor,target_id,batch_id,delete_target):
        target=cursor.execute('SELECT Name FROM dbo.TargetDatabase WITH(UPDLOCK,HOLDLOCK) WHERE TargetId=?',str(target_id)).fetchone()
        if not target: raise KeyError('Target not found.')
        cursor.execute('CREATE TABLE #Batches(BatchId uniqueidentifier PRIMARY KEY);')
        cursor.execute('INSERT #Batches SELECT BatchId FROM dbo.CollectionBatch WITH(UPDLOCK,HOLDLOCK) WHERE TargetId=?'+(' AND BatchId=?' if batch_id else ''),str(target_id),*([str(batch_id)] if batch_id else []))
        batch_ids=[str(r[0]) for r in cursor.execute('SELECT BatchId FROM #Batches ORDER BY BatchId').fetchall()]
        if batch_id and not batch_ids: raise KeyError('Collection not found.')
        cursor.execute('CREATE TABLE #Sets(CandidateSetId uniqueidentifier PRIMARY KEY); INSERT #Sets SELECT CandidateSetId FROM dbo.CandidateSet WITH(UPDLOCK,HOLDLOCK) WHERE BatchId IN(SELECT BatchId FROM #Batches) OR MetadataBatchId IN(SELECT BatchId FROM #Batches);')
        sets=[str(r[0]) for r in cursor.execute('SELECT CandidateSetId FROM #Sets ORDER BY CandidateSetId').fetchall()]
        analyses=[str(r[0]) for r in cursor.execute('''SELECT AnalysisId FROM dbo.RecommendationAnalysis WITH(UPDLOCK,HOLDLOCK) WHERE BatchId IN(SELECT BatchId FROM #Batches)
            OR MetadataBatchId IN(SELECT BatchId FROM #Batches) OR CandidateSetId IN(SELECT CandidateSetId FROM #Sets) ORDER BY AnalysisId''').fetchall()]
        cursor.execute('CREATE TABLE #Evidence(EvidenceId bigint PRIMARY KEY); INSERT #Evidence SELECT DISTINCT EvidenceId FROM dbo.CollectionQueryStoreEvidence WHERE BatchId IN(SELECT BatchId FROM #Batches);')
        counts={table:cursor.execute(f'SELECT COUNT_BIG(*) FROM dbo.{table} WHERE BatchId IN(SELECT BatchId FROM #Batches)').fetchone()[0] for table in EVIDENCE_TABLES}
        counts['query_memberships']=cursor.execute('SELECT COUNT_BIG(*) FROM dbo.CollectionQueryStoreEvidence WHERE BatchId IN(SELECT BatchId FROM #Batches)').fetchone()[0]
        counts['query_rows_to_remove']=cursor.execute('''SELECT COUNT_BIG(*) FROM dbo.QueryStoreRuntimeEvidence e WHERE
            (e.EvidenceId IN(SELECT EvidenceId FROM #Evidence) OR (?=1 AND e.TargetId=?))
            AND NOT EXISTS(SELECT 1 FROM dbo.CollectionQueryStoreEvidence l WHERE l.EvidenceId=e.EvidenceId AND l.BatchId NOT IN(SELECT BatchId FROM #Batches))''',not bool(batch_id),str(target_id)).fetchone()[0]
        runs=[] if batch_id else [str(r[0]) for r in cursor.execute('SELECT RunId FROM dbo.WorkloadSimulation WHERE TargetId=? ORDER BY RunId',str(target_id)).fetchall()]
        blocked=cursor.execute("SELECT COUNT(*) FROM dbo.CollectionBatch WITH(UPDLOCK,HOLDLOCK) WHERE TargetId=? AND Status='Collecting'",str(target_id)).fetchone()[0]>0
        blocked=blocked or cursor.execute("SELECT COUNT(*) FROM dbo.WorkloadSimulation WHERE TargetId=? AND Status IN('Pending','Running','Stopping')",str(target_id)).fetchone()[0]>0
        counts.update(collections=len(batch_ids),candidate_sets=len(sets),analyses=len(analyses),simulation_runs=len(runs),targets=int(delete_target))
        confirmation=str(batch_id) if batch_id else target[0]
        token=sha256(json.dumps([batch_ids,sets,analyses,runs,counts,bool(delete_target)],sort_keys=True).encode()).hexdigest()
        return dict(target_id=str(target_id),batch_id=str(batch_id) if batch_id else None,delete_target=delete_target,
            name=target[0],counts=counts,confirmation=confirmation,preview_token=token,blocked=blocked,
            note='Active collections/simulators must be stopped or recovered first.' if blocked else
            'Dependent candidate sets and scores will be removed. Shared query evidence is retained. Deleted metadata may require a fresh metadata collection. Only repository data is removed.')

    def preview(self,target_id,batch_id=None,delete_target=False):
        with repository_connection() as conn:
            cursor=conn.cursor()
            try: return self._plan(cursor,target_id,batch_id,delete_target)
            finally: conn.rollback(); cursor.close()

    def delete(self,target_id,batch_id,delete_target,confirmation,preview_token):
        with target_collection_lock(target_id),simulation_lock(target_id),repository_connection() as conn:
            cursor=conn.cursor()
            try:
                cursor.execute('SET XACT_ABORT ON;')
                plan=self._plan(cursor,target_id,batch_id,delete_target)
                if plan['blocked']: raise ValueError(plan['note'])
                if confirmation!=plan['confirmation'] or preview_token!=plan['preview_token']:
                    raise ValueError('Confirmation or data changed. Refresh the cleanup preview.')
                cursor.execute('''DELETE dbo.RecommendationAnalysis WHERE BatchId IN(SELECT BatchId FROM #Batches)
                    OR MetadataBatchId IN(SELECT BatchId FROM #Batches) OR CandidateSetId IN(SELECT CandidateSetId FROM #Sets);
                    DELETE dbo.CandidateSet WHERE CandidateSetId IN(SELECT CandidateSetId FROM #Sets);''')
                # Collection children cascade; shared canonical Query Store rows do not.
                cursor.execute('DELETE dbo.CollectionBatch WHERE BatchId IN(SELECT BatchId FROM #Batches);')
                cursor.execute('''DELETE e FROM dbo.QueryStoreRuntimeEvidence e WHERE
                    (e.EvidenceId IN(SELECT EvidenceId FROM #Evidence) OR (?=1 AND e.TargetId=?))
                    AND NOT EXISTS(SELECT 1 FROM dbo.CollectionQueryStoreEvidence l WHERE l.EvidenceId=e.EvidenceId)''',not bool(batch_id),str(target_id))
                if batch_id:
                    cursor.execute('''UPDATE dbo.TargetCollectionState SET LastMetadataBatchId=NULL,LastMetadataCollectedAtUtc=NULL
                        WHERE TargetId=? AND LastMetadataBatchId IN(SELECT BatchId FROM #Batches);
                        UPDATE dbo.TargetCollectionState SET LastSuccessfulQueryBatchId=NULL,LastQueryRuntimeWatermarkUtc=NULL
                        WHERE TargetId=? AND LastSuccessfulQueryBatchId IN(SELECT BatchId FROM #Batches);''',str(target_id),str(target_id))
                else:
                    cursor.execute('DELETE dbo.TargetCollectionState WHERE TargetId=?; DELETE dbo.WorkloadSimulation WHERE TargetId=?;',str(target_id),str(target_id))
                if delete_target: cursor.execute('DELETE dbo.TargetDatabase WHERE TargetId=?',str(target_id))
                conn.commit()
                return dict(deleted=True,counts=plan['counts'])
            except Exception: conn.rollback(); raise
            finally: cursor.close()
