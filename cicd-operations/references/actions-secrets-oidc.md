# Effective credentials, federation and deployment admission

## Minimize the actual job identity

Begin with workflow `permissions: {}` or explicit read-only rights, then grant only the job's required token scopes. Inspect repository/org defaults, event/fork policies, reusable call-chain ceilings and custom App/PAT identities. An action can use `github.token` without a visibly passed secret. `contents`, `actions`, `packages`, `deployments`, `attestations`, `pull-requests` and `id-token` permissions serve different operations; never grant broad write as a generic installation fix.

Separate untrusted build/test from trusted signing/admission/deployment. Scope any App/PAT to the exact repositories/actions and lifetime, prefer workload identities, and withhold production credentials from PR code and persistent runners. Pin external actions/tools and inspect their credential/network behavior. A container boundary does not automatically isolate a host token, Docker socket or metadata endpoint.

Map repository/org/environment secrets and explicit reusable-workflow inputs. Availability depends on the actual event/environment/approval; a missing secret can become an empty string or skipped step, which must fail required deployment prerequisites rather than produce success. Do not use a dummy fallback, broaden secret visibility or grant a runner new rights to silence the failure.

Keep values out of argv, tracing, debug logs, broad environment dumps, job/matrix outputs, caches, PR comments and artifacts. Masking does not cover every transformation or structured/derived value. Prefer protected runtime files/handles and redacted version references; validate artifacts/logs before upload. On suspected disclosure preserve restricted evidence, revoke/rotate with the owner, assess downstream use and invalidate affected credentials/artifacts; deleting a log is not revocation.

## OIDC requires both sides of the trust

`id-token: write` only enables obtaining a token. It does not authorize a cloud role or prove least privilege. Confirm the real issuer, audience, repository/owner IDs where supported, subject, ref/environment, workflow and reusable builder identity, actor/event constraints and cloud-side claim mapping. Verify provider-supported conditions and actual role/session actions/resources, TTL and restrictions with the cloud/credential module. Do not decode an unsigned token payload and call it authenticated verification.

Environment-based subjects can differ from branch-based ones. A branch check in YAML does not replace cloud trust, and the token's environment claim does not by itself prove an independent reviewer approved it. Reusable workflow signer/caller identities differ; validate both intended execution and callers, not only a broad organization or workflow filename. Protect renames/transfers and wildcard subjects from unexpectedly expanding trust.

Request/exchange credentials only in the exact admitted job, as late as possible, with a bounded session. Keep tokens off stdout/disk/artifacts and avoid sharing across jobs. A cancelled job can leave exchanged cloud credentials or remote operations alive; reconcile/revoke/fence them through the actual provider. CI timeout is not proof of expiry, resource rollback or revoked access.

## Protected deployment boundary

Confirm the exact environment exists and its active reviewers, self-review/bypass policy, allowed branches/tags, secret visibility and protection mechanisms are supported by the repository's plan. Referencing a new/misspelled environment may create an unprotected one; do not infer controls from `environment: production`. Match repository/ruleset and provider constraints to the same actual candidate and target.

GitHub protection approval and core's scoped authority are separate applicable controls. Preserve both when policy requires them. Prepare exact plans/targets/artifacts and reuse valid existing authority inside its envelope; do not re-prompt for every test/job, fabricate an approver or bypass an environment gate to implement autonomy. Identity/scope/window/irreversible effects outside the envelope need their actual admission. Route control-plane settings and owner verification to `github-operations`.
