---
name: capafy-audit
description: Read-only polymorphic-dispatch audit of a Python codebase using flatten's analyze/trace/plan/report pipeline. Trigger on "capafy audit", "flatten audit", "감사 실행", or a request to audit dispatch safety/rewrite candidates without modifying source. Never writes to the target repository.
---

# Capafy Read-Only Audit

Runs flatten's existing analysis pipeline (`analyze` → `trace` → `plan` →
`report`) against a user's Python codebase and produces a dispatch-safety
audit report. **This skill never modifies the target repository.**

Full design rationale: `AI/context/capafy_audit_skill_design.md` and
`AI/decisions/adr/ADR-2026-08-11-capafy-audit-skill.md`.

## Hard rules (do not deviate)

1. **Never run `flatten rewrite`, with or without `--apply`.** This skill
   is audit-only. If the user asks for an actual rewrite, tell them that's a
   separate flatten operation outside this skill's scope and stop.
2. **Never run a `git` subcommand other than `git status`.** No commit, no
   push, no checkout, no clean, no stash.
3. **All output goes under `<repo>/.capafy-audit/<timestamp>/`.** Never pass
   `--out` pointing anywhere inside the source tree.
4. **Never execute target code without asking first.** Step 3 below (trace)
   is the only step that runs the target codebase's code. Get an explicit
   yes from the user immediately before that command, every run — do not
   reuse a prior confirmation.
5. If any command in this skill would need a flag or argument not listed
   below, stop and ask the user rather than improvising.

## Preconditions

- Confirm the target is a git repository (`git rev-parse --is-inside-work-tree`).
  If not, warn the user that the git-status safety net (step 6) will be
  unavailable, and get confirmation before continuing.
- Confirm `flatten` is importable in the active Python environment
  (`python -c "import flatten"`). If it isn't, stop and tell the user to
  install it — do not attempt to install it yourself.

## Steps

### 1. Preflight

```
git status --porcelain            # capture as PRE_SNAPSHOT
mkdir -p .capafy-audit/<timestamp>
```

### 2. Static pass (no confirmation needed — does not execute target code)

```
flatten analyze <scope> --json --out .capafy-audit/<timestamp>/analyze.json
```

### 3. Runtime pass — REQUIRES CONFIRMATION

Ask the user: *"This will execute `<entry point>` in your current
environment to collect runtime observations. Continue? (y/n)"*

Prefer an existing test-suite entry point over an arbitrary `main()` when
one is available — it has more predictable side effects. Only proceed on an
explicit yes.

```
flatten trace <scope> --entry <entry> --out .capafy-audit/<timestamp>/observations.json
```

### 4. Planning pass (dry-run only)

```
flatten plan <scope> --observations .capafy-audit/<timestamp>/observations.json --out .capafy-audit/<timestamp>/plan.json
```

### 5. Reporting

```
flatten report .capafy-audit/<timestamp>/plan.json > .capafy-audit/<timestamp>/report.json
```

Then render `.capafy-audit/<timestamp>/summary.md` from `report.json`:
- Headline counts: total call sites, CLOSED-candidate count, UNSAFE count
- Top findings: riskiest UNSAFE items (file:line, hazard category)
- Top rewrite candidates (file:line, confidence) — reported only, never applied
- One short plain-language verdict paragraph

### 6. Postflight — safety net

```
git status --porcelain            # capture as POST_SNAPSHOT
```

If `POST_SNAPSHOT` differs from `PRE_SNAPSHOT`, this is a hard warning: show
the diff to the user at the top of the summary, immediately. Do not bury it.
This should only ever be triggered by side effects inside the traced entry
point (step 3) — if it fires, say so explicitly.

## On any command failure

Stop the pipeline at the failing step. Show the command's stderr verbatim.
Do not proceed to later steps with partial state, and do not retry with
different flags on your own judgment — ask the user how they want to
proceed.

## Output

Two files under `.capafy-audit/<timestamp>/`:
- `report.json` — machine-readable, flatten's existing report schema
- `summary.md` — human-readable summary as described in step 5

Tell the user both paths when the run completes.
