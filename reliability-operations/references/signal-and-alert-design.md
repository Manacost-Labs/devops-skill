# Signals and alerts

Start with the user path: availability, successful task completion, latency and correctness. Then add service, host, queue and dependency signals only when they explain or predict user impact.

Minimum web-service signals: external availability, request rate, error rate, p95 latency, saturation/restarts, and release version. Alerts require a named response, owner, severity, grouping rule, and runbook. Prefer burn-rate or sustained user-impact alerts over one-off host spikes.

Metric labels must be bounded and low cardinality. Keep logs structured and redacted. Traces should sample proportionately and preserve correlation without leaking secrets.