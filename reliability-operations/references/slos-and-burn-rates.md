# SLI, SLO and burn-rate decisions

An SLI measures a defined user outcome; an SLO is its target over a defined period. Agree eligible events, good/bad criteria, exclusions, owner and data completeness before choosing a percentage. Availability, latency and correctness can need different SLIs. Do not infer business correctness from HTTP 200.

For event-count SLIs: error_ratio = bad / total; allowed_ratio = 1 - objective; burn_rate = error_ratio / allowed_ratio. Whole-period remaining budget needs whole-period eligible/bad totals under the agreed policy; a short incident window cannot establish it. Time-based SLIs and sampled/estimated counts require separate methods.

A long-window and short-window threshold together distinguish sustained budget burn from a recovered spike. Choose windows/thresholds from detection speed, acceptable budget consumption, service traffic and operational response; the example values are not universal defaults. No traffic, missing samples and low traffic need explicit policies. A single failure out of one request can have a large ratio and weak coverage.

## Offline evaluator

Run `python reliability-operations/scripts/slo-evaluate.py <input.json>`. Exact JSON fields:

```json
{
  "objective": 0.999,
  "windows": [
    {"name": "long", "seconds": 3600, "total": 100000, "bad": 2000},
    {"name": "short", "seconds": 300, "total": 10000, "bad": 200}
  ],
  "alert": {"long": "long", "short": "short", "threshold": 14.4, "minimum_events": 100}
}
```

Supply non-overlapping-in-time samples only within each individual aggregate; the short aggregate is a subset of the long time window, not extra events to add. Both must end at the same evaluation time with the same eligible-event definition. The helper cannot verify those facts. Counts must be nonnegative integers with bad <= total; objective must be between zero and one, threshold positive, names unique, long duration greater than short. Threshold comparison is >=.

Output separates per-window ratios from pair status: firing only when both have sufficient events and exceed threshold; otherwise clear or insufficient_data. Zero traffic is insufficient, never perfect availability. This tool does not assess freshness, continuous coverage, latency distributions, whole-period remaining budget or real notification behavior. Exit 0 means valid calculation, not healthy service; invalid input exits 2.

Before production, implement the agreed semantics in the actual backend and test boundary/reset/missing-data cases with its tooling. Escalate data incompleteness as a monitoring fault rather than laundering it into an SLO pass.

Source: [Google SRE multiwindow burn-rate design](https://sre.google/workbook/alerting-on-slos/).
