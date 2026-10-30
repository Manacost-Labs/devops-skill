# Disposable test-account recovery drill

Status: the repository ships an executable offline comparator/read-only observation helper and this prepared live procedure. No test account or credential profile is bundled. A green offline CI run does not establish Cloudflare enforcement, connector propagation, Workers runtime behavior or live recovery.

## Prepare the exact target card

Name an operator/approver, dedicated non-production account and zone IDs, owned test hostname/path, account plan/entitlements, IdP test organization with allowed/denied users, isolated service identity, reusable-policy consumers, WAF ruleset/phase/rule IDs, Tunnel UUID and two independent disposable connectors, origin ports, Worker script and two immutable stateless versions. Record the permitted probe volume, observation window and abort threshold before starting. Use a namespace unique to the drill, with no production routes, bindings, IdP groups, data, queue consumers or outbound business effects. Record cost/seat/plan constraints rather than silently omitting an unavailable product.

Provision infrastructure through its owners and the current protected execution contract. Confirm emergency administrator access, DNS before-state, healthy origins/connectors and named rollback candidates. Keep all tokens/service credentials in an existing scoped broker/profile; the read-only collector uses `CLOUDFLARE_API_TOKEN` injected by that profile, never a CLI value. Scope token permissions to the exact zone/account and relevant read APIs; use a separate narrowly controlled write identity for reviewed mutation tasks. Do not add Cloudflare secrets to public pull-request CI.

Before each phase, refresh official endpoint/permission semantics, capture before-state, prepare complete intended requests and effects, bind the current target/profile/plan, and obtain the current contract's admission for the exact registered task. Recovery writes and cleanup remain real changes, with their own exact plans inside valid authority. Never manufacture approval from this document or an HTTP response.

## Capture one read-only observation

Example from the source/runtime root, with an existing environment-injected credential profile:

```text
python cloudflare-operations/scripts/capture-readonly.py --kind waf-ruleset --account-id ACCOUNT_ID --zone-id ZONE_ID --resource-id RULESET_ID --output PRIVATE_NEW_FILE.json
```

Supported kinds: `access-app`, `access-policy` (one reusable policy), `waf-ruleset` (zone scope), `tunnel-config` (remote configuration), and `worker-deployments` (one recent-deployment-history response). The collector first GETs the exact zone and verifies its account, then GETs only the selected fixed official API endpoint. Default TLS validation stays enabled; ambient proxies, redirects, mutations and automatic retries are refused. Responses have a 2 MiB limit and socket timeout; OS DNS and incremental reads are not a hard overall deadline. It suppresses raw provider errors and known credential fields, writes a new local file exclusively, and never overwrites a prior receipt. Protect the destination directory/ACLs yourself, especially on Windows.

Coverage is deliberately `one_api_response_only`: this is not a full account/application inventory, pagination engine, policy evaluator or proof of the active deployment. Read attached policy associations/consumers, all needed pages, routes/bindings, connector health and telemetry through their owners separately. Use the Worker history response to identify and then independently confirm the actual current deployment. The receipt records the raw response digest and private result; review/redact before sharing. Normalize reviewed material fields into the state-guard snapshot shape with a documented mapping. The collector and hashes do not authenticate the later uploaded evidence.

## Execute one product phase at a time

| Phase | Bounded change and failure | Required recovery evidence |
|---|---|---|
| Access | Dedicated application covering `/drill` and `/drill/*`; isolated policy with named allow/require/exclude identities. Rehearse a two-effect application/policy change where the second effect is deliberately not launched. | Read exact app/policy associations; classify the partial state; restore only the changed owned definition. Fresh allowed, excluded, wrong-group, unauthenticated and machine missing/invalid credential sessions; verify the parent/child paths independently. |
| WAF/rate limit | One dedicated expression restricted to the drill host/path, with bounded traffic and preserved neighboring rule. Apply one complete definition; perform a fresh conflict read after a separately logged test-owner edit. | Conflict must stop the stale candidate; no old whole-ruleset replacement. Prepare a fresh owned inverse; record new ruleset versions, preserved neighbor order, deny/allow/exception cases and bounded threshold/recovery if rate limiting is supported. |
| Tunnel | Two known independent connectors and two synthetic origins. Validate candidate ingress/catch-all, activate an owned remote configuration, then deliberately leave the separate DNS effect unlaunched. Separately test one unavailable synthetic origin. | Record control-plane version versus actual connector observations; retain a healthy path; reconcile partial config/DNS state and restore exact owned ingress/route without restarting all connectors. Verify catch-all isolation, origin health, allow/deny and direct-origin protection. |
| Workers | Upload two stateless versions with no production bindings; verify version identity, promote a documented bounded split, record an intentionally failed health result. For lost-response logic, suppress only the local recorded response after a confirmed test deployment, without inducing uncontrolled retries. | Re-read actual deployment/split before another write; rollback compatibly to the former version as a new 100% deployment, or explicitly recreate a prior split. Verify per-version responses, routes and no external effects. A separate incompatible-storage fixture must refuse code-only recovery. |

Do not fake transport failure by attacking production connectivity or issue an intentionally unauthorized provider request. An unlaunched second effect is enough to rehearse partial coordination; offline tests cover lost-response classifications without live ambiguous writes. Rehearse a competing test-owner edit on an owned object under serialized, recorded phases, then confirm the stale plan and stale compensation both stop. Freshly capture and re-admit any replacement plan.

## Evidence and closeout

For every phase retain UTC times, exact source/tool revision, target/profile fingerprint, actor/reference, before/intended/observed and recovered snapshots/digests, provider version IDs, launched/unlaunched/unknown effects, redacted positive/negative probes and telemetry, observation window, RTO stage durations, remaining uncertainty and cleanup disposition. A result is `rolled_back` only after compatible restoration and effective user/security checks. Missing entitlements, identities, connectors or live observations produce `partially_verified` with the missing phase named; they are never skipped green.

Verify cleanup with the owner using exact created IDs and dependency/consumer checks. Preserve required evidence; delete no unrelated app, policy, ruleset, route, tunnel, Worker or external data. Revoke the drill-only access through the credential owner. Keep private live receipts outside public source, release archives and CI artifacts. Only an actual target-owner run can fill the live evidence matrix in `docs/cloudflare-operations-depth.md`.
