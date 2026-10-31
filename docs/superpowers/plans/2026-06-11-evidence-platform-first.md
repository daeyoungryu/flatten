# Evidence Platform First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-grade evidence platform slice for `flatten`: reproducible evaluation metrics, behavior comparison, proof classification, and JSON/HTML reporting.

**Architecture:** Keep the existing rewrite pipeline intact and add evidence modules around it. The new `flatten.evaluation` module owns benchmark metrics and report records, `flatten.comparator` owns behavior comparison as a stable public API, and `flatten.proofs` owns SAFE/UNSAFE/UNKNOWN classification consumed by planner/reporting. CLI integration should expose evidence without increasing rewrite aggressiveness.

**Tech Stack:** Python 3.10+, dataclasses, stdlib JSON/pathlib/time, existing LibCST pipeline, pytest, Hypothesis for property tests.

---

## File Structure

- Create `src/flatten/evaluation.py`
  - Owns `EvaluationCounts`, `EvaluationMetrics`, `EvaluationResult`, and JSON serialization.
  - Converts call sites, rewrite decisions, and optional labeled expected outcomes into reproducible metrics.
- Create `src/flatten/comparator.py`
  - Owns `BehaviorComparator`, `BehaviorComparisonResult`, and `BehaviorMismatch`.
  - Wraps existing `flatten.harness.capture_behavior` and `assert_modules_equivalent_subprocess` behavior into a reusable public API.
- Create `src/flatten/proofs.py`
  - Owns `ProofStatus`, `ProofEvidence`, and `classify_rewrite_decision`.
  - Maps current `RewriteDecision` plus closure evidence to SAFE, UNSAFE, or UNKNOWN.
- Modify `src/flatten/contracts.py`
  - Add optional proof metadata to `RewriteDecision` JSON without breaking existing tests.
- Modify `src/flatten/planner.py`
  - Attach proof metadata to rewrite decisions and ensure non-SAFE decisions never emit plans.
- Modify `src/flatten/cli.py`
  - Add `flatten evaluate` for file-level evaluation JSON.
  - Add `--evidence` to `report` to print proof status/reasons where available.
- Modify `src/flatten/report.py`
  - Add HTML helpers for proof/evaluation output.
- Create `tests/test_evaluation.py`
  - Unit tests for counts and metrics.
- Create `tests/test_comparator.py`
  - Unit tests for return/stdout/stderr/exception/effect comparison.
- Create `tests/test_proofs.py`
  - Unit tests for SAFE/UNSAFE/UNKNOWN classification and planner gating.
- Create `tests/test_evidence_cli.py`
  - CLI smoke tests for `evaluate` and evidence report output.
- Modify `docs/architecture.md`
  - Principal Engineer review document with pipeline, public API, current limits, false positive/negative risks, and unsupported Python features.
- Modify `docs/claim_test_map.md`
  - Add claims for evaluation metrics, behavior comparator, and proof gating.

## Task 1: Evaluation Data Model

**Files:**
- Create: `src/flatten/evaluation.py`
- Test: `tests/test_evaluation.py`

- [ ] **Step 1: Write failing metric tests**

Add to `tests/test_evaluation.py`:

```python
from flatten.evaluation import EvaluationCounts, LabeledOutcome, compute_metrics


def test_evaluation_counts_derive_rates_from_labeled_outcomes():
    counts = EvaluationCounts(
        total_call_sites=5,
        candidate_call_sites=4,
        rewritten_call_sites=2,
        rejected_call_sites=2,
        unsafe_call_sites=1,
        unknown_call_sites=1,
    )
    outcomes = [
        LabeledOutcome(expected_safe=True, rewritten=True),
        LabeledOutcome(expected_safe=True, rewritten=False),
        LabeledOutcome(expected_safe=False, rewritten=True),
        LabeledOutcome(expected_safe=False, rewritten=False),
    ]

    metrics = compute_metrics(counts, outcomes)

    assert metrics.counts == counts
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.false_negative_rate == 0.5


def test_evaluation_metrics_json_is_stable():
    counts = EvaluationCounts(
        total_call_sites=1,
        candidate_call_sites=1,
        rewritten_call_sites=0,
        rejected_call_sites=1,
        unsafe_call_sites=0,
        unknown_call_sites=1,
    )

    payload = compute_metrics(counts, []).to_json()

    assert payload["counts"]["total_call_sites"] == 1
    assert payload["precision"] is None
    assert payload["recall"] is None
    assert payload["false_positive_rate"] is None
    assert payload["false_negative_rate"] is None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_evaluation.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'flatten.evaluation'`.

