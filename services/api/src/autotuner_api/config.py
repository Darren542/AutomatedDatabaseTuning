"""Explicit local configuration, independent of database credentials."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8080

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("AUTOTUNER_API_HOST must not be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("AUTOTUNER_API_PORT must be between 1 and 65535")

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        # Read only the explicit file (or .env in the launch directory).
        # Environment variables take precedence; process state is never mutated.
        values = {**dotenv_values(env_file or Path.cwd() / ".env"), **os.environ}
        host = values.get("AUTOTUNER_API_HOST", "127.0.0.1")
        try:
            port = int(values.get("AUTOTUNER_API_PORT", "8080"))
        except (TypeError, ValueError) as exc:
            raise ValueError("AUTOTUNER_API_PORT must be an integer") from exc
        return cls(host=host or "", port=port)
