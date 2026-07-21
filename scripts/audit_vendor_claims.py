from __future__ import annotations

import argparse
import csv
import json


REQUIRED_FIELDS = (
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
)

ALLOWED_SCOPES = {"comparable_with_constraints", "vendor_only"}


def audit_claims(csv_path: str) -> list[dict[str, str]]:
    """Return one audit result per vendor claim."""
    results: list[dict[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), start=2):
            missing = [field for field in REQUIRED_FIELDS if not row.get(field, "").strip()]
            scope = row.get("comparison_scope", "").strip()
            if scope and scope not in ALLOWED_SCOPES and "comparison_scope" not in missing:
                missing.append("comparison_scope")

            claim_id = row.get("claim_id", "").strip() or f"row-{row_number}"
            classification = "insufficient_context" if missing else scope
            results.append(
                {
                    "claim_id": claim_id,
                    "classification": classification,
                    "missing_fields": ";".join(missing),
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit NVIDIA Aerial vendor claims.")
    parser.add_argument("csv_path")
    args = parser.parse_args()
    print(json.dumps(audit_claims(args.csv_path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
