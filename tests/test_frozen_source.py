"""The frozen-source identity and availability boundary."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from matsi import frozen_source


class ContentIdentityTests(unittest.TestCase):
    def test_text_identity_ignores_newline_style(self):
        lf = frozen_source.content_identity(b"one\ntwo\n", frozen_source.TEXT)
        crlf = frozen_source.content_identity(b"one\r\ntwo\r\n", frozen_source.TEXT)
        cr = frozen_source.content_identity(b"one\rtwo\r", frozen_source.TEXT)
        self.assertEqual(lf["canonical_sha256"], crlf["canonical_sha256"])
        self.assertEqual(lf["canonical_sha256"], cr["canonical_sha256"])
        self.assertNotEqual(lf["raw_sha256"], crlf["raw_sha256"])
        self.assertEqual(crlf["canonicalization"], "newline_crlf_to_lf")

    def test_binary_identity_stays_byte_sensitive(self):
        first = frozen_source.content_identity(b"\x00\r\n\xff", frozen_source.BINARY)
        second = frozen_source.content_identity(b"\x00\n\xff", frozen_source.BINARY)
        self.assertNotEqual(first["canonical_sha256"], second["canonical_sha256"])
        self.assertEqual(first["canonical_sha256"], first["raw_sha256"])
        self.assertEqual(first["canonicalization"], "none")


class ResolutionTests(unittest.TestCase):
    def _root(self, directory: str) -> Path:
        root = Path(directory)
        (root / "results").mkdir()
        (root / "results" / "owned.json").write_bytes(b'{"a": 1}\n')
        return root

    def test_repo_owned_source_resolves_by_canonical_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            crlf = b'{"a": 1}\r\n'
            spec = {
                "path": "C:/elsewhere/owned.json",
                "repo_path": "results/owned.json",
                "content_kind": "text",
                "sha256": hashlib.sha256(crlf).hexdigest(),
                "canonical_sha256": hashlib.sha256(b'{"a": 1}\n').hexdigest(),
            }
            resolved = frozen_source.resolve_source(spec, source_id="OWNED", root=root, source_map={})
            self.assertEqual(resolved["status"], frozen_source.SOURCE_AVAILABLE)
            self.assertEqual(resolved["resolved_from"], "repo_path")
            self.assertEqual(resolved["identity_matched"], "canonical")
            payload, _ = frozen_source.load_source(spec, source_id="OWNED", root=root, source_map={})
            self.assertEqual(payload, b'{"a": 1}\n')

    def test_absent_private_source_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            spec = {
                "path": "C:/Users/someone/private-evidence.json",
                "content_kind": "text",
                "sha256": "0" * 64,
                "availability": "private_external",
            }
            resolved = frozen_source.resolve_source(spec, source_id="PRIVATE", root=root, source_map={})
            self.assertEqual(resolved["status"], frozen_source.SOURCE_UNAVAILABLE)
            self.assertIsNone(resolved["resolved_from"])
            self.assertIn("exists on this machine", resolved["reason"])
            self.assertFalse(any(item["exists"] for item in resolved["searched"]))
            payload, again = frozen_source.load_source(spec, source_id="PRIVATE", root=root, source_map={})
            self.assertIsNone(payload)
            self.assertEqual(again["status"], frozen_source.SOURCE_UNAVAILABLE)

    def test_hash_mismatch_is_reported_and_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            spec = {
                "path": "results/owned.json",
                "repo_path": "results/owned.json",
                "content_kind": "text",
                "sha256": "1" * 64,
            }
            resolved = frozen_source.resolve_source(spec, source_id="OWNED", root=root, source_map={})
            self.assertEqual(resolved["status"], frozen_source.SOURCE_HASH_MISMATCH)
            with self.assertRaises(frozen_source.FrozenSourceMismatch):
                frozen_source.load_source(spec, source_id="OWNED", root=root, source_map={})

    def test_local_source_map_can_supply_a_private_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            private = root / "outside.json"
            private.write_bytes(b'{"b": 2}\n')
            spec = {
                "path": "C:/Users/someone/outside.json",
                "content_kind": "text",
                "sha256": hashlib.sha256(b'{"b": 2}\n').hexdigest(),
            }
            mapping = {"C:/Users/someone/outside.json": str(private)}
            resolved = frozen_source.resolve_source(spec, source_id="B", root=root, source_map=mapping)
            self.assertEqual(resolved["status"], frozen_source.SOURCE_AVAILABLE)
            self.assertEqual(resolved["resolved_from"], "local_source_map")

    def test_source_map_is_read_from_the_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            mapping_file = root / "map.json"
            mapping_file.write_text(json.dumps({"sources": {"B": "/nowhere/b.json"}}), encoding="utf-8")
            previous = os.environ.get(frozen_source.SOURCE_MAP_ENV)
            os.environ[frozen_source.SOURCE_MAP_ENV] = str(mapping_file)
            try:
                self.assertEqual(frozen_source.load_source_map(root), {"B": "/nowhere/b.json"})
            finally:
                if previous is None:
                    del os.environ[frozen_source.SOURCE_MAP_ENV]
                else:
                    os.environ[frozen_source.SOURCE_MAP_ENV] = previous


class ReproductionStatusTests(unittest.TestCase):
    def test_all_available_is_independently_reproduced(self):
        status = frozen_source.reproduction_status(
            {"A": {"status": frozen_source.SOURCE_AVAILABLE}, "B": {"status": frozen_source.SOURCE_AVAILABLE}}
        )
        self.assertEqual(status["status"], "INDEPENDENTLY_REPRODUCED")
        self.assertTrue(status["independently_reproduced"])

    def test_mixed_and_absent_states_are_named_separately(self):
        partial = frozen_source.reproduction_status(
            {"A": {"status": frozen_source.SOURCE_AVAILABLE}, "B": {"status": frozen_source.SOURCE_UNAVAILABLE}}
        )
        self.assertEqual(partial["status"], "PARTIALLY_REPRODUCED")
        self.assertEqual(partial["unavailable_sources"], ["B"])
        none = frozen_source.reproduction_status({"B": {"status": frozen_source.SOURCE_UNAVAILABLE}})
        self.assertEqual(none["status"], "NOT_INDEPENDENTLY_REPRODUCED")
        self.assertFalse(none["independently_reproduced"])
        self.assertTrue(none["stored_historical_result_is_not_a_reproduction"])


if __name__ == "__main__":
    unittest.main()
