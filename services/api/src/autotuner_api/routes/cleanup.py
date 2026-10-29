from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from collector.repository.cleanup import CleanupRepository
from collector.repository.collection_batches import SqlCollectionBatchRepository

router=APIRouter(prefix='/cleanup',tags=['repository cleanup'])

class DeleteRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation:str=Field(min_length=1,max_length=200)
    preview_token:str=Field(pattern=r'^[0-9a-f]{64}$')
    delete_target:bool=False

def get_repository(): return CleanupRepository()
def batches(): return SqlCollectionBatchRepository()
def run(operation):
    try: return operation()
    except KeyError: raise HTTPException(404,'Target or collection not found.') from None
    except ValueError as error: raise HTTPException(409,str(error)) from None

@router.get('/targets/{target_id}/preview')
def preview_target(target_id:UUID,delete_target:bool=False,repo=Depends(get_repository)):
    return run(lambda:repo.preview(target_id,delete_target=delete_target))

@router.delete('/targets/{target_id}')
def delete_target(target_id:UUID,request:DeleteRequest,repo=Depends(get_repository)):
    return run(lambda:repo.delete(target_id,None,request.delete_target,request.confirmation,request.preview_token))

def target_for_batch(batch_id,repository):
    batch=repository.get(batch_id)
    if not batch: raise KeyError('Collection not found.')
    return batch.target_id

@router.get('/collections/{batch_id}/preview')
def preview_batch(batch_id:UUID,repo=Depends(get_repository),repository=Depends(batches)):
    return run(lambda:repo.preview(target_for_batch(batch_id,repository),batch_id=batch_id))

@router.delete('/collections/{batch_id}')
def delete_batch(batch_id:UUID,request:DeleteRequest,repo=Depends(get_repository),repository=Depends(batches)):
    if request.delete_target: raise HTTPException(422,'Collection cleanup cannot delete a target.')
    return run(lambda:repo.delete(target_for_batch(batch_id,repository),batch_id,False,request.confirmation,request.preview_token))
