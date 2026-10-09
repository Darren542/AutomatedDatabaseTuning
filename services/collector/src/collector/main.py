"""Collector command-line entry point.

The HTTP API lives in services/api. This module is reserved for collector
operations useful from scripts, scheduled jobs, and integration tests.
"""

from __future__ import annotations

import argparse
from uuid import UUID

from collector.collection.coordinator import CollectionCoordinator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autotuner-collector",
        description="Automated Database Tuner workload collector CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")

    create = subparsers.add_parser(
        "create-batch",
        help="Create a pending collection batch.",
    )
    create.add_argument("--target-id", required=True)
    create.add_argument("--label")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create-batch":
        batch = CollectionCoordinator().create_batch(
            target_id=UUID(args.target_id),
            label=args.label,
        )
        print(batch.batch_id)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
