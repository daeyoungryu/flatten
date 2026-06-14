# Benchmark Report

## Summary

- Total cases: 56
- Supported cases: 50
- Unsupported cases: 6
- False positives: 0
- Unsafe rewrites: 0

## Metrics

| Metric | Value |
| --- | --- |
| rewrite_accepted | 18 |
| rewrite_rejected | 38 |
| true_positive | 18 |
| true_negative | 38 |
| false_positive | 0 |
| false_negative | 0 |
| precision | 1.0 |
| recall | 1.0 |
| fpr | 0.0 |
| fnr | 0.0 |
| safety_failure_count | 0 |
| behavioral_equivalence_failures | 0 |

## Category Breakdown

| Category | Cases |
| --- | ---: |
| closed_hierarchy | 1 |
| deterministic_method_override | 1 |
| final_class | 1 |
| final_method | 1 |
| harness_equivalence | 10 |
| package_local_class_set | 1 |
| reject_dynamic_python | 19 |
| reject_mro | 3 |
| reject_open_world | 3 |
| safe_rewrite | 9 |
| sealed_like_local_hierarchy | 1 |
| unsupported_policy | 4 |
| unsupported_runtime | 2 |

## Coverage By Feature

| Feature | Cases |
| --- | ---: |
| `__getattr__` | 1 |
| `__getattribute__` | 2 |
| `__setattr__` | 1 |
| `abc_virtual_subclass` | 1 |
| `async_method` | 1 |
| `c_extension` | 1 |
| `closed_world` | 3 |
| `data_model_hook` | 1 |
| `decorator_wrapper` | 1 |
| `dependency_injection_container` | 1 |
| `descriptor` | 2 |
| `direct_dispatch` | 5 |
| `dynamic_imports` | 2 |
| `dynamic_subclass_creation` | 2 |
| `exception_behavior` | 2 |
| `external_subclass_possibility` | 1 |
| `final_class` | 2 |
| `final_method` | 1 |
| `finite_subclasses` | 4 |
| `generator_method` | 1 |
| `guarded_dispatch` | 2 |
| `harness_equivalence` | 10 |
| `harness_required` | 1 |
| `inheritance` | 1 |
| `late_import_subclass` | 1 |
| `leaf_class` | 2 |
| `metaclass_side_effect` | 2 |
| `method_override` | 4 |
| `method_reassignment` | 2 |
| `module_reload` | 1 |
| `monkey_patching` | 3 |
| `mro` | 3 |
| `mro_sensitive_dispatch` | 1 |
| `multiple_inheritance_ambiguity` | 1 |
| `native_behavior` | 1 |
| `no_attribute_write` | 1 |
| `no_freevars` | 1 |
| `no_nonlocal_write` | 1 |
| `observation_only` | 1 |
| `open_world` | 3 |
| `package_local` | 1 |
| `plugin_registry` | 1 |
| `probably_closed` | 1 |
| `property` | 1 |
| `protocol_structural_typing` | 1 |
| `reflection` | 1 |
| `return_value` | 1 |
| `runtime_code_generation` | 2 |
| `sealed_root` | 1 |
| `side_effectful_lookup` | 6 |
| `single_impl` | 1 |
| `state_mutation` | 1 |
| `state_read` | 1 |
| `static_package_scan` | 1 |
| `stdout` | 1 |
| `super_dependency` | 1 |

## False Positives

- None

## False Negatives

- None

## Unsupported Cases

- `async_method_001`: expected `unsupported`, actual `unsupported`; Async method flattening is not in the supported policy surface
- `generator_method_001`: expected `unsupported`, actual `unsupported`; Generator method semantics are not flattened in this version
- `probably_closed_without_positive_evidence_001`: expected `unsupported`, actual `unsupported`; Complete local observation is evidence but not proof
- `unknown_datamodel_hook_001`: expected `unsupported`, actual `unsupported`; Data model hook interaction is intentionally OPEN
- `unknown_decorator_rewrite_001`: expected `unsupported`, actual `unsupported`; Decorated method wrapper identity cannot be proven
- `unknown_reflection_001`: expected `unsupported`, actual `unsupported`; Reflection-heavy dispatch is left open until modeled

## Safety Notes

- No safety failures detected by this benchmark run.

## Regression Compared To Baseline

- Status: passed

## Reproduction Command

```powershell
python -m benchmarks.runner --format json --output benchmark-results.json
python -m benchmarks.runner --format markdown --output benchmark-report.md
python tools/check_evidence.py benchmark-results.json
```
