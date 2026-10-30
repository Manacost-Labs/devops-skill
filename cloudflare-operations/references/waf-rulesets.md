# WAF and rate limiting with ordered rulesets

## Read the executable policy

Bind account/zone, plan entitlements, ruleset ID/kind, phase entry point and current version. Read every rule's stable ID/ref, version, enabled state, complete definition, order, action parameters and managed-rule overrides. Inventory account-level and zone-level rules, skip/exception targets and the preceding/following phases. A valid expression is not proof that the intended phase executes it or that a preceding terminating action permits it to run.

Distinguish custom rules (`http_request_firewall_custom`), managed protections (`http_request_firewall_managed`) and rate limiting (`http_ratelimit`). Preserve the phase and rule order. Review exceptions/skip actions for their exact phase/product/rule scope; never skip all managed protections to fix one false positive. Expression fields, actions, logging and thresholds depend on the account's actual entitlement: lack of a staging/log option requires a different reviewed test, not silent enforcement.

For rate limiting, record expression, counting expression where supported, characteristics and their cardinality, mitigation action/timeout, period, threshold, cached-request treatment and baseline. Confirm trusted automation and NAT/shared-client impact. Tests should cross only the disposable path's bounded threshold; do not generate an uncontrolled load test against production.

## Construct the exact request

Use the exact current endpoint schema. Ruleset PUT is replacement of the submitted rules collection: omitting an existing rule deletes it. A rule-definition PATCH also needs all fields that should remain in the new definition; sending only the changed expression can drop action parameters or other fields. A position-only PATCH is a distinct documented operation. If updating both definition and position, use that operation's documented body and verify the complete returned ruleset. Do not infer generic merge semantics from the HTTP verb.

Choose a single exact rule ID and preserve its full writable definition and neighboring order. Store the before ruleset/version, candidate request digest and expected ordered result. Each successful rule change creates a new ruleset version. This version identifies history; it does not by itself make a later request a conditional atomic write. Serialize the owner/dashboard/IaC writers and re-read immediately before each mutation. A new version or changed neighboring rule invalidates the prepared candidate, even when the target expression stayed the same.

## Observe partial effects and recovery

After each write, record the returned ruleset/version and read it independently. Test the dedicated deny/challenge case, legitimate allow and narrow exception/automation cases, then verify the origin and telemetry with Ray IDs over the chosen window. A challenge HTML page is not an application health result. Low traffic or missing logs remains missing evidence.

If the response is lost, read the exact ruleset and ordered rule definitions before retrying. If rule A applied and rule B did not, stop the batch, inventory both versions and identify the active entry point; never retry the entire old ruleset PUT. On an unrelated writer/version conflict, preserve their change and prepare a new combined diff.

Recover by a reviewed compensating definition/order update for the owned rule, or a whole-ruleset replacement only when its entire scope is owned and freshly matches the operation's post-change state. Restoring old configuration normally creates another version; it does not move the historical version counter backwards. Repeat allow/deny/exception and rate-limit recovery tests. A cache purge, globally disabled WAF or direct origin bypass is not a rollback procedure.

Official behavior: [update a ruleset](https://developers.cloudflare.com/ruleset-engine/rulesets-api/update/), [update a rule](https://developers.cloudflare.com/ruleset-engine/rulesets-api/update-rule/), [phases](https://developers.cloudflare.com/ruleset-engine/reference/phases-list/), [rate limiting](https://developers.cloudflare.com/waf/rate-limiting-rules/).
