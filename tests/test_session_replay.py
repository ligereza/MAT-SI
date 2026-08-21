"""Deterministic export and replay of a CODEINE session.

These tests use a real temporary Git repository so the exported record comes from
machine-generated snapshots, not from a fixture written by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from codeine.core import (
    assess,
    checkpoint,
    export_session,
    replay_export,
    replay_session,
    serialize_export,
    start,
    write_export,
)


STABLE_COMMAND = "printf stable"


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "codeine@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "CODEINE Test"], check=True)
    (repo / "value.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "value.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
    return repo


def replay_export_dict(export: dict) -> dict:
    """Replay an in-memory export by writing it to a temporary file first."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "export.json"
        path.write_text(serialize_export(export), encoding="utf-8")
        return replay_export(path)


class SessionReplayTests(unittest.TestCase):
    _repo = staticmethod(make_repo)

    def test_export_is_deterministic_and_replays_to_the_same_recommendation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session, STABLE_COMMAND, "deterministic replay")
            checkpoint(session, "opaque-1")
            checkpoint(session, "opaque-2")
            recorded = assess(session)["recommendation"]
            self.assertEqual(recorded["decision"], "SWITCH")

            first = export_session(session)
            second = export_session(session)
            self.assertEqual(serialize_export(first), serialize_export(second))
            self.assertEqual(first["determinism"]["export_digest"], second["determinism"]["export_digest"])
            self.assertFalse(first["manually_authored"])

            export_path = root / "export.json"
            written = write_export(session, export_path)
            self.assertEqual(written["export_digest"], first["determinism"]["export_digest"])

            replay = replay_export(export_path)
            self.assertTrue(replay["deterministic"])
            self.assertEqual(replay["mismatches"], [])
            self.assertEqual(replay["recommendations_compared"], 1)
            self.assertTrue(replay["export_digest_verified"])

            from_session = replay_session(session, export_path)
            self.assertTrue(from_session["deterministic"])
            self.assertTrue(from_session["export_reproducible_byte_for_byte"])

    def test_replayed_recommendation_equals_the_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session, STABLE_COMMAND, "equality of recomputation")
            checkpoint(session, "opaque-1")
            checkpoint(session, "opaque-2")
            recorded = assess(session)["recommendation"]

            export = export_session(session)
            replayed = export["recommendations"][0]
            for field in ("decision", "evidence_for", "evidence_against", "evidence_strength", "reason", "fingerprint"):
                self.assertEqual(replayed[field], recorded[field], field)
            self.assertTrue(replay_export_dict(export)["deterministic"])

    def test_tampered_recommendation_fails_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session, STABLE_COMMAND, "tamper detection")
            checkpoint(session, "opaque-1")
            checkpoint(session, "opaque-2")
            assess(session)
            export_path = root / "export.json"
            write_export(session, export_path)

            payload = json.loads(export_path.read_text(encoding="utf-8"))
            payload["recommendations"][0]["decision"] = "STOP"
            export_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            replay = replay_export(export_path)
            self.assertFalse(replay["deterministic"])
            self.assertTrue(replay["mismatches"])
            self.assertFalse(replay["export_digest_verified"])

    def test_export_preserves_raw_digests_beside_stable_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session, STABLE_COMMAND, "digest preservation")
            checkpoint(session, "opaque-1")
            export = export_session(session)
            test = export["attempts"][0]["after"]["test"]
            for key in ("stdout_digest", "stderr_digest", "stable_stdout_digest", "stable_stderr_digest"):
                self.assertTrue(test[key], key)
            self.assertEqual(test["availability"], "OBSERVED")

    def test_export_withholds_local_paths_and_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            (repo / "untracked-secret.txt").write_text("private\n", encoding="utf-8")
            start(repo, session, STABLE_COMMAND, "privacy boundary")
            checkpoint(session, "opaque-1")
            serialized = serialize_export(export_session(session))
            self.assertNotIn(str(repo), serialized)
            self.assertNotIn("untracked-secret.txt", serialized)
            self.assertNotIn("private", serialized)
            self.assertIn("withheld_local_path", serialized)

    def test_export_records_no_semantic_conclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session, STABLE_COMMAND, "no semantic labels")
            checkpoint(session, "opaque-1")
            export = export_session(session)
            audit = export["raw_record_label_audit"]
            self.assertEqual(audit["forbidden_keys_present"], [])
            self.assertTrue(audit["raw_records_carry_no_conclusion"])
            self.assertFalse(export["gate_inputs"]["causal_help_claimed"])


class RepetitionStreakTests(unittest.TestCase):
    _repo = staticmethod(make_repo)

    def test_non_consecutive_unchanged_attempts_do_not_become_consecutive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session, STABLE_COMMAND, "non-consecutive repetition")
            first = checkpoint(session, "opaque-1")
            self.assertFalse(first["derived"]["state_changed"])
            (repo / "value.txt").write_text("two\n", encoding="utf-8")
            second = checkpoint(session, "opaque-2")
            self.assertTrue(second["derived"]["state_changed"])
            third = checkpoint(session, "opaque-3")
            self.assertFalse(third["derived"]["state_changed"])

            recommendation = assess(session)["recommendation"]
            self.assertEqual(recommendation["decision"], "CONTINUE")
            self.assertEqual(recommendation["evidence_strength"], "weak_repetition")
            self.assertEqual(recommendation["evaluation"]["consecutive_unchanged_attempts"], 1)
            self.assertEqual(recommendation["evidence_for"], ["attempt-0003"])
            self.assertIn("attempt-0002", recommendation["evidence_against"])

    def test_productive_observable_change_breaks_a_repetition_streak(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session, STABLE_COMMAND, "streak reset")
            checkpoint(session, "opaque-1")
            checkpoint(session, "opaque-2")
            self.assertEqual(assess(session)["decision"], "SWITCH")

            (repo / "value.txt").write_text("three\n", encoding="utf-8")
            changed = checkpoint(session, "opaque-3")
            self.assertTrue(changed["derived"]["state_changed"])

            recommendation = assess(session)["recommendation"]
            self.assertEqual(recommendation["decision"], "CONTINUE")
            self.assertEqual(recommendation["evidence_strength"], "observed_change")
            self.assertEqual(recommendation["evaluation"]["consecutive_unchanged_attempts"], 0)
            self.assertEqual(recommendation["evidence_for"], [])
            self.assertIn("attempt-0003", recommendation["evidence_against"])


if __name__ == "__main__":
    unittest.main()