- [ ] **Step 3: Implement evaluation module**

Create `src/flatten/evaluation.py`:

```python
"""Reproducible evaluation metrics for flatten rewrite decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationCounts:
    total_call_sites: int = 0
    candidate_call_sites: int = 0
    rewritten_call_sites: int = 0
    rejected_call_sites: int = 0
    unsafe_call_sites: int = 0
    unknown_call_sites: int = 0

    def to_json(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class LabeledOutcome:
    expected_safe: bool
    rewritten: bool


@dataclass(frozen=True)
class EvaluationMetrics:
    counts: EvaluationCounts
    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    false_negative_rate: float | None

    def to_json(self) -> dict[str, Any]:
        return {
            "counts": self.counts.to_json(),
            "precision": self.precision,
            "recall": self.recall,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
        }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def compute_metrics(
    counts: EvaluationCounts,
    outcomes: list[LabeledOutcome],
) -> EvaluationMetrics:
    true_positive = sum(1 for item in outcomes if item.expected_safe and item.rewritten)
    false_positive = sum(1 for item in outcomes if not item.expected_safe and item.rewritten)
    false_negative = sum(1 for item in outcomes if item.expected_safe and not item.rewritten)
    true_negative = sum(1 for item in outcomes if not item.expected_safe and not item.rewritten)
    return EvaluationMetrics(
        counts=counts,
        precision=_rate(true_positive, true_positive + false_positive),
        recall=_rate(true_positive, true_positive + false_negative),
        false_positive_rate=_rate(false_positive, false_positive + true_negative),
        false_negative_rate=_rate(false_negative, false_negative + true_positive),
    )
```

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/test_evaluation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/flatten/evaluation.py tests/test_evaluation.py
git commit -m "feat: add evaluation metrics model"
```

## Task 2: Build Evaluation From Pipeline Artifacts

**Files:**
- Modify: `src/flatten/evaluation.py`
- Test: `tests/test_evaluation.py`

- [ ] **Step 1: Write failing artifact aggregation test**

Append to `tests/test_evaluation.py`:

```python
from flatten.contracts import ClosureStatus, RewriteDecision
from flatten.discovery import discover_call_sites
from flatten.evaluation import evaluate_artifacts


def test_evaluate_artifacts_counts_call_sites_and_decisions():
    source = """
class A:
    def run(self):
        return 1

def main(a):
    return a.run()
"""
    call_sites = discover_call_sites(source, filename="case.py")
    decisions = [
        RewriteDecision(
            method_qualname="A.run",
            allowed=False,
            status=ClosureStatus.UNSAFE,
            blockers=("UNSAFE: monkey patch",),
            reason_code="UNSAFE_MONKEY_PATCH",
        )
    ]

    result = evaluate_artifacts(call_sites, decisions)

    assert result.counts.total_call_sites == 1
    assert result.counts.candidate_call_sites == 1
    assert result.counts.rewritten_call_sites == 0
    assert result.counts.rejected_call_sites == 1
    assert result.counts.unsafe_call_sites == 1
    assert result.counts.unknown_call_sites == 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_evaluation.py::test_evaluate_artifacts_counts_call_sites_and_decisions -q`

Expected: FAIL with missing `evaluate_artifacts`.

- [ ] **Step 3: Implement artifact aggregation**

Add to `src/flatten/evaluation.py`:

```python
from collections.abc import Sequence

from flatten.contracts import ClosureStatus, RewriteDecision


