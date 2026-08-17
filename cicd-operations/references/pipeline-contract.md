# Provider-neutral pipeline contract

## Required chain

Establish this evidence chain:

1. Source: protected repository and immutable revision with review evidence.
2. Build: isolated runner image/toolchain digest, locked dependencies, tests, and scans.
3. Package: content-addressed artifact and checksum stored immutably.
4. Describe: SBOM covering packaged content and build provenance/attestation binding source, builder, workflow, inputs, and artifact digest.
5. Promote: policy verifies signatures/attestations and moves the same digest between environments.
6. Deploy: short-lived least-privilege identity targets one approved environment.
7. Verify: target reports the deployed digest and passes health, user-path, security, and observation-window criteria.

Fail closed when the source, builder, attestation, digest, target, or approval binding is missing. A scan result is evidence, not authorization; define severity policy, exceptions, owner, and expiry.

## Runner trust

Use ephemeral clean runners for privileged jobs. Pin the runner image/toolchain, patch it, isolate networks and credentials, and destroy or sanitize it after the job. Separate untrusted builds from signing and deployment. On self-hosted runners, prevent cross-job workspace, process, container, credential, Docker socket, metadata-service, and cache leakage. Treat runner administrator access as supply-chain authority.

## Release and rollback

Use a unique release ID, artifact digest, target, idempotency key, concurrency lock, start/end window, and abort criteria. Prefer canary/rolling/blue-green strategies when the application supports them. Verify target-reported digest rather than pipeline success alone.

Predefine rollback to a known-good immutable digest and preserve configuration compatibility. Record database migrations, feature flags, queues/events, and external API changes that make code rollback unsafe. For forward-only data changes, define stabilization and forward-fix ownership instead of promising rollback.
