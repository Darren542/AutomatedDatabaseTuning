"""Target metadata and transient credentials; no persistence or HTTP dependencies."""

from dataclasses import dataclass, field
from enum import Enum


class TargetConfigurationError(ValueError):
    """Safe configuration error: messages never contain submitted values."""


class AuthenticationMode(str, Enum):
    WINDOWS = "windows"
    SQL = "sql"


def _required_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise TargetConfigurationError(f"{name} is required.")
    if any(ord(char) < 32 for char in value):
        raise TargetConfigurationError(f"{name} contains unsupported control characters.")


@dataclass(frozen=True)
class TargetConfiguration:
    name: str
    server: str
    database: str
    authentication: AuthenticationMode = AuthenticationMode.WINDOWS
    driver: str = "ODBC Driver 18 for SQL Server"
    encrypt: bool = True
    trust_server_certificate: bool = False
    connection_timeout_seconds: int = 5
    query_timeout_seconds: int = 5

    def __post_init__(self) -> None:
        for name in ("name", "server", "database", "driver"):
            _required_text(getattr(self, name), name)
        if self.driver not in ("ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"):
            raise TargetConfigurationError("Select Microsoft ODBC Driver 17 or 18 for SQL Server.")
        try:
            mode = AuthenticationMode(self.authentication)
        except (ValueError, TypeError):
            raise TargetConfigurationError("Authentication must be windows or sql.") from None
        object.__setattr__(self, "authentication", mode)
        for name in ("encrypt", "trust_server_certificate"):
            if type(getattr(self, name)) is not bool:
                raise TargetConfigurationError(f"{name} must be a boolean.")
        for name in ("connection_timeout_seconds", "query_timeout_seconds"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 60:
                raise TargetConfigurationError(f"{name} must be an integer from 1 to 60.")


@dataclass(frozen=True)
class SqlCredentials:
    # Transient only. Never persist/serialize this object or include it in API DTOs.
    username: str = field(repr=False)
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        _required_text(self.username, "username")
        # Password whitespace is significant; do not strip or normalize it.
        if not isinstance(self.password, str) or not self.password:
            raise TargetConfigurationError("password is required.")
        if "\x00" in self.password:
            raise TargetConfigurationError("password contains an unsupported null character.")


def validate_authentication(target: TargetConfiguration, credentials: SqlCredentials | None) -> None:
    if target.authentication == AuthenticationMode.SQL:
        if not isinstance(credentials, SqlCredentials):
            raise TargetConfigurationError("SQL authentication requires username and password.")
    elif credentials is not None:
        raise TargetConfigurationError("Windows authentication must not include SQL credentials.")
