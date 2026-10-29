from uuid import UUID
import pyodbc
from fastapi import APIRouter,Request,HTTPException
from autotuner_api.simulator import SimulationRequest,Phase

router=APIRouter(prefix='/simulator',tags=['workload simulator'])

def manager(request): return request.app.state.simulator
def call(operation):
    try: return operation()
    except KeyError: raise HTTPException(404,'Enabled target or simulator run not found.') from None
    except ValueError as error: raise HTTPException(409,str(error)) from None
    except pyodbc.Error: raise HTTPException(503,'Simulator database access failed. Apply repository migration 006 and sandbox setup SQL, then check target credentials and permissions.') from None

@router.post('/runs',status_code=201)
def start(body:SimulationRequest,request:Request):
    return call(lambda:dict(run_id=manager(request).start(body)))

@router.get('/runs')
def list_runs(request:Request,target_id:UUID|None=None):
    return manager(request).repo.list(target_id)

@router.get('/runs/{run_id}')
def get_run(run_id:UUID,request:Request):
    return call(lambda:manager(request).repo.get(run_id))

@router.post('/runs/{run_id}/stop')
def stop_run(run_id:UUID,request:Request):
    return call(lambda:manager(request).stop(run_id))

@router.post('/runs/{run_id}/phase')
def change_phase(run_id:UUID,body:Phase,request:Request):
    return call(lambda:manager(request).change(run_id,body))
