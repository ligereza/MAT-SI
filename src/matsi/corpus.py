"""Loading and validating the common Phase 1 corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_corpus(path: str | Path = "corpus/phase1.json") -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        corpus = json.load(handle)
    if not isinstance(corpus, list) or len(corpus) != 9:
        raise ValueError("Phase 1 corpus must contain exactly nine cases")
    identifiers = [case.get("id") for case in corpus]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("corpus identifiers must be unique")
    return corpus
