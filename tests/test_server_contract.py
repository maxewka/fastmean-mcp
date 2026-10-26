"""Offline authoring and saved-trace semantics, independent of native engines."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp import server
from fastmean_mcp.schematic import _load, _write_document, create_circuit, example_circuit


class ServerContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.scm"
        create_circuit(example_circuit(), self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def test_offline_status_and_authoring_do_not_require_a_fake_executable(self):
        with patch.dict("os.environ", {"FASTMEAN_APP_DIR": str(self.root / "absent-app"),
                                      "FASTMEAN_OUTPUT_DIR": str(self.root / "results")}):
            status = server.fastmean_status()
            self.assertTrue(status["ok"])
            self.assertFalse(status["installed"])
            self.assertIsNone(status["executable_sha256"])
            self.assertIn("Fastmean.exe", status["installation_error"])
            self.assertFalse((self.root / "results").exists())
            self.assertEqual(server.output_dir(), self.root / "results")
            with self.assertRaises(FileNotFoundError):
                server.engine()

    def test_offline_output_still_rejects_installation_directory(self):
        with patch.dict("os.environ", {"FASTMEAN_APP_DIR": str(self.root / "absent-app"),
                                      "FASTMEAN_OUTPUT_DIR": str(self.root / "absent-app" / "results")}):
            with self.assertRaisesRegex(ValueError, "outside"):
                server.output_dir()

    def test_saved_disabled_stale_traces_are_not_sent_to_native_solver(self):
        _, document, _ = _load(self.source)
        document["scm"]["FD"]["Expressions"] = [
            {"plot": None, "x": "f", "y": "undefined_expression"},
            {"plot": 0, "x": "f", "y": "another_stale_trace"},
            {"plot": 1, "x": "f", "y": "mag(U(out))"},
            {"plot": 2, "x": "f", "y": "mag(U(out))"},
        ]
        _write_document(document, self.source, overwrite=True)
        before = self.source.read_bytes()
        self.assertEqual(server._saved_signals(self.source, "FD"), ["mag(U(out))"])
        self.assertEqual(self.source.read_bytes(), before)

    def test_saved_custom_xy_axis_requires_explicit_signals(self):
        _, document, _ = _load(self.source)
        document["scm"]["FD"]["Expressions"] = [{"plot": 1, "x": "Re(T(p))", "y": "Im(T(p))"}]
        _write_document(document, self.source, overwrite=True)
        with self.assertRaisesRegex(ValueError, "custom x axis"):
            server._saved_signals(self.source, "FD")
        document["scm"]["FD"]["Expressions"][0]["plot"] = None
        _write_document(document, self.source, overwrite=True)
        with self.assertRaisesRegex(ValueError, "explicit signals"):
            server._saved_signals(self.source, "FD")


if __name__ == "__main__":
    unittest.main()
