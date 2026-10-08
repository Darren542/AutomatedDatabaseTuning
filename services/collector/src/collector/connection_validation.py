"""Read-only connectivity validation. Does not save or activate targets."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

import pyodbc

from collector.targets import (
    AuthenticationMode,
    SqlCredentials,
    TargetConfiguration,
    TargetConfigurationError,
    validate_authentication,
)


class ValidationCode(str, Enum):
    CONNECTED = "connected"
    INVALID_CONFIGURATION = "invalid_configuration"
    DRIVER_UNAVAILABLE = "driver_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    TIMEOUT = "timeout"
    CONNECTION_FAILED = "connection_failed"
    DATABASE_UNAVAILABLE = "database_unavailable"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True)
class ConnectionValidationResult:
    code: ValidationCode
    message: str

    @property
    def connected(self) -> bool:
        return self.code == ValidationCode.CONNECTED


class Cursor(Protocol):
    def execute(self, sql: str, *parameters: object) -> object: ...
    def fetchone(self) -> object: ...
    def close(self) -> None: ...


class Connection(Protocol):
    timeout: int
    def cursor(self) -> Cursor: ...
    def close(self) -> None: ...


def _odbc_value(value: str) -> str:
    # Brace quoting prevents semicolons from becoming extra ODBC attributes.
    return "{" + value.replace("}", "}}") + "}"


def _connection_string(target: TargetConfiguration, credentials: SqlCredentials | None) -> str:
    validate_authentication(target, credentials)
    parts = [
        "DRIVER=" + _odbc_value(target.driver),
        "SERVER=" + _odbc_value(target.server),
        "DATABASE=" + _odbc_value(target.database),
        "Encrypt=" + ("yes" if target.encrypt else "no"),
        "TrustServerCertificate=" + ("yes" if target.trust_server_certificate else "no"),
        "APP=AutomatedDatabaseTuner",
    ]
    if target.authentication == AuthenticationMode.WINDOWS:
        parts.append("Trusted_Connection=yes")
    else:
        assert credentials is not None
        parts.extend(["UID=" + _odbc_value(credentials.username), "PWD=" + _odbc_value(credentials.password)])
    return ";".join(parts) + ";"


def _failure(error: pyodbc.Error) -> ConnectionValidationResult:
    # Never propagate driver diagnostics: they may contain credentials or SQL.
    state = error.args[0] if error.args else ""
    if state in ("IM002", "IM003"):
        return ConnectionValidationResult(ValidationCode.DRIVER_UNAVAILABLE, "Install the selected SQL Server ODBC driver.")
    if state == "28000":
        return ConnectionValidationResult(ValidationCode.AUTHENTICATION_FAILED, "Authentication failed. Check the authentication mode and account access to the database.")
    if state in ("HYT00", "HYT01"):
        return ConnectionValidationResult(ValidationCode.TIMEOUT, "Connection validation timed out. Check server availability and timeout settings.")
    if state == "3D000":
        return ConnectionValidationResult(ValidationCode.DATABASE_UNAVAILABLE, "The selected database is unavailable or inaccessible to this account.")
    if isinstance(state, str) and state.startswith("08"):
        return ConnectionValidationResult(ValidationCode.CONNECTION_FAILED, "Could not connect. Check the instance, network access, and TLS certificate configuration.")
    return ConnectionValidationResult(ValidationCode.VALIDATION_FAILED, "Could not validate database access. Check the selected database and account permissions.")


class ConnectionValidationService:
    def __init__(self, connect: Callable[..., Connection] = pyodbc.connect):
        self._connect = connect

    def validate(self, target: TargetConfiguration, credentials: SqlCredentials | None = None) -> ConnectionValidationResult:
        try:
            connection_string = _connection_string(target, credentials)
        except TargetConfigurationError as error:
            return ConnectionValidationResult(ValidationCode.INVALID_CONFIGURATION, str(error))

        connection = None
        cursor = None
        try:
            connection = self._connect(connection_string, timeout=target.connection_timeout_seconds, autocommit=True)
            connection.timeout = target.query_timeout_seconds
            cursor = connection.cursor()
            # Resolve the name on the server, respecting SQL Server collation.
            # Bind the name as data; do not interpolate it into SQL.
            cursor.execute("SELECT CASE WHEN DB_ID(?) = DB_ID() THEN 1 ELSE 0 END", target.database)
            row = cursor.fetchone()
            if row is None or row[0] != 1:
                return ConnectionValidationResult(ValidationCode.DATABASE_UNAVAILABLE, "The connection did not validate the selected database.")
            return ConnectionValidationResult(ValidationCode.CONNECTED, "Connection to the selected database succeeded.")
        except pyodbc.Error as error:
            return _failure(error)
        finally:
            # pyodbc's context manager manages transactions, not connection lifetime.
            for resource in (cursor, connection):
                if resource is not None:
                    try:
                        resource.close()
                    except pyodbc.Error:
                        # Cleanup must not leak driver diagnostics or hide the result.
                        pass
