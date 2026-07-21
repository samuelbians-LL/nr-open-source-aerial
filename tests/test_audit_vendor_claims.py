import csv
from pathlib import Path

from scripts.audit_vendor_claims import audit_claims


FIELDNAMES = [
    "claim_id",
    "metric",
    "value",
    "unit",
    "source_url",
    "document_version",
    "hardware",
    "bandwidth_mhz",
    "antenna_config",
    "cell_scope",
    "test_boundary",
    "statistic",
    "comparison_scope",
]


def write_rows(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "vendor-claims.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


def complete_row(**overrides: str) -> dict[str, str]:
    row = {
        "claim_id": "AERIAL-PERF-TEST-001",
        "metric": "peak_cells",
        "value": "20",
        "unit": "cells",
        "source_url": "https://docs.nvidia.com/aerial/example.html",
        "document_version": "26.1",
        "hardware": "Grace Hopper MGX with H100 and BF3",
        "bandwidth_mhz": "100",
        "antenna_config": "4T4R",
        "cell_scope": "20 coordinated cells",
        "test_boundary": "vendor E2E gNB with RU emulator",
        "statistic": "peak validated configuration",
        "comparison_scope": "comparable_with_constraints",
    }
    row.update(overrides)
    return row


def test_missing_comparison_context_is_reported_explicitly(tmp_path: Path) -> None:
    row = complete_row(hardware="", statistic="", test_boundary="")

    results = audit_claims(str(write_rows(tmp_path, [row])))

    assert results == [
        {
            "claim_id": "AERIAL-PERF-TEST-001",
            "classification": "insufficient_context",
            "missing_fields": "hardware;test_boundary;statistic",
        }
    ]


def test_complete_claim_can_be_compared_only_with_its_constraints(tmp_path: Path) -> None:
    results = audit_claims(str(write_rows(tmp_path, [complete_row()])))

    assert results[0]["classification"] == "comparable_with_constraints"
    assert results[0]["missing_fields"] == ""


def test_vendor_only_scope_is_preserved(tmp_path: Path) -> None:
    results = audit_claims(
        str(write_rows(tmp_path, [complete_row(comparison_scope="vendor_only")]))
    )

    assert results[0]["classification"] == "vendor_only"
    assert results[0]["missing_fields"] == ""


def test_unknown_comparison_scope_is_insufficient(tmp_path: Path) -> None:
    results = audit_claims(
        str(write_rows(tmp_path, [complete_row(comparison_scope="global_ranking")]))
    )

    assert results[0]["classification"] == "insufficient_context"
    assert results[0]["missing_fields"] == "comparison_scope"
