"""Read-only connectivity/capability validation. Does not save or activate targets."""

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
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    EXCESSIVE_PERMISSIONS = "excessive_permissions"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True)
class ConnectionValidationResult:
    code: ValidationCode
    message: str
    database_connected: bool = False
    query_store_readable: bool = False
    index_usage_readable: bool = False
    metadata_readable: bool = False
    ddl_restricted: bool = False

    @property
    def connected(self) -> bool:
        return self.database_connected

    @property
    def collector_ready(self) -> bool:
        return (
            self.database_connected
            and self.query_store_readable
            and self.index_usage_readable
            and self.metadata_readable
            and self.ddl_restricted
        )


class Cursor(Protocol):
    def execute(self, sql: str, *parameters: object) -> object: ...
    def fetchone(self) -> object: ...
    def fetchall(self) -> object: ...
    def close(self) -> None: ...


class Connection(Protocol):
    timeout: int

    def cursor(self) -> Cursor: ...
    def close(self) -> None: ...


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def _connection_string(
    target: TargetConfiguration,
    credentials: SqlCredentials | None,
) -> str:
    validate_authentication(target, credentials)

    parts = [
        "DRIVER=" + _odbc_value(target.driver),
        "SERVER=" + _odbc_value(target.server),
        "DATABASE=" + _odbc_value(target.database),
        "Encrypt=" + ("yes" if target.encrypt else "no"),
        "TrustServerCertificate="
        + ("yes" if target.trust_server_certificate else "no"),
        "APP=AutomatedDatabaseTuner.CollectorValidation",
    ]

    if target.authentication == AuthenticationMode.WINDOWS:
        parts.append("Trusted_Connection=yes")
    else:
        assert credentials is not None
        parts.extend(
            [
                "UID=" + _odbc_value(credentials.username),
                "PWD=" + _odbc_value(credentials.password),
            ]
        )

    return ";".join(parts) + ";"


def _failure(error: pyodbc.Error) -> ConnectionValidationResult:
    state = error.args[0] if error.args else ""

    if state in ("IM002", "IM003"):
        return ConnectionValidationResult(
            ValidationCode.DRIVER_UNAVAILABLE,
            "Install the selected SQL Server ODBC driver.",
        )

    if state == "28000":
        return ConnectionValidationResult(
            ValidationCode.AUTHENTICATION_FAILED,
            "Authentication failed. Check the authentication mode and account access.",
        )

    if state in ("HYT00", "HYT01"):
        return ConnectionValidationResult(
            ValidationCode.TIMEOUT,
            "Connection validation timed out.",
        )

    if state == "3D000":
        return ConnectionValidationResult(
            ValidationCode.DATABASE_UNAVAILABLE,
            "The selected database is unavailable or inaccessible.",
        )

    if isinstance(state, str) and state.startswith("08"):
        return ConnectionValidationResult(
            ValidationCode.CONNECTION_FAILED,
            "Could not connect. Check the instance, network, and TLS configuration.",
        )

    return ConnectionValidationResult(
        ValidationCode.VALIDATION_FAILED,
        "Could not validate database access.",
    )


def _can_execute(cursor: Cursor, sql: str) -> bool:
    try:
        cursor.execute(sql)
        cursor.fetchall()
        return True
    except pyodbc.Error:
        return False


class ConnectionValidationService:
    def __init__(self, connect: Callable[..., Connection] = pyodbc.connect):
        self._connect = connect

    def validate(
        self,
        target: TargetConfiguration,
        credentials: SqlCredentials | None = None,
    ) -> ConnectionValidationResult:
        try:
            connection_string = _connection_string(target, credentials)
        except TargetConfigurationError as error:
            return ConnectionValidationResult(
                ValidationCode.INVALID_CONFIGURATION,
                str(error),
            )

        connection = None
        cursor = None

        try:
            connection = self._connect(
                connection_string,
                timeout=target.connection_timeout_seconds,
                autocommit=True,
            )
            connection.timeout = target.query_timeout_seconds
            cursor = connection.cursor()

            cursor.execute(
                "SELECT CASE WHEN DB_ID(?) = DB_ID() THEN 1 ELSE 0 END",
                target.database,
            )
            row = cursor.fetchone()

            if row is None or row[0] != 1:
                return ConnectionValidationResult(
                    ValidationCode.DATABASE_UNAVAILABLE,
                    "The connection did not validate the selected database.",
                )

            query_store_readable = _can_execute(
                cursor,
                "SELECT TOP (1) query_id FROM sys.query_store_query;",
            )

            index_usage_readable = _can_execute(
                cursor,
                """
                SELECT TOP (1) object_id, index_id
                FROM sys.dm_db_index_usage_stats
                WHERE database_id = DB_ID();
                """,
            )

            metadata_readable = _can_execute(
                cursor,
                """
                SELECT TOP (1) object_id, name
                FROM sys.tables
                WHERE is_ms_shipped = 0;
                """,
            )

            cursor.execute(
                "SELECT HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'ALTER');"
            )
            alter_row = cursor.fetchone()
            ddl_restricted = alter_row is not None and not bool(alter_row[0])

            if not (
                query_store_readable
                and index_usage_readable
                and metadata_readable
            ):
                return ConnectionValidationResult(
                    ValidationCode.INSUFFICIENT_PERMISSIONS,
                    (
                        "Database connection succeeded, but the account cannot read "
                        "all telemetry required by the Workload Collector."
                    ),
                    database_connected=True,
                    query_store_readable=query_store_readable,
                    index_usage_readable=index_usage_readable,
                    metadata_readable=metadata_readable,
                    ddl_restricted=ddl_restricted,
                )

            if not ddl_restricted:
                return ConnectionValidationResult(
                    ValidationCode.EXCESSIVE_PERMISSIONS,
                    (
                        "Database connection and telemetry reads succeeded, but the "
                        "collector account has ALTER permission. Use a lower-privilege "
                        "collector credential."
                    ),
                    database_connected=True,
                    query_store_readable=True,
                    index_usage_readable=True,
                    metadata_readable=True,
                    ddl_restricted=False,
                )

            return ConnectionValidationResult(
                ValidationCode.CONNECTED,
                "Connection and collector permissions validated.",
                database_connected=True,
                query_store_readable=True,
                index_usage_readable=True,
                metadata_readable=True,
                ddl_restricted=True,
            )

        except pyodbc.Error as error:
            return _failure(error)

        finally:
            for resource in (cursor, connection):
                if resource is not None:
                    try:
                        resource.close()
                    except pyodbc.Error:
                        pass
