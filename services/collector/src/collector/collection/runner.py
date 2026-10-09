from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from collector.collection.index_operational import read_index_operational
from collector.collection.index_usage import read_index_usage
from collector.collection.metadata import read_metadata
from collector.collection.missing_indexes import read_missing_indexes
from collector.collection.query_store import read_query_runtime
from collector.collection.source_state import read_source_state
from collector.repository.collection_batches import SqlCollectionBatchRepository
from collector.repository.component_results import SqlComponentResultRepository
from collector.repository.evidence import SqlEvidenceRepository
from collector.repository.models import CollectionBatchStatus
from collector.repository.targets import SqlTargetRepository
from collector.target_connection import open_target_connection


logger = logging.getLogger(__name__)

COMPONENTS = (
    "SOURCE_STATE",
    "QUERY_RUNTIME",
    "INDEX_USAGE",
    "INDEX_OPERATIONAL",
    "MISSING_INDEX",
    "METADATA",
)


@dataclass(frozen=True)
class CollectionRunResult:
    batch_id: UUID
    final_status: CollectionBatchStatus
    completeness_percent: float
    completed_components: int
    failed_components: int


class CollectionRunner:
    def __init__(
        self,
        *,
        targets: SqlTargetRepository | None = None,
        batches: SqlCollectionBatchRepository | None = None,
        evidence: SqlEvidenceRepository | None = None,
        components: SqlComponentResultRepository | None = None,
    ):
        self._targets = targets or SqlTargetRepository()
        self._batches = batches or SqlCollectionBatchRepository()
        self._evidence = evidence or SqlEvidenceRepository()
        self._components = components or SqlComponentResultRepository()

    def collect(self, batch_id: UUID) -> CollectionRunResult:
        batch = self._batches.get(batch_id)

        if batch is None:
            raise KeyError("Collection batch not found.")

        if batch.status == CollectionBatchStatus.PENDING:
            batch = self._batches.transition(
                batch_id,
                CollectionBatchStatus.COLLECTING,
            )
        elif batch.status != CollectionBatchStatus.COLLECTING:
            raise ValueError(
                f"Collection cannot run from status {batch.status.value}."
            )

        target = self._targets.get(batch.target_id)

        if target is None:
            self._batches.transition(
                batch_id,
                CollectionBatchStatus.FAILED,
                failure_reason="Target no longer exists.",
            )
            raise KeyError("Target not found.")

        completed = 0
        failed = 0

        try:
            with open_target_connection(target) as connection:
                state = self._run_component(
                    batch_id=batch_id,
                    name="SOURCE_STATE",
                    reader=lambda: read_source_state(connection),
                    writer=lambda value: self._evidence.save_source_state(
                        batch_id=batch_id,
                        target_id=batch.target_id,
                        state=value,
                    ),
                    counter=lambda _: 1,
                )

                if state is None:
                    final = self._batches.transition(
                        batch_id,
                        CollectionBatchStatus.FAILED,
                        completeness_percent=0.0,
                        failure_reason="SOURCE_STATE collection failed.",
                    )

                    return CollectionRunResult(
                        batch_id=batch_id,
                        final_status=final.status,
                        completeness_percent=final.completeness_percent,
                        completed_components=0,
                        failed_components=1,
                    )

                completed += 1

                jobs = [
                    (
                        "QUERY_RUNTIME",
                        lambda: read_query_runtime(
                            connection,
                            requested_window_start_utc=
                                batch.requested_window_start_utc,
                            requested_window_end_utc=
                                batch.requested_window_end_utc,
                        ),
                        lambda rows: self._evidence.save_query_runtime(
                            batch_id=batch_id,
                            target_id=batch.target_id,
                            rows=rows,
                        ),
                        len,
                    ),
                    (
                        "INDEX_USAGE",
                        lambda: read_index_usage(connection),
                        lambda rows: self._evidence.save_index_usage(
                            batch_id=batch_id,
                            target_id=batch.target_id,
                            sql_server_start_time_utc=
                                state.sql_server_start_time_utc,
                            observed_at_utc=state.observed_at_utc,
                            rows=rows,
                        ),
                        len,
                    ),
                    (
                        "INDEX_OPERATIONAL",
                        lambda: read_index_operational(connection),
                        lambda rows: self._evidence.save_index_operational(
                            batch_id=batch_id,
                            target_id=batch.target_id,
                            sql_server_start_time_utc=
                                state.sql_server_start_time_utc,
                            observed_at_utc=state.observed_at_utc,
                            rows=rows,
                        ),
                        len,
                    ),
                    (
                        "MISSING_INDEX",
                        lambda: read_missing_indexes(connection),
                        lambda rows: self._evidence.save_missing_indexes(
                            batch_id=batch_id,
                            target_id=batch.target_id,
                            sql_server_start_time_utc=
                                state.sql_server_start_time_utc,
                            observed_at_utc=state.observed_at_utc,
                            rows=rows,
                        ),
                        len,
                    ),
                    (
                        "METADATA",
                        lambda: read_metadata(connection),
                        lambda metadata: self._evidence.save_metadata(
                            batch_id=batch_id,
                            target_id=batch.target_id,
                            observed_at_utc=state.observed_at_utc,
                            metadata=metadata,
                        ),
                        lambda metadata: sum(
                            map(
                                len,
                                (
                                    metadata.tables,
                                    metadata.columns,
                                    metadata.indexes,
                                    metadata.index_columns,
                                    metadata.constraints,
                                ),
                            )
                        ),
                    ),
                ]

                for name, reader, writer, counter in jobs:
                    value = self._run_component(
                        batch_id=batch_id,
                        name=name,
                        reader=reader,
                        writer=writer,
                        counter=counter,
                    )

                    if value is None:
                        failed += 1
                    else:
                        completed += 1

        except Exception as error:
            logger.exception(
                "Collection batch %s failed outside an individual component",
                batch_id,
            )

            final = self._batches.transition(
                batch_id,
                CollectionBatchStatus.FAILED,
                completeness_percent=(
                    completed / len(COMPONENTS) * 100.0
                ),
                failure_reason=type(error).__name__,
            )

            return CollectionRunResult(
                batch_id=batch_id,
                final_status=final.status,
                completeness_percent=final.completeness_percent,
                completed_components=completed,
                failed_components=max(1, failed),
            )

        completeness = completed / len(COMPONENTS) * 100.0

        if failed == 0:
            final = self._batches.transition(
                batch_id,
                CollectionBatchStatus.COMPLETED,
                completeness_percent=100.0,
            )
        else:
            final = self._batches.transition(
                batch_id,
                CollectionBatchStatus.PARTIAL,
                completeness_percent=completeness,
                failure_reason=f"{failed} collection component(s) failed.",
            )

        return CollectionRunResult(
            batch_id=batch_id,
            final_status=final.status,
            completeness_percent=final.completeness_percent,
            completed_components=completed,
            failed_components=failed,
        )

    def _run_component(
        self,
        *,
        batch_id: UUID,
        name: str,
        reader: Callable[[], Any],
        writer: Callable[[Any], Any],
        counter: Callable[[Any], int],
    ) -> Any | None:
        try:
            self._components.start(
                batch_id,
                name,
            )

            logger.info(
                "Starting collection component %s",
                name,
            )

            value = reader()

            logger.info(
                "Finished reading collection component %s",
                name,
            )

            writer(value)

            logger.info(
                "Finished persisting collection component %s",
                name,
            )

            rows_collected = counter(value)

            self._components.complete(
                batch_id,
                name,
                rows_collected,
            )

            logger.info(
                "Collection component %s completed successfully (%s rows)",
                name,
                rows_collected,
            )

            return value

        except Exception as error:
            logger.exception(
                "Collection component %s failed",
                name,
            )

            try:
                self._components.fail(
                    batch_id,
                    name,
                    error_code=type(error).__name__,
                    error_message=(
                        f"{name} collection failed. "
                        "See development logs for diagnosis."
                    ),
                )
            except Exception:
                logger.exception(
                    "Could not persist Failed status for component %s",
                    name,
                )

            return None