def evaluate_artifacts(
    call_sites: Sequence[object],
    rewrite_decisions: Sequence[RewriteDecision],
    outcomes: list[LabeledOutcome] | None = None,
) -> EvaluationMetrics:
    rewritten = sum(1 for decision in rewrite_decisions if decision.allowed)
    rejected = sum(1 for decision in rewrite_decisions if not decision.allowed)
    unsafe = sum(
        1 for decision in rewrite_decisions if decision.status is ClosureStatus.UNSAFE
    )
    unknown = sum(
        1 for decision in rewrite_decisions if decision.status is ClosureStatus.UNKNOWN
    )
    counts = EvaluationCounts(
        total_call_sites=len(call_sites),
        candidate_call_sites=len(rewrite_decisions),
        rewritten_call_sites=rewritten,
        rejected_call_sites=rejected,
        unsafe_call_sites=unsafe,
        unknown_call_sites=unknown,
    )
    return compute_metrics(counts, outcomes or [])
```

- [ ] **Step 4: Run evaluation tests**

Run: `python -m pytest tests/test_evaluation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/flatten/evaluation.py tests/test_evaluation.py
git commit -m "feat: evaluate rewrite pipeline artifacts"
```

## Task 3: Behavior Comparator API

**Files:**
- Create: `src/flatten/comparator.py`
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Write failing comparator tests**

Create `tests/test_comparator.py`:

```python
import sys

from flatten.comparator import BehaviorComparator


def test_behavior_comparator_reports_equivalent_return_and_streams():
    def left(value):
        print("out")
        print("err", file=sys.stderr)
        return value + 1

    def right(value):
        print("out")
        print("err", file=sys.stderr)
        return value + 1

    result = BehaviorComparator().compare(left, right, [((1,), {})])

    assert result.equivalent is True
    assert result.mismatches == []


def test_behavior_comparator_reports_exception_message_mismatch():
    def left():
        raise ValueError("left")

    def right():
        raise ValueError("right")

    result = BehaviorComparator().compare(left, right, [((), {})])

    assert result.equivalent is False
    assert result.mismatches[0].field == "exception"
    assert "left" in result.mismatches[0].original
    assert "right" in result.mismatches[0].transformed
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_comparator.py -q`

Expected: FAIL with missing `flatten.comparator`.

- [ ] **Step 3: Implement comparator**

Create `src/flatten/comparator.py`:

```python
"""Behavior comparison API for original and rewritten callables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flatten.harness import BehaviorObservation, capture_behavior


@dataclass(frozen=True)
class BehaviorMismatch:
    case_index: int
    field: str
    original: str
    transformed: str


@dataclass(frozen=True)
class BehaviorComparisonResult:
    equivalent: bool
    cases: int
    mismatches: list[BehaviorMismatch]

    def to_json(self) -> dict[str, Any]:
        return {
            "equivalent": self.equivalent,
            "cases": self.cases,
            "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
        }


class BehaviorComparator:
    def compare(
        self,
        original: Callable[..., Any],
        transformed: Callable[..., Any],
        cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
    ) -> BehaviorComparisonResult:
        mismatches: list[BehaviorMismatch] = []
        for index, (args, kwargs) in enumerate(cases):
            left = capture_behavior(original, *args, **kwargs)
            right = capture_behavior(transformed, *args, **kwargs)
            mismatches.extend(_compare_observation(index, left, right))
        return BehaviorComparisonResult(
            equivalent=not mismatches,
            cases=len(cases),
            mismatches=mismatches,
        )


def _compare_observation(
    index: int,
    original: BehaviorObservation,
    transformed: BehaviorObservation,
) -> list[BehaviorMismatch]:
    mismatches: list[BehaviorMismatch] = []
    if original.outcome != transformed.outcome:
        return [
            BehaviorMismatch(index, "outcome", original.outcome, transformed.outcome)
        ]
    if original.outcome == "raise":
        left = f"{original.exception_type}: {original.exception_message}"
        right = f"{transformed.exception_type}: {transformed.exception_message}"
        if left != right:
            mismatches.append(BehaviorMismatch(index, "exception", left, right))
    elif original.value != transformed.value:
        mismatches.append(
            BehaviorMismatch(index, "return", repr(original.value), repr(transformed.value))
        )
    if original.effects != transformed.effects:
        mismatches.append(
            BehaviorMismatch(index, "effects", repr(original.effects), repr(transformed.effects))
        )
    return mismatches
```

- [ ] **Step 4: Run comparator tests**

Run: `python -m pytest tests/test_comparator.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/flatten/comparator.py tests/test_comparator.py
git commit -m "feat: add behavior comparator api"
```

## Task 4: Proof Classification Layer

**Files:**
- Create: `src/flatten/proofs.py`
- Modify: `src/flatten/contracts.py`
- Test: `tests/test_proofs.py`

- [ ] **Step 1: Write failing proof tests**

Create `tests/test_proofs.py`:

```python
from flatten.contracts import ClosureStatus, RewriteDecision
from flatten.proofs import ProofStatus, classify_rewrite_decision


def test_closed_allowed_decision_with_evidence_is_safe():
    decision = RewriteDecision(
        method_qualname="A.run",
        allowed=True,
        status=ClosureStatus.CLOSED,
        evidence=("receiver uniquely identified", "dynamic dispatch resolved"),
    )

    proof = classify_rewrite_decision(decision)

    assert proof.status is ProofStatus.SAFE
    assert "receiver uniquely identified" in proof.evidence


def test_unknown_decision_is_never_safe():
    decision = RewriteDecision(
        method_qualname="A.run",
        allowed=False,
        status=ClosureStatus.UNKNOWN,
        blockers=("type restoration failed",),
    )

    proof = classify_rewrite_decision(decision)

    assert proof.status is ProofStatus.UNKNOWN
    assert "type restoration failed" in proof.reasons


def test_unsafe_decision_is_unsafe():
    decision = RewriteDecision(
        method_qualname="A.run",
        allowed=False,
        status=ClosureStatus.UNSAFE,
        blockers=("UNSAFE: monkey patch",),
    )

    proof = classify_rewrite_decision(decision)

    assert proof.status is ProofStatus.UNSAFE
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_proofs.py -q`

Expected: FAIL with missing `flatten.proofs`.

- [ ] **Step 3: Implement proofs module**

Create `src/flatten/proofs.py`:

```python
"""Proof classification for rewrite authorization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from flatten.contracts import ClosureStatus, RewriteDecision


