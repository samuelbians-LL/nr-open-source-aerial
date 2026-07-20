from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


LEVEL_ORDER = {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4}


def _load_yaml(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    return document if isinstance(document, dict) else {}


def _missing(record: dict[str, Any], field: str) -> bool:
    value = record.get(field)
    return value is None or value == "" or value == [] or value == {}


def validate_claims(claims_path: str, repositories_path: str) -> list[str]:
    claims_document = _load_yaml(claims_path)
    repositories_document = _load_yaml(repositories_path)
    schema_path = Path(repositories_path).with_name("evidence-schema.yaml")
    schema = _load_yaml(str(schema_path))

    errors: list[str] = []
    claims = claims_document.get("claims", [])
    repositories = repositories_document.get("repositories", {})
    evidence_levels = schema.get("evidence_levels", {})
    conclusion_types = schema.get("conclusion_types", {})
    required_fields = schema.get("required_claim_fields", [])
    allowed_statuses = set(schema.get("allowed_statuses", []))

    if not isinstance(claims, list):
        return ["claims: expected a list"]

    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            errors.append(f"claim[{index}]: expected a mapping")
            continue

        claim_id = claim.get("claim_id") or f"claim[{index}]"
        for field in required_fields:
            if _missing(claim, field):
                errors.append(f"{claim_id}: missing required claim field: {field}")

        evidence_level = claim.get("evidence_level")
        if evidence_level not in evidence_levels:
            errors.append(f"{claim_id}: unknown evidence_level: {evidence_level}")
            continue

        conclusion_type = claim.get("conclusion_type")
        conclusion_rule = conclusion_types.get(conclusion_type)
        if conclusion_rule is None:
            errors.append(f"{claim_id}: unknown conclusion_type: {conclusion_type}")
        else:
            minimum_level = conclusion_rule.get("minimum_level")
            if LEVEL_ORDER[evidence_level] < LEVEL_ORDER[minimum_level]:
                errors.append(
                    f"{claim_id}: {conclusion_type} requires at least {minimum_level}, "
                    f"got {evidence_level}"
                )

        for field in evidence_levels[evidence_level].get("requires", []):
            if _missing(claim, field):
                errors.append(
                    f"{claim_id}: missing evidence field for {evidence_level}: {field}"
                )

        if conclusion_type == "vendor_claim":
            for field in ("official_url", "document_version"):
                if _missing(claim, field) and field not in evidence_levels[evidence_level].get(
                    "requires", []
                ):
                    errors.append(f"{claim_id}: vendor_claim missing required field: {field}")

        status = claim.get("status")
        if status is not None and status not in allowed_statuses:
            errors.append(f"{claim_id}: unknown status: {status}")

        if LEVEL_ORDER[evidence_level] >= LEVEL_ORDER["E2"] and not _missing(
            claim, "repository"
        ):
            repository_key = claim["repository"]
            repository = repositories.get(repository_key)
            if repository is None:
                errors.append(f"{claim_id}: unknown repository: {repository_key}")
            elif not _missing(claim, "commit") and claim["commit"] != repository.get("commit"):
                errors.append(
                    f"{claim_id}: commit does not match frozen repository {repository_key}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate research claim evidence records.")
    parser.add_argument("claims_path")
    parser.add_argument("repositories_path")
    args = parser.parse_args()

    errors = validate_claims(args.claims_path, args.repositories_path)
    if errors:
        for error in errors:
            print(error)
        return 1

    print("CLAIMS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
