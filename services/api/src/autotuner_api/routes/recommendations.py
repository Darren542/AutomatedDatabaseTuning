from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from autotuner_api.utc import UTCResponse
from recommender.engine import Policy
from recommender.repository import RecommendationRepository
from recommender.service import RecommendationService

router = APIRouter(prefix='/recommendations', tags=['recommendations'])


class ScoringWeights(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    read_weight: float = Field(default=1, ge=0, le=100)
    write_weight: float = Field(default=1, ge=0, le=100)
    storage_weight: float = Field(default=0.1, ge=0, le=100)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    batch_id: UUID
    weights: ScoringWeights = Field(default_factory=ScoringWeights)


class AnalysisSummary(UTCResponse):
    candidate_set_id: UUID | None = None
    analysis_id: UUID
    target_id: UUID
    batch_id: UUID
    metadata_batch_id: UUID
    engine_version: str
    input_hash: str
    recommendation_count: int
    created_at_utc: datetime


def get_service():
    return RecommendationService()


def get_repository():
    return RecommendationRepository()


@router.post('/analyze', status_code=201)
def analyze_collection(request: AnalyzeRequest, service=Depends(get_service)):
    try:
        return service.analyze(request.batch_id, Policy(**request.weights.model_dump()))
    except KeyError:
        raise HTTPException(status_code=404, detail='Collection not found.') from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get('/analyses', response_model=list[AnalysisSummary])
def list_analyses(target_id: UUID | None = None, candidate_set_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=100), repository=Depends(get_repository)):
    return repository.list(target_id, limit, candidate_set_id) if candidate_set_id else repository.list(target_id, limit)


@router.get('/analyses/{analysis_id}')
def get_analysis(analysis_id: UUID, repository=Depends(get_repository)):
    try:
        return repository.get(analysis_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Analysis not found.') from None
