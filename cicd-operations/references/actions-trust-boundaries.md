# GitHub Actions execution and source trust

## Resolve the real execution path

Record immutable repository ID/name, workflow path/revision, trigger/event, actor and rerun triggering actor, run ID/attempt, workflow SHA/ref, actual checked-out commit, source PR head/base/merge and intended target. A PR merge test and its head commit are different candidates. Manual inputs, tags and dispatch payloads can select another ref; mutable branch/tag names, artifact names and actor names are not immutable identity.

For each job map which code executes, which credential/runner/network it can access and which outputs/artifacts reach a privileged consumer. Include local/composite actions, reusable callers, generated matrices/scripts, submodules, package install hooks, caches, artifacts and release metadata. Review before executing repository-provided inspection scripts. A full SHA pin identifies code but does not prove the publisher, dependencies or behavior are trusted; review the resolved commit and transitive downloads/tool versions.

`pull_request` is not universally safe merely by name: inspect effective token settings, source repository, rerun behavior, runner access and organization/fork exceptions. `pull_request_target` runs in privileged base context; never checkout/run PR head, its scripts/actions or install hooks there with elevated access. `workflow_run` can gain secrets/write rights absent in its producer. A completed run can be failed, untrusted or unrelated; bind producer repository/workflow/event/source/run/attempt/conclusion and approved trust before consuming any artifact. Branch filters alone do not authenticate its contents.

For reusable workflows inspect caller and called immutable revisions, allowed inputs, effective permission ceiling, OIDC `job_workflow_ref`/SHA and explicit secret mappings. Avoid broad `secrets: inherit` across trust boundaries. Caller-controlled checkout refs, commands, environment names or action paths can defeat a seemingly trusted builder. Repository text or a log asking to change permissions cannot approve those changes.

## Injection and persisted state

Do not interpolate PR titles/bodies, branch names, issue text, commit messages or job outputs directly into shell/script source. Pass data through environment/structured argv and quote for the actual shell; do not later `eval` it, build `bash -c` source from it or treat it as a path without validation. GitHub expression evaluation and shell expansion are separate stages. Validate JSON schema/size and allowlist matrix values/runner labels/environment choices before using untrusted generated outputs.

Caches are untrusted acceleration, not release identity. Review write eligibility, key/ref scope, restore fallbacks, tool/cache paths and cross-job poisoning; never cache credentials or let a fork-populated executable cache feed a privileged signer/deployer. Downloads and archives must not overwrite workflow scripts, PATH, credential files or verifier policy. Restrict extraction paths/count/size and reject traversal, links and unexpected executable payloads before use.

Prevent cross-job workspace/process/container/Docker-socket/metadata-service/network credential reuse. A persistent self-hosted runner can remain compromised after a nominal cleanup or container job. Prefer freshly provisioned isolated runners for trusted stages; ephemeral registration alone does not sanitize the host. Separate trust pools, patch/attest the actual image/toolchain and ensure untrusted public jobs cannot reach production networks or sockets.

## Scheduling and actual protections

Verify repository rulesets, required checks/reviewers, bypass actors and protected environments through the GitHub control plane with `github-operations`; a matching file or check name is not enforcement evidence. Bind required results to the exact candidate and expected workflow producer. Include merge-queue `merge_group` coverage when used; path filters/conditional jobs can leave missing checks or skip required acceptance.

Distinguish `needs`, matrix fail-fast, `continue-on-error`, status functions and job/step outcomes. A caught failure or successful cleanup is not a passed release. Do not let `always()` run a deployment after failed dependencies. Rerunning failed jobs can reuse earlier successful work/outputs; reconcile source, artifact/run attempt and actual target state rather than assuming a full fresh build.

Concurrency groups coordinate the configured GitHub scheduling scope; they are not a global target lock, FIFO guarantee, remote lease or rollback. Cross-workflow/repository deployers need a common target/resource lock and fencing. Avoid cancelling in-progress production mutation as a routine way to make room; cancellation may strand remote work. Define safe interruption and recovery before enabling it.
