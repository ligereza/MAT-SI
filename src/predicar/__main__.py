"""Non-executing status entry point for the prepared laboratory."""

from __future__ import annotations

import json

from .bootstrap import INITIAL_SPEC, research_area_ids


def main() -> int:
    print(
        json.dumps(
            {
                "protocol": "predicar-v0",
                "status": "prepared_not_started",
                "spec": {
                    "universe_size": INITIAL_SPEC.universe_size,
                    "cardinality": INITIAL_SPEC.cardinality,
                },
                "research_areas": research_area_ids(),
                "execution": {
                    "fit": False,
                    "forecast": False,
                    "score": False,
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
