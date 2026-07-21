from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation


REQUIRED_FIELDS = (
    "record_id",
    "project",
    "software_version",
    "hardware_id",
    "bandwidth_mhz",
    "scs_khz",
    "duplex",
    "tdd_pattern",
    "tx_antennas",
    "rx_antennas",
    "layers",
    "ues",
    "mcs_or_load",
    "test_boundary",
    "latency_statistic",
    "latency_value",
    "latency_unit",
    "throughput_value",
    "throughput_unit",
    "deadline_misses",
    "repetitions",
    "warmup_seconds",
    "duration_seconds",
    "raw_source",
)

GROUP_FIELDS = (
    "hardware_id",
    "bandwidth_mhz",
    "scs_khz",
    "duplex",
    "tdd_pattern",
    "tx_antennas",
    "rx_antennas",
    "layers",
    "ues",
    "mcs_or_load",
    "test_boundary",
    "latency_statistic",
    "repetitions",
    "warmup_seconds",
    "duration_seconds",
)

LATENCY_TO_US = {
    "ns": Decimal("0.001"),
    "us": Decimal("1"),
    "ms": Decimal("1000"),
    "s": Decimal("1000000"),
}

THROUGHPUT_TO_MBPS = {
    "kbit/s": Decimal("0.001"),
    "mbit/s": Decimal("1"),
    "gbit/s": Decimal("1000"),
}


def normalize_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Validate units, derive comparison groups, and preserve raw provenance."""
    normalized: list[dict[str, str]] = []
    for index, source in enumerate(records, start=1):
        missing = [field for field in REQUIRED_FIELDS if not source.get(field, "").strip()]
        if missing:
            record_id = source.get("record_id", "").strip() or f"record[{index}]"
            raise ValueError(f"{record_id}: missing fields: {';'.join(missing)}")

        latency_unit = source["latency_unit"].strip().lower().replace("µ", "u")
        throughput_unit = source["throughput_unit"].strip().lower()
        if latency_unit not in LATENCY_TO_US:
            raise ValueError(f"{source['record_id']}: unsupported latency_unit")
        if throughput_unit not in THROUGHPUT_TO_MBPS:
            raise ValueError(f"{source['record_id']}: unsupported throughput_unit")

        try:
            latency_us = Decimal(source["latency_value"]) * LATENCY_TO_US[latency_unit]
            throughput_mbps = (
                Decimal(source["throughput_value"])
                * THROUGHPUT_TO_MBPS[throughput_unit]
            )
        except InvalidOperation as error:
            raise ValueError(f"{source['record_id']}: invalid numeric value") from error

        group_key = "|".join(source[field].strip().lower() for field in GROUP_FIELDS)
        result = dict(source)
        result["latency_us"] = format(latency_us.normalize(), "f")
        result["throughput_mbps"] = format(throughput_mbps.normalize(), "f")
        result["comparison_group"] = hashlib.sha256(group_key.encode("utf-8")).hexdigest()[:16]
        normalized.append(result)

    return normalized
