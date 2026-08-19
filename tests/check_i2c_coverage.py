from __future__ import annotations

import re
import sys
from pathlib import Path


MIN_LINE_COVERAGE = 80.0
EXPECTED_FUNCTIONAL_TOTAL = 18
RTL_FILES = [
    "periphx_i2c_adapter.v",
    "i2c_master.v",
]


def parse_functional_coverage(log_text: str) -> tuple[int, int]:
    match = re.search(r"FUNCTIONAL_COVERAGE:\s*(\d+)/(\d+)", log_text)
    if match is None:
        raise ValueError("FUNCTIONAL_COVERAGE line not found")
    return int(match.group(1)), int(match.group(2))


def parse_line_coverage(path: Path) -> tuple[int, int, float]:
    hit = 0
    miss = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        prefix = line[:8]
        if prefix.startswith("%"):
            count_text = prefix[1:].strip()
            if count_text.isdigit():
                count = int(count_text)
                if count == 0:
                    miss += 1
                else:
                    hit += 1
        elif prefix.strip().isdigit():
            hit += 1

    total = hit + miss
    percent = 100.0 if total == 0 else (hit * 100.0 / total)
    return hit, total, percent


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_i2c_coverage.py <tb-log> <coverage-report-dir>")
        return 2

    log_path = Path(sys.argv[1])
    report_dir = Path(sys.argv[2])
    passed = True

    covered, total = parse_functional_coverage(log_path.read_text(encoding="utf-8"))
    print(f"functional coverage: {covered}/{total}")
    if covered != EXPECTED_FUNCTIONAL_TOTAL or total != EXPECTED_FUNCTIONAL_TOTAL:
        print("FAIL: functional coverage is incomplete")
        passed = False

    for file_name in RTL_FILES:
        hit, line_total, percent = parse_line_coverage(report_dir / file_name)
        print(f"{file_name}: line coverage {percent:.2f}% ({hit}/{line_total})")
        if percent < MIN_LINE_COVERAGE:
            print(f"FAIL: {file_name} line coverage below {MIN_LINE_COVERAGE:.2f}%")
            passed = False

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
