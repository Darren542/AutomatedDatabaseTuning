from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from collector.collection.coordinator import (
    CollectionCoordinator,
    TargetUnavailableError,
)
from collector.collection.runner import CollectionRunner
from collector.collection.summary import CollectionSummaryService
from collector.repository.collection_batches import SqlCollectionBatchRepository
from collector.repository.component_results import SqlComponentResultRepository
from collector.repository.models import CollectionBatchRecord, CollectionBatchStatus

router = APIRouter(prefix="/collections", tags=["collections"])

class CreateCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: UUID
    label: str | None = Field(default=None, max_length=200)
    requested_window_start_utc: datetime | None = None
    requested_window_end_utc: datetime | None = None
    force_metadata: bool = False

    @model_validator(mode="after")
    def validate_window(self):
        start = self.requested_window_start_utc
        end = self.requested_window_end_utc

        if (start is None) != (end is None):
            raise ValueError(
                "requested_window_start_utc and requested_window_end_utc "
                "must either both be supplied or both be null."
            )

        if start is not None and end is not None and start > end:
            raise ValueError(
                "requested_window_start_utc must be <= requested_window_end_utc."
            )

        return self

class CollectionResponse(BaseModel):
    batch_id: UUID
    target_id: UUID
    label: str | None
    requested_window_start_utc: datetime | None
    requested_window_end_utc: datetime | None
    effective_window_start_utc: datetime | None
    effective_window_end_utc: datetime | None
    window_source: str | None
    force_metadata: bool
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
    skipped_components: int
    failed_components: int
    effective_window_start_utc: datetime
    effective_window_end_utc: datetime
    window_source: str

class ComponentResultResponse(BaseModel):
    component_name: str
    status: str
    rows_collected: int | None
    started_at_utc: datetime | None
    completed_at_utc: datetime | None
    error_code: str | None
    error_message: str | None
    status_message: str | None

class SourceStateSummaryResponse(BaseModel):
    observed_at_utc: datetime
    sql_server_start_time_utc: datetime | None
    query_store_actual_state: str | None
    dmv_reset_detected: bool
    query_store_reset_detected: bool

class EvidenceCountResponse(BaseModel):
    query_runtime_rows: int
    index_usage_rows: int
    index_operational_rows: int
    missing_index_rows: int
    table_metadata_rows: int
    column_metadata_rows: int
    index_metadata_rows: int
    index_column_metadata_rows: int
    constraint_metadata_rows: int
    metadata_rows: int

class QueryRuntimeSummaryResponse(BaseModel):
    runtime_evidence_rows: int
    execution_count: int
    total_duration_ms: float
    total_cpu_ms: float
    logical_reads: float
    logical_writes: float
    physical_reads: float

class CollectionSummaryResponse(BaseModel):
    batch: CollectionResponse
    source_state: SourceStateSummaryResponse | None
    component_statuses: dict[str, str]
    evidence: EvidenceCountResponse
    query_runtime: QueryRuntimeSummaryResponse
    metadata_source_batch_id: UUID | None
    target_query_watermark_utc: datetime | None

def get_coordinator() -> CollectionCoordinator:
    return CollectionCoordinator()

def get_runner() -> CollectionRunner:
    return CollectionRunner()

def get_batch_repository() -> SqlCollectionBatchRepository:
    return SqlCollectionBatchRepository()

def get_component_repository() -> SqlComponentResultRepository:
    return SqlComponentResultRepository()

def get_summary_service() -> CollectionSummaryService:
    return CollectionSummaryService()

def _response(batch: CollectionBatchRecord) -> CollectionResponse:
    return CollectionResponse(
        batch_id=batch.batch_id,
        target_id=batch.target_id,
        label=batch.label,
        requested_window_start_utc=batch.requested_window_start_utc,
        requested_window_end_utc=batch.requested_window_end_utc,
        effective_window_start_utc=batch.effective_window_start_utc,
        effective_window_end_utc=batch.effective_window_end_utc,
        window_source=batch.window_source,
        force_metadata=batch.force_metadata,
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
def create_collection(
    request: CreateCollectionRequest,
    coordinator: CollectionCoordinator = Depends(get_coordinator),
) -> CollectionResponse:
    try:
        return _response(
            coordinator.create_batch(
                target_id=request.target_id,
                label=request.label,
                requested_window_start_utc=request.requested_window_start_utc,
                requested_window_end_utc=request.requested_window_end_utc,
                force_metadata=request.force_metadata,
            )
        )
    except TargetUnavailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

@router.get("", response_model=list[CollectionResponse])
def list_collections(
    target_id: UUID | None = None,
    status: CollectionBatchStatus | None = None,
    created_from_utc: datetime | None = None,
    created_to_utc: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    repository: SqlCollectionBatchRepository = Depends(get_batch_repository),
) -> list[CollectionResponse]:
    return [
        _response(batch)
        for batch in repository.list(
            target_id=target_id,
            status=status,
            created_from_utc=created_from_utc,
            created_to_utc=created_to_utc,
            limit=limit,
        )
    ]

@router.get("/{batch_id}/components", response_model=list[ComponentResultResponse])
def get_collection_components(
    batch_id: UUID,
    repository: SqlComponentResultRepository = Depends(get_component_repository),
) -> list[ComponentResultResponse]:
    return [
        ComponentResultResponse(**row)
        for row in repository.list(batch_id)
    ]

@router.get("/{batch_id}/summary", response_model=CollectionSummaryResponse)
def get_collection_summary(
    batch_id: UUID,
    service: CollectionSummaryService = Depends(get_summary_service),
) -> CollectionSummaryResponse:
    try:
        result = service.get(batch_id)
        return CollectionSummaryResponse(
            batch=_response(result["batch"]),
            source_state=result["source_state"],
            component_statuses=result["component_statuses"],
            evidence=result["evidence"],
            query_runtime=result["query_runtime"],
            metadata_source_batch_id=result["metadata_source_batch_id"],
            target_query_watermark_utc=result["target_query_watermark_utc"],
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Collection not found.") from None

@router.get("/{batch_id}", response_model=CollectionResponse)
def get_collection(
    batch_id: UUID,
    repository: SqlCollectionBatchRepository = Depends(get_batch_repository),
) -> CollectionResponse:
    batch = repository.get(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Collection not found.")
    return _response(batch)

@router.post("/{batch_id}/collect", response_model=CollectionRunResponse)
def collect_batch(
    batch_id: UUID,
    runner: CollectionRunner = Depends(get_runner),
) -> CollectionRunResponse:
    try:
        result = runner.collect(batch_id)
        return CollectionRunResponse(
            batch_id=result.batch_id,
            final_status=result.final_status,
            completeness_percent=result.completeness_percent,
            completed_components=result.completed_components,
            skipped_components=result.skipped_components,
            failed_components=result.failed_components,
            effective_window_start_utc=result.effective_window_start_utc,
            effective_window_end_utc=result.effective_window_end_utc,
            window_source=result.window_source,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
