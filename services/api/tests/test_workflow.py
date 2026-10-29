from contextlib import nullcontext
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from autotuner_api.app import create_app
from autotuner_api.routes.candidates import get_service,get_repository
from autotuner_api.simulator import Phase,SimulationRequest,arrivals,request_parameters
from recommender.candidates import generate_candidates,CandidateService
from recommender.engine import Policy,analyze
from recommender.fixtures import acceptance_bundle
from collector.repository.cleanup import CleanupRepository

def test_discovery_has_shapes_features_and_evidence_but_no_scores_or_ranks():
    result=generate_candidates(acceptance_bundle())
    assert 'policy' not in result
    assert {r['action'] for r in result['recommendations']}=={'CREATE','RETAIN','DROP'}
    for row in result['recommendations']:
        assert not {'score','rank','score_components'} & row.keys()
        assert row['source_evidence'] and row['features']
        if row['action']=='CREATE': assert row['status']=='Unscored'

def test_weighted_scoring_reuses_frozen_inputs_and_preserves_candidate_shapes(monkeypatch):
    monkeypatch.setattr('recommender.candidates.target_collection_lock',lambda target:nullcontext())
    bundle=acceptance_bundle(); candidates=generate_candidates(bundle)
    selected=[r['recommendation_id'] for r in candidates['recommendations'] if r['action']=='CREATE']
    repository=Mock();repository.get.side_effect=lambda id,inputs=False:(bundle,candidates) if inputs else candidates
    analyses=Mock();analyses.save.side_effect=lambda bundle,result:result
    service=CandidateService(repository,analyses)
    normal=service.score('set',selected,dict(read_weight=1,write_weight=1,storage_weight=.1))
    expensive=service.score('set',selected,dict(read_weight=1,write_weight=10,storage_weight=.1))
    assert {r['recommendation_id'] for r in normal['recommendations']}==set(selected)
    assert normal['recommendations'][0]['score']>expensive['recommendations'][0]['score']
    analyses.load.assert_not_called()
    assert normal['candidate_set_id']=='set'
    with pytest.raises(ValueError):service.score('set',[],{})
    with pytest.raises(ValueError):service.score('set',['not-in-set'],{})

def test_candidate_api_has_distinct_generate_and_score_operations():
    app=create_app();service=Mock();service.generate.return_value={'candidate_set_id':'saved'};service.score.return_value={'analysis_id':'scored'}
    app.dependency_overrides[get_service]=lambda:service
    with TestClient(app) as client:
        assert client.post('/api/v1/candidate-sets',json={'batch_id':str(uuid4())}).status_code==201
        assert client.post('/api/v1/recommendations/score',json={'candidate_set_id':str(uuid4()),'weights':{'write_weight':5}}).status_code==201
        assert client.post('/api/v1/candidate-sets',json={'batch_id':str(uuid4()),'weights':{'read_weight':5}}).status_code==422
        assert client.post('/api/v1/recommendations/score',json={'candidate_set_id':str(uuid4()),'weights':{'read_weight':'NaN'}}).status_code==422
        assert client.post('/api/v1/recommendations/score',json={'candidate_set_id':str(uuid4()),'weights':{'read_weight':101}}).status_code==422

def test_poisson_arrival_schedule_is_seeded_and_has_expected_rate():
    first=list(arrivals(100,200,42))
    assert first==list(arrivals(100,200,42))
    assert first!=list(arrivals(100,200,43))
    assert 19000<len(first)<21000
    assert all(a<b for a,b in zip(first,first[1:]))
    assert list(arrivals(0,20,42))==[]

@pytest.mark.parametrize('bad',[
    {'phases':[{'requests_per_second':101}]},
    {'phases':[{'duration_seconds':3601}]},
    {'phases':[{'insert':1}]},
    {'phases':[{'customer_read':0,'product_read':0}]},
    {'phases':[{},{}],'auto_collect':False,'auto_score':True},
    {'phases':[{}],'sql':'DROP TABLE dbo.Users'},
    {'phases':[{}],'concurrency':9},
    {'phases':[{}],'max_writes':10001},
])
def test_simulator_rejects_unsafe_or_invalid_plans(bad):
    with pytest.raises(ValueError):SimulationRequest(target_id=uuid4(),**bad)

def test_controlled_write_weights_require_explicit_opt_in_and_parameters_stay_bounded():
    import random
    config=SimulationRequest(target_id=uuid4(),allow_writes=True,phases=[{'customer_read':0,'product_read':0,'insert':100}])
    for _ in range(20):
        kind,params=request_parameters(config.phases[0],random.Random(_))
        assert kind=='insert' and 1<=params[0]<=1000 and 1<=params[1]<=500
        assert len(params[-1])<=800

