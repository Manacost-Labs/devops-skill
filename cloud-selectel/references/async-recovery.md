# Asynchronous effects, quotas and recovery

Selectel IAM, quota manager, Nova, Neutron and Cinder expose different response models. Do not invent a universal operation job/waiter. Persist each step's intent before dispatch: account/project, pool/segment, exact service endpoint/version, operation/input digest, before-state, known UUIDs, credential reference, request correlation IDs, dependencies, overall UTC deadline and recovery owner. An intent without an acknowledgement remains uncertain after restart.

## Quota and cost evidence

Select the pool-specific quota-manager URL from the official URL list and confirm the project. Read `GET /v1/projects/{projectID}/limits` and `GET /v1/projects/{projectID}/quotas` as supported. Quotas can differ by resource and pool/segment; inspect `value`, `used` and `zone` for every resource the operation or its transition needs. Never substitute a zero/empty default for missing data.

The quota API documents `207 Multi-Status` and a body containing per-resource/per-zone errors alongside successful quota entries. Parse status and every relevant error entry: a transport success or partial quota list is not complete headroom evidence. Missing, failed or contradictory dimensions block mutations depending on them; retain successful evidence without calling the whole preflight verified. A quota increase and a support-mediated project-limit increase are separate authorized operations. Check current billing/balance/account restrictions through appropriate read-only references; neither funds nor quotas guarantee physical placement capacity or price.

## Observation and contention

Use one overall execution window covering request attempts, consistency reads, service checks and compensation. A conservative local GET default is exponential backoff with jitter from 2 to 30 seconds, at most 20 reads or the approved deadline, whichever comes first. These are observation bounds, not provider consistency promises. Bound hidden SDK/CLI attempts and request duration too; a restarted client must not reset the budget.

| Situation | Next bounded action |
|---|---|
| Read throttled or temporarily unavailable | Same exact endpoint/project read with documented retry guidance; lower concurrency |
| Write response lost | Retain original identity and reconcile that API's actual resource/permission effects; no generic replay |
| VM `BUILD` or non-null task state | Read exact server and volume/port dependencies; do not launch another VM |
| VM `ERROR` or resource fault | Preserve native reason privately, inventory surviving effects, choose owned repair/recovery |
| Missing resource after acknowledgement | Check exact scope, permissions and propagation; absence at one instant is not failed-create proof |
| Partial quota response | Resolve missing/failed required dimensions before dependent writes |
| Partial dependent changes | Stop new effects, compare before/current state and compensate only attributable owned effects |
| Compensation response lost | Reconcile the compensation itself; do not claim rollback from dispatch |

Keep one in-flight mutation per IAM user/scope, group or port, and VM dependency chain. Local locks do not exclude other clients. Unknown endpoint/version, principal/project drift, concurrent ownership changes, permission failures, malformed payloads or unproven quota data stop dependent writes. Correlation IDs do not confer idempotency, and a changed request, pool or resource identity needs a revised plan/current authority.

## Closure

Recovery must preserve preexisting/shared resources, current writers, retained data and management access. Compare current state to this operation's expected post-state before compensating; stop if another writer changed it. Record every actual changed UUID and every unresolved candidate/charge. Keep original receipts and uncertainty across restart rather than allocating a new operation ID to hide it.

Use `verified` only after desired state, effective access/network behavior and user-visible service acceptance; `rolled_back` only after the authorized recovery state and retained data/service behavior are checked; `partially_verified` for observed effects lacking complete evidence; `blocked` when safe continuation is unavailable. Record last observation/time, next safe read and accountable provider/specialist handoff.

Sources checked 2026-10-30: [quota API including partial results](https://docs.selectel.ru/en/api/quota-management/), [limits versus quotas](https://docs.selectel.ru/en/access-control/projects/quotas/), [pool-specific API URLs](https://docs.selectel.ru/en/api/urls/), [supported OpenStack components](https://docs.selectel.ru/en/cloud-servers/tools/openstack-cli/about-openstack-cli/). Refresh the exact service's error/retry and recovery semantics before execution.
