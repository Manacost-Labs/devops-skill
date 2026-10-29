# Logs, traces and OpenTelemetry pipelines

Define permitted fields and retention before collection. Prefer structured timestamps, severity, service/environment and bounded event codes. Avoid request bodies, auth headers, cookies, SQL values, personal identifiers and unrestricted baggage. Redact/drop at source or earliest trusted processor before persistent queues/export; query-time hiding does not remove stored secrets.

## Logs / Loki

Use stable low-cardinality index labels such as service/environment with an explicit volume budget. Keep request/trace IDs and other unbounded data out of indexed labels; use approved structured metadata or content when supported, still subject to privacy/retention. Structured metadata does not make sensitive data safe. Validate ingestion timestamp, multiline parsing, clock skew, size limits, dropped entries, tenant identity and query scope. Do not enable unrestricted debug logging or search the whole fleet by default.

## Traces

Propagate approved correlation context across the actual path. Head sampling decides early and may miss rare errors; tail sampling requires buffering, memory, complete routing and a decision delay. Biased samples cannot establish error ratios for the full request population. Validate root/child continuity and sampling/drop rates before concluding a dependency is absent. Never put secrets into baggage, trace attributes or links.

## Collector diagnosis/change

Confirm exact binary distribution/version and included components. A component existing in contrib does not mean it is shipped in core. Defining receivers/processors/exporters without enabling them in the service pipeline does not collect data.

Map each signal pipeline, auth/TLS and trust boundary. Inspect receiver accepted/refused, processor drops, export failures, queue utilisation/retries and backend arrival in the same interval. Names/availability of internal metrics vary by release. Missing telemetry can arise at any hop; a running Collector does not prove export.

Validate with the actual binary's supported validation command (for distributions supporting it, `otelcol validate --config=<candidate>`). Check component availability, environment expansion by reference and endpoint exposure. Stage a synthetic trace/log/metric through the whole pipeline, confirm redaction before queue/storage, correct tenant/query visibility and bounded resource impact. Test outage/backpressure/restart behavior and rollback; queues may drop when limits are reached. Do not increase buffers blindly until the host OOMs.

Sources: [OTel config](https://opentelemetry.io/docs/collector/configuration/), [sensitive data](https://opentelemetry.io/docs/security/handling-sensitive-data/), [Loki cardinality](https://grafana.com/docs/loki/latest/get-started/labels/cardinality/), [trace sampling](https://opentelemetry.io/docs/concepts/sampling/).
