# GitHub repository settings checklist

Repository files can recommend these controls but cannot prove that GitHub enforces them. The owner must configure and verify each item after the remote repository exists. Current intended repository owner: @Shpuntyara.

## Before pushing project content publicly

- [ ] Confirm the final repository organization/name, visibility, default branch, legal/IP owner, and license attribution.
- [ ] Build a fresh tree with `python tools/build_public_source.py --output ..\devops-skill-platform-public`; review its manifest and full initial commit instead of publishing private Git history.
- [ ] Review the exported file list for credentials, customer data, live hostnames/IPs, private inventory, evidence, archives, and target-specific administration scripts.
- [ ] Create the public remote without pushing the project source. GitHub private vulnerability reporting is a public-repository feature.
- [ ] Under **Settings > Security > Private vulnerability reporting**, enable private vulnerability reporting.
- [ ] In a private/incognito session, verify that **Security > Report a vulnerability** opens a private advisory draft. Do not submit sensitive test data.
- [ ] Push no project source or release asset if that reporting path is absent or unverified; keep the source local or in an access-controlled private repository.
- [ ] Enable the dependency graph and Dependabot alerts. Enable secret scanning and push protection where the repository plan makes them available.

## Actions policy

- [ ] Under **Settings > Actions > General**, restrict allowed actions to GitHub-authored actions and any separately reviewed full-SHA exceptions.
- [ ] Set default workflow token permissions to **Read repository contents and packages**.
- [ ] Disable **Allow GitHub Actions to create and approve pull requests**.
- [ ] Require approval before workflows from fork pull requests run; do not expose secrets or privileged self-hosted runners to fork code.
- [ ] Use GitHub-hosted runners for this public validation baseline. Do not attach a persistent production-network runner.
- [ ] Review every Dependabot action update before merging and retain full 40-character SHA pins with human-readable version comments.

The repository workflows declare empty permissions globally and grant only contents: read to jobs that need source or dependency metadata. They contain no pull_request_target, write permission, environment, custom secret, or OIDC path.

## Protect main

Create a ruleset or branch protection rule targeting main:

- [ ] Require pull requests before merging and dismiss stale approvals after new commits.
- [ ] Require review from Code Owners.
- [ ] Require conversation resolution.
- [ ] Block force pushes and branch deletion.
- [ ] Require branches to be up to date before merge, unless a merge queue with equivalent checks is configured.
- [ ] Require these checks only after their exact names have completed successfully at least once:
  - Python 3.13 / ubuntu-24.04
  - Python 3.13 / windows-2025
  - Dependency review
- [ ] Do not require the manual Verify 0.3.0 RC candidate job for ordinary pull requests.

CODEOWNERS currently names one account. That is enough to route portfolio maintenance review, but it does not implement separation of duties. Production or enterprise use requires adding a second qualified identity and configuring the ruleset so the author cannot satisfy their own required approval.

## Tags and releases

- [ ] Protect tags matching v* against deletion and unauthorized update.
- [ ] Allow only the release owner to create RC tags/releases.
- [ ] Mark -rc.N releases as prereleases and record the reviewed source SHA and exact archive digest.
- [ ] Do not claim signing, provenance, SBOM coverage, vulnerability clearance, or production readiness until corresponding evidence is attached and independently verified.
- [ ] Keep release prep manual and read-only. It prepares evidence but does not publish an artifact or release.

## Verification record

For each settings review, record the repository URL, settings reviewer identity, timestamp, ruleset/export or sanitized screenshots, successful check run URLs, private-reporting test result, limitations, and next review date. Screenshots and policy prose show design intent; periodic repository/API evidence is required to show continuing enforcement.
