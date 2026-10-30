# ARM asynchronous observation and recovery

Persist intent before dispatch: target cloud/tenant/subscription, exact resource and request digest, before-state/incarnation, dependency IDs, operation deadline, owned-effect evidence and recovery owner. Add returned request/correlation IDs and original headers without logging credentials. Keep one operation identity after transport loss, timeout or restart; a missing response is an uncertain outcome.

## Follow the actual response protocol

An initial `201` or `202` may mean work was accepted. Prefer a returned `Azure-AsyncOperation` URL; use `Location` only when that header is absent. Their response formats differ. Retain the original URL/API version and interpret the selected provider/API's protocol; do not parse a `Location` result as an `Azure-AsyncOperation` status object. For APIs without tracking headers, use their documented final-resource observation rather than inventing a job ID.

Before an authenticated poll, validate the URL against the already confirmed cloud ARM endpoint, subscription and operation evidence. Reject credentials in URLs, fragments, redirects, foreign origins/clouds and unexpected scope. A URL in an API response is data, not permission to forward an access token. Tracking permission can require resource-group scope even when the initial resource action is permitted; establish that access in preflight instead of broadening the role after dispatch.

For `Azure-AsyncOperation`, terminal values include `Succeeded`, `Failed` and `Canceled`; other provider statuses remain in progress. Inspect returned errors. A success status with an error or a contradictory resource result is inconsistent evidence. Completion still requires a separate exact GET and acceptance checks. `Location` termination rules depend on the operation; HTTP `200` alone is not a universal service-success test.

Honor `Retry-After` when returned. Without it, use bounded read backoff with jitter, for example 2 seconds increasing to 30 seconds. Predeclare one overall deadline and at most 30 observations as local limits, not Azure latency guarantees. If `Retry-After` exceeds the remaining budget, retain uncertainty and hand off; do not poll earlier to fit the budget. Include hidden CLI/SDK attempts and elapsed recovery time in the same window. Throttling reduces concurrency; permission, precondition, policy or capacity errors need diagnosis rather than unlimited retries.

## Reconcile effects before compensation

Timeout, expired authority, unreadable status or missing final GET does not prove failure or absence. Stop new mutations and preserve exact outstanding operation/resource IDs, last evidence time, billable survivors and the next safe read. Polling observation is not permission to replay the original write.

For partial success, enumerate each dependency's actual state and distinguish preexisting/shared objects from attributable effects. Compensate in safe reverse dependency order only within current authority and only while the present state matches the expected post-state. Recovery calls have their own uncertain-response handling; do not blindly repeat a delete or restore a stale group/VM snapshot over another writer. Preserve data and escalate when safe compensation cannot be established.

Use `verified` only after desired-state and user-path evidence pass, `rolled_back` only after the separately authorized recovery result is observed, `partially_verified` for known effects with incomplete convergence/health evidence, and `blocked` when work cannot safely start or proceed. Saved JSON and local step phases never authenticate execution authority.

Sources checked 2026-10-30: [ARM async status and permissions](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/async-operations), [throttling and retry headers](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling). Refresh the exact resource-provider operation before planning execution.
