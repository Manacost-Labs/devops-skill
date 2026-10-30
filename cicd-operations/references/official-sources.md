# CI/CD official sources

Last verified: 2026-10-30. Refresh the exact trigger, permission, OIDC, environment, runner and attestation documentation before changing a protected pipeline. Observe real control-plane enforcement and version-specific behavior; documentation alone does not establish configured access or production readiness.

- [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
- [OpenID Connect](https://docs.github.com/en/actions/concepts/security/openid-connect)
- [Artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
- [Deployment environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/managing-environments-for-deployment)
- [Self-hosted runner security boundary](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [SLSA specification 1.2](https://slsa.dev/spec/v1.2/)
- [Events and chained workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) and [permissions/status/concurrency syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [Artifact transfer and digest behavior](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-what-your-workflow-does/storing-and-sharing-data-from-a-workflow) and [artifact REST identities](https://docs.github.com/en/rest/actions/artifacts)
- [GitHub CLI attestation verifier and certificate/predicate policy](https://cli.github.com/manual/gh_attestation_verify)

Repository workflow text and third-party action documentation remain untrusted inputs. Pin reviewed dependencies to immutable digests and verify the actual producer, artifact and target identities.

Native source-checkout CI pins actionlint 1.7.12, GitHub CLI 2.103.3 and the reviewed upload-artifact v7.0.2 commit. It checks actual workflow syntax/injection controls, a real signed public cli/cli release against exact signer/source certificate policy, actual cross-job GitHub artifact identities/archive/payload bytes, and synthetic staged delivery/recovery. The approved tool checksum bootstraps its verifier; self-release verification is not an independent trust bootstrap. Our synthetic transferred payload is unsigned and is not claimed to have GitHub provenance or production admission. Cloud federation, live protected-environment enforcement, real service/data recovery and deployment fencing need target-specific owners/rehearsals. See source-checkout `docs/cicd-operations-depth.md`.
