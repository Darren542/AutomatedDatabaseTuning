from __future__ import annotations

import os
from pathlib import Path
from dotenv import dotenv_values
from collector.targets import SqlCredentials
from contextlib import contextmanager
from typing import Iterator

import pyodbc

from collector.repository.models import TargetRecord
from collector.targets import AuthenticationMode


class TargetCredentialError(ValueError):
    pass


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def _credentials(reference: str) -> tuple[str, str]:
    prefix = reference.strip().upper()
    values = {**dotenv_values(Path.cwd() / ".env"), **os.environ}
    username = values.get(f"{prefix}_SQL_USERNAME")
    password = values.get(f"{prefix}_SQL_PASSWORD")
    if not username or not password:
        raise TargetCredentialError(f"Credential reference {reference!r} is not configured.")
    return username, password


def target_connection_string(target: TargetRecord) -> str:
    config = target.configuration
    parts = [
        "DRIVER=" + _odbc_value(config.driver),
        "SERVER=" + _odbc_value(config.server),
        "DATABASE=" + _odbc_value(config.database),
        "Encrypt=" + ("yes" if config.encrypt else "no"),
        "TrustServerCertificate=" + ("yes" if config.trust_server_certificate else "no"),
        "APP=AutomatedDatabaseTuner.Collector",
    ]
    if config.authentication == AuthenticationMode.WINDOWS:
        parts.append("Trusted_Connection=yes")
    else:
        if not target.credential_reference:
            raise TargetCredentialError("SQL-authenticated target has no credential reference.")
        username, password = _credentials(target.credential_reference)
        parts += ["UID=" + _odbc_value(username), "PWD=" + _odbc_value(password)]
    return ";".join(parts) + ";"


@contextmanager
def open_target_connection(target: TargetRecord) -> Iterator[pyodbc.Connection]:
    config = target.configuration
    connection = pyodbc.connect(
        target_connection_string(target),
        timeout=config.connection_timeout_seconds,
        autocommit=True,
    )
    try:
        connection.timeout = config.query_timeout_seconds
        yield connection
    finally:
        connection.close()


def resolve_credentials(reference: str) -> SqlCredentials:
    username, password = _credentials(reference)
    return SqlCredentials(username, password)
