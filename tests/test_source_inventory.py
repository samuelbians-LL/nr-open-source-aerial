import csv
import re
from pathlib import Path


INVENTORY_PATH = Path("data/inventory/source-inventory.csv")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def test_source_inventory_is_complete_and_content_addressed() -> None:
    with INVENTORY_PATH.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows
    assert set(rows[0]) >= {
        "project",
        "path",
        "extension",
        "language",
        "bytes",
        "sha256",
        "commit",
        "source_url",
    }
    assert {row["project"] for row in rows} == {"aerial", "oai", "ocudu"}
    assert all(int(row["bytes"]) > 0 for row in rows)
    assert all(SHA256_PATTERN.fullmatch(row["sha256"]) for row in rows)


def test_inventory_covers_cuda_and_primary_c_cpp_implementations() -> None:
    with INVENTORY_PATH.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert any(row["project"] == "aerial" and row["extension"] == ".cu" for row in rows)
    for project in ("aerial", "oai", "ocudu"):
        assert any(
            row["project"] == project and row["language"] in {"C", "C++"}
            for row in rows
        )
