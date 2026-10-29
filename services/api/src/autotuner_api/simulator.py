"""Bounded Poisson traffic, fixed sandbox SQL, persisted runs and live controls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timezone
import json
import math
import random
import threading
import time
from uuid import UUID,uuid4

from pydantic import BaseModel,ConfigDict,Field,model_validator
from collector.repository.connection import repository_connection
from collector.repository.targets import SqlTargetRepository
from collector.repository.collection_lock import target_collection_lock
from collector.repository.activity_lock import simulation_lock
from collector.target_connection import open_target_connection

TEMPLATES={
    'customer_read':'SELECT TOP(200) OrderId,Amount,Payload FROM TunerSim.Orders WHERE CustomerId=? AND Status=? ORDER BY CreatedAt DESC,OrderId DESC;',
    'product_read':'SELECT TOP(200) OrderId,Amount,Payload FROM TunerSim.Orders WHERE ProductId=? AND Status=? ORDER BY CreatedAt DESC,OrderId DESC;',
    'insert':'INSERT TunerSim.Orders(CustomerId,ProductId,Status,Amount,Payload) VALUES(?,?,?,?,?);',
    'update':'UPDATE TunerSim.Orders SET Status=?,Amount=Amount+? WHERE OrderId=?;',
}
WRITES={'insert','update'}
TERMINAL={'Completed','Stopped','Failed','Interrupted'}

class Phase(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    name:str=Field(default='Read-heavy',min_length=1,max_length=80)
    duration_seconds:int=Field(default=120,ge=1,le=3600)
    requests_per_second:float=Field(default=5,ge=0,le=100)
    customer_read:float=Field(default=80,ge=0,le=100)
    product_read:float=Field(default=20,ge=0,le=100)
    insert:float=Field(default=0,ge=0,le=100)
    update:float=Field(default=0,ge=0,le=100)
    hot_key_percent:float=Field(default=80,ge=0,le=100)
    hot_customer_id:int=Field(default=1,ge=1,le=1000)
    hot_product_id:int=Field(default=1,ge=1,le=500)

    @model_validator(mode='after')
    def validate_mix(self):
        if sum(getattr(self,k) for k in TEMPLATES)<=0: raise ValueError('At least one query weight must be positive.')
        return self

class SimulationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target_id:UUID
    label:str=Field(default='Pattern experiment',min_length=1,max_length=100)
    seed:int=Field(default=42,ge=0,le=2147483647)
    concurrency:int=Field(default=2,ge=1,le=8)
    max_requests:int=Field(default=20000,ge=1,le=100000)
    max_writes:int=Field(default=2000,ge=0,le=10000)
    allow_writes:bool=False
    collect_every_seconds:int=Field(default=60,ge=30,le=3600)
    auto_collect:bool=True
    auto_score:bool=False
    phases:list[Phase]=Field(min_length=1,max_length=20)

    @model_validator(mode='after')
    def validate_plan(self):
        if sum(p.duration_seconds for p in self.phases)>3600: raise ValueError('A run is limited to one hour.')
        if not self.allow_writes and any(p.insert+p.update>0 for p in self.phases): raise ValueError('Enable controlled writes for write-weighted phases.')
        if self.auto_score and not self.auto_collect: raise ValueError('Automatic scoring requires automatic collections.')
        return self

def arrival_delay(rate,rng):
    return rng.expovariate(rate) if rate>0 else math.inf

def arrivals(rate,duration,seed):
    """Independent exponential inter-arrivals; no interval jitter approximations."""
    if rate<=0: return
    rng=random.Random(seed); elapsed=0.0
    while True:
        elapsed+=arrival_delay(rate,rng)
        if elapsed>=duration: return
        yield elapsed

def request_parameters(phase,rng):
    kind=rng.choices(list(TEMPLATES),weights=[getattr(phase,k) for k in TEMPLATES])[0]
    hot=rng.random()<phase.hot_key_percent/100
    customer=phase.hot_customer_id if hot else rng.randint(1,1000)
    product=phase.hot_product_id if hot else rng.randint(1,500)
    status=rng.randrange(4)
    params={'customer_read':(customer,status),'product_read':(product,status),
        'insert':(customer,product,status,rng.randint(10,1000),'simulated '+'x'*790),
        'update':(status,rng.randint(0,5),rng.randint(1,20000))}
    return kind,params[kind]

class RunRepository:
    def create(self,config):
        run_id=str(uuid4())
        self._execute('INSERT dbo.WorkloadSimulation(RunId,TargetId,Status,ConfigJson,StatsJson) VALUES(?,?,\'Pending\',?,\'{}\')',run_id,str(config.target_id),config.model_dump_json())
        return run_id

    def _execute(self,sql,*params):
        with repository_connection() as conn:
            cursor=conn.cursor()
            try: cursor.execute(sql,*params); conn.commit()
            except Exception: conn.rollback(); raise
            finally: cursor.close()

    def update(self,run_id,status,stats):
        self._execute('UPDATE dbo.WorkloadSimulation SET Status=?,StatsJson=?,UpdatedAtUtc=SYSUTCDATETIME() WHERE RunId=?',status,json.dumps(stats),str(run_id))

    def begin(self,run_id,stats):
        with repository_connection() as conn:
            cursor=conn.cursor()
            try:
                row=cursor.execute("UPDATE dbo.WorkloadSimulation SET Status='Running',StatsJson=?,UpdatedAtUtc=SYSUTCDATETIME() OUTPUT inserted.RunId WHERE RunId=? AND Status='Pending'",json.dumps(stats),str(run_id)).fetchone()
                started=row is not None
                conn.commit()
                return started
            except Exception: conn.rollback(); raise
            finally: cursor.close()

    def control(self,run_id,phase):
        self._execute('INSERT dbo.WorkloadSimulationControl(RunId,PhaseJson) VALUES(?,?)',str(run_id),phase.model_dump_json())

    def list(self,target_id=None):
        with repository_connection() as conn:
            cursor=conn.cursor()
            try:
                rows=cursor.execute('SELECT TOP(100) RunId,TargetId,Status,ConfigJson,StatsJson,CreatedAtUtc,UpdatedAtUtc FROM dbo.WorkloadSimulation'+
                    (' WHERE TargetId=?' if target_id else '')+' ORDER BY CreatedAtUtc DESC',*([str(target_id)] if target_id else [])).fetchall()
                return [dict(run_id=str(UUID(str(r[0]))),target_id=str(UUID(str(r[1]))),status=r[2],config=json.loads(r[3]),stats=json.loads(r[4]),created_at_utc=r[5].isoformat()+'Z',updated_at_utc=r[6].isoformat()+'Z') for r in rows]
            finally: cursor.close()

    def get(self,run_id):
        # Direct lookup must still work after more than 100 newer runs.
        with repository_connection() as conn:
            cursor=conn.cursor()
            try:
                row=cursor.execute('SELECT TargetId,Status,ConfigJson,StatsJson,CreatedAtUtc,UpdatedAtUtc FROM dbo.WorkloadSimulation WHERE RunId=?',str(run_id)).fetchone()
                if not row: raise KeyError('Simulation not found.')
                controls=[dict(phase=json.loads(r[0]),created_at_utc=r[1].isoformat()+'Z') for r in cursor.execute('SELECT PhaseJson,CreatedAtUtc FROM dbo.WorkloadSimulationControl WHERE RunId=? ORDER BY ControlId',str(run_id)).fetchall()]
                return dict(run_id=str(run_id),target_id=str(UUID(str(row[0]))),status=row[1],config=json.loads(row[2]),stats=json.loads(row[3]),created_at_utc=row[4].isoformat()+'Z',updated_at_utc=row[5].isoformat()+'Z',controls=controls)
            finally: cursor.close()

def check_sandbox(target):
    with open_target_connection(target) as conn:
        cursor=conn.cursor()
        try:
            row=cursor.execute('SELECT SchemaVersion,Enabled FROM TunerSim.Configuration WHERE Id=1').fetchone()
            if not row or row[0]!=1 or not row[1]: raise ValueError('The simulator sandbox is not enabled. Apply its setup SQL to this test database.')
            cursor.execute('SELECT TOP(0) OrderId,CustomerId,ProductId,Status,Amount,Payload FROM TunerSim.Orders')
        finally: cursor.close()

def execute_request(target,kind,parameters):
    start=time.monotonic()
    with open_target_connection(target) as conn:
        cursor=conn.cursor()
        try:
            cursor.execute(TEMPLATES[kind],*parameters)
            if kind not in WRITES: cursor.fetchall()
            return (time.monotonic()-start)*1000,max(0,cursor.rowcount) if kind in WRITES else 0
        finally: cursor.close()

def collect_snapshot(target_id,run_id,auto_score):
    from collector.collection.coordinator import CollectionCoordinator
    from collector.collection.runner import CollectionRunner
    from recommender.candidates import CandidateService
    batch=CollectionCoordinator().create_batch(target_id=UUID(str(target_id)),label=f'Simulator {run_id[:8]}',force_metadata=True)
    result=CollectionRunner().collect(batch.batch_id)
    row=dict(batch_id=str(batch.batch_id),status=result.final_status.value)
    if auto_score and result.final_status.value in ('Completed','Partial'):
        try:
            service=CandidateService(); candidates=service.generate(batch.batch_id)
            row['candidate_set_id']=candidates['candidate_set_id']
            if candidates['recommendations']:
                scored=service.score(candidates['candidate_set_id'],None,dict(read_weight=1,write_weight=1,storage_weight=.1))
                row['analysis_id']=scored['analysis_id']
        except (ValueError,KeyError): row['analysis_note']='Evidence is not ready for analysis; wait for closed Query Store intervals and complete source components.'
    return row

class SimulationManager:
    def __init__(self,repository=None):
        self.repo=repository or RunRepository(); self.guard=threading.RLock(); self.active={}; self.closed=False

    def start(self,config):
        with self.guard:
            if self.closed or len(self.active)>=4: raise ValueError('At most four runs can be active in this API process.')
            with target_collection_lock(config.target_id):
                if any(str(r['config'].target_id)==str(config.target_id) for r in self.active.values()): raise ValueError('This target already has an active run.')
                with simulation_lock(config.target_id):
                    if any(r['status'] not in TERMINAL for r in self.repo.list(config.target_id)): raise ValueError('Stop or recover the previous run for this target first.')
                    target=SqlTargetRepository().get(config.target_id)
                    if not target or not target.is_enabled: raise KeyError('Enabled target not found.')
                    # Keep worker SQL bounded even if the collector has a larger timeout.
                    target=replace(target,configuration=replace(target.configuration,query_timeout_seconds=min(5,target.configuration.query_timeout_seconds),connection_timeout_seconds=min(5,target.configuration.connection_timeout_seconds)))
                    check_sandbox(target)
                    run_id=self.repo.create(config)
                record=dict(config=config,stop=threading.Event(),override=None,controls=0)
                worker=threading.Thread(target=self._run,args=(run_id,config,target,record),daemon=True,name=f'simulator-{run_id[:8]}')
                record['thread']=worker; self.active[run_id]=record; worker.start()
                return run_id

    def stop(self,run_id):
        with self.guard:
            record=self.active.get(str(run_id))
            if record:
                record['stop'].set(); return self.repo.get(run_id)
            current=self.repo.get(run_id)
            if current['status'] not in TERMINAL:
                with target_collection_lock(current['target_id']),simulation_lock(current['target_id']):
                    current=self.repo.get(run_id)
                    if current['status'] not in TERMINAL:
                        self.repo.update(run_id,'Interrupted',dict(current['stats'],note='No worker owns this run; recovered by operator.'))
            return self.repo.get(run_id)

    def change(self,run_id,phase):
        with self.guard:
            record=self.active.get(str(run_id))
            if not record or record['stop'].is_set(): raise ValueError('Live controls require a running job in this API process.')
            if phase.insert+phase.update>0 and not record['config'].allow_writes: raise ValueError('This run did not enable controlled writes.')
            if record['controls']>=100: raise ValueError('Live controls are limited to 100 changes per run.')
            self.repo.control(run_id,phase)
            record['override']=phase; record['controls']+=1
        return dict(accepted=True)

    def shutdown(self):
        with self.guard:
            self.closed=True
            workers=list(self.active.values())
            for record in workers: record['stop'].set()
        for record in workers: record['thread'].join(timeout=10)

    def _run(self,run_id,config,target,record):
        stats=dict(scheduled=0,submitted=0,completed=0,failed=0,dropped=0,write_attempts=0,rows_written=0,
            latency_total_ms=0,elapsed_seconds=0,phase='',by_template={},collections=[],samples=[],phase_events=[])
        start=time.monotonic(); stop=record['stop']; futures={}; collection_future=None; terminal='Completed'
        rng=random.Random(config.seed); timing=random.Random(config.seed+1)
        try:
            with simulation_lock(config.target_id),ThreadPoolExecutor(max_workers=config.concurrency) as pool,ThreadPoolExecutor(max_workers=1) as collector:
                if not self.repo.begin(run_id,stats): return
                index=0; phase=config.phases[0]; phase_start=start; phase_end=start+phase.duration_seconds
                next_arrival=start+arrival_delay(phase.requests_per_second,timing)
                next_collection=start if config.auto_collect else math.inf
                next_save=start; last_completed=0; last_sample=start
                stats['phase_events'].append(dict(name=phase.name,elapsed_seconds=0,source='plan'))
                while True:
                    now=time.monotonic(); elapsed=now-start
                    with self.guard:
                        override=record['override']; record['override']=None
                    if override:
                        phase=override; index=len(config.phases); phase_start=now; phase_end=min(start+3600,now+phase.duration_seconds)
                        next_arrival=now+arrival_delay(phase.requests_per_second,timing)
                        stats['phase_events'].append(dict(name=phase.name,elapsed_seconds=round(elapsed,3),source='live'))
                    if now>=phase_end and not stop.is_set():
                        index+=1
                        if index>=len(config.phases): break
                        phase=config.phases[index]; phase_start=phase_end; phase_end+=phase.duration_seconds
                        next_arrival=phase_start+arrival_delay(phase.requests_per_second,timing)
                        stats['phase_events'].append(dict(name=phase.name,elapsed_seconds=round(phase_start-start,3),source='plan'))
                        continue
                    for future in list(futures):
                        if future.done():
                            kind=futures.pop(future)
                            try:
                                ms,rows=future.result(); stats['completed']+=1; stats['latency_total_ms']+=ms; stats['rows_written']+=rows
                                stats['by_template'][kind]=stats['by_template'].get(kind,0)+1
                            except Exception:
                                stats['failed']+=1; stats['last_error']='A sandbox request failed. Check sandbox permissions, connectivity and SQL timeout.'
                    if collection_future and collection_future.done():
                        try: stats['collections'].append(collection_future.result())
                        except Exception: stats['collections'].append(dict(status='Failed',note='Collection could not finish. Inspect workload history and collector access.'))
                        collection_future=None
                    stats.update(elapsed_seconds=round(elapsed,2),phase=phase.name,
                        average_latency_ms=round(stats['latency_total_ms']/stats['completed'],2) if stats['completed'] else None)
                    if stop.is_set(): terminal='Stopped'; break
                    if stats['scheduled']>=config.max_requests: stats['limit_reason']='Request budget reached.'; break
                    if stats['failed']>=20: terminal='Failed'; stats['limit_reason']='Stopped after 20 failed requests.'; break
                    if now>=next_collection:
                        if not collection_future: collection_future=collector.submit(collect_snapshot,config.target_id,run_id,config.auto_score)
                        next_collection=now+config.collect_every_seconds
                    if now>=next_arrival:
                        kind,parameters=request_parameters(phase,rng); stats['scheduled']+=1
                        if len(futures)>=config.concurrency or now-next_arrival>1:
                            stats['dropped']+=1
                        elif kind in WRITES and stats['write_attempts']>=config.max_writes:
                            stats['dropped']+=1; stats['write_budget_reached']=True
                        else:
                            if kind in WRITES: stats['write_attempts']+=1
                            futures[pool.submit(execute_request,target,kind,parameters)]=kind; stats['submitted']+=1
                        next_arrival+=arrival_delay(phase.requests_per_second,timing)
                    if now>=next_save:
                        stats['samples'].append(dict(elapsed_seconds=round(elapsed,2),phase=phase.name,completed=stats['completed'],
                            achieved_rps=round((stats['completed']-last_completed)/max(now-last_sample,.001),2),configured_rps=phase.requests_per_second,dropped=stats['dropped']))
                        stats['samples']=stats['samples'][-3600:]; last_completed=stats['completed']; last_sample=now
                        self.repo.update(run_id,'Running',stats); next_save=now+1
                    stop.wait(max(0,min(.1,next_arrival-time.monotonic(),phase_end-time.monotonic())))
                self.repo.update(run_id,'Stopping',stats)
                for future,kind in futures.items():
                    try:
                        ms,rows=future.result(); stats['completed']+=1; stats['latency_total_ms']+=ms; stats['rows_written']+=rows
                        stats['by_template'][kind]=stats['by_template'].get(kind,0)+1
                    except Exception: stats['failed']+=1
                if collection_future:
                    try: stats['collections'].append(collection_future.result())
                    except Exception: stats['collections'].append(dict(status='Failed'))
                stats['elapsed_seconds']=round(time.monotonic()-start,2)
                stats['average_latency_ms']=round(stats['latency_total_ms']/stats['completed'],2) if stats['completed'] else None
                self.repo.update(run_id,terminal,stats)
        except Exception:
            try: self.repo.update(run_id,'Failed',dict(stats,last_error='Simulation stopped after a worker/repository failure. Check repository migrations and sandbox access.'))
            except Exception: pass  # Persistent nonterminal rows can be explicitly recovered under the simulation lock.
        finally:
            with self.guard: self.active.pop(run_id,None)
