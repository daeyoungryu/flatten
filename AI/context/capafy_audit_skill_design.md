# Capafy Read-Only Audit Skill — Design Spec

Last updated: 2026-08-11
Status: Design approved, SKILL.md drafted, orchestration implementation not started (Codex handoff pending)
Related: `AI/decisions/adr/ADR-2026-08-11-capafy-audit-skill.md`

## 1. Purpose

flatten was evaluated as a Capafy monetization channel candidate. This spec
defines a **read-only audit product**: a Claude Code Skill that runs
flatten's existing analysis pipeline against a user's codebase and reports
polymorphic-dispatch complexity, rewrite candidates, and safety hazards —
without ever modifying the target codebase.

## 2. Execution Model

Runs entirely inside the user's own local Claude Code session, against the
user's own codebase, in the user's own Python environment. This mirrors the
trust boundary of the user running their own test suite locally — no new
sandbox/isolation infrastructure is introduced. See ADR-2026-08-11 for the
full rationale and the rejected server-side-batch alternative.

## 3. Audit Scope

### 3.1 Allowed commands

| Command | Purpose | Write behavior |
|---|---|---|
| `flatten analyze` | Static dispatch-site discovery, hierarchy extraction | No writes; `--json`/`--format html` write only to the audit output dir |
| `flatten trace` | Runtime observation of an entry point | Executes target code; `--out` writes only to the audit output dir |
| `flatten plan` | Closure verdict + rewrite-candidate plan | Dry-run only; `--out` writes only to the audit output dir |
| `flatten report` | Human-readable summary of a plan | Reads a plan file, writes only to the audit output dir |
| `flatten evaluate` / `flatten benchmark` | Aggregate metrics (optional, if the user wants project-wide scoring) | Writes only to the audit output dir |

### 3.2 Forbidden commands

| Command | Reason |
|---|---|
| `flatten rewrite --apply` | Writes to source files — out of scope for an audit product |
| `flatten rewrite` (dry-run) | Not needed for audit; keeps the command surface minimal and auditable |
| Any `git commit` / `git push` / `git checkout --` / `git clean` | Audit observes only; never mutates repository state |

The Skill instructions enumerate this table explicitly as an allow/deny list.
Any command containing `--apply`, or any `git` subcommand outside `git
status`, must be refused.

## 4. Pipeline

```text
1. Preflight
   - Confirm target is a git repo; capture `git status --porcelain` snapshot (pre)
   - Create isolated output dir: <repo>/.capafy-audit/<timestamp>/
   - Confirm flatten is importable in the active environment

2. Static pass (always runs)
   - flatten analyze <scope> --json --out .capafy-audit/<ts>/analyze.json
   - flatten analyze <scope> --format html --out .capafy-audit/<ts>/analyze.html  (optional, for the summary)

3. Runtime pass (requires explicit user confirmation before executing)
   - Ask user: "This will execute <entry point> in your environment. Continue? (y/n)"
   - flatten trace <scope> --entry <entry> --out .capafy-audit/<ts>/observations.json

4. Planning pass (dry-run only, never --apply)
   - flatten plan <scope> --observations .capafy-audit/<ts>/observations.json --out .capafy-audit/<ts>/plan.json

5. Reporting
   - flatten report .capafy-audit/<ts>/plan.json > .capafy-audit/<ts>/report.json
   - Render .capafy-audit/<ts>/summary.md from report.json (see §6)

6. Postflight
   - Capture `git status --porcelain` snapshot (post)
   - Diff pre/post snapshots; if non-empty, warn the user immediately and
     surface the diff (do not silently continue)
```

Step 3 (runtime trace) is the only step that executes target code and is
therefore the only step gated behind an explicit per-run user confirmation.
Steps 1, 2, 4, 5, 6 never execute target code and never require confirmation.

## 5. Read-Only Guarantee

"Read-only" is scoped precisely to **filesystem writes to the target
repository**, not to code execution (see ADR §Context for why code execution
isolation is out of scope). Guarantee mechanisms:

1. **Output isolation** — every artifact the Skill produces goes under
   `<repo>/.capafy-audit/<timestamp>/`, never into the source tree. This
   directory is gitignore-able and disposable.
2. **Command whitelist** — the Skill instructions hardcode the allowed
   command table (§3.1) and an explicit refusal rule for anything matching
   `--apply` or a write-capable `git` subcommand.
3. **Pre-execution confirmation gate** — `trace` is the only step that runs
   target code; it requires an explicit per-invocation user confirmation.
4. **git status diff safety net** — pre/post `git status --porcelain`
   snapshots catch any unintended filesystem mutation caused by side effects
   inside the traced entry point, even ones the Skill itself didn't cause.
5. **Entry point guidance** — the Skill recommends pointing `trace` at an
   existing test-suite entry point (known, bounded side effects) over an
   arbitrary `main()`, and surfaces this recommendation to the user before
   the confirmation prompt.

## 6. Output Format

Two artifacts per audit run, both under `.capafy-audit/<timestamp>/`:

- **`report.json`** — machine-readable. Reuses flatten's existing
  dataclass-backed report schema (call-site counts, CLOSED/OPEN/UNSAFE
  verdict breakdown, confidence scores, proof-artifact references). This is
  what a Capafy dashboard/backend would ingest.
- **`summary.md`** — human-readable. Generated from `report.json`:
  - Headline: total call sites, CLOSED-candidate count, UNSAFE count
  - Top-N riskiest UNSAFE findings (file:line, hazard category)
  - Top-N rewrite candidates (file:line, confidence)
  - One-paragraph plain-language verdict

## 7. Error Handling

- flatten not importable in the active environment → stop before step 2,
  report the missing dependency, do not attempt to install anything
  automatically.
- `analyze`/`trace`/`plan` non-zero exit → stop the pipeline at that step,
  surface stderr verbatim in the summary, do not proceed to later steps with
  partial state.
- Target is not a git repository → skip the git-status safety net (§5.4) but
  warn the user explicitly that the safety net is unavailable before running
  `trace`.
- Post-run git diff is non-empty → treat as a hard warning surfaced at the
  top of `summary.md`, not a silent log line.

## 8. Implementation Split

Design and the `SKILL.md` draft are authored directly (this stage). Actual
code — the orchestration script that sequences steps 1–6, output-directory
management, and the `summary.md` renderer — is delegated to Codex via
`AI/tasks/codex_capafy_audit_orchestration.md`.

## 9. Out of Scope (this stage)

- Capafy-side billing/entitlement integration.
- Server-side batch execution (rejected in ADR-2026-08-11; may be revisited
  as a separate ADR if Capafy later needs a no-local-environment offering).
- Multi-language support (flatten is Python-only).
- Automatic dependency installation for the target project.
