from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SourceState:
    observed_at_utc: datetime
    sql_server_start_time_utc: datetime | None
    database_id: int
    database_create_date_utc: datetime | None
    query_store_actual_state: str | None
    query_store_max_interval_id: int | None
    query_store_max_query_id: int | None
    query_store_max_plan_id: int | None


@dataclass(frozen=True)
class QueryRuntimeEvidence:
    runtime_stats_interval_id: int
    runtime_stats_id: int
    plan_id: int
    query_id: int
    query_text_id: int
    object_id: int | None
    query_hash: bytes | None
    query_plan_hash: bytes | None
    query_sql_text: str
    execution_type: int
    execution_type_desc: str | None
    interval_start_utc: datetime
    interval_end_utc: datetime
    first_execution_time_utc: datetime | None
    last_execution_time_utc: datetime | None
    execution_count: int
    avg_duration_microseconds: float | None
    avg_cpu_time_microseconds: float | None
    avg_logical_io_reads: float | None
    avg_logical_io_writes: float | None
    avg_physical_io_reads: float | None
    avg_row_count: float | None


@dataclass(frozen=True)
class IndexUsageObservation:
    object_id: int
    index_id: int
    schema_name: str
    table_name: str
    index_name: str | None
    user_seeks: int
    user_scans: int
    user_lookups: int
    user_updates: int
    last_user_seek_utc: datetime | None
    last_user_scan_utc: datetime | None
    last_user_lookup_utc: datetime | None
    last_user_update_utc: datetime | None


@dataclass(frozen=True)
class IndexOperationalObservation:
    object_id: int
    index_id: int
    partition_number: int
    schema_name: str
    table_name: str
    index_name: str | None
    leaf_insert_count: int
    leaf_delete_count: int
    leaf_update_count: int
    row_lock_count: int
    row_lock_wait_count: int
    row_lock_wait_ms: int
    page_lock_count: int
    page_lock_wait_count: int
    page_lock_wait_ms: int
    page_latch_wait_count: int
    page_latch_wait_ms: int


@dataclass(frozen=True)
class MissingIndexObservation:
    group_handle: int
    index_handle: int
    object_id: int
    schema_name: str
    table_name: str
    equality_columns: str | None
    inequality_columns: str | None
    included_columns: str | None
    user_seeks: int
    user_scans: int
    last_user_seek_utc: datetime | None
    last_user_scan_utc: datetime | None
    avg_total_user_cost: float
    avg_user_impact: float


@dataclass(frozen=True)
class TableMetadata:
    object_id: int
    schema_name: str
    table_name: str
    row_count: int
    reserved_size_mb: float
    used_size_mb: float
    data_size_mb: float


@dataclass(frozen=True)
class ColumnMetadata:
    object_id: int
    column_id: int
    column_name: str
    data_type: str
    max_length: int
    numeric_precision: int
    numeric_scale: int
    is_nullable: bool
    is_identity: bool
    is_computed: bool


@dataclass(frozen=True)
class IndexMetadata:
    object_id: int
    index_id: int
    index_name: str | None
    index_type: int
    index_type_desc: str
    is_unique: bool
    is_primary_key: bool
    is_unique_constraint: bool
    is_disabled: bool
    has_filter: bool
    filter_definition: str | None


@dataclass(frozen=True)
class IndexColumnMetadata:
    object_id: int
    index_id: int
    column_id: int
    key_ordinal: int
    index_column_id: int
    is_included_column: bool
    is_descending_key: bool


@dataclass(frozen=True)
class ConstraintMetadata:
    object_id: int
    constraint_object_id: int
    constraint_name: str
    constraint_type: str
    unique_index_id: int | None
    referenced_object_id: int | None
    is_disabled: bool | None


@dataclass(frozen=True)
class MetadataBundle:
    tables: list[TableMetadata]
    columns: list[ColumnMetadata]
    indexes: list[IndexMetadata]
    index_columns: list[IndexColumnMetadata]
    constraints: list[ConstraintMetadata]
