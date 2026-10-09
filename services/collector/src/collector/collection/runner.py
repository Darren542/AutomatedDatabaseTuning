from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from collector.collection.index_operational import read_index_operational
from collector.collection.index_usage import read_index_usage
from collector.collection.metadata import read_metadata
from collector.collection.missing_indexes import read_missing_indexes
from collector.collection.policy import CollectionPolicy
from collector.collection.query_store import read_query_runtime
from collector.collection.source_state import read_source_state
from collector.collection.windowing import (
    metadata_is_due,
    resolve_effective_window,
    utc_now_naive,
)
from collector.repository.collection_batches import SqlCollectionBatchRepository
from collector.repository.collection_state import SqlTargetCollectionStateRepository
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
    skipped_components: int
    failed_components: int
    effective_window_start_utc: datetime
    effective_window_end_utc: datetime
    window_source: str

class CollectionRunner:
    def __init__(
        self,
        *,
        targets: SqlTargetRepository | None = None,
        batches: SqlCollectionBatchRepository | None = None,
        evidence: SqlEvidenceRepository | None = None,
        components: SqlComponentResultRepository | None = None,
        states: SqlTargetCollectionStateRepository | None = None,
        policy: CollectionPolicy | None = None,
    ):
        self._targets = targets or SqlTargetRepository()
        self._batches = batches or SqlCollectionBatchRepository()
        self._evidence = evidence or SqlEvidenceRepository()
        self._components = components or SqlComponentResultRepository()
        self._states = states or SqlTargetCollectionStateRepository()
        self._policy = policy or CollectionPolicy.load()

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

        target_state = self._states.get(batch.target_id)
        now_utc = utc_now_naive()

        if (
            batch.effective_window_start_utc is not None
            and batch.effective_window_end_utc is not None
            and batch.window_source is not None
        ):
            effective_start = batch.effective_window_start_utc
            effective_end = batch.effective_window_end_utc
            window_source = batch.window_source
        else:
            resolved = resolve_effective_window(
                requested_start_utc=batch.requested_window_start_utc,
                requested_end_utc=batch.requested_window_end_utc,
                previous_watermark_utc=(
                    target_state.last_query_runtime_watermark_utc
                    if target_state is not None
                    else None
                ),
                now_utc=now_utc,
                initial_lookback_minutes=self._policy.initial_lookback_minutes,
            )

            batch = self._batches.set_effective_window(
                batch_id,
                start_utc=resolved.start_utc,
                end_utc=resolved.end_utc,
                window_source=resolved.source,
            )

            effective_start = resolved.start_utc
            effective_end = resolved.end_utc
            window_source = resolved.source

        last_metadata_at = (
            target_state.last_metadata_collected_at_utc
            if target_state is not None
            else None
        )

        should_collect_metadata = metadata_is_due(
            last_metadata_collected_at_utc=last_metadata_at,
            now_utc=now_utc,
            refresh_minutes=self._policy.metadata_refresh_minutes,
            force_metadata=batch.force_metadata,
        )

        completed = 0
        skipped = 0
        failed = 0

        query_runtime_succeeded = False
        metadata_succeeded = False

        try:
            with open_target_connection(target) as connection:
                source_state = self._run_component(
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

                if source_state is None:
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
                        skipped_components=0,
                        failed_components=1,
                        effective_window_start_utc=effective_start,
                        effective_window_end_utc=effective_end,
                        window_source=window_source,
                    )

                completed += 1

                jobs = [
                    (
                        "QUERY_RUNTIME",
                        lambda: read_query_runtime(
                            connection,
                            requested_window_start_utc=effective_start,
                            requested_window_end_utc=effective_end,
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
                                source_state.sql_server_start_time_utc,
                            observed_at_utc=source_state.observed_at_utc,
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
                                source_state.sql_server_start_time_utc,
                            observed_at_utc=source_state.observed_at_utc,
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
                                source_state.sql_server_start_time_utc,
                            observed_at_utc=source_state.observed_at_utc,
                            rows=rows,
                        ),
                        len,
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
                        if name == "QUERY_RUNTIME":
                            query_runtime_succeeded = True

                if should_collect_metadata:
                    metadata = self._run_component(
                        batch_id=batch_id,
                        name="METADATA",
                        reader=lambda: read_metadata(connection),
                        writer=lambda value: self._evidence.save_metadata(
                            batch_id=batch_id,
                            target_id=batch.target_id,
                            observed_at_utc=source_state.observed_at_utc,
                            metadata=value,
                        ),
                        counter=lambda value: sum(
                            map(
                                len,
                                (
                                    value.tables,
                                    value.columns,
                                    value.indexes,
                                    value.index_columns,
                                    value.constraints,
                                ),
                            )
                        ),
                    )

                    if metadata is None:
                        failed += 1
                    else:
                        completed += 1
                        metadata_succeeded = True
                else:
                    self._components.skip(
                        batch_id,
                        "METADATA",
                        status_message=(
                            "Metadata refresh is not due yet. "
                            f"Cadence is {self._policy.metadata_refresh_minutes} minutes."
                        ),
                    )
                    skipped += 1

            if query_runtime_succeeded:
                self._states.advance_query_watermark(
                    target_id=batch.target_id,
                    watermark_utc=effective_end,
                    batch_id=batch_id,
                )

            if metadata_succeeded:
                self._states.mark_metadata_collected(
                    target_id=batch.target_id,
                    collected_at_utc=source_state.observed_at_utc,
                    batch_id=batch_id,
                )

        except Exception as error:
            logger.exception(
                "Collection batch %s failed outside an individual component",
                batch_id,
            )

            final = self._batches.transition(
                batch_id,
                CollectionBatchStatus.FAILED,
                completeness_percent=(
                    (completed + skipped) / len(COMPONENTS) * 100.0
                ),
                failure_reason=type(error).__name__,
            )

            return CollectionRunResult(
                batch_id=batch_id,
                final_status=final.status,
                completeness_percent=final.completeness_percent,
                completed_components=completed,
                skipped_components=skipped,
                failed_components=max(1, failed),
                effective_window_start_utc=effective_start,
                effective_window_end_utc=effective_end,
                window_source=window_source,
            )

        completeness = (
            (completed + skipped) / len(COMPONENTS) * 100.0
        )

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
            skipped_components=skipped,
            failed_components=failed,
            effective_window_start_utc=effective_start,
            effective_window_end_utc=effective_end,
            window_source=window_source,
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
            self._components.start(batch_id, name)

            logger.info("Starting collection component %s", name)
            value = reader()
            logger.info("Finished reading collection component %s", name)

            writer(value)
            logger.info("Finished persisting collection component %s", name)

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
            logger.exception("Collection component %s failed", name)

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