class ProofStatus(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProofEvidence:
    status: ProofStatus
    reasons: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
        }


def classify_rewrite_decision(decision: RewriteDecision) -> ProofEvidence:
    if decision.allowed and decision.status is ClosureStatus.CLOSED and decision.evidence:
        return ProofEvidence(
            status=ProofStatus.SAFE,
            reasons=decision.reasons,
            evidence=decision.evidence,
        )
    if decision.status is ClosureStatus.UNSAFE:
        return ProofEvidence(
            status=ProofStatus.UNSAFE,
            reasons=decision.blockers or decision.reasons,
            evidence=decision.evidence,
        )
    return ProofEvidence(
        status=ProofStatus.UNKNOWN,
        reasons=decision.blockers or decision.reasons,
        evidence=decision.evidence,
    )
```

- [ ] **Step 4: Add proof fields to RewriteDecision JSON**

Modify `src/flatten/contracts.py` `RewriteDecision`:

```python
    proof_status: str = ""
    proof_reasons: tuple[str, ...] = ()
    proof_evidence: tuple[str, ...] = ()
```

Add these keys inside `to_json()`:

```python
            "proof_status": self.proof_status,
            "proof_reasons": list(self.proof_reasons),
            "proof_evidence": list(self.proof_evidence),
```

- [ ] **Step 5: Run proof tests**

Run: `python -m pytest tests/test_proofs.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/flatten/proofs.py src/flatten/contracts.py tests/test_proofs.py
git commit -m "feat: add rewrite proof classification"
```

## Task 5: Planner Proof Gating

**Files:**
- Modify: `src/flatten/planner.py`
- Test: `tests/test_proofs.py`

- [ ] **Step 1: Write failing planner proof test**

Append to `tests/test_proofs.py`:

```python
from flatten.contracts import ClosureVerdict
from flatten.planner import RewritePlanner


def test_planner_decisions_include_proof_status():
    verdict = ClosureVerdict(
        method_qualname="A.run",
        status=ClosureStatus.CLOSED,
        reasons=("typing.final class or method",),
        evidence=("checked static package subclasses",),
    )

    decisions = RewritePlanner(opt_in=True).decide([verdict])

    assert decisions[0].proof_status == "safe"
    assert decisions[0].proof_evidence == ("checked static package subclasses",)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_proofs.py::test_planner_decisions_include_proof_status -q`

Expected: FAIL because `proof_status` is empty.

- [ ] **Step 3: Attach proof classification in planner**

Modify `src/flatten/planner.py` in `RewritePlanner.decide()` after `RewriteDecision.from_verdict(verdict)` is created:

```python
from dataclasses import replace

