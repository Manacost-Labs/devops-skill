# Support policy

This portfolio project provides community-style, best-effort support with no response-time, remediation-time, availability, recovery, or compatibility SLA.

## Public support

After the repository is public, use the structured GitHub issue forms for sanitized bug reports and feature requests. Include the release tag or full commit SHA, selected profile/modules, expected behavior, and minimal synthetic reproduction. Maintainers may close requests that cannot be reproduced safely or fall outside the current release-candidate scope.

Never attach credentials, personal data, customer evidence, live domain or IP inventory, private topology, unrestricted logs, or production configuration. Security reports must follow SECURITY.md and must not be filed as public issues.

## Supported baseline

After the first tagged RC, only the latest 0.3.x release candidate is intended to receive best-effort fixes. Contract v1 requests are planning-only. The reference CI runtime is CPython 3.13.5 on GitHub-hosted ubuntu-24.04 and windows-2025 x86-64 runner labels; the contents behind hosted labels still evolve.

Other Python ABIs, operating systems, self-hosted runners, offline mirrors, providers, and production targets require adopter-owned qualification. Provider behavior must be revalidated against current official documentation and target discovery.

## Production support boundary

A target operator must maintain a private operations channel, named incident and rollback owners, tested backup/restore procedures, credential revocation, monitoring, and an escalation path. Those target-specific responsibilities are intentionally not represented as public-project support.

Before any production adoption, publish an accountable support matrix and escalation process for that environment. This repository does not imply commercial support or operational responsibility.
