from copy import deepcopy

import pytest

from scripts.normalize_benchmarks import normalize_records


def complete_record(**overrides: str) -> dict[str, str]:
    record = {
        "record_id": "CPU-BASELINE-001",
        "project": "oai",
        "software_version": "frozen-commit",
        "hardware_id": "lab-host-01",
        "bandwidth_mhz": "100",
        "scs_khz": "30",
        "duplex": "TDD",
        "tdd_pattern": "DDDSU",
        "tx_antennas": "4",
        "rx_antennas": "4",
        "layers": "2",
        "ues": "8",
        "mcs_or_load": "MCS 16",
        "test_boundary": "upper_phy_slot",
        "latency_statistic": "p99",
        "latency_value": "0.75",
        "latency_unit": "ms",
        "throughput_value": "1.2",
        "throughput_unit": "Gbit/s",
        "deadline_misses": "0",
        "repetitions": "5",
        "warmup_seconds": "30",
        "duration_seconds": "120",
        "raw_source": "data/performance/raw/oai/run-001.json",
    }
    record.update(overrides)
    return record


def test_missing_comparison_context_is_rejected() -> None:
    record = complete_record(
        hardware_id="", antenna_config="", latency_statistic="", test_boundary=""
    )
    del record["tx_antennas"]

    with pytest.raises(ValueError) as error:
        normalize_records([record])

    message = str(error.value)
    assert "hardware_id" in message
    assert "tx_antennas" in message
    assert "latency_statistic" in message
    assert "test_boundary" in message


def test_units_are_normalized_and_raw_provenance_is_preserved() -> None:
    result = normalize_records([complete_record()])[0]

    assert result["latency_us"] == "750"
    assert result["throughput_mbps"] == "1200"
    assert result["raw_source"] == "data/performance/raw/oai/run-001.json"


def test_projects_share_group_only_when_comparison_context_matches() -> None:
    oai = complete_record(project="oai", record_id="OAI-001")
    ocudu = complete_record(project="ocudu", record_id="OCUDU-001")

    results = normalize_records([oai, ocudu])

    assert results[0]["comparison_group"] == results[1]["comparison_group"]


def test_different_antenna_configurations_do_not_share_a_group() -> None:
    four_by_four = complete_record(record_id="FOUR", tx_antennas="4", rx_antennas="4")
    sixty_four = deepcopy(four_by_four)
    sixty_four.update(record_id="SIXTY-FOUR", tx_antennas="64", rx_antennas="64")

    results = normalize_records([four_by_four, sixty_four])

    assert results[0]["comparison_group"] != results[1]["comparison_group"]


def test_unknown_units_are_rejected() -> None:
    with pytest.raises(ValueError, match="latency_unit"):
        normalize_records([complete_record(latency_unit="frames")])
