"""Lock the concrete reproducibility failures found by the independent audit.

Each test here reproduces one failure observed while auditing the accepted state
from a second machine.  They are written before the fixes so the failure mode is
recorded as executable evidence rather than prose.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from matsi import frozen_source
from matsi.baseline_audit import fair_prediction_metrics, run_phase4a_baseline_audit
from matsi.canonical import canonical_newline_bytes
from matsi.minimum_observability import run_phase4c
from matsi.real_experience_transfer import run_phase4b


ROOT = Path(__file__).resolve().parents[1]


class FailureALineEndingIdentity(unittest.TestCase):
    """A: repo-owned textual evidence must not lose its identity on LF vs CRLF."""

    def test_canonical_newline_bytes_collapses_crlf_to_lf(self):
        self.assertEqual(canonical_newline_bytes(b"a\r\nb\r\n"), b"a\nb\n")
        self.assertEqual(canonical_newline_bytes(b"a\nb\n"), b"a\nb\n")

    def test_repo_owned_text_identity_is_stable_across_checkout_newlines(self):
        payload = (ROOT / "results" / "phase2-self-reference-results.json").read_bytes()
        lf = payload.replace(b"\r\n", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        self.assertNotEqual(
            frozen_source.content_identity(lf, "text")["raw_sha256"],
            frozen_source.content_identity(crlf, "text")["raw_sha256"],
            "the historical raw byte hash is newline sensitive; that is the failure",
        )
        self.assertEqual(
            frozen_source.content_identity(lf, "text")["canonical_sha256"],
            frozen_source.content_identity(crlf, "text")["canonical_sha256"],
            "canonical identity must ignore checkout newline style",
        )

    def test_binary_sources_stay_byte_sensitive(self):
        identity = frozen_source.content_identity(b"\x00\r\n\x01", "binary")
        self.assertEqual(identity["canonicalization"], "none")
        self.assertEqual(identity["canonical_sha256"], identity["raw_sha256"])

    def test_phase4c_matsi_source_is_declared_repo_owned(self):
        manifest = json.loads(
            (ROOT / "corpus" / "phase4c-observability-manifest.json").read_text(encoding="utf-8")
        )
        spec = next(item for item in manifest["sources"] if item["system_id"] == "MAT-SI")
        self.assertIn("repo_path", spec)
        self.assertIn("canonical_sha256", spec)
        resolved = frozen_source.resolve_source(spec, source_id="MAT-SI", root=ROOT)
        self.assertEqual(resolved["status"], frozen_source.SOURCE_AVAILABLE)
        self.assertEqual(resolved["resolved_from"], "repo_path")


class FailureBAbsentPrivateEvidence(unittest.TestCase):
    """B: absent private evidence must degrade explicitly instead of crashing."""

    def test_phase4b_does_not_crash_without_private_sources(self):
        result = run_phase4b()
        self.assertIn("source_resolution", result)
        self.assertIn("reproduction", result)
        self.assertIn(
            result["reproduction"]["status"],
            {"INDEPENDENTLY_REPRODUCED", "PARTIALLY_REPRODUCED", "NOT_INDEPENDENTLY_REPRODUCED"},
        )

    def test_phase4c_does_not_crash_without_private_sources(self):
        result = run_phase4c()
        self.assertIn("source_resolution", result)
        self.assertIn("reproduction", result)
        self.assertEqual(
            result["minimal_record"]["mandatory_fields"],
            ["before", "intervention", "after", "provenance"],
            "the analytical contract does not depend on private sources",
        )

    def test_unavailable_source_is_not_relabeled_as_reproduced(self):
        result = run_phase4c()
        unavailable = result["reproduction"]["unavailable_sources"]
        if unavailable:
            self.assertFalse(result["reproduction"]["independently_reproduced"])
            self.assertTrue(result["reproduction"]["not_independently_reproducible"])


class FailureCManuallyAuthoredEvidence(unittest.TestCase):
    """C: session summaries must be produced by executable code."""

    def test_export_and_replay_entry_points_exist(self):
        from codeine import core

        for name in ("export_session", "replay_export", "replay_session"):
            self.assertTrue(callable(getattr(core, name, None)), f"missing {name}")

    def test_committed_linux_session_is_replayable_without_the_raw_session(self):
        from codeine import core

        export_path = ROOT / "results" / "codeine-linux-session.json"
        self.assertTrue(export_path.exists(), "a machine-generated session export must be committed")
        replay = core.replay_export(export_path)
        self.assertTrue(replay["deterministic"])
        self.assertEqual(replay["mismatches"], [])
        self.assertGreater(replay["recommendations_compared"], 0)


class FailureDPhase4ABaselinePopulation(unittest.TestCase):
    """D: G and its baseline must be scored on the same prediction population."""

    def test_fair_metrics_use_one_population(self):
        evaluations = [
            {"prefix_match": True, "prediction_holds": True},
            {"prefix_match": True, "prediction_holds": False},
            {"prefix_match": True, "prediction_holds": True},
            {"prefix_match": False, "prediction_holds": True},
        ]
        metrics = fair_prediction_metrics(evaluations)
        self.assertEqual(metrics["population"], "matched_windows_only")
        self.assertEqual(metrics["population_size"], 3)
        self.assertAlmostEqual(metrics["G_accuracy"], 2 / 3)
        self.assertAlmostEqual(metrics["baseline_modal_accuracy"], 2 / 3)
        self.assertAlmostEqual(metrics["predictive_gain"], 0.0)
        self.assertFalse(metrics["G_beats_baseline"])

    def test_audit_reports_historical_and_corrected_comparison(self):
        audit = run_phase4a_baseline_audit()
        historical = audit["historical_metrics"]
        corrected = audit["corrected_metrics"]
        self.assertNotEqual(
            historical["population_of_G"],
            historical["population_of_baseline"],
            "the historical comparison used two different populations; that is the failure",
        )
        self.assertEqual(corrected["population"], "matched_windows_only")
        self.assertIn("gate_changes_under_corrected_comparison", audit)
        self.assertIn("historical_result_preserved", audit)


if __name__ == "__main__":
    unittest.main()
