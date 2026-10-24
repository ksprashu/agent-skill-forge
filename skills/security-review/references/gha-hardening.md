Read this during manual review (step 4) whenever the change adds or edits anything under `.github/workflows/`, `.github/actions/`, or a composite action. actionlint and zizmor (step 2) produce leads here; this file is how you judge them.

# GitHub Actions hardening

Primary sources:
- GitHub Security Lab, "Keeping your GitHub Actions and workflows secure":
  - Part 1, Preventing pwn requests: <https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/>
  - Part 2, Untrusted input: <https://securitylab.github.com/resources/github-actions-untrusted-input/>
  - Part 3, How to trust your building blocks: <https://securitylab.github.com/resources/github-actions-building-blocks/>
  - Part 4, New vulnerability patterns and mitigation strategies: <https://securitylab.github.com/resources/github-actions-new-patterns-and-mitigations/>
- GitHub Docs:
  - Secure use reference: <https://docs.github.com/en/actions/reference/security/secure-use>
  - Script injections: <https://docs.github.com/en/actions/concepts/security/script-injections>
  - GITHUB_TOKEN: <https://docs.github.com/en/actions/concepts/security/github_token>
  - `permissions` syntax: <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions>
  - OpenID Connect: <https://docs.github.com/en/actions/concepts/security/openid-connect> and reference <https://docs.github.com/en/actions/reference/security/oidc>
  - Events that trigger workflows: <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>
  - Self-hosted runners: <https://docs.github.com/en/actions/concepts/runners/self-hosted-runners>
  - Compromised runners: <https://docs.github.com/en/actions/concepts/security/compromised-runners>
  - Artifact attestations: <https://docs.github.com/en/actions/concepts/security/artifact-attestations>
  - Keeping actions up to date with Dependabot: <https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/auto-update-actions>
- OWASP GitHub Actions Security Cheat Sheet: <https://cheatsheetseries.owasp.org/cheatsheets/GitHub_Actions_Security_Cheat_Sheet.html>
- Linters: actionlint <https://github.com/rhysd/actionlint>, zizmor <https://github.com/zizmorcore/zizmor> (audit list: <https://docs.zizmor.sh/audits/>).

The six-element test still applies. For workflows the lower-trust principal is almost always "anyone who can open a pull request, issue or comment on a public repo" (or a fork contributor), and the crossed boundary is "untrusted code or text runs with the base repository's secrets or write token".

CWE choices: CWE-94 / CWE-78 for script injection, CWE-829 for untrusted actions or checked-out code executing in a privileged context, CWE-250 / CWE-269 for over-broad `permissions`, CWE-494 for unpinned or unverified downloads, CWE-345 for trusting artifacts across workflows.

---

## 1. `pull_request_target` (and `workflow_run`) with an untrusted checkout

`pull_request_target` runs in the context of the base repository: it has secrets and, unless restricted, a write-scoped `GITHUB_TOKEN`. It exists so maintainers can label or comment on fork PRs. Checking out the PR's head and then building, testing or installing it hands that context to the PR author (a "pwn request", Part 1).

What to look for in a diff:
- `on: pull_request_target` combined with `actions/checkout` using `ref: ${{ github.event.pull_request.head.sha }}`, `head.ref`, `refs/pull/.../merge`, or `repository: ${{ github.event.pull_request.head.repo.full_name }}`.
- After such a checkout: `npm install`, `pip install`, `make`, `./gradlew`, running tests, or any local action (`uses: ./...`) — all execute PR-controlled code.
- `on: workflow_run` workflows that download artifacts from the triggering (unprivileged) run and then use them with secrets.
- `issue_comment` triggers that check out the PR on a magic comment without verifying the commenter's permission and pinning the SHA that was reviewed.

Safer shape: run untrusted build and test under `pull_request` (no secrets, read-only token). If a privileged follow-up is needed, have it consume only data (not code) from the unprivileged run, validate that data, and never execute it.

## 2. Script injection via `${{ github.event.* }}`

Expressions are substituted into the `run:` script text before the shell sees it. An attacker-controlled value containing `"; curl ... | sh #` becomes code (Part 2; Docs "Script injections").

Attacker-controlled contexts include `github.event.issue.title`, `.issue.body`, `.pull_request.title`, `.pull_request.body`, `.pull_request.head.ref`, `.pull_request.head.label`, `.comment.body`, `.review.body`, `.review_comment.body`, `.pages.*.page_name`, `.commits.*.message`, `.head_commit.message`, `.head_commit.author.email`, `.head_commit.author.name`, `github.head_ref`, and any `inputs.*` or step outputs derived from them.

