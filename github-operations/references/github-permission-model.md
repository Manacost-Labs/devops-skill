# GitHub permission model for bounded operations

Authority on GitHub comes from four different credential shapes. Confirm which one
is in use before planning any change, because each fails differently and each is
audited differently.

## Credential shapes

| Shape | Scope model | Operational notes |
|---|---|---|
| `GITHUB_TOKEN` (Actions) | Per-workflow-run token, permissions set by the workflow `permissions:` block and repository/organization defaults | Dies with the run. Cannot administer most repository settings. Fork PRs receive a read-only variant; `pull_request_target` runs in the base context with base permissions. |
| Fine-grained PAT | Explicit per-repository and per-permission grants with expiry | Preferred for bounded human-delegated automation. Organization owners can require approval before a fine-grained PAT can access org repositories. |
| Classic PAT | Coarse scopes (`repo`, `admin:org`, ...) | A `repo` scope grants write to every repository the user can reach. Treat as over-broad; prefer replacement over reuse. |
| GitHub App installation | Permissions declared by the app, granted per installation, short-lived installation tokens | Best audit trail for standing automation. Installation tokens expire; do not persist them. |

## Rules that follow from the model

- The identity that executes a change is the identity that appears in the audit
  log. Never run an approved operation with a broader credential than the one the
  approval names.
- Repository admin (or an org owner) can bypass classic branch protection unless
  "do not allow bypassing the above settings" / equivalent enforcement is set, and
  `gh pr merge --admin` exists precisely to do this. An admin credential in an
  automation context therefore voids most protection guarantees; scope automation
  below admin wherever possible.
- Rulesets carry their own bypass lists (actors, roles, apps, deploy keys). A
  protection audit that does not enumerate bypass actors has not audited the
  control.
- Organization-level rulesets and policies override or extend repository
  settings; a repository-level read cannot prove the effective control set.
  Discover both levels before asserting what is enforced.
- Workflow-level `permissions:` should default to none or read-only, with
  per-job elevation. This module treats a request to broaden default workflow
  permissions as a protection change (at least R3), not a convenience edit.
- Deploy keys are per-repository SSH credentials with optional write; they do not
  appear in collaborator lists. Include them in access reviews.

Refresh `https://docs.github.com/en/rest` and the operation-specific page before
any permission change; API fields and ruleset semantics evolve.
