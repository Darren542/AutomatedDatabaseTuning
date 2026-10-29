"""FR-01 HTTP boundary.

Connection tests use transient credentials and never persist them.
Saved targets persist metadata plus an optional credential reference only.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from collector.connection_validation import (
    ConnectionValidationService,
    ValidationCode,
)
from collector.repository.models import TargetRecord
from collector.repository.targets import SqlTargetRepository
from collector.target_connection import resolve_credentials, TargetCredentialError

from collector.targets import (
    SqlCredentials,
    TargetConfiguration,
    TargetConfigurationError,
    validate_authentication,
)

router = APIRouter(prefix="/targets", tags=["targets"])


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    username: str = Field(repr=False)
    password: SecretStr = Field(repr=False)


class TargetConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    server: str
    database: str
    authentication: Literal["windows", "sql"] = "windows"

    driver: Literal[
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 18 for SQL Server",
    ] = "ODBC Driver 18 for SQL Server"

    encrypt: bool = True
    trust_server_certificate: bool = False
    connection_timeout_seconds: int = Field(default=5, ge=1, le=60)
    query_timeout_seconds: int = Field(default=30, ge=1, le=60)


class TestConnectionRequest(TargetConfigurationRequest):
    credentials: CredentialsRequest | None = Field(
        default=None,
        repr=False,
        exclude=True,
    )


class SaveTargetRequest(TargetConfigurationRequest):
    acknowledge_excessive_permissions: bool = False
    credential_reference: str | None = Field(
        default=None,
        max_length=200,
    )


class TestConnectionResponse(BaseModel):
    connected: bool
    collector_ready: bool
    code: ValidationCode
    message: str
    query_store_readable: bool
    index_usage_readable: bool
    metadata_readable: bool
    ddl_restricted: bool
    source_state_readable: bool
    index_operational_readable: bool
    missing_indexes_readable: bool


class TargetResponse(BaseModel):
    target_id: UUID
    name: str
    server: str
    database: str
    authentication: str
    driver: str
    encrypt: bool
    trust_server_certificate: bool
    connection_timeout_seconds: int
    query_timeout_seconds: int
    credential_reference: str | None
    is_enabled: bool


class InvalidRequestResponse(BaseModel):
    detail: str


def get_validation_service() -> ConnectionValidationService:
    return ConnectionValidationService()


def get_target_repository() -> SqlTargetRepository:
    return SqlTargetRepository()


def _target_configuration(
    request: TargetConfigurationRequest,
) -> TargetConfiguration:
    try:
        return TargetConfiguration(
            name=request.name,
            server=request.server,
            database=request.database,
            authentication=request.authentication,
            driver=request.driver,
            encrypt=request.encrypt,
            trust_server_certificate=request.trust_server_certificate,
            connection_timeout_seconds=request.connection_timeout_seconds,
            query_timeout_seconds=request.query_timeout_seconds,
        )
    except TargetConfigurationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


def _response(record: TargetRecord) -> TargetResponse:
    config = record.configuration
    return TargetResponse(
        target_id=record.target_id,
        name=config.name,
        server=config.server,
        database=config.database,
        authentication=config.authentication.value,
        driver=config.driver,
        encrypt=config.encrypt,
        trust_server_certificate=config.trust_server_certificate,
        connection_timeout_seconds=config.connection_timeout_seconds,
        query_timeout_seconds=config.query_timeout_seconds,
        credential_reference=record.credential_reference,
        is_enabled=record.is_enabled,
    )


@router.post(
    "/test-connection",
    response_model=TestConnectionResponse,
    responses={422: {"model": InvalidRequestResponse}},
)
def test_connection(
    request: TestConnectionRequest,
    service: ConnectionValidationService = Depends(get_validation_service),
) -> TestConnectionResponse:
    try:
        target = _target_configuration(request)

        credentials = None
        if request.credentials is not None:
            credentials = SqlCredentials(
                request.credentials.username,
                request.credentials.password.get_secret_value(),
            )

        validate_authentication(target, credentials)

    except TargetConfigurationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

    result = service.validate(target, credentials)

    return TestConnectionResponse(
        connected=result.connected,
        collector_ready=result.collector_ready,
        code=result.code,
        message=result.message,
        query_store_readable=result.query_store_readable,
        index_usage_readable=result.index_usage_readable,
        metadata_readable=result.metadata_readable,
        ddl_restricted=result.ddl_restricted,
        source_state_readable=result.source_state_readable,
        index_operational_readable=result.index_operational_readable,
        missing_indexes_readable=result.missing_indexes_readable,
    )


@router.post("", response_model=TargetResponse, status_code=201)
def save_target(
    request: SaveTargetRequest,
    repository: SqlTargetRepository = Depends(get_target_repository),
    service: ConnectionValidationService = Depends(get_validation_service),
) -> TargetResponse:
    target = _target_configuration(request)
    try:
        credentials = resolve_credentials(request.credential_reference) if target.authentication.value == "sql" and request.credential_reference else None
        validate_authentication(target, credentials)
    except (TargetCredentialError, TargetConfigurationError) as error:
        raise HTTPException(status_code=422, detail="Configure the credential reference on the API server before saving a SQL target.") from None
    result = service.validate(target, credentials)
    if not result.collector_ready:
        raise HTTPException(status_code=422, detail="Target is not collector-ready. Check connectivity and required telemetry permissions.")
    if not result.ddl_restricted and not request.acknowledge_excessive_permissions:
        raise HTTPException(status_code=428, detail="This account can alter database objects. Acknowledge the excessive-permissions warning to save this target.")

    try:
        record = repository.create(
            target,
            credential_reference=request.credential_reference,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except Exception as error:
        raise HTTPException(
            status_code=409,
            detail="Could not save target. Check for a duplicate target name.",
        ) from error

    return _response(record)


@router.get("", response_model=list[TargetResponse])
def list_targets(
    limit: int = Query(default=100, ge=1, le=500),
    repository: SqlTargetRepository = Depends(get_target_repository),
) -> list[TargetResponse]:
    return [_response(record) for record in repository.list(limit)]


@router.get("/{target_id}", response_model=TargetResponse)
def get_target(
    target_id: UUID,
    repository: SqlTargetRepository = Depends(get_target_repository),
) -> TargetResponse:
    record = repository.get(target_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Target not found.")
    return _response(record)


@router.post("/{target_id}/test-connection", response_model=TestConnectionResponse)
def test_saved_target(target_id: UUID, repository=Depends(get_target_repository), service=Depends(get_validation_service)):
    record = repository.get(target_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Target not found.")
    try:
        credentials = resolve_credentials(record.credential_reference) if record.configuration.authentication.value == "sql" else None
    except (TargetCredentialError, AttributeError):
        raise HTTPException(status_code=422, detail="The target credential reference is not configured on the API server.") from None
    result = service.validate(record.configuration, credentials)
    return TestConnectionResponse(connected=result.connected, collector_ready=result.collector_ready,
        code=result.code, message=result.message, query_store_readable=result.query_store_readable,
        index_usage_readable=result.index_usage_readable, metadata_readable=result.metadata_readable,
        ddl_restricted=result.ddl_restricted, source_state_readable=result.source_state_readable,
        index_operational_readable=result.index_operational_readable, missing_indexes_readable=result.missing_indexes_readable)
