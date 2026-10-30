# Delegated authority contract

Modes are Safe/R0–R1, Balanced/R0–R2, Semi-Auto/R0–R3 and Full Auto/R0–R4. Safe is the absent-selection default. `schemas/autonomy-authorization.schema.json` describes the external record; `scripts/autonomy.py` implements validation and draft/hash utilities.

An optional v2 request `autonomy` object contains only mode, authorization ID and canonical record digest. Delegated modes also require explicit boolean `change.irreversible`. The existing exact command-plan digest is still mandatory. The record comes only from operator-configured `DEVOPS_AUTHORITY_DIR`, an absolute, non-reparse external directory outside the runtime/source tree. Request-provided paths/bodies are not authority. The loader rejects invalid IDs, symlinks/reparse paths, hardlinks, nonregular files, duplicate/nonfinite JSON and oversized input.

The canonical payload digest excludes only `authorizations`. Each issuer record binds that payload digest, attributable actor/role, evidence and a covering approval window; the full record digest includes the issuer records. Distinct issuer/role counts follow the selected policy at the mode ceiling, with at least one issuer and executor/issuer separation. These are metadata/evidence checks, not cryptographic identity signatures: an accountable operator/broker must verify the real issuers and protect the store from agent writes.

Record scope uses exact action and scope entries, never wildcard/prefix expansion. Targets include owner/environment/profile digest. Selected mode, executor and policy must match. Grant/issuer/operation windows must fit; default grant TTL is at most120 minutes and the enterprise baseline caps autonomy at Safe. Policy inheritance cannot broaden maximum mode, TTL or delegated production permission.

Valid same-target authority can substitute prior scoped authorization for individual confirmations below the mode ceiling. Above-ceiling or outside action/scope/data/effect permissions falls back to exact manual operation approval with at least one approver. Invalid/stale/revoked/changed records or target/executor/policy/mode drift are hard stops, not fallback. Destructive/irreversible work and exceptions never use delegated admission. Hard policy-denied actions remain blocked.

Delegated R3/R4 needs a target lock; stateful R3/R4 must satisfy recovery requirements. Every operation still gets verification criteria, exact argv digest and journal. Grant references/mode are recorded in the launch/outcome journal; raw grants are not copied there. A new plan inside an envelope needs a fresh gate check, not new human authority.

The executor sends its frozen in-memory request through bounded gate stdin, so changing the original request path between parent and gate cannot substitute a differently authorized plan. With an authority store configured, deterministic `--at` clocks are refused. Check current authority immediately before each launch; revocation does not cancel a child already running.

`scripts/autonomy.py --draft-from ...` creates a deliberately unapproved draft outside the active store. It has no approve/issue switch. `--digests` prints hashes only. Activation, actual issuer evidence and protected-store publication are operator/broker tasks. Private issued records must never enter source/release archives. Changing policy semantics rotates its digest and invalidates prior bindings.

The wrapper validates declared scopes and facts; it is not an arbitrary CLI scope parser or OS sandbox. Real credential/sandbox restrictions and protected runtime/store are required, especially in Full Auto. Do not represent metadata references or “trusted” text as proof that isolation/access has been independently established.
