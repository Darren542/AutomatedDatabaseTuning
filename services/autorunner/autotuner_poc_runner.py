
from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import pyodbc  # type: ignore
except ImportError:
    pyodbc = None  # type: ignore

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

try:
    from db_config import get_connection as external_get_connection  # type: ignore
except Exception:
    external_get_connection = None

APPLIED_INDEX_LOG = "applied_indexes.json"


def print_header(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def prompt_yes_no(message: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{message} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def format_query_preview(text: str, width: int = 140) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[: width - 3] + "..." if len(text) > width else text


def sql_string_literal(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def sql_datetime_literal(dt: datetime) -> str:
    return "CAST('" + dt.strftime("%Y-%m-%d %H:%M:%S.%f") + "' AS DATETIME2)"


def split_sql_batches(sql_text: str) -> list[str]:
    parts = re.split(r"(?im)^[ \t]*GO[ \t]*;?[ \t]*$", sql_text)
    return [p.strip() for p in parts if p.strip()]


def apply_declaration_overrides(sql_text: str, overrides: dict[str, str]) -> str:
    result = sql_text
    for var_name, sql_literal in overrides.items():
        pattern = rf"(DECLARE\s+@{re.escape(var_name)}\s+[^=]+=\s*)(.*?)(\s*;)"

        def _repl(match: re.Match[str]) -> str:
            return f"{match.group(1)}{sql_literal}{match.group(3)}"

        result = re.sub(pattern, _repl, result, flags=re.IGNORECASE | re.DOTALL)
    return result


def rows_to_dicts(cursor: Any, rows: list[Any]) -> list[dict[str, Any]]:
    if not cursor.description:
        return []
    cols = [c[0] for c in cursor.description]
    return [{cols[i]: row[i] for i in range(len(cols))} for row in rows]


def execute_sql_file(conn: Any, path: Path, overrides: dict[str, str] | None = None) -> list[list[dict[str, Any]]]:
    sql_text = path.read_text(encoding="utf-8")
    if overrides:
        sql_text = apply_declaration_overrides(sql_text, overrides)

    result_sets: list[list[dict[str, Any]]] = []
    cur = conn.cursor()

    for batch in split_sql_batches(sql_text):
        cur.execute(batch)
        while True:
            if cur.description:
                rows = cur.fetchall()
                result_sets.append(rows_to_dicts(cur, rows))
            if not cur.nextset():
                break

    try:
        conn.commit()
    except Exception:
        pass
    return result_sets


def execute_sql_text(conn: Any, sql_text: str) -> None:
    cur = conn.cursor()
    cur.execute(sql_text)
    try:
        conn.commit()
    except Exception:
        pass


def clear_query_store(conn: Any) -> None:
    print("\nClearing Query Store ...")
    execute_sql_text(conn, "ALTER DATABASE CURRENT SET QUERY_STORE CLEAR ALL;")
    time.sleep(1.5)


def fallback_connection_string(args: argparse.Namespace) -> str:
    host = args.host or os.getenv("WWI_SQL_SERVER", "localhost")
    database = args.database or os.getenv("WWI_SQL_DATABASE", "WideWorldImporters")
    driver = args.driver or os.getenv("WWI_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    trusted = os.getenv("WWI_SQL_TRUSTED_CONNECTION", "yes")
    trust_cert = os.getenv("WWI_SQL_TRUST_SERVER_CERTIFICATE", "yes")
    username = os.getenv("WWI_SQL_USERNAME")
    password = os.getenv("WWI_SQL_PASSWORD")

    if username and password:
        return (
            f"DRIVER={{{driver}}};SERVER={host};DATABASE={database};"
            f"UID={username};PWD={password};TrustServerCertificate={trust_cert};"
        )

    return (
        f"DRIVER={{{driver}}};SERVER={host};DATABASE={database};"
        f"Trusted_Connection={trusted};TrustServerCertificate={trust_cert};"
    )


def get_connection(args: argparse.Namespace):
    if pyodbc is None:
        raise RuntimeError("pyodbc is not installed. Run: pip install pyodbc python-dotenv")

    if args.connection_string:
        conn = pyodbc.connect(args.connection_string)
        try:
            conn.autocommit = True
        except Exception:
            pass
        return conn

    if external_get_connection is not None:
        conn = external_get_connection(args.database)
        try:
            conn.autocommit = True
        except Exception:
            pass
        return conn

    conn = pyodbc.connect(fallback_connection_string(args))
    try:
        conn.autocommit = True
    except Exception:
        pass
    return conn


def find_repo_root(start: Path) -> Path:
    for candidate in [start] + list(start.parents):
        if (candidate / "sql").exists():
            return candidate
    raise RuntimeError("Could not find repo root containing a 'sql' folder. Use --repo-root.")


def resolve_sql_paths(repo_root: Path, db_key: str) -> dict[str, Path]:
    current_db_root = repo_root / "sql" / "demo" / db_key
    future_db_root = repo_root / "sql" / "databases" / db_key
    future_shared_root = repo_root / "sql" / "shared"

    if current_db_root.exists():
        db_root = current_db_root
        shared_setup = current_db_root / "setup"
    elif future_db_root.exists():
        db_root = future_db_root
        shared_setup = future_shared_root / "setup" if (future_shared_root / "setup").exists() else future_db_root / "setup"
    else:
        raise RuntimeError(
            f"Could not resolve SQL folders for db_key='{db_key}'. "
            f"Tried '{current_db_root}' and '{future_db_root}'."
        )

    workloads = db_root / "workloads"
    shared = shared_setup

    required = {
        "read_proc": workloads / "wwi_read_heavy.sql",
        "write_proc": workloads / "wwi_write_heavy.sql",
        "run_workload": workloads / "run_workload.sql",
        "baseline_capture": shared / "poc_baseline_capture.sql",
        "compare_runs": shared / "poc_compare_runs.sql",
        "generate_candidates": shared / "poc_generate_index_candidates.sql",
    }

    optional = {
        "prepare_demo": shared / "poc_prepare_demo_baseline.sql",
        "cleanup_demo": shared / "poc_cleanup_restore_demo.sql",
    }

    missing = [str(p) for p in required.values() if not p.exists()]
    if missing:
        raise RuntimeError("Missing required SQL files:\n- " + "\n- ".join(missing))

    required.update(optional)
    return required


def initialize_workload_scripts(conn: Any, paths: dict[str, Path]) -> None:
    execute_sql_file(conn, paths["read_proc"])
    execute_sql_file(conn, paths["write_proc"])


def run_workload_sql(
    conn: Any,
    run_workload_path: Path,
    workload: str,
    read_iterations: int,
    write_iterations: int,
    orders_per_iteration: int,
    rollback_changes: bool,
) -> tuple[datetime, datetime]:
    overrides = {
        "WorkloadName": sql_string_literal(workload),
        "ReadIterations": str(read_iterations),
        "WriteIterations": str(write_iterations),
        "OrdersPerIteration": str(orders_per_iteration),
        "RollbackChanges": "1" if rollback_changes else "0",
    }
    start_utc = datetime.now(timezone.utc)
    execute_sql_file(conn, run_workload_path, overrides)
    end_utc = datetime.now(timezone.utc)
    return start_utc, end_utc


def capture_baseline_sql(
    conn: Any,
    baseline_capture_path: Path,
    run_label: str,
    workload_type: str,
    notes: str,
    lookback_minutes: int,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, Any]:
    overrides = {
        "RunLabel": sql_string_literal(run_label),
        "WorkloadType": sql_string_literal(workload_type),
        "Notes": sql_string_literal(notes),
        "LookbackMinutes": str(lookback_minutes),
    }

    if window_start is not None and window_end is not None:
        padded_start = window_start - timedelta(seconds=2)
        padded_end = window_end + timedelta(seconds=2)
        overrides["WindowStart"] = sql_datetime_literal(padded_start.replace(tzinfo=None))
        overrides["WindowEnd"] = sql_datetime_literal(padded_end.replace(tzinfo=None))

    result_sets = execute_sql_file(conn, baseline_capture_path, overrides)

    run_row = None
    top_queries = []
    missing_indexes = []
    index_usage = []

    for rs in result_sets:
        if not rs:
            continue
        first = rs[0]
        if "RunID" in first and "RunLabel" in first:
            run_row = rs[0]
        elif "QueryId" in first and ("QueryPreview" in first or "QuerySqlText" in first):
            top_queries = rs
        elif "SchemaName" in first and "ImprovementMeasure" in first and "EqualityColumns" in first:
            missing_indexes = rs
        elif "IndexName" in first and "IndexTypeDesc" in first:
            index_usage = rs

    if run_row is None:
        raise RuntimeError("Could not find RunID in baseline capture results.")

    return {
        "run": run_row,
        "top_queries": top_queries,
        "missing_indexes": missing_indexes,
        "index_usage": index_usage,
    }


def fetch_candidate_sql(conn: Any, generate_candidates_path: Path, run_id: int) -> list[dict[str, Any]]:
    result_sets = execute_sql_file(conn, generate_candidates_path, {"RunID": str(run_id)})
    for rs in result_sets:
        if rs and "CandidateNumber" in rs[0] and "SuggestedSql" in rs[0]:
            return rs
    return []


def choose_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    while True:
        raw = input("\nEnter candidate number to apply (0 to skip): ").strip()
        if raw == "0":
            return None
        if raw.isdigit():
            selected_num = int(raw)
            for row in candidates:
                if int(row.get("CandidateNumber")) == selected_num:
                    return row
        print("Invalid selection. Try again.")


def print_top_queries(queries: list[dict[str, Any]], limit: int = 10) -> None:
    print_header("Top workload queries")
    if not queries:
        print("No query rows returned.")
        return
    for idx, q in enumerate(queries[:limit], start=1):
        print(
            f"{idx:>2}. total_duration_ms={q.get('TotalDurationMs')}, "
            f"avg_duration_ms={q.get('AvgDurationMs')}, avg_cpu_ms={q.get('AvgCpuMs')}, "
            f"avg_logical_reads={q.get('AvgLogicalIoReads')}"
        )
        print(f"    {format_query_preview(str(q.get('QueryPreview') or q.get('QuerySqlText') or ''))}")


def print_missing_indexes(missing_indexes: list[dict[str, Any]], limit: int = 10) -> None:
    print_header("Missing index DMV rows")
    if not missing_indexes:
        print("No missing-index rows returned.")
        return
    for idx, row in enumerate(missing_indexes[:limit], start=1):
        print(
            f"{idx:>2}. [{row.get('SchemaName')}].[{row.get('TableName')}] "
            f"improvement={row.get('ImprovementMeasure')}"
        )
        print(f"    equality   : {row.get('EqualityColumns')}")
        print(f"    inequality : {row.get('InequalityColumns')}")
        print(f"    includes   : {row.get('IncludedColumns')}")


def print_candidate_sql(candidates: list[dict[str, Any]], limit: int = 20) -> None:
    print_header("Suggested tuning actions")
    if not candidates:
        print("No generated candidates returned.")
        return
    for row in candidates[:limit]:
        cnum = row.get("CandidateNumber")
        schema = row.get("SchemaName")
        table = row.get("TableName")
        improvement = row.get("ImprovementMeasure")
        print(f"{cnum:>2}. [{schema}].[{table}] improvement={improvement}")
        print(f"    equality   : {row.get('EqualityColumns')}")
        print(f"    inequality : {row.get('InequalityColumns')}")
        print(f"    includes   : {row.get('IncludedColumns')}")
        print(textwrap_indent(str(row.get("SuggestedSql", "")), prefix="    "))


def textwrap_indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def fetch_existing_indexes_for_table(conn: Any, schema_name: str, table_name: str) -> list[dict[str, Any]]:
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
            s.name AS SchemaName,
            t.name AS TableName,
            i.name AS IndexName,
            i.type_desc AS IndexTypeDesc,
            i.is_disabled,
            ic.key_ordinal,
            ic.is_included_column,
            c.name AS ColumnName
        FROM sys.indexes AS i
        INNER JOIN sys.tables AS t ON t.object_id = i.object_id
        INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
        LEFT JOIN sys.index_columns AS ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        LEFT JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE s.name = ?
          AND t.name = ?
        ORDER BY i.name, ic.is_included_column, ic.key_ordinal, c.column_id
        """,
        schema_name,
        table_name,
    ).fetchall()
    cols = [c[0] for c in cur.description]
    return [{cols[i]: row[i] for i in range(len(cols))} for row in rows]


def print_existing_indexes(index_rows: list[dict[str, Any]]) -> None:
    print_header("Existing indexes on selected table")
    if not index_rows:
        print("No indexes found.")
        return
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in index_rows:
        grouped[str(row["IndexName"])].append(row)

    for index_name, rows in grouped.items():
        index_type = rows[0]["IndexTypeDesc"]
        is_disabled = rows[0]["is_disabled"]
        key_cols = [r["ColumnName"] for r in rows if r.get("ColumnName") and not r["is_included_column"]]
        include_cols = [r["ColumnName"] for r in rows if r.get("ColumnName") and r["is_included_column"]]
        print(f"- {index_name} ({index_type}) disabled={is_disabled}")
        print(f"    keys    : {', '.join(key_cols) if key_cols else '(none)'}")
        print(f"    include : {', '.join(include_cols) if include_cols else '(none)'}")


def extract_action_parts(candidate: dict[str, Any]) -> dict[str, Any]:
    suggested_sql = str(candidate.get("SuggestedSql") or "")
    schema_name = str(candidate.get("SchemaName") or "")
    table_name = str(candidate.get("TableName") or "")
    m = re.search(
        r"CREATE\s+NONCLUSTERED\s+INDEX\s+(?:\[([^\]]+)\]|([A-Za-z0-9_]+))\s+ON\s+\[([^\]]+)\]\.\[([^\]]+)\]",
        suggested_sql,
        flags=re.IGNORECASE,
    )
    if m:
        index_name = m.group(1) or m.group(2)
        schema_name = m.group(3)
        table_name = m.group(4)
    else:
        index_name = "UNKNOWN_INDEX"
    return {
        "action_type": "create_missing_index",
        "index_name": index_name,
        "schema_name": schema_name,
        "table_name": table_name,
        "apply_sql": suggested_sql,
        "cleanup_sql": f"DROP INDEX [{index_name}] ON [{schema_name}].[{table_name}];",
    }


def apply_action(conn: Any, action: dict[str, Any]) -> None:
    execute_sql_text(conn, action["apply_sql"])


def cleanup_action(conn: Any, action: dict[str, Any]) -> None:
    execute_sql_text(conn, action["cleanup_sql"])


def load_applied_indexes(log_dir: Path) -> list[dict[str, Any]]:
    path = log_dir / APPLIED_INDEX_LOG
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_applied_indexes(log_dir: Path, indexes: list[dict[str, Any]]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / APPLIED_INDEX_LOG
    path.write_text(json.dumps(indexes, indent=2), encoding="utf-8")


def compare_runs_from_sql(conn: Any, compare_runs_path: Path, baseline_run_id: int, compare_run_id: int) -> list[list[dict[str, Any]]]:
    overrides = {
        "BaselineRunID": str(baseline_run_id),
        "CompareRunID": str(compare_run_id),
        "BaselineRunID2": str(baseline_run_id),
        "CompareRunID2": str(compare_run_id),
        "BaselineRunID3": str(baseline_run_id),
        "CompareRunID3": str(compare_run_id),
        "BaselineRunID4": str(baseline_run_id),
        "CompareRunID4": str(compare_run_id),
    }
    return execute_sql_file(conn, compare_runs_path, overrides)


def print_compare_results(compare_result_sets: list[list[dict[str, Any]]]) -> None:
    print_header("Before vs after summary")
    totals_row = None
    tagged_rows = None
    top_query_rows = None

    for rs in compare_result_sets:
        if not rs:
            continue
        first = rs[0]
        if "WorkloadTag" in first and "BaselineTotalDurationMs" in first:
            tagged_rows = rs
        elif "QueryKey" in first and "QueryPreview" in first:
            top_query_rows = rs
        elif "BaselineTotalDurationMs" in first and "CompareTotalDurationMs" in first and "ExecutionCountPctChange" in first:
            totals_row = first

    if totals_row:
        print(
            f"Total duration ms   : {totals_row.get('BaselineTotalDurationMs')} -> {totals_row.get('CompareTotalDurationMs')} "
            f"({totals_row.get('TotalDurationPctChange')})"
        )
        print(
            f"Total CPU ms        : {totals_row.get('BaselineTotalCpuMs')} -> {totals_row.get('CompareTotalCpuMs')} "
            f"({totals_row.get('TotalCpuPctChange')})"
        )
        print(
            f"Total logical reads : {totals_row.get('BaselineTotalLogicalIoReads')} -> {totals_row.get('CompareTotalLogicalIoReads')} "
            f"({totals_row.get('TotalLogicalReadsPctChange')})"
        )
        print(
            f"Execution count     : {totals_row.get('BaselineExecutionCount')} -> {totals_row.get('CompareExecutionCount')} "
            f"({totals_row.get('ExecutionCountPctChange')})"
        )

    if tagged_rows:
        print("\nTagged workload groups:")
        for row in tagged_rows:
            print(
                f"- {row.get('WorkloadTag')}: "
                f"duration {row.get('BaselineTotalDurationMs')} -> {row.get('CompareTotalDurationMs')} "
                f"({row.get('TotalDurationPctChange')}), "
                f"reads {row.get('BaselineTotalLogicalIoReads')} -> {row.get('CompareTotalLogicalIoReads')} "
                f"({row.get('TotalLogicalReadsPctChange')}), "
                f"execs {row.get('BaselineExecutionCount')} -> {row.get('CompareExecutionCount')}"
            )

    if top_query_rows:
        print("\nTop 10 important queries (by total duration):")
        for idx, row in enumerate(top_query_rows[:10], start=1):
            print(
                f"{idx:>2}. duration {row.get('BaselineTotalDurationMs')} -> {row.get('CompareTotalDurationMs')} "
                f"({row.get('TotalDurationPctChange')}), "
                f"reads {row.get('BaselineTotalLogicalIoReads')} -> {row.get('CompareTotalLogicalIoReads')} "
                f"({row.get('TotalLogicalReadsPctChange')}), "
                f"execs {row.get('BaselineExecutionCount')} -> {row.get('CompareExecutionCount')}"
            )
            print(f"    {format_query_preview(str(row.get('QueryPreview') or ''))}")


def write_report(log_dir: Path, baseline_run: dict[str, Any], compare_run: dict[str, Any] | None, action: dict[str, Any] | None) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"autotuner_poc_report_{ts}.md"
    lines = [
        "# SQL Server Autotuner POC Report",
        "",
        f"- Baseline RunID: {baseline_run.get('RunID')} ({baseline_run.get('RunLabel')})",
    ]
    if compare_run:
        lines.append(f"- Compare RunID: {compare_run.get('RunID')} ({compare_run.get('RunLabel')})")
    if action:
        lines.append(f"- Applied action: `{action['index_name']}` on `{action['schema_name']}.{action['table_name']}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive SQL Server autotuner POC runner using repo SQL scripts.")
    parser.add_argument("--connection-string", help="Full ODBC connection string.")
    parser.add_argument("--host", help="Fallback SQL Server host if db_config.py is not available.")
    parser.add_argument("--database", default="WideWorldImporters", help="Target database.")
    parser.add_argument("--driver", help="Fallback ODBC driver.")
    parser.add_argument("--repo-root", help="Repository root. Auto-detected if omitted.")
    parser.add_argument("--db-key", default="wwi", help="Database script folder key, e.g. wwi.")
    parser.add_argument("--read-iterations", type=int, default=25)
    parser.add_argument("--write-iterations", type=int, default=10)
    parser.add_argument("--orders-per-iteration", type=int, default=25)
    parser.add_argument("--lookback-minutes", type=int, default=10)
    parser.add_argument("--log-dir", default="reports/out")
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    print_header("SQL Server Autotuner POC Runner")

    this_file = Path(__file__).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(this_file.parent)
    log_dir = (repo_root / args.log_dir).resolve()

    print(f"Repo root: {repo_root}")

    try:
        sql_paths = resolve_sql_paths(repo_root, args.db_key)
    except Exception as exc:
        print(f"SQL path resolution failed: {exc}")
        return 1

    try:
        conn = get_connection(args)
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return 1

    try:
        if sql_paths.get("prepare_demo") and sql_paths["prepare_demo"].exists():
            if prompt_yes_no("Run demo baseline prep script first?", default=False):
                execute_sql_file(conn, sql_paths["prepare_demo"])
                print("Demo baseline prep completed.")

        print("\nInitializing workload procedures from SQL files...")
        initialize_workload_scripts(conn, sql_paths)
        print("Workload SQL loaded.")

        workload = input("Choose workload to run [read/write/mixed] (default read): ").strip().lower() or "read"

        baseline_window_start = None
        baseline_window_end = None

        if prompt_yes_no("Run the baseline workload now?", default=True):
            print("\nRunning workload via run_workload.sql ...")
            baseline_window_start, baseline_window_end = run_workload_sql(
                conn,
                sql_paths["run_workload"],
                workload,
                args.read_iterations,
                args.write_iterations,
                args.orders_per_iteration,
                rollback_changes=True,
            )
            print("Baseline workload completed.")

        baseline_label = input("Baseline run label (default: Baseline - Python POC): ").strip() or "Baseline - Python POC"
        baseline_notes = input("Baseline notes (optional): ").strip() or "Captured by Python POC runner"
        baseline_capture = capture_baseline_sql(
            conn,
            sql_paths["baseline_capture"],
            run_label=baseline_label,
            workload_type=workload,
            notes=baseline_notes,
            lookback_minutes=args.lookback_minutes,
            window_start=baseline_window_start,
            window_end=baseline_window_end,
        )
        baseline_run = baseline_capture["run"]
        baseline_run_id = int(baseline_run["RunID"])
        print(f"\nCaptured baseline RunID={baseline_run_id}")

        print_top_queries(baseline_capture["top_queries"])
        print_missing_indexes(baseline_capture["missing_indexes"])

        candidate_rows = fetch_candidate_sql(conn, sql_paths["generate_candidates"], baseline_run_id)
        print_candidate_sql(candidate_rows)

        chosen = choose_candidate(candidate_rows)
        action = None

        if chosen:
            schema_name = str(chosen.get("SchemaName"))
            table_name = str(chosen.get("TableName"))

            existing_indexes = fetch_existing_indexes_for_table(conn, schema_name, table_name)
            print_existing_indexes(existing_indexes)

            print_header("Selected tuning action")
            print(str(chosen.get("SuggestedSql")))

            if prompt_yes_no("Apply this tuning action now?", default=True):
                # CRITICAL: isolate baseline and compare runs.
                clear_query_store(conn)

                action = extract_action_parts(chosen)
                apply_action(conn, action)
                print(f"Applied action: {action['index_name']}")

                applied = load_applied_indexes(log_dir)
                applied.append(action)
                save_applied_indexes(log_dir, applied)

                compare_window_start = None
                compare_window_end = None

                if prompt_yes_no("Re-run the workload after applying the action?", default=True):
                    print("\nRunning post-change workload via run_workload.sql ...")
                    compare_window_start, compare_window_end = run_workload_sql(
                        conn,
                        sql_paths["run_workload"],
                        workload,
                        args.read_iterations,
                        args.write_iterations,
                        args.orders_per_iteration,
                        rollback_changes=True,
                    )
                    print("Post-change workload completed.")

                compare_label = input("Post-change run label (default: Post-change - Python POC): ").strip() or "Post-change - Python POC"
                compare_notes = input("Post-change notes (optional): ").strip() or f"After applying {action['index_name']}"
                compare_capture = capture_baseline_sql(
                    conn,
                    sql_paths["baseline_capture"],
                    run_label=compare_label,
                    workload_type=workload,
                    notes=compare_notes,
                    lookback_minutes=args.lookback_minutes,
                    window_start=compare_window_start,
                    window_end=compare_window_end,
                )
                compare_run = compare_capture["run"]
                compare_run_id = int(compare_run["RunID"])
                print(f"Captured comparison RunID={compare_run_id}")

                compare_result_sets = compare_runs_from_sql(conn, sql_paths["compare_runs"], baseline_run_id, compare_run_id)
                print_compare_results(compare_result_sets)

                report_path = write_report(log_dir, baseline_run, compare_run, action)
                print(f"\nSaved report: {report_path}")

                if prompt_yes_no("Undo the applied tuning action now?", default=False):
                    cleanup_action(conn, action)
                    print(f"Undid action for: {action['index_name']}")
            else:
                print("Action skipped.")
        else:
            print("No action selected.")

        if sql_paths.get("cleanup_demo") and sql_paths["cleanup_demo"].exists():
            if prompt_yes_no("Run demo cleanup/restore script now?", default=False):
                execute_sql_file(conn, sql_paths["cleanup_demo"])
                print("Demo cleanup/restore completed.")

        print("\nDone.")
        return 0

    except Exception as exc:
        print(f"\nError: {exc}")
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
