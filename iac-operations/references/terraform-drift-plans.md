# Terraform/OpenTofu drift and saved plans

## Compare configuration, recorded bindings and actual objects

A normal full plan refreshes readable managed objects, compares provider observations with recorded state, then evaluates desired configuration. Distinguish configuration edits, external drift and provider/schema/computed-value changes. Verify account/region/aliases and observation time: read-denied, wrong-account or unavailable APIs give incomplete evidence, not a healthy empty plan.

After code/plugin provenance review, format/validate and run a full `plan -detailed-exitcode` with reviewed variables and dependencies. Exit 0 means no proposed changes in that evaluated graph, 2 means changes, 1 means error. Wrappers must distinguish all three. Keep logs/JSON protected; summarize addresses/actions without secret values. Refresh/planning can run provider/data-source code and APIs, so neither is automatically credential-free or sandboxed.

| Observation | Evidence needed before mutation |
| --- | --- |
| Approved emergency/manual change | Owner decides to encode the live value or restore reviewed configuration |
| Unexplained access/network/security drift | Preserve evidence; coordinate incident authority and provider/security owner |
| Computed/read-only/schema difference | Review provider/version, normalization, permissions and eventual consistency |
| Missing binding/object or duplicate owner | Reconcile exact ID and all states/controllers before import/forget/create |
| Replacement/destruction with persistent data | Usable restore evidence, fenced writers, accepted loss and application/data compatibility |

Do not auto-accept drift into code or erase it by applying old configuration. `ignore_changes` defines ownership, not repair: document and independently verify the other controller. Disabled refresh, targets, ignored fields, stale inputs, insufficient reads and objects outside the graph hide impact. No-change output does not establish application health.

## Refresh-only does not repair resources

A refresh-only plan proposes recording provider observations without ordinary convergence. Applying it mutates state/outputs and can forget a vanished object; it does not recreate that object. Review/gate the exact plan under state controls. A normal plan's refreshed in-memory view does not prove the backend snapshot was updated. Never silently accept unexpected drift through ad hoc/deprecated refresh commands.

## Bind the execution artifact

Save a binary plan for execution. Record exact engine/version, source/root revision, provider/module artifacts and lockfile, protected input/secret-version references, workspace/backend fingerprint, snapshot lineage/serial/native version, refresh mode and target/replace/import options. Review the full graph, replacement ordering, unknown values, outputs, aliases, imports/moves and data/external effects. Unknown values are unresolved risk; warnings/checks are not always hard preconditions.

Protect binary/rendered JSON in restricted encrypted storage and bind its digest plus exact argv/target/scope to the contract-v2 plan. Sensitive display flags do not remove plaintext secrets from artifacts. Do not publish raw JSON or low-entropy secret hashes. Provider/module/provisioner/external-data sources need trust review before planning.

Planning normally releases its backend lock; a saved plan reserves neither state nor real infrastructure. At apply keep the platform/resource lock, reacquire native locking and verify artifact digest/age/engine/backend/input identity, actual state freshness and authority. An intervening state write may reject a saved plan; an external resource change without a state write may evade that check. Reconcile material facts and replan when changed; arbitrary age limits alone do not establish freshness.

Apply only the reviewed saved plan. Its lack of an interactive CLI question is not authorization. Do not regenerate/apply implicitly, inject new variables, interchange binary plans across engines, bypass locks or overwrite newer state after rejection. Prepare a new exact artifact/review/gate; reuse unchanged valid scoped authority without redundant consent.

## Graph changes and verification

Use reviewed moved blocks/exact moves for address refactors and confirm no recreate. Declarative import/removed support and schemas vary by engine/version; inspect effective actions and remaining real objects, then a full plan. `-target` is exceptional recovery graph reduction: record omitted dependencies and require a later full plan. Do not substitute it for fleet/resource staging or service acceptance.

Verify actual IDs, service paths, data/replication, networking/access, capacity and health through specialist modules. Keep plan/state/object evidence together and report excluded/unknown coverage honestly.
