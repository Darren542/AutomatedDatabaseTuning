```mermaid
flowchart LR
  %% =======================
  %% Production DB + Signals
  %% =======================
  subgraph PROD["Production Environment"]
    APP["Applications / Users\n(OLTP + Search + Reports)"] -->|T-SQL Queries| SQL["SQL Server Database"]
    SQL --> QS["Query Store\n(query text + plans + runtime stats)"]
    SQL --> DMVS["DMVs\n(missing indexes, index usage,\noperational + physical stats)"]
  end

  %% =======================
  %% Collector + Storage
  %% =======================
  subgraph TUNE["Autotuner Service"]
    COL["Telemetry Collector\n(scheduled job/service)\n- pulls QS + DMVs"] --> FS["Feature Store / Tuning DB\n(time-bucketed workload history)"]
    
    FS --> CG["Candidate Generator\n- missing-index hints\n- query pattern mining\n- dedupe + safety rules"]
    
    CG --> SCORE["Scoring + What-If Analyzer\n- read benefit estimate\n- write amplification penalty\n- storage/maintenance cost\n(optional: hypothetical index what-if)"]
    
    FS --> ML["ML Forecaster\n- predict hot queries/tables\n- proactive recommendations"]
    
    ML --> DEC["Decision Engine\n- rank actions\n- combine SCORE + ML\n- choose create/drop/keep"]
    SCORE --> DEC

    DEC --> SAFE["Safety & Guardrails\n- never drop PK/unique\n- trial window\n- monitor + rollback rules"]
    
    SAFE --> RECS["Recommendation Store\n- actions + rationale\n- predicted impact\n- audit trail"]
  end

  %% =======================
  %% Actuation + Reporting
  %% =======================
  subgraph OUT["Outputs"]
    RECS --> UI["Dashboard / Report UI\n- top recommendations\n- explanations\n- predicted vs actual"]
    RECS --> EXEC["Change Executor (Optional)\n- apply index changes\n- controlled rollout\n- canary/trial mode"]
  end

  EXEC -->|DDL changes| SQL
  SQL -->|post-change metrics| QS
  SQL -->|post-change stats| DMVS
  QS --> COL
  DMVS --> COL
  ```