from flatten.proofs import classify_rewrite_decision
```

Then attach:

```python
decision = RewriteDecision.from_verdict(verdict)
proof = classify_rewrite_decision(decision)
decision = replace(
    decision,
    proof_status=proof.status.value,
    proof_reasons=proof.reasons,
    proof_evidence=proof.evidence,
)
```

- [ ] **Step 4: Ensure rewrite plans only emit SAFE decisions**

Add a guard in the planning path where decisions are mapped to plans:

```python
if decision.proof_status != "safe":
    continue
```

If the current planner does not keep the decision next to the verdict in that method, do not refactor broadly. Instead, ensure plan emission still requires `ClosureStatus.CLOSED`, no blockers, and non-empty evidence.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_proofs.py tests/test_staff_contracts.py::test_planner_exposes_rewrite_decisions_for_closed_and_refused_verdicts -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/flatten/planner.py tests/test_proofs.py
git commit -m "feat: gate rewrite decisions with proof status"
```

## Task 6: Evaluate CLI

**Files:**
- Modify: `src/flatten/cli.py`
- Test: `tests/test_evidence_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_evidence_cli.py`:

```python
import json
from pathlib import Path

from flatten.cli import main


def test_evaluate_cli_reports_counts_for_source_file(tmp_path, capsys):
    source = tmp_path / "case.py"
    source.write_text(
        """
class A:
    def run(self):
        return 1

def main(a):
    return a.run()
""",
        encoding="utf-8",
    )

    assert main(["evaluate", source.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["total_call_sites"] == 1
    assert payload["counts"]["candidate_call_sites"] == 0
    assert payload["precision"] is None


def test_evaluate_cli_accepts_plan_file(tmp_path, capsys):
    source = tmp_path / "case.py"
    source.write_text(
        """
class A:
    def run(self):
        return 1

def main(a):
    return a.run()
""",
        encoding="utf-8",
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "rewrite_decisions": [
                    {
                        "method_qualname": "A.run",
                        "allowed": False,
                        "status": "unsafe",
                        "blockers": ["UNSAFE: monkey patch"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["evaluate", source.as_posix(), "--plan", plan.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["candidate_call_sites"] == 1
    assert payload["counts"]["unsafe_call_sites"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_evidence_cli.py -q`

Expected: FAIL because `evaluate` subcommand is missing.

- [ ] **Step 3: Add CLI parser and command**

Modify `src/flatten/cli.py` imports:

```python
from flatten.evaluation import evaluate_artifacts
```

Add helper:

```python
def _decision_from_json(raw: dict[str, Any]) -> RewriteDecision:
    status = ClosureStatus(str(raw.get("status", "unknown")))
    return RewriteDecision(
        method_qualname=str(raw.get("method_qualname", "")),
        allowed=bool(raw.get("allowed", False)),
        status=status,
        blockers=tuple(str(item) for item in raw.get("blockers", [])),
        reasons=tuple(str(item) for item in raw.get("reasons", [])),
        evidence=tuple(str(item) for item in raw.get("evidence", [])),
        reason_code=str(raw.get("reason_code", "")),
    )
```

Add command:

```python
def cmd_evaluate(args: argparse.Namespace) -> int:
    args.path = args.path.resolve()
    source = _read(args.path)
    call_sites = discover_call_sites(source, filename=str(args.path).replace("\\", "/"))
    decisions: list[RewriteDecision] = []
    if args.plan is not None:
        payload = json.loads(_read(args.plan.resolve()))
        decisions = [
            _decision_from_json(item)
            for item in payload.get("rewrite_decisions", [])
            if isinstance(item, dict)
        ]
    _json_print(evaluate_artifacts(call_sites, decisions).to_json())
    return 0
```

Register parser:

```python
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("path", type=Path)
    evaluate.add_argument("--plan", type=Path)
    evaluate.add_argument("--json", action="store_true")
    evaluate.set_defaults(func=cmd_evaluate)
```

- [ ] **Step 4: Run CLI tests**