@pytest.mark.parametrize('blocked,confirmation,token',[(True,'target','a'*64),(False,'wrong','a'*64),(False,'target','b'*64)])
def test_cleanup_never_deletes_on_busy_target_wrong_confirmation_or_changed_preview(monkeypatch,blocked,confirmation,token):
    monkeypatch.setattr('collector.repository.cleanup.target_collection_lock',lambda target:nullcontext())
    monkeypatch.setattr('collector.repository.cleanup.simulation_lock',lambda target:nullcontext())
    connection=Mock();monkeypatch.setattr('collector.repository.cleanup.repository_connection',lambda:nullcontext(connection))
    repo=CleanupRepository();repo._plan=Mock(return_value=dict(blocked=blocked,note='busy',confirmation='target',preview_token='a'*64))
    with pytest.raises(ValueError):repo.delete(uuid4(),None,True,confirmation,token)
    assert not any('DELETE' in str(call) for call in connection.cursor.return_value.execute.call_args_list)
    connection.rollback.assert_called_once();connection.commit.assert_not_called()


def test_worker_obeys_write_and_request_budgets_without_unbounded_queue(monkeypatch):
    import threading,time
    from autotuner_api.simulator import SimulationManager
    monkeypatch.setattr('autotuner_api.simulator.simulation_lock',lambda target:nullcontext())
    def execute(target,kind,parameters):
        time.sleep(.01)
        return 10,1
    monkeypatch.setattr('autotuner_api.simulator.execute_request',execute)
    repository=Mock();manager=SimulationManager(repository)
    config=SimulationRequest(target_id=uuid4(),allow_writes=True,max_writes=3,max_requests=20,
        auto_collect=False,phases=[dict(duration_seconds=1,requests_per_second=100,customer_read=0,product_read=0,insert=100)])
    record=dict(stop=threading.Event(),override=None)
    manager._run('test',config,None,record)
    _,status,stats=repository.update.call_args.args
    assert status=='Completed'
    assert stats['scheduled']==20 and stats['write_attempts']<=3 and stats['rows_written']<=3
    assert stats['completed']+stats['failed']==stats['submitted']
    assert stats['scheduled']==stats['submitted']+stats['dropped']


def test_worker_stop_prevents_new_requests_and_live_writes_cannot_bypass_opt_in(monkeypatch):
    import threading
    from autotuner_api.simulator import SimulationManager
    monkeypatch.setattr('autotuner_api.simulator.simulation_lock',lambda target:nullcontext())
    execute=Mock();monkeypatch.setattr('autotuner_api.simulator.execute_request',execute)
    repository=Mock();manager=SimulationManager(repository)
    config=SimulationRequest(target_id=uuid4(),auto_collect=False,phases=[{}])
    stop=threading.Event();stop.set()
    manager._run('test',config,None,dict(stop=stop,override=None))
    assert repository.update.call_args.args[1]=='Stopped';execute.assert_not_called()
    manager.active['live']=dict(stop=threading.Event(),config=config,controls=0,override=None)
    with pytest.raises(ValueError):manager.change('live',Phase(insert=10))
    repository.control.assert_not_called()


def test_a_recovered_pending_run_cannot_restart_work_later(monkeypatch):
    import threading
    from autotuner_api.simulator import SimulationManager
    monkeypatch.setattr('autotuner_api.simulator.simulation_lock',lambda target:nullcontext())
    execute=Mock();monkeypatch.setattr('autotuner_api.simulator.execute_request',execute)
    repository=Mock();repository.begin.return_value=False
    manager=SimulationManager(repository)
    config=SimulationRequest(target_id=uuid4(),auto_collect=False,phases=[{}])
    manager._run('test',config,None,dict(stop=threading.Event(),override=None))
    execute.assert_not_called();repository.update.assert_not_called()


def test_earlier_analysis_can_be_reused_without_rescanning_the_target(monkeypatch):
    monkeypatch.setattr('recommender.candidates.target_collection_lock',lambda target:nullcontext())
    analyses=Mock();analyses.get_input.return_value=acceptance_bundle()
    candidates=Mock();candidates.save.side_effect=lambda bundle,result:result
    result=CandidateService(candidates,analyses).from_analysis('saved')
    assert result['recommendations'] and all('score' not in r for r in result['recommendations'])
    analyses.load.assert_not_called();candidates.save.assert_called_once()
