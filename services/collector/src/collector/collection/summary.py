from __future__ import annotations
from uuid import UUID

from collector.repository.collection_batches import SqlCollectionBatchRepository
from collector.repository.collection_state import SqlTargetCollectionStateRepository
from collector.repository.component_results import SqlComponentResultRepository
from collector.repository.summary import SqlCollectionSummaryRepository

class CollectionSummaryService:
    def __init__(
        self,
        *,
        batches: SqlCollectionBatchRepository | None = None,
        components: SqlComponentResultRepository | None = None,
        states: SqlTargetCollectionStateRepository | None = None,
        summaries: SqlCollectionSummaryRepository | None = None,
    ):
        self._batches = batches or SqlCollectionBatchRepository()
        self._components = components or SqlComponentResultRepository()
        self._states = states or SqlTargetCollectionStateRepository()
        self._summaries = summaries or SqlCollectionSummaryRepository()

    def get(self, batch_id: UUID) -> dict[str, object]:
        batch = self._batches.get(batch_id)
        if batch is None:
            raise KeyError("Collection batch not found.")

        components = self._components.list(batch_id)
        statuses = {
            str(item["component_name"]): str(item["status"])
            for item in components
        }

        target_state = self._states.get(batch.target_id)

        return {
            "batch": batch,
            "source_state": self._summaries.source_state(batch_id),
            "component_statuses": statuses,
            "evidence": self._summaries.evidence_counts(batch_id),
            "query_runtime": self._summaries.query_runtime_totals(batch_id),
            "metadata_source_batch_id": (
                target_state.last_metadata_batch_id
                if target_state is not None
                else None
            ),
            "target_query_watermark_utc": (
                target_state.last_query_runtime_watermark_utc
                if target_state is not None
                else None
            ),
        }
