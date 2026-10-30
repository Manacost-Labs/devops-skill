# Four modes, one scoped authorization

Select how independently the agent may work, then authorize the environment and work it may perform. It should not ask again for ordinary steps already covered.

| Mode | Automatically permitted risk | Confirmation |
|---|---|---|
| Safe | R0–R1 | Exact approval for R2–R4 |
| Balanced | R0–R2 in issued scope | Exact approval for R3–R4 |
| Semi-Auto | R0–R3 in issued scope | Exact approval for R4 |
| Full Auto | R0–R4 in a specifically trusted, authorized environment | Separate admission for destructive/irreversible effects or exceptions; hard policy denials stay blocked |

Safe is the installation default. Balanced is a useful daily choice after scope is issued. Production deployment remains R3 even if tested. Read-only work can be higher risk when it exposes sensitive/cross-tenant data or creates substantial load/cost.

## What the user approves once

An authority card names the mode, exact target/profile/environment, executor, permitted actions/resources, data classes, state/external effects, expiry and recovery boundaries. For example: “Balanced, this development environment, build/test/prepare release for this service until the stated time.” It is not authority over every machine the credentials happen to reach.

The agent prepares a draft. An accountable operator or identity-backed broker verifies the issuer, reviews the envelope, re-times/activates it at issuance, supplies authorization evidence and places it into a protected external authority store. The agent receives read access to issued records. It never approves or publishes its own authority.

The Full Auto record additionally identifies real isolation, bounded credentials and owner evidence. References are not proof by themselves: the operator must establish those controls. The supplied enterprise policy retains Safe and stricter per-operation approvals; changing mode cannot override it.

## Runtime use

The trusted launcher configures an absolute `DEVOPS_AUTHORITY_DIR` outside the runtime/source tree, protected against agent writes. It is not a path supplied by a repository, request or log. Provision access deliberately; the installer does not create or copy an active authority store.

From a runtime/source checkout, prepare the current operation normally, then create an unapproved authority draft:

```powershell
python devops-platform-contracts/scripts/autonomy.py --draft-from operations/plans/build.json --mode balanced --authorization-id authority-shop-build --output operations/authority-draft.json
```

The operator/broker reviews exact actions/scopes and timing, sets the activation/trust fields, obtains the payload hash with `--digests`, and adds real issuer records bound to it. It publishes the complete reviewed record as `authority-shop-build.json` in the protected store. The example template is deliberately unapproved; filling invented identities or evidence does not establish real authority. Hashes are integrity bindings, not signatures.

The direct preparation example assumes an authorized tool session. If an optional interception adapter does not register the new preparer, prepare/execute it through the existing Safe R1 planner and wrapper with an exact output path and verification; do not disable interception. Adapter support is separate from authority issuance.

After issuance the agent prepares each concrete command against that authority:

```powershell
python tools/devops_plan.py --target-profile target.yaml --mode balanced --authorization-id authority-shop-build --action build_release --risk R2 --objective "Build the reviewed service release" --scope service:shop --verify "archive verification passes" --output operations/plans/build-001.json -- python tools/build_release.py --output dist/reviewed.zip
python tools/devops_exec.py --operation operations/plans/build-001.json --timeout-seconds 120 -- python tools/build_release.py --output dist/reviewed.zip
```

The issued record must cover those exact declared actions/scopes and the validated target. A later plan may use a new command digest inside the same envelope; the planner clips its window to the remaining grant lifetime. The gate re-reads current authority at every launch and the journal records its ID/digest/mode. It does not re-request already issued authority.

Changing mode, target/profile/owner, policy or execution identity requires a new matching grant. Above-ceiling/outside-scope work needs one grouped exact approval or a new envelope; destructive/irreversible effects still need separate exact admission. Mark an irreversible operation with `--irreversible` (R4). Exact approval now binds the complete operation through `operation_digest`, including scope/risk/effects, rather than argv alone. After completing the operation facts, the agent calculates it with `operation_gate.py --request operation.json --print-operation-digest`; the real approver binds admission to it. The agent must not relabel risk/effects to stay below the ceiling.

## Stop and revoke

Expired, revoked, changed or missing authority at the final admission check stops launch. Remove/revoke the record through the trusted issuer. The check runs after durable journal intent so storage delays cannot extend permission; its successful completion is the admission point. Revocation after that point is not an atomic cancellation of process creation or an already running process: those require containment or coordinated issuer/launcher control. Invalid authority is not silently ignored, and policy-denied actions cannot be approved by a casual prompt.

Failures in discovery or verification are not automatically permission questions. The agent should resolve missing evidence within its authority, ask once for an actual missing permission, and report unresolved/uncertain outcomes honestly. Recovery/data compatibility, locks, secrets handling and verification remain required in every mode.

## Compatibility and limits

V2 requests without `autonomy` retain Safe behavior. Policy semantics changed in 0.9.0: regenerate policy bindings and obtain real replacement approvals for old pending requests. Old runtimes reject the new fields; do not use them to execute delegated requests. No local or production environment is automatically switched to a higher mode by installing this release.

The gate validates supplied contracts/evidence references, not arbitrary command semantics or actual remote identity/access. Restricted OS/cloud credentials, sandboxing, protected runtime/policy/store and real issuer verification remain necessary. A writable authority store lets the agent manufacture records, so it cannot serve as independent approval. Platform modes do not change separate host/tool permission prompts.

Local synthetic tests cover repeated authorized launches, revocation, ceilings, scope/identity/policy drift, irreversible admission, trust/recovery requirements, authority-file attacks and request replacement during gate validation. They do not certify an organization's identity broker, ACL provisioning, sandbox or production recovery.
