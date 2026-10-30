# Access application and policy changes

Use the current core authority, risk, registered execution task and evidence contract. A local test identity, policy tester result or API response cannot authorize a policy write. Production Access changes retain the R3 floor; broad access loss/removal can be R4.

## Identify the effective application

Inventory the account, application ID/type, hostname/path, AUD, session/cookie settings, IdP/posture/group dependencies, all attached policy IDs/actions/precedence and service-token consumers. Inventory overlapping applications, including the parent hostname, exact path, wildcard child and nested paths. A more specific application's policies replace the parent's policies: a restrictive parent does not protect a permissive child. `/alpha/*` does not cover `/alpha`; test both. Map the selected path to the application actually enforcing it.

Policies match Include selectors with OR, Require selectors with AND and Exclude selectors as rejection. Policies without a matching allow remain denied. Service Auth and Bypass have evaluation precedence over ordinary Allow/Block; a numeric position alone does not describe the effective decision. Preserve selectors, action and associations explicitly. Avoid Everyone and Bypass as incident repairs. Service Auth is for deliberate machine authentication, with positive and missing/invalid credential tests.

Read the application, every attached/reusable policy and its consumers from the current API with complete pagination. A reusable policy may affect other applications. Do not edit it under authority for only one application: either include all consumers in the reviewed plan or create and associate a deliberately isolated policy through the owner. A service-token ID is a reference; its credential value must never enter the plan/snapshot.

## Plan and stage

Record a canonical fingerprint of application fields, ordered policy associations and complete policy definitions. Where the API provides no documented atomic conditional update, this fingerprint is a client-side drift detector, not an ETag/CAS promise. Acquire exclusive ownership with the dashboard/IaC/other automation owners, then re-read immediately before each write. Unknown or changing writers are a stop condition.

Prepare the complete endpoint-specific request using the current API schema. Preserve unrelated application settings, policy fields and association order. Never assume an update is a JSON merge because the request contains a few fields. Changing the application and a reusable policy is two separately recorded effects; a successful first write followed by failed second write is partial work.

Rehearse on a dedicated hostname and isolated application. Keep a separately verified administrator route outside the changed application. Use the policy tester where available, then fresh browser sessions for allowed, explicitly excluded, wrong group/posture/IdP and unauthenticated identities. Existing sessions can hide the new-login behavior; inspect session expiry/revocation requirements separately without silently revoking all users.

## Reconcile and recover

On timeout, disconnect or API/semantic failure, stop progression. Re-read the exact application and policy IDs; classify each as before, intended, changed by another writer or unknown. Inspect association order and the effective path again. Do not repeat a create and accidentally attach duplicate policies. API success without allowed/denied user-path evidence is incomplete.

Reverse only the policy/application effects still owned by this operation and still matching its recorded post-change fingerprint. Preserve independent changes; a conflicting consumer or new association requires a fresh combined plan. Re-read the restored definitions/associations and repeat fresh positive and negative sessions across every affected path. Credentials or IdP state changed elsewhere are not restored by the policy snapshot. Report `partially_verified` until effective authentication and denial evidence is available.

Official behavior: [policies](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/), [application paths](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/), [Access applications API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/applications/), [reusable policies API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/policies/).
