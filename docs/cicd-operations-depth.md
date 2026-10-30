# CI/CD trust, artifact and recovery depth

Platform 0.13.0 expands the existing cicd-operations module to 0.4.0. Guidance separates GitHub event/runner/caller trust, effective secrets/OIDC/environment admission, artifact/provenance policy, and staged deployment/partial recovery. No production deployment, credential issuer or new runtime module is added.

Source, event head, tested merge checkout, workflow revision and run attempt are different identities. Bind the actual candidate and producer to explicit artifact IDs/digests and required checks. Keep untrusted code away from credentials/privileged runners, verify real environment/cloud enforcement, and preserve core mode/gate/journal without repeated consent inside valid existing scope.

A signed artifact still requires the intended signer/source/builder and exact subject bytes. A job exit, self-reported manifest, cache key or download warning is insufficient. A failed/cancelled deployment may have changed nodes, committed schema/data or emitted external effects; reconcile real state before retry or compatible recovery. Returning an old image is not automatic data rollback.

## Real CI evidence

The workflow `cicd-operations.yml` has three required review jobs:

- **CI/CD / workflow and signed provenance** uses checksum-pinned actionlint 1.7.12 to check all actual repository workflows and reject invalid dependencies and direct untrusted expression injection. A real Bash probe preserves a malicious title as literal data. Checksum-pinned GitHub CLI 2.103.3 cryptographically verifies its published Linux release against cli/cli repository ID, exact Deployment signer/source commit, branch context and GitHub-hosted runner policy. Authentic bundles then reject tampered bytes, wrong signer and wrong source. This is real certificate/subject verification, not mocked JSON parsing. The approved tool hash is the verifier bootstrap; verifying its own release is not an independent bootstrap proof.
- **CI/CD / synthetic artifact producer** builds only public synthetic bytes on a disposable runner, then uploads one immutable named artifact with a one-day retention. No runtime/release/customer data or credentials are uploaded.
- **CI/CD / artifact admission and partial recovery** independently queries the exact artifact and run attempt through the GitHub API, checks source/repository/workflow identity and creation time, downloads without forwarding the GitHub bearer to storage, verifies archive SHA-256 before reading its single bounded payload, then verifies payload SHA-256/context. The same admitted bytes feed the synthetic delivery tests.

All jobs fail on missing tools, unavailable required provenance, mismatch or failed assertions. No native test is skipped or allowed to fail. Global permissions stay empty; only the public-provenance job adds attestations read and the artifact consumer adds actions read. No write permission, OIDC minting, custom secret, protected environment, cloud identity or production target is introduced. GitHub's internal upload runtime token is used by the pinned official artifact action; it is not exposed to the fixture.

The synthetic payload does **not** have a signed attestation; its service metadata and transport/content checks are a transfer test, not production artifact authorization. Real cryptographic provenance is tested separately against the public GitHub CLI release. Policy expectations come from reviewed workflow context/constants, never from the payload itself.

The 12 source-only delivery scenarios cover actual target digest, unchanged repeated application, migration/external-effect deduplication, middle-node failure with exclusion/later node untouched, lost response after activation and observed-state resume, failed recovery, unsafe old-writer/queue rollback refusal, compatible code reversal preserving current data, unknown targets/idempotency conflict, payload tampering/context forgery, unsafe archives, digest-domain confusion and foreign/stale artifact metadata.

Local fixture files represent nodes, schema/writes, traffic and external effects; they do not prove remote API idempotency, durable distributed journaling, cloud-token revocation, target lock/fencing, real canary health, protected-environment enforcement or database restoration. Those require isolated target-specific rehearsals and actual identity-backed owners. AI technical review is separate from that approval.

Run platform/skill validation, full regressions, deterministic release/export checks and secret scanning too. Runtime packages include the focused guidance but exclude test tools, fixtures, public-release downloads, artifact payloads and CI services. Temporary third-party binaries and generated target state are never committed or packaged.
