"""FR-01 HTTP boundary. Connection tests never persist target configuration."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from collector.connection_validation import ConnectionValidationService, ValidationCode
from collector.targets import (
    SqlCredentials, TargetConfiguration, TargetConfigurationError, validate_authentication,
)

router = APIRouter(prefix="/targets", tags=["targets"])


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    username: str = Field(repr=False)
    password: SecretStr = Field(repr=False)


class TestConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    server: str
    database: str
    authentication: Literal["windows", "sql"] = "windows"
    driver: Literal["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"] = "ODBC Driver 18 for SQL Server"
    encrypt: bool = True
    trust_server_certificate: bool = False
    connection_timeout_seconds: int = Field(default=5, ge=1, le=60)
    query_timeout_seconds: int = Field(default=5, ge=1, le=60)
    credentials: CredentialsRequest | None = Field(default=None, repr=False, exclude=True)


class TestConnectionResponse(BaseModel):
    connected: bool
    code: ValidationCode
    message: str


class InvalidRequestResponse(BaseModel):
    detail: str


def get_validation_service() -> ConnectionValidationService:
    return ConnectionValidationService()


@router.post("/test-connection", response_model=TestConnectionResponse,
             responses={422: {"model": InvalidRequestResponse}})
def test_connection(
    request: TestConnectionRequest,
    service: ConnectionValidationService = Depends(get_validation_service),
) -> TestConnectionResponse:
    """Test database access without saving or activating a target.

    HTTP 200 describes a completed test, including connection failures.
    Invalid configuration is HTTP 422. Only a connected=true result is success.
    """
    try:
        target = TargetConfiguration(**request.model_dump(exclude={"credentials"}))
        credentials = None
        if request.credentials is not None:
            credentials = SqlCredentials(
                request.credentials.username, request.credentials.password.get_secret_value()
            )
        validate_authentication(target, credentials)
    except TargetConfigurationError as error:
        # Domain errors use fixed field names and never echo submitted values.
        raise HTTPException(status_code=422, detail=str(error)) from None
    # Sync route runs blocking ODBC work in FastAPI's thread pool.
    result = service.validate(target, credentials)
    return TestConnectionResponse(connected=result.connected, code=result.code, message=result.message)
