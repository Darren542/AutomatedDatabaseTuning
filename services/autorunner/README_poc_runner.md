# Project-structure SQL POC runner

This version uses your repo SQL files directly.

It supports both:

## Current layout
```text
sql/
  demo/
    wwi/
      setup/
        poc_baseline_capture.sql
        poc_compare_runs.sql
        poc_generate_index_candidates.sql
      workloads/
        run_workload.sql
        wwi_read_heavy.sql
        wwi_write_heavy.sql
```

## Recommended future layout
```text
sql/
  shared/
    setup/
      poc_baseline_capture.sql
      poc_compare_runs.sql
      poc_generate_index_candidates.sql
  databases/
    wwi/
      setup/
      workloads/
        run_workload.sql
        wwi_read_heavy.sql
        wwi_write_heavy.sql
```

## What it does
- loads the workload procedures from the SQL files in `workloads/`
- runs `run_workload.sql`
- runs `poc_baseline_capture.sql`
- runs `poc_generate_index_candidates.sql`
- optionally creates one candidate index
- reruns workload
- reruns baseline capture
- runs `poc_compare_runs.sql`
- optionally drops the created index
