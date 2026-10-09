from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class CollectionPolicy:
    initial_lookback_minutes: int = 60
    metadata_refresh_minutes: int = 60

    def __post_init__(self) -> None:
        if self.initial_lookback_minutes < 1:
            raise ValueError("initial_lookback_minutes must be at least 1.")
        if self.metadata_refresh_minutes < 1:
            raise ValueError("metadata_refresh_minutes must be at least 1.")

    @classmethod
    def load(cls) -> "CollectionPolicy":
        return cls(
            initial_lookback_minutes=_positive_int(
                "AUTOTUNER_INITIAL_LOOKBACK_MINUTES", 60
            ),
            metadata_refresh_minutes=_positive_int(
                "AUTOTUNER_METADATA_REFRESH_MINUTES", 60
            ),
        )

def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error
    if value < 1:
        raise ValueError(f"{name} must be at least 1.")
    return value
