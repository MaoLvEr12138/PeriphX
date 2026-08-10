#!/usr/bin/env python3
"""Check UART Verilator functional and estimated line coverage."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_FUNCTIONAL_POINTS = [
    "data_bits_5",
    "data_bits_6",
    "data_bits_7",
    "data_bits_8",
    "parity_none",
    "parity_odd",
    "parity_even",
    "stop_bits_1",
    "stop_bits_2",
    "baud_div_fast",
    "baud_div_slow",
    "tx_normal",
    "rx_normal",
    "tx_fifo_full",
    "rx_fifo_empty",
    "rx_fifo_overflow",
    "parity_error",
    "frame_error",
    "configure_success",
    "configure_bad",
    "configure_busy",
]

ANNOTATED_LINE_RE = re.compile(r"^\s*(%?\d+)\s+(.*)$")
CASE_ITEM_RE = re.compile(r"^(\d+'[bdh][0-9a-fA-F_xXzZ]+|default)\s*:")


def read_functional_coverage(path: Path) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip() == "1"
    return values


def is_executable_verilog_line(source: str) -> bool:
    text = source.strip()
    if not text:
        return False
    if text.startswith("//") or text.startswith("verilator_coverage:"):
        return False
    if text in {"begin", "end", "endcase", "endmodule", "endfunction", ");", ")"}:
        return False
    if text.endswith("begin") and text.startswith("function "):
        return False
    declaration_prefixes = (
        "module ",
        "input ",
        "output ",
        "inout ",
        "wire ",
        "reg ",
        "localparam ",
        "parameter ",
    )
    if text.startswith(declaration_prefixes):
        return False
    if text.startswith("."):
        return False
    if text.endswith("(") or text.endswith(") u_tx_fifo (") or text.endswith(") u_rx_fifo ("):
        return False
    if text.startswith("assign "):
        return True
    if text.startswith("always "):
        return True
    if text.startswith("case(") or text.startswith("case ("):
        return True
    if text.startswith("if(") or text.startswith("if ("):
        return True
    if text.startswith("else if(") or text.startswith("else if ("):
        return True
    if text.startswith("end else begin") or text.startswith("else begin"):
        return True
    if CASE_ITEM_RE.match(text):
        return True
    if "<=" in text:
        return True
    if " = " in text and not text.startswith("for(") and not text.startswith("for ("):
        return True
    return False


def annotation_count(prefix: str) -> int:
    digits = prefix[1:] if prefix.startswith("%") else prefix
    return int(digits)


def collect_line_coverage(coverage_dir: Path) -> tuple[int, int, list[str]]:
    total = 0
    covered = 0
    misses: list[str] = []
    for path in sorted(coverage_dir.glob("*.v")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = ANNOTATED_LINE_RE.match(line)
            if match is None:
                continue
            prefix, source = match.groups()
            if not is_executable_verilog_line(source):
                continue
            total += 1
            count = annotation_count(prefix)
            if count > 0:
                covered += 1
            else:
                misses.append(f"{path.name}:{line_no}: {source.strip()}")
    return covered, total, misses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--functional", default="functional_coverage.txt")
    parser.add_argument("--coverage-dir", default="coverage_report")
    parser.add_argument("--line-threshold", type=float, default=85.0)
    args = parser.parse_args()

    functional_path = Path(args.functional)
    coverage_dir = Path(args.coverage_dir)
    if not functional_path.exists():
        print(f"FAIL: missing functional coverage file: {functional_path}")
        return 1
    if not coverage_dir.is_dir():
        print(f"FAIL: missing Verilator annotation directory: {coverage_dir}")
        return 1

    functional = read_functional_coverage(functional_path)
    missing_points = [
        point for point in REQUIRED_FUNCTIONAL_POINTS
        if not functional.get(point, False)
    ]
    covered_points = len(REQUIRED_FUNCTIONAL_POINTS) - len(missing_points)
    functional_pct = 100.0 * covered_points / len(REQUIRED_FUNCTIONAL_POINTS)

    line_covered, line_total, line_misses = collect_line_coverage(coverage_dir)
    if line_total == 0:
        print("FAIL: no executable annotated Verilog lines found")
        return 1
    line_pct = 100.0 * line_covered / line_total

    print(f"Functional coverage: {covered_points}/{len(REQUIRED_FUNCTIONAL_POINTS)} ({functional_pct:.2f}%)")
    print(f"Estimated line coverage: {line_covered}/{line_total} ({line_pct:.2f}%)")

    failed = False
    if missing_points:
        failed = True
        print("FAIL: missing functional points:")
        for point in missing_points:
            print(f"  - {point}")
    if line_pct < args.line_threshold:
        failed = True
        print(f"FAIL: estimated line coverage below {args.line_threshold:.2f}%")
        for item in line_misses[:50]:
            print(f"  - {item}")
        if len(line_misses) > 50:
            print(f"  ... {len(line_misses) - 50} more uncovered executable lines")

    if failed:
        return 1
    print("PASS: UART coverage thresholds met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
