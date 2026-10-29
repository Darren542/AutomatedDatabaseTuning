"""SQL-backed checks, restricted to disposable workflow acceptance databases.

Create the repository first with sprint2_demo.py --seed. This creates/reuses a
separate sandbox database, generates bounded traffic/writes, and deletes only
records this check creates. Never accepts a normal project database name.
"""
import argparse
from dataclasses import replace
from pathlib import Path
import json,os,re,time
from uuid import UUID
import pyodbc
from fastapi.testclient import TestClient

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',required=True)
    parser.add_argument('--target',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'AutoTuner_Sprint2_Demo_Flow_[A-Za-z0-9_]+',args.repository):parser.error('Use an isolated workflow repository name.')
    if not re.fullmatch(r'AutoTuner_Workload_Flow_[A-Za-z0-9_]+',args.target):parser.error('Use an isolated workflow target name.')
    os.environ['AUTOTUNER_REPO_SQL_DATABASE']=args.repository
    from collector.repository.connection import RepositorySettings,repository_connection
    from collector.repository.targets import SqlTargetRepository
    from collector.repository.collection_batches import SqlCollectionBatchRepository
    from collector.repository.models import CollectionBatchStatus as Status
    from collector.targets import TargetConfiguration,AuthenticationMode
    from collector.repository.cleanup import EVIDENCE_TABLES
    from autotuner_api.app import create_app
    root=Path(__file__).resolve().parents[1];settings=RepositorySettings.load()
    with pyodbc.connect(replace(settings,database='master').to_connection_string(),autocommit=True) as master:
        if master.execute('SELECT DB_ID(?)',args.target).fetchone()[0] is None:
            master.execute(f'CREATE DATABASE [{args.target}]')
    with pyodbc.connect(replace(settings,database=args.target).to_connection_string(),autocommit=True) as target:
        for batch in re.split(r'^\s*GO\s*$',(root/'sql/simulator/001_simulator_sandbox.sql').read_text(encoding='utf-8'),flags=re.M|re.I):
            if batch.strip():
                cursor=target.cursor();cursor.execute(batch)
                while cursor.nextset():pass
                cursor.close()
        target.execute('ALTER DATABASE CURRENT SET QUERY_STORE = ON;')
        target.execute('ALTER DATABASE CURRENT SET QUERY_STORE (OPERATION_MODE=READ_WRITE,QUERY_CAPTURE_MODE=ALL,INTERVAL_LENGTH_MINUTES=1);')
    # Migration rerun is verified only in this isolated repository.
    with pyodbc.connect(settings.to_connection_string(),autocommit=True) as conn:
        migration=(root/'sql/databases/repository/migrations/006_workflow_and_simulator.sql').read_text(encoding='utf-8').replace('AutoTunerRepository',args.repository)
        for batch in re.split(r'^\s*GO\s*$',migration,flags=re.M|re.I):
            if batch.strip():conn.execute(batch)
    targets=SqlTargetRepository();batches=SqlCollectionBatchRepository()
    name='Workflow simulator acceptance '+args.target.removeprefix('AutoTuner_Workload_Flow_')
    live=next((t for t in targets.list(500) if t.configuration.name==name),None)
    if live is None:
        live=targets.create(TargetConfiguration(name=name,server=settings.server,database=args.target,driver=settings.driver,
            authentication=AuthenticationMode.WINDOWS if settings.trusted_connection else AuthenticationMode.SQL,
            trust_server_certificate=settings.trust_server_certificate),None if settings.trusted_connection else 'AUTOTUNER_REPO')
    synthetic=next(t for t in targets.list(500) if t.configuration.name=='Sprint 2 synthetic acceptance')
    source=next(b for b in batches.list(target_id=synthetic.target_id) if b.status==Status.COMPLETED and 'read/write' in (b.label or ''))
    evidence={}
    with TestClient(create_app()) as client:
        def post(path,body=None):
            response=client.post('/api/v1'+path,json=body)
            assert response.status_code==201,response.text
            return response.json()
        candidates=post('/candidate-sets',{'batch_id':str(source.batch_id)})
        assert all('score' not in r and 'rank' not in r for r in candidates['recommendations'])
        one=post('/recommendations/score',{'candidate_set_id':candidates['candidate_set_id']})
        two=post('/recommendations/score',{'candidate_set_id':candidates['candidate_set_id'],'weights':{'write_weight':10}})
        assert one['input_hash']==two['input_hash']==candidates['input_hash']
        assert one['recommendations'][0]['score']>two['recommendations'][0]['score']
        evidence['frozen_scoring']=dict(candidate_set_id=candidates['candidate_set_id'],analysis_ids=[one['analysis_id'],two['analysis_id']],input_hash=one['input_hash'])
        # Clone only fixture batch children; share canonical Query Store evidence.
        clone=batches.create(target_id=synthetic.target_id,label='Disposable cleanup acceptance',requested_window_start_utc=None,requested_window_end_utc=None,collector_version='workflow-acceptance')
        with repository_connection() as conn:
            cursor=conn.cursor()
            for table in EVIDENCE_TABLES:
                columns=[r[0] for r in cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=? AND COLUMNPROPERTY(OBJECT_ID('dbo.'+TABLE_NAME),COLUMN_NAME,'IsIdentity')=0 ORDER BY ORDINAL_POSITION",table).fetchall()]
                other=[c for c in columns if c!='BatchId']
                quoted=','.join('['+c+']' for c in other)
                cursor.execute(f'INSERT dbo.{table}([BatchId],{quoted}) SELECT ?,{quoted} FROM dbo.{table} WHERE BatchId=?',str(clone.batch_id),str(source.batch_id))
            cursor.execute('INSERT dbo.CollectionQueryStoreEvidence(BatchId,EvidenceId) SELECT ?,EvidenceId FROM dbo.CollectionQueryStoreEvidence WHERE BatchId=?',str(clone.batch_id),str(source.batch_id));conn.commit()
        batches.transition(clone.batch_id,Status.COLLECTING);batches.transition(clone.batch_id,Status.COMPLETED)
        temporary=post('/candidate-sets',{'batch_id':str(clone.batch_id)})
        temporary_score=post('/recommendations/score',{'candidate_set_id':temporary['candidate_set_id']})
        preview=client.get(f'/api/v1/cleanup/collections/{clone.batch_id}/preview').json()
        assert preview['counts']['query_rows_to_remove']==0
        assert client.request('DELETE',f'/api/v1/cleanup/collections/{clone.batch_id}',json={}).status_code==422
        wrong=client.request('DELETE',f'/api/v1/cleanup/collections/{clone.batch_id}',json=dict(confirmation='wrong',preview_token=preview['preview_token']))
        assert wrong.status_code==409
        deleted=client.request('DELETE',f'/api/v1/cleanup/collections/{clone.batch_id}',json=dict(confirmation=preview['confirmation'],preview_token=preview['preview_token']))
        assert deleted.status_code==200,deleted.text
        assert client.get(f'/api/v1/candidate-sets/{temporary["candidate_set_id"]}').status_code==404
        assert client.get(f'/api/v1/recommendations/analyses/{temporary_score["analysis_id"]}').status_code==404
        summary=client.get(f'/api/v1/collections/{source.batch_id}/summary').json()
        assert summary['query_runtime']['execution_count']>0
        evidence['cleanup']=dict(shared_query_rows_retained=True,deleted=deleted.json())
        # Exercise purge while retaining a target, then delete the empty target.
        disposable=targets.create(TargetConfiguration(name='Disposable cleanup target',server=settings.server,database='SyntheticCleanupOnly'),None)
        batches.create(target_id=disposable.target_id,label='Cleanup batch',requested_window_start_utc=None,requested_window_end_utc=None,collector_version='acceptance')
        for remove_target in (False,True):
            preview=client.get(f'/api/v1/cleanup/targets/{disposable.target_id}/preview?delete_target={str(remove_target).lower()}').json()
            response=client.request('DELETE',f'/api/v1/cleanup/targets/{disposable.target_id}',json=dict(confirmation=preview['confirmation'],preview_token=preview['preview_token'],delete_target=remove_target))
            assert response.status_code==200,response.text
            assert bool(targets.get(disposable.target_id))!=remove_target
        config=dict(target_id=str(live.target_id),label='SQL acceptance traffic',allow_writes=True,max_writes=5,max_requests=500,auto_collect=True,auto_score=True,collect_every_seconds=30,
            phases=[dict(name='Customer reads',duration_seconds=50,requests_per_second=5,customer_read=100,product_read=0)])
        run=post('/simulator/runs',config);run_id=run['run_id']
        time.sleep(3)
        change=client.post(f'/api/v1/simulator/runs/{run_id}/phase',json=dict(name='Live write/product shift',duration_seconds=40,requests_per_second=5,customer_read=0,product_read=70,insert=15,update=15))
        assert change.status_code==200,change.text
        deadline=time.monotonic()+34
        while time.monotonic()<deadline:time.sleep(.5)
        assert client.post(f'/api/v1/simulator/runs/{run_id}/stop').status_code==200
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            state=client.get(f'/api/v1/simulator/runs/{run_id}').json()
            if state['status'] in ('Stopped','Completed','Failed'):break
            time.sleep(.5)
        assert state['status']=='Stopped',state
        assert state['stats']['failed']==0 and 0<state['stats']['rows_written']<=5
        assert state['stats']['write_attempts']<=5
        assert len(state['stats']['phase_events'])>=2 and state['controls']
        assert len(state['stats']['collections'])>=2
        latest=next(row for row in reversed(state['stats']['collections']) if row.get('candidate_set_id'))
        shapes=client.get('/api/v1/candidate-sets/'+latest['candidate_set_id']).json()
        create_keys=[row['key_columns'] for row in shapes['recommendations'] if row['action']=='CREATE']
        assert any('CustomerId' in keys for keys in create_keys) and any('ProductId' in keys for keys in create_keys),shapes
        evidence['observed_candidate_keys']=create_keys
        assert state['stats']['completed']+state['stats']['failed']==state['stats']['submitted']
        evidence['simulator']=state
    output=root/'docs/workflow-evidence';output.mkdir(exist_ok=True)
    (output/'sql-acceptance.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(dict(repository=args.repository,target=args.target,run_id=run_id,checks='Candidate discovery, frozen rescoring, shared-evidence cleanup, target purge/delete, bounded SQL reads/writes, live phase, periodic collection, stop and persisted history passed.'),indent=2))

if __name__=='__main__':main()
