from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from recommender.candidates import CandidateRepository, CandidateService
from recommender.repository import RecommendationRepository
from recommender.engine import utc
from autotuner_api.routes.recommendations import ScoringWeights

router=APIRouter(tags=['candidate workflow'])

class GenerateRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    batch_id: UUID

class ScoreRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_set_id: UUID
    candidate_ids: list[str] | None = Field(default=None,max_length=10000)
    weights: ScoringWeights=Field(default_factory=ScoringWeights)

def get_service(): return CandidateService()
def get_repository(): return CandidateRepository()

def call(operation):
    try: return operation()
    except KeyError: raise HTTPException(404,'Collection or candidate set not found.') from None
    except ValueError as error: raise HTTPException(422,str(error)) from None

@router.post('/candidate-sets',status_code=201)
def generate(request:GenerateRequest,service=Depends(get_service)):
    return call(lambda:service.generate(request.batch_id))

@router.get('/candidate-sets')
def list_sets(target_id:UUID|None=None,repository=Depends(get_repository)):
    return repository.list(target_id)

@router.get('/candidate-sets/{candidate_set_id}')
def get_set(candidate_set_id:UUID,repository=Depends(get_repository)):
    return call(lambda:repository.get(candidate_set_id))

@router.get('/candidate-sets/eligibility/{batch_id}')
def eligibility(batch_id:UUID):
    try:
        bundle=RecommendationRepository().load(batch_id)
        age=(utc(bundle['source']['observed_at_utc'])-utc(bundle['metadata_observed_at_utc'])).total_seconds()/3600
        if not 0<=age<=24: raise ValueError('Metadata is not fresh for this source snapshot. Collect with Force metadata refresh.')
        return dict(eligible=True,missing_index_hints=len(bundle['missing']),existing_indexes=len(bundle['indexes']),
            has_baseline=bool(bundle.get('baseline')),message='Ready for candidate generation.')
    except KeyError: raise HTTPException(404,'Collection not found.') from None
    except ValueError as error: return dict(eligible=False,message=str(error))

@router.post('/recommendations/score',status_code=201)
def score(request:ScoreRequest,service=Depends(get_service)):
    return call(lambda:service.score(request.candidate_set_id,request.candidate_ids,request.weights.model_dump()))


@router.post('/candidate-sets/from-analysis/{analysis_id}',status_code=201)
def from_analysis(analysis_id:UUID,service=Depends(get_service)):
    return call(lambda:service.from_analysis(analysis_id))
