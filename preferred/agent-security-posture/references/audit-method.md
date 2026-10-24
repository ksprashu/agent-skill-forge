# Audit Method: Findings, Verdicts and Severity

Read this when you triage a finding, decide whether to block, or write up a security result.

Adapted from Cloudflare's `security-audit` skill (MIT, © 2025-2026 Cloudflare, Inc.), pinned at commit `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`: <https://github.com/cloudflare/security-audit-skill/tree/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit>. The principles are condensed here; the six-phase audit workflow, its schemas and validators stay upstream.

## When to use the full Cloudflare workflow instead

This skill keeps a coding session safe. It is not a full audit. When the user explicitly asks to audit or pen-test a codebase, or wants a complete report, use Cloudflare's skill, which runs reconnaissance, coverage-led hunting, independent validation and schema-checked reporting:

```bash
npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit
```

Installing it is a new tool, so it needs the user's approval (see SKILL.md, "What needs the user's approval").

## A finding needs a boundary and a result

For every candidate, name all six:

1. the lower-trust principal (who acts),
2. the input or action they control,
3. the control that should stop them,
4. the boundary crossed,
5. the principal or resource affected, and
6. the concrete result, observed or observable by the owner.

If you can't fill one in, it isn't a finding yet. A missing best practice, a guessed deployment behaviour, a crash with no security effect, or harm only to the actor themselves is not a vulnerability.

**Defence in depth is not a vulnerability.** If layer A already prevents the attack, the absence of layer B is a hardening note, not a finding.

## Three verdicts

| Verdict | Means | Severity |
|---|---|---|
| `confirmed` | Complete source trace plus a bounded observed result | Yes |
| `needs_validation` | A source-grounded hypothesis blocked on one exact missing fact (a deployment setting, proxy behaviour, identity policy). State the fact and a safe way for the owner to check it | **No** |
| `rejected` | Disproved; record why so it isn't rediscovered | No |

`needs_validation` is not "low-confidence confirmed". Don't attach a severity to it. Independent safe work carries on, but a specific action that depends on the unresolved fact stays paused until the fact is checked: not being able to test something safely is never permission to go ahead.

## Severity, for confirmed findings only

Likelihood times impact, capped by the impact you actually demonstrated.

- **Critical**: an unauthenticated actor gains code execution, full data-store access, or takeover of arbitrary accounts.
- **High**: an explicit security control is fully defeated with real consequences: authentication bypass, cross-tenant read or write, stored script execution affecting other users, authenticated code execution, an unauthenticated remote stop of a shared service.
- **Medium**: a real boundary violation with limited blast radius, uncommon preconditions, or a narrow set of affected resources.
- **Low**: disclosure of non-secret internals, or an effect that needs sustained effort for little gain.
- **Informational**: confirmed but minimal; mainly useful as a step in a larger chain.

The high/medium test: does the result *fully defeat* a control on an action with real consequences, or only weaken it? If you can't state the concrete damage, the severity is lower than it feels.

Use this to decide what blocks: stop the specific unsafe action for a confirmed critical or high; note medium and low and carry on.

## The checker is never the finder

Whoever found a candidate doesn't confirm it. Give it to a fresh agent or a fresh pass whose job is to disprove it. Where the harness has sub-agents, use one; otherwise re-check from the source with the claim stated as a hypothesis.

## Evidence stays local and minimal

- Source inspection is read-only.
- Run target code (builds, tests, fixtures) only in a sandbox with no external network, an allowlisted environment, a read-only target, writes limited to a scratch directory, and CPU, memory, disk and time limits. If you can't enforce all of that, don't execute: record `needs_validation` with the missing control.
- Use dummy principals, fixtures and secrets. Never probe deployed endpoints, shared infrastructure, production identities or other users' data. Stop at the minimum effect that shows the defect.
- Don't install dependencies or let a build fetch them during a check.

## Fix the invariant, not the symptom

For each confirmed finding, name the invariant the code must enforce and the narrowest change that enforces it at the last trusted decision point. Prefer a specific file-level change plus a regression test over generic hardening advice.

## Anti-patterns

1. Presenting a checklist deviation as a vulnerability.
2. Defence-in-depth advice with no reachable boundary violation.
3. Testing against live or shared environments when local evidence would do.
4. Guessing provider, proxy, browser, identity or deployment behaviour that isn't in source.
5. Treating a user's own authority over their own data as a cross-boundary result.
6. Reporting a stronger effect than the one observed.
7. Giving `needs_validation` items a severity.
8. Writing the report before the findings are independently checked.
