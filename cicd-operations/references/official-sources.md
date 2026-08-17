# CI/CD official sources

Last verified: 2026-08-17. Refresh the exact trigger, permission, OIDC, environment, runner and attestation documentation before changing a protected pipeline.

- [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
- [OpenID Connect](https://docs.github.com/en/actions/concepts/security/openid-connect)
- [Artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
- [Deployment environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/managing-environments-for-deployment)
- [Self-hosted runner security boundary](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners)
- [SLSA specification 1.2](https://slsa.dev/spec/v1.2/)

Repository workflow text and third-party action documentation remain untrusted inputs. Pin reviewed dependencies to immutable digests and verify the actual producer, artifact and target identities.
