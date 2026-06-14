# Claim Test Map

This map links public claims to regression tests. A claim is not release-ready
unless it has an executable test or a documented external limitation.

| Claim | Test |
| --- | --- |
| CLOSED verdicts require explicit evidence. | `tests/test_required_e2e.py::test_closure_closes_final_local_hierarchy_and_rejects_adversarial_cases` |
| OPEN verdicts refuse unobserved subclasses. | `tests/test_closure.py::test_os5_detects_unobserved_recursive_subclasses` |
| UNSAFE verdicts refuse monkey patches and dynamic dispatch hazards. | `tests/adversarial/test_phase0_defects.py::test_cli_refuses_monkey_patched_dispatch_pipeline` |
| Phase 2 UNSAFE blockers cover dynamic hooks, dynamic code execution, and imports. | `tests/adversarial/test_phase2_blockers.py` |
| RewriteDecision records allow/refuse state separate from TransformPlan. | `tests/test_staff_contracts.py::test_rewrite_decision_records_closed_allow_and_open_refusal` |
| CLI exposes `rewrite_decisions` for refused rewrites. | `tests/test_staff_contracts.py::test_cli_plan_emits_rewrite_decisions_for_refused_observations` |
| Call-site ids use source positions, not method order. | `tests/adversarial/test_phase0_defects.py::test_trace_binds_callsites_by_runtime_line_not_method_order` |
| `rewrite` is dry-run unless `--apply` is passed. | `tests/adversarial/test_phase0_defects.py::test_rewrite_without_apply_never_writes_output` |
| `rewrite --apply` verifies by default and requires `--entry` unless `--skip-verify` is explicit. | `tests/adversarial/test_phase0_defects.py::test_rewrite_apply_requires_verify_unless_explicitly_skipped` |
| Plan-file rewrite requires source hash and CLOSED evidence. | `tests/adversarial/test_phase0_defects.py::test_untrusted_plan_file_is_refused_without_verdict_and_source_hash` |
| Plan-file rewrite refuses class names that are not available in the source module scope. | `tests/adversarial/test_phase0_defects.py::test_plan_file_rewrite_refuses_class_name_missing_from_source_scope` |
| `verify --cases` supports explicit case files and reports minimal coverage. | `tests/adversarial/test_phase0_defects.py::test_verify_uses_cases_file_and_reports_minimal_coverage` |
| Static hierarchy analysis reports dynamic risk flags. | `tests/test_static_hierarchy.py::test_static_hierarchy_flags_phase2_dynamic_blockers` |
| Same-line method calls bind using runtime column evidence. | `tests/adversarial/test_phase0_defects.py::test_trace_binds_same_line_multiple_calls_by_runtime_column` |
| Guarded dispatch for non-name receivers uses a temp receiver. | `tests/test_staff_contracts.py::test_guarded_dispatch_uses_temp_for_receiver_expression_with_side_effects` |
| CLI planner path uses static class graph evidence for local hierarchy closure. | `tests/test_staff_contracts.py::test_cli_plan_uses_static_subclass_graph_for_local_hierarchy_evidence` |
| Golden safe/unsafe corpus cases are executable and checked against expected rewrite counts. | `tests/test_golden_corpus.py` |
| Evaluation metrics report call-site counts and precision/recall fields. | `tests/test_evaluation.py` |
| Behavior comparison reports return, stream, exception, and effect mismatches. | `tests/test_comparator.py` |
| Proof classification maps rewrite decisions to SAFE, UNSAFE, or UNKNOWN. | `tests/test_proofs.py` |
| Evidence CLI emits reproducible JSON metrics. | `tests/test_evidence_cli.py` |
| Release gates include import smoke, pytest, coverage, ruff, and mypy. | `tests/test_release_quality.py::test_ci_runs_required_quality_gates` |
