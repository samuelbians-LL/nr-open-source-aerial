from pathlib import Path

import yaml

from scripts.validate_claims import validate_claims


REPOSITORIES_PATH = Path("config/repositories.yaml")


def write_claims(tmp_path: Path, claims: list[dict]) -> Path:
    claims_path = tmp_path / "claims.yaml"
    claims_path.write_text(
        yaml.safe_dump({"schema_version": 1, "claims": claims}, sort_keys=False),
        encoding="utf-8",
    )
    return claims_path


def base_claim(**overrides) -> dict:
    claim = {
        "claim_id": "TEST-001",
        "question": "Which implementation path is used?",
        "statement": "The referenced source contains the stated implementation path.",
        "conclusion_type": "confirmed_fact",
        "evidence_level": "E2",
        "projects": ["aerial"],
        "limitations": "Static source evidence only.",
        "status": "confirmed",
        "repository": "aerial",
        "commit": "29f5870fd84b0176df48b40667c1b8f1740e6d09",
        "paths": ["cuPHY/src/example.cu"],
        "symbols": ["example_kernel"],
    }
    claim.update(overrides)
    return claim


def test_e2_to_e4_require_commit_path_and_symbol_evidence(tmp_path: Path) -> None:
    claim = base_claim()
    del claim["commit"]
    del claim["paths"]
    del claim["symbols"]

    errors = validate_claims(str(write_claims(tmp_path, [claim])), str(REPOSITORIES_PATH))

    assert errors == [
        "TEST-001: missing evidence field for E2: commit",
        "TEST-001: missing evidence field for E2: paths",
        "TEST-001: missing evidence field for E2: symbols",
    ]


def test_measured_fact_requires_independent_experiment_configuration(tmp_path: Path) -> None:
    claim = base_claim(
        conclusion_type="measured_fact",
        evidence_level="E4",
        environment_manifest="experiments/environment.yaml",
        raw_log_paths=["experiments/raw/run-001.log"],
        analysis_script="scripts/analyze_run.py",
        result_checksum="sha256:example",
    )

    errors = validate_claims(str(write_claims(tmp_path, [claim])), str(REPOSITORIES_PATH))

    assert errors == ["TEST-001: missing evidence field for E4: configuration"]


def test_vendor_claim_requires_official_url_and_version_but_not_local_logs(tmp_path: Path) -> None:
    claim = base_claim(
        conclusion_type="vendor_claim",
        evidence_level="E0",
        official_url="https://docs.nvidia.com/aerial/",
        document_version="26.1",
        retrieved_at="2026-07-20",
    )
    for field in ("repository", "commit", "paths", "symbols"):
        claim.pop(field)

    errors = validate_claims(str(write_claims(tmp_path, [claim])), str(REPOSITORIES_PATH))

    assert errors == []


def test_vendor_claim_without_document_version_fails(tmp_path: Path) -> None:
    claim = base_claim(
        conclusion_type="vendor_claim",
        evidence_level="E0",
        official_url="https://docs.nvidia.com/aerial/",
        retrieved_at="2026-07-20",
    )
    for field in ("repository", "commit", "paths", "symbols"):
        claim.pop(field)

    errors = validate_claims(str(write_claims(tmp_path, [claim])), str(REPOSITORIES_PATH))

    assert errors == ["TEST-001: vendor_claim missing required field: document_version"]


def test_valid_e2_claim_passes(tmp_path: Path) -> None:
    errors = validate_claims(
        str(write_claims(tmp_path, [base_claim()])),
        str(REPOSITORIES_PATH),
    )

    assert errors == []
