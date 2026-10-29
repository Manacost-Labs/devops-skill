# Prometheus and Alertmanager operations

Confirm installed versions, configuration owner, target discovery, scrape/evaluation intervals and applicable query tenant. Work locally/offline first; configs may contain credentials.

## Metrics and queries

Use rate/increase on counters over a justified window; apply rate before aggregation so individual resets are handled. Compare reset/uptime and sample coverage. Gauges are not counters. Weight fleet error ratios by request totals, not an average of instance percentages.

For classic latency histograms retain the le label when aggregating buckets before histogram_quantile; do not average p95 values. Native histograms differ and mixed samples can change results. For an SLO threshold prefer good/total event counts from the corresponding bucket, with exact boundary semantics. Counters that never emit an error series need instrumentation/zero initialization or an explicit absent-series policy: a missing numerator can remove the result.

Distinguish a failed scrape (up=0), missing discovery/series, stale data and genuine zero traffic. Compare target status, last sample time, scrape errors, relabeling and rule evaluation. A wildcard absent check cannot identify each expected tenant/target without an inventory. Never fill every missing series with zero to turn a panel green.

## Rule verification

Use version-matched `promtool check config <candidate>`, `promtool check rules <rules>` and `promtool test rules <tests>`. Validate the real rendered configuration, not just source templates. Test error burst, recovery, counter reset, missing scrape, absent series, low/zero traffic and label matching. Bundled synthetic rules demonstrate only a subset; they do not assert coverage of a real service.

After staging, inspect actual rule evaluation, resulting labels, pending/firing/resolved transitions and resource cost. A for duration delays firing; it is not a substitute for a deliberate long/short burn window.

## Routing/delivery

Review route order, matchers, grouping labels, group_wait/group_interval/repeat_interval, continue behavior and receiver credentials by reference. Inhibition needs shared distinguishing labels; missing labels can broaden suppression. Silences need scoped matchers, owner, reason and expiry. Keep incident/test routes separate from production paging.

Validate the candidate with version-matched `amtool check-config` and test route matching offline. An offline routing match does not prove receiver auth or delivery. Only with user authorization send a clearly marked synthetic alert to the agreed test receiver and confirm ingestion, grouping, notification, resolution and absence of unintended recipients. Account for HA deduplication and routing time delays.

Do not publish receivers/webhooks, disable TLS checks, expose unauthenticated APIs, silence all alerts or enable expensive broad recording rules as a quick fix. Restore previous config on failed acceptance, then verify old routes remain effective.

Sources: [functions](https://prometheus.io/docs/prometheus/latest/querying/functions/), [rule tests](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/), [Alertmanager configuration](https://prometheus.io/docs/alerting/latest/configuration/), [alerting principles](https://prometheus.io/docs/practices/alerting/).
