# System Diagram (POC)

```mermaid
flowchart LR
  APP[Apps/Users] --> SQL[SQL Server]
  SQL --> QS[Query Store]
  SQL --> DMVS[DMVs]

  QS --> COL[Collector]
  DMVS --> COL

  COL --> FS[Feature Store Tables]

  FS --> REC[Recommender
(candidates + scoring)]
  REC --> OUT[Recommended Index SQL + Report]

  OUT -->|manual apply| SQL
```

## Explanation
- **Collector** pulls Query Store + DMV snapshots for a time window and stores them in simple feature tables.
- **Recommender** uses missing-index hints + observed top-cost queries to score candidate indexes.
- For the POC, applying indexes is **manual** to keep changes safe and transparent.
