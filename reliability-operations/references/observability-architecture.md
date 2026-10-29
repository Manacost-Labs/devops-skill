# Observability architecture and capacity

Start with a service journey and operational decisions: detect failure, locate cause, choose safe action, verify recovery. Inventory existing systems before adding another stack.

| Layer | Purpose | Acceptance evidence |
|---|---|---|
| Instrumentation/exporter | Emit bounded measurements | Known request appears with correct units/labels |
| Prometheus / metrics backend | Scrape/store/query time series | Target freshness, expected series and interval deltas |
| Alertmanager | Group/route/deduplicate alerts | Matching route and authorized receiver evidence |
| Grafana | Visualise/query | Correct datasource, tenant, time range and query semantics |
| Loki / log store | Search structured events | Timestamp, redaction and bounded searchable metadata |
| OTel Collector / trace backend | Receive/process/export signals | Pipeline active; accepted/refused/dropped/exported trend |

A local exporter proves neither remote ingestion nor alert delivery. External synthetic checks should run from the relevant user path/failure domain. Keep a way to detect failure of monitoring itself (independent heartbeat or other confirmed path); circular self-monitoring alone misses total outages.

## Design worksheet

Record owners, versions/distributions, endpoints by reference, auth/TLS, tenancy, permitted signals, retention/deletion, expected traffic/series/span/log volume, growth ceiling, failure budget and rollback. Estimate metric series from label combinations; estimate samples/second and storage with measured compression/replication overhead. Logs and traces need measured byte/ingest/query budgets. Do not invent a universal bytes-per-sample or retention recommendation.

Separate collection frequency from rule evaluation and notification delay. Specify acceptable detection/recovery times and account for each delay. Scope recording rules and dashboards to avoid expensive fleet-wide queries during an incident.

Choose single-node versus HA from failure requirements and capacity evidence. Two scrapers can double series unless the backend/query layer handles replicas correctly. Replication is not backup; retention is not recovery. Plan configuration recovery and telemetry storage recovery with their owners.

## Change and acceptance

Baseline ingestion latency, queue/drop/retry rates, query latency, cardinality, resource usage and alert coverage. Test with synthetic signals free of production data. Validate component config, canary one service, compare same-window before/after, and verify missing-data behavior. For overload, reduce the evidenced source of excess with owner approval rather than discard random telemetry.

Hosting files/services -> Linux/Docker/Kubernetes; storage/managed service APIs -> provider; workload instrumentation -> application owner; credential lifecycle -> secrets-access. Reliability owns the signal and acceptance contract across them.

Sources: [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/), [OTel pipelines](https://opentelemetry.io/docs/collector/configuration/).
