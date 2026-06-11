from pathlib import Path

import tomllib
import yaml


def test_phase3_required_docs_exist_and_state_limits():
    required = [
        "ARCHITECTURE.md",
        "SAFETY_MODEL.md",
        "REWRITE_POLICY.md",
        "UNSUPPORTED_CASES.md",
        "TESTING_STRATEGY.md",
        "CLI.md",
        "EXAMPLES.md",
        "ROADMAP.md",
    ]
    for name in required:
        path = Path("docs") / name
        assert path.exists(), name
        content = path.read_text(encoding="utf-8")
        assert "observation" in content.lower() or name == "CLI.md"
    readme = Path("README.md").read_text(encoding="utf-8").lower()
    assert "observation is evidence, not proof" in readme
    assert "safe reject" in readme


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


def test_phase3_report_schema_exists_with_required_audit_fields():
    schema = Path("docs/rewrite_report.schema.json")
    assert schema.exists()
    text = schema.read_text(encoding="utf-8")
    for field in [
        "project_version",
        "timestamp",
        "input_file_hash",
        "output_file_hash",
        "callsites_discovered",
        "callsites_planned",
        "callsites_rewritten",
        "callsites_rejected",
        "reason_codes",
        "closure_verdicts",
        "verification_result",
        "warnings",
        "open_issues",
    ]:
        assert field in text


def test_phase3_packaging_metadata_and_typed_markers():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    assert project["name"] == "flatten-polymorph"
    assert project["requires-python"] == ">=3.10"
    assert project["license"] == "MIT"
    assert "License :: OSI Approved :: MIT License" in project["classifiers"]
    assert pyproject["project"]["scripts"]["flatten"] == "flatten.cli:main"
    assert Path("src/flatten/py.typed").exists()
    assert Path("src/flatten_polymorph/py.typed").exists()


def test_phase3_main_modules_are_guarded():
    for path in [Path("src/flatten/__main__.py"), Path("src/flatten_polymorph/__main__.py")]:
        content = path.read_text(encoding="utf-8")
        assert 'if __name__ == "__main__":' in content
        assert "raise SystemExit(main())" in content


def test_phase3_ci_matrix_and_smoke_jobs_are_fixed():
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    for job in ["lint", "typecheck", "test", "build", "wheel-install-smoke", "cli-smoke"]:
        assert job in jobs
    for job in jobs.values():
        matrix = job.get("strategy", {}).get("matrix", {})
        if matrix:
            assert matrix["os"] == ["windows-latest", "ubuntu-latest"]
            assert matrix["python-version"] == ["3.10", "3.12"]


def test_phase3_examples_have_required_directories_and_scripts():
    for name in [
        "simple_dispatch_success",
        "multi_subclass_success",
        "dynamic_getattr_rejected",
        "monkey_patch_rejected",
        "multiple_inheritance_rejected",
    ]:
        path = Path("examples") / name / "run.py"
        assert path.exists(), name
        assert 'if __name__ == "__main__":' in path.read_text(encoding="utf-8")
