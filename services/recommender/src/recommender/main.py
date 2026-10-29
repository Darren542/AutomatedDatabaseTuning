"""CLI for persisted analysis; prints advisory JSON and never executes tuning SQL."""
import argparse
import json
from uuid import UUID
from recommender.service import RecommendationService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", type=UUID, required=True)
    args = parser.parse_args()
    result = RecommendationService().analyze(args.batch_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
