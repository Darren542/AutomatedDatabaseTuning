from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from collector.collection.coordinator import CollectionCoordinator, TargetUnavailableError
from collector.collection.runner import CollectionRunner
from collector.repository.collection_batches import CollectionBatchNotFoundError, SqlCollectionBatchRepository
from collector.repository.component_results import SqlComponentResultRepository
from collector.repository.models import CollectionBatchRecord, CollectionBatchStatus

router = APIRouter(prefix="/collections", tags=["collections"])


class CreateCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_id: UUID
    label: str | None = Field(default=None, max_length=200)
    requested_window_start_utc: datetime | None = None
    requested_window_end_utc: datetime | None = None

    @model_validator(mode="after")
    def validate_window(self):
        if self.requested_window_start_utc is not None and self.requested_window_end_utc is not None and self.requested_window_start_utc > self.requested_window_end_utc:
            raise ValueError("requested_window_start_utc must be <= requested_window_end_utc")
        return self


class FailCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class PartialCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completeness_percent: float = Field(ge=0, le=100)
    reason: str | None = Field(default=None, max_length=2000)


class CollectionResponse(BaseModel):
    batch_id: UUID
    target_id: UUID
    label: str | None
    requested_window_start_utc: datetime | None
    requested_window_end_utc: datetime | None
    collection_started_at_utc: datetime | None
    collection_completed_at_utc: datetime | None
    status: CollectionBatchStatus
    completeness_percent: float
    collector_version: str | None
    failure_reason: str | None
    created_at_utc: datetime
    updated_at_utc: datetime


class CollectionRunResponse(BaseModel):
    batch_id: UUID
    final_status: CollectionBatchStatus
    completeness_percent: float
    completed_components: int
    failed_components: int


class ComponentResultResponse(BaseModel):
    component_name: str
    status: str
    rows_collected: int | None
    started_at_utc: datetime | None
    completed_at_utc: datetime | None
    error_code: str | None
    error_message: str | None


def get_coordinator() -> CollectionCoordinator:
    return CollectionCoordinator()


def get_runner() -> CollectionRunner:
    return CollectionRunner()


def get_batch_repository() -> SqlCollectionBatchRepository:
    return SqlCollectionBatchRepository()


def get_component_repository() -> SqlComponentResultRepository:
    return SqlComponentResultRepository()


def _response(batch: CollectionBatchRecord) -> CollectionResponse:
    return CollectionResponse(
        batch_id=batch.batch_id,
        target_id=batch.target_id,
        label=batch.label,
        requested_window_start_utc=batch.requested_window_start_utc,
        requested_window_end_utc=batch.requested_window_end_utc,
        collection_started_at_utc=batch.collection_started_at_utc,
        collection_completed_at_utc=batch.collection_completed_at_utc,
        status=batch.status,
        completeness_percent=batch.completeness_percent,
        collector_version=batch.collector_version,
        failure_reason=batch.failure_reason,
        created_at_utc=batch.created_at_utc,
        updated_at_utc=batch.updated_at_utc,
    )


@router.post("", response_model=CollectionResponse, status_code=201)
def create_collection(request: CreateCollectionRequest, coordinator: CollectionCoordinator = Depends(get_coordinator)) -> CollectionResponse:
    try:
        return _response(coordinator.create_batch(
            target_id=request.target_id,
            label=request.label,
            requested_window_start_utc=request.requested_window_start_utc,
            requested_window_end_utc=request.requested_window_end_utc,
        ))
    except TargetUnavailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("", response_model=list[CollectionResponse])
def list_collections(target_id: UUID | None = None, limit: int = Query(default=100, ge=1, le=500), repository: SqlCollectionBatchRepository = Depends(get_batch_repository)) -> list[CollectionResponse]:
    return [_response(x) for x in repository.list(target_id=target_id, limit=limit)]


@router.get("/{batch_id}", response_model=CollectionResponse)
def get_collection(batch_id: UUID, repository: SqlCollectionBatchRepository = Depends(get_batch_repository)) -> CollectionResponse:
    batch = repository.get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Collection not found.")
    return _response(batch)


@router.get("/{batch_id}/components", response_model=list[ComponentResultResponse])
def get_collection_components(batch_id: UUID, repository: SqlComponentResultRepository = Depends(get_component_repository)) -> list[ComponentResultResponse]:
    return [ComponentResultResponse(**x) for x in repository.list(batch_id)]


@router.post("/{batch_id}/collect", response_model=CollectionRunResponse)
def collect_batch(batch_id: UUID, runner: CollectionRunner = Depends(get_runner)) -> CollectionRunResponse:
    try:
        result = runner.collect(batch_id)
        return CollectionRunResponse(
            batch_id=result.batch_id,
            final_status=result.final_status,
            completeness_percent=result.completeness_percent,
            completed_components=result.completed_components,
            failed_components=result.failed_components,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/{batch_id}/start", response_model=CollectionResponse)
def start_collection(batch_id: UUID, coordinator: CollectionCoordinator = Depends(get_coordinator)) -> CollectionResponse:
    try:
        return _response(coordinator.start(batch_id))
    except CollectionBatchNotFoundError:
        raise HTTPException(status_code=404, detail="Collection not found.") from None
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/{batch_id}/complete", response_model=CollectionResponse)
def complete_collection(batch_id: UUID, coordinator: CollectionCoordinator = Depends(get_coordinator)) -> CollectionResponse:
    try:
        return _response(coordinator.complete(batch_id))
    except CollectionBatchNotFoundError:
        raise HTTPException(status_code=404, detail="Collection not found.") from None
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/{batch_id}/partial", response_model=CollectionResponse)
def partial_collection(batch_id: UUID, request: PartialCollectionRequest, coordinator: CollectionCoordinator = Depends(get_coordinator)) -> CollectionResponse:
    try:
        return _response(coordinator.partial(batch_id, completeness_percent=request.completeness_percent, reason=request.reason))
    except CollectionBatchNotFoundError:
        raise HTTPException(status_code=404, detail="Collection not found.") from None
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/{batch_id}/fail", response_model=CollectionResponse)
def fail_collection(batch_id: UUID, request: FailCollectionRequest, coordinator: CollectionCoordinator = Depends(get_coordinator)) -> CollectionResponse:
    try:
        return _response(coordinator.fail(batch_id, reason=request.reason))
    except CollectionBatchNotFoundError:
        raise HTTPException(status_code=404, detail="Collection not found.") from None
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
