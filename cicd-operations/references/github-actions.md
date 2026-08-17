# GitHub Actions controls

## Trigger trust

Map each trigger to actor, ref, checked-out revision, available token, secrets, environment, and runner. For pull requests from forks, keep permissions read-only and withhold secrets. Treat `pull_request_target` as privileged base-repository execution: never checkout or execute the pull request head before trust is established. Review chained `workflow_run`, `repository_dispatch`, manual inputs, reusable workflows, and tag/release triggers for ref confusion.

Protect deployment branches/tags and environments. Require named reviewers, prevent self-review where supported/policy requires, scope environment secrets to deployment jobs, and bind concurrency to target environment so two releases cannot race.

## Dependencies and permissions

Pin every `uses:` reference, including reusable workflows, to a full 40-character reviewed commit SHA. Keep a human-readable version comment and use an approved update process. Review transitive scripts, package installation, and network downloads; never pipe downloads to a shell.

Set workflow permissions explicitly. Start with `contents: read` or `{}` and grant only necessary job-level permissions. Use separate jobs for build and release so untrusted build steps cannot inherit deployment credentials. Restrict `actions: write`, `contents: write`, `packages: write`, `pull-requests: write`, and `attestations: write` to their exact use.

Grant `id-token: write` only to the deployment/attestation job. Configure the cloud identity provider to validate GitHub's issuer and intended audience plus immutable trust conditions such as organization/repository, protected ref, workflow identity, and protected environment. A job-level condition is not a substitute for cloud-side trust policy.

## Data paths

Treat caches as untrusted acceleration, never release evidence. Prevent untrusted jobs from poisoning keys consumed by privileged jobs. Verify downloaded artifact IDs/digests and producer run before use; do not select “latest successful” without binding repository, workflow, ref, and commit.

Masking is not a complete secret control. Avoid command tracing, broad environment export, secrets in matrix/job outputs, pull-request comments, or artifacts. Review third-party actions for input-to-shell injection and unsafe interpolation; pass untrusted values through environment variables and quote them in the target shell.