What to look for in a diff:
- `run: echo "${{ github.event.pull_request.title }}"` or any `${{ ... }}` from the list above inside `run:`.
- The same inside `actions/github-script`'s `script:` (JavaScript injection), or passed into `with:` of an action that interpolates into a shell.
- Writing untrusted values to `$GITHUB_ENV`, `$GITHUB_OUTPUT` or `$GITHUB_PATH` (environment or path injection into later steps).

Fix: pass the value through an environment variable and quote it in the shell.

```yaml
- env:
    TITLE: ${{ github.event.pull_request.title }}
  run: printf '%s\n' "$TITLE"
```

## 3. Pin third-party actions to a full commit SHA

Tags and branches are mutable; a compromised maintainer or a tag move changes the code you run (Part 3).

What to look for in a diff:
- `uses: owner/action@v4`, `@main`, `@master` for anything outside `actions/*` and your own org (and ideally those too).
- Docker actions using `docker://image:latest`.
- `curl ... | bash` installers, or binaries downloaded without a checksum.

Fix: `uses: owner/action@<40-char SHA> # v4.1.2`, with Dependabot or Renovate configured for `github-actions` so the pins get updated.

## 4. Least-privilege `permissions:`

Without a `permissions:` block the token gets the repository or org default, which can be write-all.

What to look for in a diff:
- New workflows with no top-level `permissions:`.
- `permissions: write-all`, or broad writes (`contents: write`, `packages: write`, `id-token: write`, `actions: write`, `pull-requests: write`) at the workflow level when only one job needs them.
- `actions/checkout` without `persist-credentials: false` in jobs that then run untrusted code or upload the workspace as an artifact (the token is left in `.git/config`).

Fix: `permissions: contents: read` (or `{}`) at the top, and grant the minimum per job.

## 5. OIDC instead of long-lived cloud secrets

OIDC lets a job exchange a short-lived GitHub-signed token for cloud credentials; no stored cloud keys.

What to look for in a diff:
- New `AWS_SECRET_ACCESS_KEY`, `GOOGLE_CREDENTIALS`, `AZURE_CLIENT_SECRET` style secrets where OIDC is available.
- `id-token: write` granted at the workflow level or to jobs that run untrusted code.
- Cloud trust policies (in Terraform or JSON in the same diff) that accept any `sub` from the repo, any branch, or `repo:org/*`. The trust condition should pin repository plus ref or environment (`repo:org/repo:environment:prod`).

## 6. Artifact and cache poisoning

Artifacts and caches written by an unprivileged run can be read by a privileged one (Part 4).

What to look for in a diff:
- `workflow_run` jobs using `actions/download-artifact` (or the API) and then executing, sourcing or extracting the contents into the workspace before privileged steps; extracting archives without path checks (zip slip).
- Caches keyed so that a PR run can write an entry that a default-branch or release run restores.
- Release jobs that publish artifacts built in a job that ran untrusted code.

Fix: treat downloaded artifacts as untrusted data, extract to a temp dir, validate, never execute; build release artifacts in a clean privileged job; add artifact attestations for provenance.

## 7. Self-hosted runners

GitHub's guidance: self-hosted runners should almost never be used for public repositories, because any fork PR can run code on them, and non-ephemeral runners keep state between jobs.

What to look for in a diff:
- `runs-on: self-hosted` (or custom labels) in a workflow triggered by `pull_request`, `pull_request_target`, `issue_comment` or other events from outside contributors on a public repo.
- Persistent runners with cloud instance credentials, Docker socket access or network reach into production.

Fix: GitHub-hosted runners for untrusted events; ephemeral, isolated self-hosted runners (one job per VM or container) restricted to trusted workflows via runner groups.

## 8. Other patterns zizmor and actionlint flag

- Secrets echoed or passed on command lines; `secrets: inherit` to reusable workflows that do not need them.
- `ACTIONS_ALLOW_UNSECURE_COMMANDS` or deprecated `set-env` / `add-path`.
- Overly broad triggers (`on: [push, pull_request_target]` on every branch).
- Unpinned container images in `services:` and `container:`.
- Missing `environment:` protection (required reviewers) on deploy jobs that hold production secrets.
