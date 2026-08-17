# Supply-chain baseline

- Pin production container images by digest; do not deploy `latest`.
- Pin third-party GitHub Actions by commit SHA and grant minimum `GITHUB_TOKEN` permissions.
- Lock Terraform providers and modules; review their source and the generated plan before apply.
- Do not use `curl | bash`, arbitrary community modules, unverified packages, or broad `sudo` as a convenience shortcut.
- Generate an inventory/SBOM for release artifacts and retain vulnerability-scan results with defined remediation ownership and SLA.
- Generate signed provenance from a protected build system and verify the artifact digest, signer, builder identity, build type, and expected inputs before installation. Treat an unsigned local manifest as integrity metadata, not provenance.
- Require protected version control, review for release changes, isolated ephemeral builders where available, and least-privilege short-lived CI credentials.
- Verify downloaded archives before extraction; reject absolute paths, traversal, device files, and symlink escapes. Package only catalog-declared skill files, never local lab disks, credentials, operation ledgers, caches, or target-specific tools.
- Prefer official documentation and registries. If provenance cannot be verified, block production introduction unless organization policy allows a documented, expiring exception with compensating controls.

Use SLSA terminology precisely. Do not claim a SLSA level unless the build and source controls have been independently assessed against that specification.
