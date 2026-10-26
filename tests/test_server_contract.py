"""Offline authoring and saved-trace semantics, independent of native engines."""
import base64
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from mcp.server.mcpserver.exceptions import ToolError

from fastmean_mcp import server
from fastmean_mcp.artifacts import ArtifactStore
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
            self.assertEqual(server.output_dir(), (self.root / "results").resolve())
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


class PersistedImageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.job = self.root / "preview-job"
        self.job.mkdir()
        self.png = self.job / "plot.png"
        self.original = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB9sAAAAASUVORK5CYII=")
        self.png.write_bytes(self.original)
        self.store = ArtifactStore(self.root)
        self.record = self.store.publish({"ok": True, "working_dir": str(self.job),
                                          "plot_path": str(self.png)})
        environment = patch.dict("os.environ", {"FASTMEAN_OUTPUT_DIR": str(self.root),
                                                "FASTMEAN_APP_DIR": str(self.root / "absent-app")})
        environment.start()
        self.addCleanup(environment.stop)

    def images(self):
        result = server.fastmean_get_result(self.record["run_id"])
        return [base64.b64decode(item.data) for item in result.content if item.type == "image"]

    def test_reopened_inline_image_matches_registered_artifact(self):
        self.assertEqual(self.images(), [self.original])

    def test_reopened_inline_image_rejects_same_size_modification(self):
        self.png.write_bytes(self.original[:-1] + bytes([self.original[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, "changed after publication"):
            self.store.read_artifact(self.record["run_id"], "plot.png")
        with self.assertRaisesRegex(ToolError, "changed after publication"):
            self.images()

    def test_inline_image_uses_this_runs_catalog_not_an_absolute_result_path(self):
        other = self.root / "another-job"
        other.mkdir()
        foreign = other / "plot.png"
        foreign.write_bytes(b"unrelated image bytes")
        self.record["plot_path"] = str(foreign)
        (self.job / "mcp-result.json").write_text(json.dumps(self.record), encoding="utf-8")
        self.assertEqual(self.images(), [self.original])


class SymbolicPrerequisiteTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_worker_is_reported_before_native_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source.scm"
            create_circuit(example_circuit(), source)
            app = root / "app"
            app.mkdir()
            (app / "Fastmean.exe").write_bytes(b"fixture; must never launch")
            with patch.dict("os.environ", {"FASTMEAN_APP_DIR": str(app),
                                           "FASTMEAN_OUTPUT_DIR": str(root / "runs")}):
                with patch.object(server, "native_operation") as launch:
                    for missing in ("cirsymw.exe", "human.sym"):
                        with self.subTest(missing=missing):
                            symbolic = app / "symbolic"
                            symbolic.mkdir(exist_ok=True)
                            for name in ("cirsymw.exe", "human.sym"):
                                file = symbolic / name
                                if name == missing:
                                    file.unlink(missing_ok=True)
                                else:
                                    file.write_bytes(b"fixture")
                            self.assertFalse(server.fastmean_status()["symbolic_available"])
                            with self.assertRaisesRegex(ToolError, "symbolic.*" + missing):
                                await server.fastmean_symbolic(str(source))
                    launch.assert_not_called()
            self.assertFalse((root / "runs").exists())

    async def test_disappearing_worker_keeps_its_error_and_export_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source.scm"
            create_circuit(example_circuit(), source)
            app = root / "app"
            (app / "symbolic").mkdir(parents=True)
            for file in (app / "Fastmean.exe", app / "symbolic" / "cirsymw.exe",
                         app / "symbolic" / "human.sym"):
                file.write_bytes(b"fixture; must never launch")
            job = root / "runs" / "export-job"
            job.mkdir(parents=True)
            text = "R1 1 2 1k\nC1 2 0 1u 0\nU1 0 1 AC 1 1k 0 -1 0\nin 1\nout 2\n"
            netlist = job / "netlist.txt"
            netlist.write_text(text, encoding="ascii")
            native = SimpleNamespace(cancel_event=threading.Event(), export_netlist=lambda _: {
                "ok": True, "working_dir": str(job), "path": str(netlist), "text": text})
            async def execute(name, path, operation):
                return operation(native)
            failure = {"ok": False, "cwd": None, "equations": [],
                       "error": {"kind": "engine_missing", "message": "Worker disappeared"}}
            with patch.dict("os.environ", {"FASTMEAN_APP_DIR": str(app),
                                           "FASTMEAN_OUTPUT_DIR": str(root / "runs")}):
                with patch.object(server, "native_operation", side_effect=execute), \
                        patch.object(server, "run_symbolic", return_value=failure):
                    result = await server.fastmean_symbolic(str(source))
            self.assertTrue(result.is_error)
            self.assertEqual(result.structured_content["error"]["kind"], "engine_missing")
            self.assertIn("netlist.txt", {entry["name"] for entry in result.structured_content["artifacts"]})


if __name__ == "__main__":
    unittest.main()