Run: `python -m pytest tests/test_evidence_cli.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/flatten/cli.py tests/test_evidence_cli.py
git commit -m "feat: add evaluation cli"
```

## Task 7: Architecture Document For Evidence Review

**Files:**
- Create or replace: `docs/architecture.md`
- Modify: `docs/claim_test_map.md`
- Test: `tests/test_phase3_release_contracts.py`

- [ ] **Step 1: Write document contract test**

Add to `tests/test_phase3_release_contracts.py`:

```python
def test_evidence_architecture_doc_covers_review_topics():
    text = Path("docs/architecture.md").read_text(encoding="utf-8")
    required = [
        "Data Flow",
        "Public API",
        "Safety Limits",
        "False Positives",
        "False Negatives",
        "Unsupported Python Features",
        "Evidence Platform",
    ]
    for heading in required:
        assert heading in text
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_phase3_release_contracts.py::test_evidence_architecture_doc_covers_review_topics -q`

Expected: FAIL if `docs/architecture.md` does not exist or lacks headings.

- [ ] **Step 3: Add architecture document**

Create `docs/architecture.md` with these sections:

```markdown
# flatten Architecture

## Data Flow

`flatten` processes source through discovery, runtime observation, static hierarchy extraction, closure checking, proof classification, planning, LibCST rewrite, differential validation, and reporting.

## Module Responsibilities

- `flatten.discovery`: source-positioned method call-site discovery.
- `flatten.tracer`: runtime receiver and caller evidence collection.
- `flatten.observations`: stable JSON observation contracts.
- `flatten.static`: class hierarchy and dynamic risk extraction.
- `flatten.closure`: CLOSED, PROBABLY_CLOSED, OPEN, UNSAFE, UNKNOWN verdicts.
- `flatten.proofs`: SAFE, UNSAFE, UNKNOWN rewrite proof classification.
- `flatten.planner`: rewrite authorization and transform plan creation.
- `flatten.transformer`: exact position-based LibCST replacement.
- `flatten.comparator`: behavior comparison of original and rewritten callables.
- `flatten.evaluation`: reproducible counts and precision/recall metrics.
- `flatten.report`: human and HTML report rendering.
- `flatten.cli`: command-line orchestration.

## Public API

The stable public dataclasses are `CallSite`, `ObservationRecord`, `ClosureVerdict`, `RewriteDecision`, `TransformPlan`, `EvaluationCounts`, `EvaluationMetrics`, `ProofEvidence`, and `BehaviorComparisonResult`.

## Evidence Platform

The evidence platform records total call sites, candidate call sites, rewritten call sites, rejected call sites, unsafe call sites, unknown call sites, precision, recall, false positive rate, and false negative rate. Metrics with no labeled corpus are reported as `null`, not guessed.

## Safety Limits

Runtime observation is evidence for observed executions only. A rewrite requires positive closure evidence and SAFE proof classification. UNKNOWN never rewrites.

## False Positives

False positives can occur if a labeled corpus marks an unsafe call site as rewritten, if dynamic behavior is hidden outside observed executions, or if a plan file is trusted without matching source and evidence checks.

## False Negatives

False negatives are expected under conservative policy. Final classes with unsupported descriptors, dynamic imports, custom metaclasses, or incomplete hierarchy evidence can be rejected even when a human can prove safety.

## Unsupported Python Features

Unsupported or rejected features include dynamic `__getattr__`, custom `__getattribute__`, monkey patching, custom metaclasses, descriptor/property dispatch, complex multiple inheritance, dynamic imports, eval/exec, async methods, generator methods, and open-world plugin extension points.
```

- [ ] **Step 4: Update claim map**

Append rows to `docs/claim_test_map.md`:

```markdown
| Evaluation metrics report call-site counts and precision/recall fields. | `tests/test_evaluation.py` |
| Behavior comparison reports return, stream, exception, and effect mismatches. | `tests/test_comparator.py` |
| Proof classification maps rewrite decisions to SAFE, UNSAFE, or UNKNOWN. | `tests/test_proofs.py` |
| Evidence CLI emits reproducible JSON metrics. | `tests/test_evidence_cli.py` |
```

- [ ] **Step 5: Run document tests**

