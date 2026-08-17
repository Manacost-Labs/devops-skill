# Security policy

## Publication gate

Do not push the project source or publish an RC to a public repository until the repository owner has enabled and tested GitHub private vulnerability reporting. GitHub exposes this setting for public repositories, so the safe initial sequence is: create the empty public remote, enable reporting, verify the private form, and only then push project content. The expected private entry point is the repository's **Security** tab and its **Report a vulnerability** action. If that action is absent, keep the source local or private and access-controlled; a public issue, pull request, discussion, or commit is not an acceptable substitute.

The repository settings checklist in docs/github-repository-settings.md records how to enable and verify the channel. No email address or response SLA is promised by this project.

## Supported versions

Before the first tagged RC, no public version is supported. After publication, only the latest 0.3.x release candidate receives best-effort security fixes. Contract v1 remains planning-only and must not authorize R2-R4 execution.

## Report a vulnerability

After private vulnerability reporting is confirmed, use **Security > Report a vulnerability** in this repository. Include:

- the affected tag or full commit SHA and module;
- the security boundary and realistic impact;
- minimal reproduction steps using synthetic or isolated targets;
- whether credentials, personal data, customer systems, or production state may be exposed;
- a safe way for the maintainer to validate the finding.

Do not include literal credentials, personal data, customer evidence, sensitive topology, destructive payloads, or live-target exploit output. If a report concerns an exposed credential, revoke or rotate it through the credential owner first; do not paste it into the advisory.

## Maintainer handling

The maintainer will acknowledge and triage reports on a best-effort basis, preserve a private finding history, and distinguish reported, mitigated, remediated, and independently verified closure. Remediation does not become verified closure until a retest supports it.

Where appropriate, the maintainer will coordinate disclosure, publish a GitHub Security Advisory, identify affected releases, and record remediation and verification evidence. Response or remediation deadlines must not be invented without a named accountable owner and an approved support policy.

## Security properties and limits

The platform is designed to fail closed on missing contracts, stale or mismatched approvals, missing recovery evidence, and untrusted-content instructions. Local validation, hash manifests, and ledger chains do not prove external identity, provide cryptographic release signing, create immutable storage, or certify compliance.

Public portfolio RCs are unsigned evaluation artifacts unless a release explicitly carries independently verifiable signature and provenance evidence. Production adopters must supply protected source control, independent review, CI isolation, a credential broker, policy ownership, signed provenance, and an external immutable audit sink.
