# Dashboards and access

Each panel must answer a decision: impact, scope, likely bottleneck or recovery. Record owner, datasource/tenant, environment/service selectors, query, units, interval, aggregation and missing-data behavior. Start with user outcomes, then dependency/host explanations.

Review denominators and weighted ratios; distinguish milliseconds/seconds, bytes/bits, rates/totals and UTC/local time. Show volume beside ratios, percentile with histogram/sample coverage, and deployments on a matching timeline. Align interval/timezone across panels before causal conclusions. Do not connect missing samples as healthy zero or hide a failing region behind a fleet average.

Use bounded variables and default scope; unlimited regex variables and broad log queries can overload the backend during incidents. State whether a graph is sampled/estimated. Link alerts to the exact service/interval and a runbook with an owner and action.

## Provisioning/change

Inspect the current provisioned versus UI-owned source, stable dashboard identity, datasource references and supported plugin versions. Review plugin trust and credentials separately; exporting a dashboard can include internal topology. Stage using synthetic data, validate rendered query results and access with the intended viewer role, then confirm persistence after the normal deployment process. Preserve the reviewed previous definition for rollback.

Grafana folder/dashboard permissions do not automatically create row/tenant isolation in a datasource. Verify the datasource credential's actual scope and backend authorization; tenant headers/labels supplied by a client are not a trust boundary. Keep anonymous/public dashboards, snapshots and sharing exports within explicit policy. Test access denial as well as legitimate access, and redact before exporting incident evidence.

Source: [Grafana security](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/). Confirm edition-specific permission features and plugin behavior from matching docs.