Run: `python -m pytest tests/test_phase3_release_contracts.py::test_evidence_architecture_doc_covers_review_topics -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add docs/architecture.md docs/claim_test_map.md tests/test_phase3_release_contracts.py
git commit -m "docs: document evidence architecture"
```

## Task 8: HTML Evidence Report Slice

**Files:**
- Modify: `src/flatten/report.py`
- Test: `tests/test_evidence_cli.py`

- [ ] **Step 1: Write failing HTML report test**

Append to `tests/test_evidence_cli.py`:

```python
from flatten.evaluation import EvaluationCounts, compute_metrics
from flatten.report import evaluation_metrics_to_html


def test_evaluation_metrics_html_contains_review_fields():
    html = evaluation_metrics_to_html(
        compute_metrics(
            EvaluationCounts(
                total_call_sites=2,
                candidate_call_sites=1,
                rewritten_call_sites=1,
                rejected_call_sites=0,
                unsafe_call_sites=0,
                unknown_call_sites=0,
            ),
            [],
        )
    )

    assert "<html" in html
    assert "total_call_sites" in html
    assert "precision" in html
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_evidence_cli.py::test_evaluation_metrics_html_contains_review_fields -q`

Expected: FAIL with missing `evaluation_metrics_to_html`.

- [ ] **Step 3: Implement HTML renderer**

Add to `src/flatten/report.py`:

```python
from html import escape

from flatten.evaluation import EvaluationMetrics


def evaluation_metrics_to_html(metrics: EvaluationMetrics) -> str:
    rows = []
    payload = metrics.to_json()
    for key, value in payload["counts"].items():
        rows.append(f"<tr><th>{escape(key)}</th><td>{escape(str(value))}</td></tr>")
    for key in ("precision", "recall", "false_positive_rate", "false_negative_rate"):
        rows.append(f"<tr><th>{escape(key)}</th><td>{escape(str(payload[key]))}</td></tr>")
    return (
        "<html><body><h1>flatten evidence report</h1>"
        "<table>"
        + "".join(rows)
        + "</table></body></html>"
    )
```

- [ ] **Step 4: Run report tests**

Run: `python -m pytest tests/test_evidence_cli.py::test_evaluation_metrics_html_contains_review_fields -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/flatten/report.py tests/test_evidence_cli.py
git commit -m "feat: render evaluation metrics html"
```

## Task 9: Release Verification For Evidence Slice

**Files:**
- Modify only if failures reveal a directly related defect.

- [ ] **Step 1: Run focused evidence tests**

Run:

```powershell
python -m pytest tests/test_evaluation.py tests/test_comparator.py tests/test_proofs.py tests/test_evidence_cli.py -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run integration regression tests touching planner/CLI/report**

Run:

```powershell
python -m pytest tests/test_staff_contracts.py tests/test_planner_report_cli.py tests/test_phase3_release_contracts.py -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run quality gates**

Run:

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy src\flatten
```

Expected: all commands exit 0.

- [ ] **Step 4: Update AI context**

Modify:
- `AI/context/project_summary.md`
- `AI/context/architecture.md`
- `AI/decisions/decision_log.md`
- `AI/tasks/current_tasks.md`

Add a concise entry that Evidence Platform First added evaluation metrics, comparator API, proof classification, CLI `evaluate`, and architecture evidence docs.

- [ ] **Step 5: Final commit**

```powershell
git add AI/context/project_summary.md AI/context/architecture.md AI/decisions/decision_log.md AI/tasks/current_tasks.md
git status --short
git commit -m "docs: update ai context for evidence platform"
```

## Self-Review

- Spec coverage: This plan covers the first Evidence Platform First slice: evaluation counts, reproducible metrics JSON, behavior comparison, proof classification, CLI exposure, HTML report foundation, and architecture documentation. Repository-scale traversal, real-world benchmark suites, mutation score automation, Prometheus export, and full type-flow/alias analysis remain later plans because they are independent subsystems.
- Placeholder scan: No task contains deferred-work markers. Each implementation task has concrete code and commands.
- Type consistency: The plan consistently uses `EvaluationCounts`, `EvaluationMetrics`, `LabeledOutcome`, `BehaviorComparator`, `ProofEvidence`, and `ProofStatus`.
