from __future__ import annotations

import argparse
from pathlib import Path
import sys

from mlr.builder import build_workspace


def get_user_workspace() -> Path:
    return Path(__file__).resolve().parent.parent / "userSpace"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mlr", description="PeriphX build tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Generate RTL, SDK, and bitstream artifacts.")
    build_parser.add_argument(
        "--workspace",
        type=Path,
        default=get_user_workspace(),
        help="Path to the userSpace directory.",
    )
    build_parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Generate RTL and SDK only, and skip Quartus compilation.",
    )

    args = parser.parse_args(argv)

    if args.command == "build":
        build_workspace(args.workspace, run_quartus=not args.generate_only)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
