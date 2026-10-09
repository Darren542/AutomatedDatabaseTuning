"""Persistence for target metadata. Credentials themselves are never stored here."""

from __future__ import annotations

from uuid import UUID

from collector.repository.connection import RepositorySettings, repository_connection
from collector.repository.models import TargetRecord
from collector.targets import AuthenticationMode, TargetConfiguration


def _record(row: object) -> TargetRecord:
    return TargetRecord(
        target_id=UUID(str(row.TargetId)),
        configuration=TargetConfiguration(
            name=row.Name,
            server=row.ServerName,
            database=row.DatabaseName,
            authentication=AuthenticationMode(row.AuthenticationMode),
            driver=row.DriverName,
            encrypt=bool(row.EncryptConnection),
            trust_server_certificate=bool(row.TrustServerCertificate),
            connection_timeout_seconds=int(row.ConnectionTimeoutSeconds),
            query_timeout_seconds=int(row.QueryTimeoutSeconds),
        ),
        credential_reference=row.CredentialReference,
        is_enabled=bool(row.IsEnabled),
        created_at_utc=row.CreatedAtUtc,
        updated_at_utc=row.UpdatedAtUtc,
    )


class SqlTargetRepository:
    def __init__(self, settings: RepositorySettings | None = None):
        self._settings = settings

    def create(
        self,
        target: TargetConfiguration,
        credential_reference: str | None,
    ) -> TargetRecord:
        if (
            target.authentication == AuthenticationMode.SQL
            and (
                credential_reference is None
                or not credential_reference.strip()
            )
        ):
            raise ValueError(
                "SQL-authenticated targets require a credential reference."
            )

        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    INSERT INTO dbo.TargetDatabase
                    (
                        Name,
                        ServerName,
                        DatabaseName,
                        AuthenticationMode,
                        DriverName,
                        EncryptConnection,
                        TrustServerCertificate,
                        ConnectionTimeoutSeconds,
                        QueryTimeoutSeconds,
                        CredentialReference
                    )
                    OUTPUT
                        inserted.TargetId,
                        inserted.Name,
                        inserted.ServerName,
                        inserted.DatabaseName,
                        inserted.AuthenticationMode,
                        inserted.DriverName,
                        inserted.EncryptConnection,
                        inserted.TrustServerCertificate,
                        inserted.ConnectionTimeoutSeconds,
                        inserted.QueryTimeoutSeconds,
                        inserted.CredentialReference,
                        inserted.IsEnabled,
                        inserted.CreatedAtUtc,
                        inserted.UpdatedAtUtc
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    target.name,
                    target.server,
                    target.database,
                    target.authentication.value,
                    target.driver,
                    target.encrypt,
                    target.trust_server_certificate,
                    target.connection_timeout_seconds,
                    target.query_timeout_seconds,
                    credential_reference,
                ).fetchone()
                connection.commit()
                return _record(row)
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def get(self, target_id: UUID) -> TargetRecord | None:
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT
                        TargetId,
                        Name,
                        ServerName,
                        DatabaseName,
                        AuthenticationMode,
                        DriverName,
                        EncryptConnection,
                        TrustServerCertificate,
                        ConnectionTimeoutSeconds,
                        QueryTimeoutSeconds,
                        CredentialReference,
                        IsEnabled,
                        CreatedAtUtc,
                        UpdatedAtUtc
                    FROM dbo.TargetDatabase
                    WHERE TargetId = ?;
                    """,
                    str(target_id),
                ).fetchone()
                return _record(row) if row is not None else None
            finally:
                cursor.close()

    def list(self, limit: int = 100) -> list[TargetRecord]:
        safe_limit = max(1, min(int(limit), 500))
        with repository_connection(self._settings) as connection:
            cursor = connection.cursor()
            try:
                rows = cursor.execute(
                    f"""
                    SELECT TOP ({safe_limit})
                        TargetId,
                        Name,
                        ServerName,
                        DatabaseName,
                        AuthenticationMode,
                        DriverName,
                        EncryptConnection,
                        TrustServerCertificate,
                        ConnectionTimeoutSeconds,
                        QueryTimeoutSeconds,
                        CredentialReference,
                        IsEnabled,
                        CreatedAtUtc,
                        UpdatedAtUtc
                    FROM dbo.TargetDatabase
                    ORDER BY Name;
                    """
                ).fetchall()
                return [_record(row) for row in rows]
            finally:
                cursor.close()
