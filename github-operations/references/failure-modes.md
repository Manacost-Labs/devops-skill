# GitHub control-plane failure modes

Cases where a successful call, a green status, or an existing rule does not mean
the control is applied or effective. Verify against these before reporting
`verified`.

1. **Ruleset created but not enforcing.** A ruleset saved with enforcement
   `evaluate` (or `disabled`) records evaluations without blocking anything. A
   201 from the rulesets API proves existence, not enforcement. Verify the
   `enforcement` field and a denied action.
2. **Bypass list voids the rule.** A ruleset or protection with organization
   admins, an app, or a deploy key in its bypass list does not constrain those
   actors. Audits must enumerate bypass actors, not just rules.
3. **Admin bypass on classic protection.** Unless enforcement is extended to
   admins, repository admins can merge or push around classic branch protection,
   and `gh pr merge --admin` makes it a one-liner. Protection for admins is a
   separate setting to verify.
4. **Required status check waits on a renamed job.** Required checks match by
   check-run name. Renaming the job in the workflow leaves the protection
   requiring a check that will never report again: merges hang on "Expected"
   rather than failing loudly, and removing the stale requirement silently drops
   the gate.
5. **Environment gates apply only to jobs that reference the environment.** A
   job without an `environment:` key is not gated by any environment protection
   rule or required reviewer. Adding reviewers to an environment proves nothing
   about workflows that skip it.
6. **`pull_request_target` runs untrusted changes with base-repository
   authority.** The trigger exists for label/comment automation; combined with a
   checkout of the PR head it hands fork code a write-capable token. A green run
   here can itself be the incident.
7. **Fork PR token looks like a pass.** Fork `pull_request` runs get a read-only
   token and no secrets, so a "successful" fork CI run does not prove the
   workflow works with real permissions, and a maintainer re-run in base context
   changes the trust situation entirely.
8. **Self-hosted runner persistence.** Self-hosted runners have no clean-VM
   guarantee; untrusted workflow code can persist on the host and poison later
   privileged jobs. A runner that ever executed untrusted code is not a trusted
   runner because its last job succeeded.
9. **Actions cache poisoning across branches.** Caches restored by key can be
   seeded from a less-trusted branch context and consumed by a privileged
   workflow. A cache hit is not provenance.
10. **Release tags are mutable references.** A release can be deleted and its
    tag force-moved to different content while the release URL and name stay
    stable. Consumers pinned to a tag, not a digest, can receive substituted
    artifacts. Treat moving a published tag as R4.
11. **Deleted repository names can be re-registered.** After a repository is
    deleted or transferred without a retained redirect owner, its name can be
    claimed by someone else, and stale references (submodules, actions
    `uses:`, install scripts) resolve to the new owner's content.
12. **Org-level policy changes effective state without touching the repo.** An
    organization ruleset, Actions policy, or default-permission change alters
    what a repository enforces with no event in that repository's settings
    history. Re-read effective state at both levels before and after a change.

Sources: `https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets`,
`https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches`,
`https://docs.github.com/en/actions/reference/security/secure-use`,
`https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners`,
`https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases`.
