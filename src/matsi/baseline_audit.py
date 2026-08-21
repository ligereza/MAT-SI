"""Phase 4A baseline audit: score G and its baseline on one population.

The historical Phase 4A run reported ``G_prediction_accuracy_on_matched_windows``
over the windows G matched, and ``no_G_baseline_modal_accuracy_over_all_C_windows``
over every window.  Those are two different populations, so the reported gain
mixes prediction quality with coverage.

This module does not overwrite the historical result.  It recomputes the held-out
evaluations, restates the historical numbers, and reports a same-opportunity
comparison in which both G and the baseline are scored on the windows where G
actually makes a prediction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import frozen_source
from .cross_domain import _prediction_metrics, run_phase4


ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_RESULT = ROOT / "results" / "phase4-cross-domain-results.json"


def fair_prediction_metrics(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    """Score G and the no-G modal baseline on the same matched-window population.

    The baseline is the best single constant answer available without G on that
    same population.  A relation only earns credit by beating the best answer a
    machine could give without it on the cases it claims to cover.
    """
    matched = [item for item in evaluations if item["prefix_match"]]
    true_count = sum(1 for item in matched if item["prediction_holds"])
    false_count = len(matched) - true_count
    g_accuracy = true_count / len(matched) if matched else None
    baseline = max(true_count, false_count) / len(matched) if matched else None
    return {
        "population": "matched_windows_only",
        "population_size": len(matched),
        "total_windows": len(evaluations),
        "coverage": len(matched) / len(evaluations) if evaluations else None,
        "G_accuracy": g_accuracy,
        "baseline_modal_accuracy": baseline,
        "predictive_gain": (
            g_accuracy - baseline if g_accuracy is not None and baseline is not None else None
        ),
        "G_beats_baseline": (
            g_accuracy is not None and baseline is not None and g_accuracy > baseline
        ),
        "provenance": {
            "derivation": "modal class of the continuation property restricted to matched windows",
            "rule": "G and baseline are scored on identical windows; coverage is reported separately",
        },
    }


def _historical_view(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "population_of_G": "matched_windows",
        "population_of_baseline": "all_C_windows",
        "populations_are_identical": False,
        "matched_windows": metrics["matched_windows"],
        "total_windows": metrics["total_windows"],
        "G_accuracy": metrics["G_prediction_accuracy_on_matched_windows"],
        "baseline_modal_accuracy": metrics["no_G_baseline_modal_accuracy_over_all_C_windows"],
        "predictive_gain": metrics["predictive_gain"],
        "G_beats_baseline": metrics["G_beats_no_G_baseline"],
        "defect": (
            "the baseline denominator includes windows G never predicts on, so the "
            "reported gain also credits G for not matching a window"
        ),
    }


def run_phase4a_baseline_audit() -> dict[str, Any]:
    phase4 = run_phase4()
    evaluations = phase4["held_out_C"]["evaluations"]
    historical_metrics = _prediction_metrics(evaluations)
    corrected = fair_prediction_metrics(evaluations)

    historical_gate = "A" if historical_metrics["G_beats_no_G_baseline"] else "D"
    corrected_gate = "A" if corrected["G_beats_baseline"] else "D"

    return {
        "protocol": "phase4a-baseline-audit",
        "audited_protocol": "phase4-cross-domain",
        "parent_commit": phase4["parent_commit"],
        "question": "does G beat the best no-G answer on the windows where G predicts",
        "source_resolution": phase4["source_resolution"],
        "reproduction": phase4["reproduction"],
        "historical_metrics": _historical_view(historical_metrics),
        "corrected_metrics": corrected,
        "corrected_predictive_gain": corrected["predictive_gain"],
        "gate_changes_under_corrected_comparison": historical_gate != corrected_gate,
        "gate": {
            "historical_decision": historical_gate,
            "corrected_decision": corrected_gate,
            "historical_meaning": "a relation derived from A+B predicts a held-out property in C",
            "corrected_meaning": (
                "G matches the best no-G answer on its own population; no predictive "
                "advantage survives the same-opportunity comparison"
                if corrected["predictive_gain"] == 0
                else "the corrected comparison keeps a measurable difference"
            ),
        },
        "historical_result_preserved": {
            "path": HISTORICAL_RESULT.name,
            "overwritten": False,
            "identity": frozen_source.content_identity(
                HISTORICAL_RESULT.read_bytes(), frozen_source.TEXT
            )
            if HISTORICAL_RESULT.is_file()
            else None,
        },
        "corpus_limits": {
            "sources_are_authored_fixtures": True,
            "held_out_window_count": corrected["total_windows"],
            "note": (
                "with this population size a single window decides the gate; the audit "
                "reports the arithmetic and does not claim a corrected transfer result"
            ),
        },
        "host_represented_derived": {
            "HOST": ["JSON parsing", "modal class counting"],
            "REPRESENTED": ["frozen G", "held-out window evaluations"],
            "DERIVED": ["historical restatement", "same-population baseline", "gate comparison"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the Phase 4A predictive baseline")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "results" / "phase4a-baseline-audit-results.json",
    )
    args = parser.parse_args(argv)
    result = run_phase4a_baseline_audit()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["gate"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
