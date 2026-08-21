import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from codeine.core import assess, checkpoint, finish, start


class CodeineV0Tests(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "codeine@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "CODEINE Test"], check=True)
        (repo / "value.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "value.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
        return repo

    def test_two_unchanged_boundaries_emit_switch_with_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            command = 'python -c "print(\'stable\')"'
            started = start(repo, session, command, "real debugging context")
            first = checkpoint(session, "opaque-1")
            self.assertFalse(first["derived"]["state_changed"])
            second = checkpoint(session, "opaque-2")
            self.assertFalse(second["derived"]["state_changed"])
            recommendation = assess(session)
            self.assertEqual(recommendation["decision"], "SWITCH")
            self.assertEqual(recommendation["recommendation"]["evidence_for"], ["attempt-0001", "attempt-0002"])
            self.assertTrue(recommendation["recommendation"]["evaluation"]["no_hidden_score"])
            self.assertIn("before", first["record"])
            self.assertIn("intervention", first["record"])
            self.assertIn("after", first["record"])
            self.assertIn("provenance", first["record"])
            self.assertNotIn("success", first["record"])
            self.assertNotIn("progress", first["record"])
            self.assertNotIn("stuck", first["record"])
            self.assertEqual(started["hypothesis"]["id"], "persistence_without_observable_change")

    def test_productive_change_emits_continue_and_is_evidence_against_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            command = 'python -c "print(\'stable\')"'
            start(repo, session, command)
            (repo / "value.txt").write_text("two\n", encoding="utf-8")
            checkpoint(session, "opaque-1")
            (repo / "value.txt").write_text("three\n", encoding="utf-8")
            checkpoint(session, "opaque-2")
            recommendation = assess(session)
            self.assertEqual(recommendation["decision"], "CONTINUE")
            self.assertEqual(recommendation["recommendation"]["evidence_for"], [])
            self.assertEqual(recommendation["recommendation"]["evidence_against"], ["attempt-0001", "attempt-0002"])

    def test_missing_resource_measurement_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            start(repo, session)
            checkpoint(session, "opaque-1")
            self.assertEqual(assess(session)["decision"], "UNKNOWN")

    def test_consequence_is_observed_without_claiming_causality(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._repo(root)
            session = root / "session.json"
            command = 'python -c "print(\'stable\')"'
            start(repo, session, command)
            checkpoint(session, "opaque-1")
            checkpoint(session, "opaque-2")
            assess(session)
            (repo / "value.txt").write_text("fixed\n", encoding="utf-8")
            checkpoint_result = checkpoint(session, "opaque-switch")
            self.assertTrue(checkpoint_result["derived"]["state_changed"])
            data = json.loads(session.read_text(encoding="utf-8"))
            consequence = data["recommendations"][0]["consequence"]
            self.assertEqual(consequence["observed_in_attempt"], "attempt-0003")
            self.assertFalse(consequence["causal_effect_claimed"])
            summary = finish(session)["summary"]
            self.assertEqual(summary["attempt_count"], 3)


if __name__ == "__main__":
    unittest.main()
