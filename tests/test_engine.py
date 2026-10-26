"""Safety, parser and actual native RC numerical regression tests."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import yaml

from fastmean_mcp.engine import Engine, EngineError, parse_native_table, prepare_copy, validate_signal
from fastmean_mcp.schematic import create_circuit, example_circuit


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EngineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-engine-test-")
        self.root = Path(self.temporary.name)
        self.app = self.root / "app"
        self.app.mkdir()
        (self.app / "Fastmean.exe").write_bytes(b"dummy fixture; never execute")
        self.source = self.root / "source.scm"
        create_circuit(example_circuit(), self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def test_private_copy_disables_saved_side_effects_preserves_model_and_original(self):
        doc = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        body = doc["scm"]
        body["AOD"]["DrawGraph"] = 1
        body["TD"]["IC"] = 2
        body["TD"]["SVD"].update({"IC": 2, "SVWriteFlag": 1, "SV2SchemeFlag": 1,
                                    "SVPredictFlag": 1, "ICReadFileName": "outside.sv"})
        for key in ("TD", "FD"):
            body[key]["ParamSweep"] = 1
            body[key]["FFT"] = 1
            body[key]["PSD"][0]["On"] = 1
        body["Scheme"]["Objects"].append({"ID": 300, "Type": 6615, "Name": "MOS1",
                                             "Params": {"native_model": "preserve verbatim"}})
        self.source.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        before = digest(self.source)
        target = self.root / "copy.scm"
        self.assertEqual(prepare_copy(self.source, target), target.resolve())
        safe = yaml.safe_load(target.read_text(encoding="utf-8"))["scm"]
        self.assertEqual(digest(self.source), before)
        self.assertEqual(safe["Scheme"], body["Scheme"])
        self.assertEqual(safe["TD"]["IC"], 0)
        self.assertEqual(safe["AOD"]["DrawGraph"], 0)
        for key in ("TD", "FD"):
            self.assertEqual(safe[key]["ParamSweep"], 0)
            self.assertEqual(safe[key]["FFT"], 0)
            self.assertFalse(any(item["On"] for item in safe[key]["PSD"]))
        for key in ("IC", "SVWriteFlag", "SV2SchemeFlag", "SVPredictFlag"):
            self.assertEqual(safe["TD"]["SVD"][key], 0)
        with self.assertRaises(EngineError):
            prepare_copy(self.source, self.source)
        with self.assertRaises(EngineError):
            prepare_copy(self.source, target)

    def test_schematic_output_directives_rejected_before_destination_write(self):
        for text in ['.write "outside.txt" t U(out);', '.include "outside.scm"',
                     '.read "outside.sv"', '.save "outside.scm"', '.WRITE after 1u']:
            with self.subTest(text=text):
                doc = yaml.safe_load(self.source.read_text(encoding="utf-8"))
                doc["scm"]["Scheme"]["Objects"].append({"ID": 999, "Type": 900,
                                                           "Params": {"Text": text}})
                candidate = self.root / "candidate.scm"
                candidate.write_text(yaml.safe_dump(doc), encoding="utf-8")
                with self.assertRaisesRegex(EngineError, "Embedded"):
                    prepare_copy(candidate, self.root / "unsafe-copy.scm")
                self.assertFalse((self.root / "unsafe-copy.scm").exists())

    def test_signal_validator_accepts_math_and_rejects_script_fragments(self):
        for signal in ["db(U(out)/U(in))", "phs(U(out)/U(in))", "I(R1)",
                       "U(out) + 2 * I(R1)", "exp(-t/(R1.R*C1.C))", "max(U(out),0)"]:
            with self.subTest(signal=signal):
                self.assertTrue(validate_signal(signal))
        for signal in ['U(out);exit;', 'U(out)\nexit', '"out.txt"', 'U(out)%ignored',
                       'write(U(out))', 'U(out) read', 'U(out', 'U(out)[1]', 'U(выход)',
                       'U(out)=1', '1 2', 'U(out)\\bad', 'exit']:
            with self.subTest(signal=signal), self.assertRaises(EngineError):
                validate_signal(signal)

    def test_native_table_crcrlf_finite_columns_and_limits(self):
        table = self.root / "native.txt"
        table.write_bytes(b"0 0 1\r\r\n1D-3 .5 2\r\n\r\n2e-3 1 3\n")
        self.assertEqual(parse_native_table(table, 3), [[0., 0., 1.], [.001, .5, 2.], [.002, 1., 3.]])
        with self.assertRaises(EngineError):
            parse_native_table(table, 3, max_rows=2)
        for content in (b"0 1\n1 2 3", b"0 NaN", b"0 inf", b"f output", b"\n\r\n"):
            with self.subTest(content=content):
                table.write_bytes(content)
                with self.assertRaises(EngineError):
                    parse_native_table(table, 2)
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaisesRegex(EngineError, "cancelled"):
            parse_native_table(table, 2, cancelled=cancelled)

    def test_unicode_si_normalization_is_limited_to_known_numeric_fields(self):
        doc = yaml.safe_load(self.source.read_text())
        objects = doc["scm"]["Scheme"]["Objects"]
        resistor = next(item for item in objects if item["Name"] == "R1")
        resistor["Params"]["R"] = "1к"
        objects.append({"ID": 900, "Type": 900, "Name": "label", "Params": {"Text": "1к"}})
        objects.append({"ID": 901, "Type": 6615, "Name": "unknown", "Params": {"native_model": "1к"}})
        self.source.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        before = digest(self.source)
        engine = Engine(self.app, self.root / "jobs")
        job, manifest = engine._job(self.source, "ac")
        private = yaml.safe_load((job / "circuit.scm").read_text(encoding="utf-8"))
        copied = private["scm"]["Scheme"]["Objects"]
        self.assertEqual(next(item for item in copied if item["Name"] == "R1")["Params"]["R"], 1000)
        self.assertEqual(copied[-2]["Params"]["Text"], "1к")
        self.assertEqual(copied[-1]["Params"]["native_model"], "1к")
        changes = manifest["source_models"][0]["numeric_normalizations"]
        self.assertEqual(changes, [{"component": "R1", "type": 1000, "field": "R",
                                    "original": "1к", "si_value": 1000}])
        self.assertEqual(digest(self.source), before)

    def test_limits_and_installed_directory_protection_precede_native_launch(self):
        forbidden = self.app / "must-not-be-created"
        with self.assertRaisesRegex(EngineError, "outside"):
            Engine(self.app, forbidden)
        self.assertFalse(forbidden.exists())
        engine = Engine(self.app, self.root / "jobs")
        with patch("fastmean_mcp.engine.subprocess.Popen") as launch:
            for call in [lambda: engine.run_ac(self.source, points=10001),
                         lambda: engine.run_ac(self.source, fmin=10, fmax=1),
                         lambda: engine.run_transient(self.source, stop=1, step=1e-9),
                         lambda: engine.run_transient(self.source, stop=0),
                         lambda: engine.run_transient(self.source, eps=1),
                         lambda: engine.run_ac(self.source, signals=['U(out);exit'])]:
                with self.assertRaises(ValueError):
                    call()
            launch.assert_not_called()

    def test_timeout_kills_only_the_process_created_for_this_job(self):
        engine = Engine(self.app, self.root / "jobs", timeout=.01)
        job, manifest = engine._job(self.source, "ac")
        owned = Mock()
        owned.pid, owned.returncode = 12345, None
        owned.poll.return_value = None
        def kill():
            owned.returncode = -9
            owned.poll.return_value = -9
        def communicate(timeout):
            if owned.poll() is None:
                time.sleep(min(timeout, .005))
                raise subprocess.TimeoutExpired("owned", timeout)
            return b"", b""
        owned.kill.side_effect = kill
        owned.communicate.side_effect = communicate
        with patch("fastmean_mcp.engine.subprocess.Popen", return_value=owned) as launch:
            with self.assertRaisesRegex(EngineError, "only owned PID 12345"):
                engine._execute(job, manifest, 'open "circuit.scm";\nexit;\n')
        owned.kill.assert_called_once_with()
        self.assertEqual(launch.call_count, 1)
        # Windows TEMP may use a DOS 8.3 alias (RUNNER~1) while Engine resolves
        # the installed executable to its canonical filesystem path.
        self.assertEqual(Path(launch.call_args.args[0][0]).resolve(),
                         (self.app / "Fastmean.exe").resolve())
        saved = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "timed_out")
        self.assertEqual(saved["owned_pid"], 12345)

    def test_cancel_event_stops_only_owned_worker_and_records_cancellation(self):
        engine = Engine(self.app, self.root / "jobs", timeout=30)
        owned = Mock()
        owned.pid, owned.returncode = 54321, None
        owned.poll.return_value = None
        started = threading.Event()
        def kill():
            owned.returncode = -9
            owned.poll.return_value = -9
        def communicate(timeout):
            if owned.poll() is None:
                started.set()
                time.sleep(.01)
                raise subprocess.TimeoutExpired("owned", timeout)
            return b"", b""
        owned.kill.side_effect = kill
        owned.communicate.side_effect = communicate
        errors = []
        def run():
            try:
                engine.run_ac(self.source, ["U(out)"])
            except Exception as error:
                errors.append(error)
        with patch("fastmean_mcp.engine.subprocess.Popen", return_value=owned):
            worker = threading.Thread(target=run)
            worker.start()
            self.assertTrue(started.wait(3))
            engine.cancel()
            self.assertTrue(engine.cancel_event.is_set())
            worker.join(3)
            self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], EngineError)
        self.assertIn("cancelled", str(errors[0]))
        owned.kill.assert_called_once_with()
        manifests = list((self.root / "jobs").glob("*/manifest.json"))
        self.assertEqual(json.loads(manifests[0].read_text())["status"], "cancelled")
        self.assertFalse(engine._active_processes)
        fresh = engine._begin_request()
        self.assertTrue(fresh.is_set())
        self.assertTrue(engine.cancel_event.is_set())
        engine._end_request(fresh)

    def test_cancellation_before_worker_start_never_launches_native_process(self):
        engine = Engine(self.app, self.root / "jobs")
        engine.cancel()
        with patch("fastmean_mcp.engine.subprocess.Popen") as launch:
            with self.assertRaisesRegex(EngineError, "cancelled"):
                engine.run_ac(self.source, ["U(out)"])
            launch.assert_not_called()
        manifest = next((self.root / "jobs").glob("*/manifest.json"))
        self.assertEqual(json.loads(manifest.read_text())["status"], "cancelled")

    def test_keyboard_interrupt_cleans_up_owned_process(self):
        engine = Engine(self.app, self.root / "jobs")
        job, manifest = engine._job(self.source, "ac")
        owned = Mock()
        owned.pid, owned.returncode = 111, None
        owned.poll.return_value = None
        def kill():
            owned.returncode = -9
            owned.poll.return_value = -9
        owned.kill.side_effect = kill
        owned.communicate.side_effect = [KeyboardInterrupt(), (b"", b"")]
        with patch("fastmean_mcp.engine.subprocess.Popen", return_value=owned):
            with self.assertRaises(KeyboardInterrupt):
                engine._execute(job, manifest, 'open "circuit.scm";\nexit;\n')
        owned.kill.assert_called_once_with()
        self.assertEqual(json.loads((job / "manifest.json").read_text())["status"], "cancelled")

    def test_recursive_model_packaging_and_unsafe_dependency_failures(self):
        model_dir = self.root / "models"
        model_dir.mkdir()
        child = model_dir / "child.scm"
        create_circuit(example_circuit(), child)
        doc = yaml.safe_load(self.source.read_text())
        doc["scm"]["Scheme"]["Objects"].append({"ID": 999, "Type": 7100, "Name": "MODEL1",
                                                   "Params": {"FileName": "models\\child.scm"}})
        self.source.write_text(yaml.safe_dump(doc), encoding="utf-8")
        source_before, child_before = digest(self.source), digest(child)
        target = prepare_copy(self.source, self.root / "packed.scm")
        packed = yaml.safe_load(target.read_text())
        model_path = Path(packed["scm"]["Scheme"]["Objects"][-1]["Params"]["FileName"])
        self.assertTrue(model_path.is_absolute())
        self.assertTrue(model_path.is_file())
        self.assertNotEqual(model_path, child)
        self.assertEqual(digest(self.source), source_before)
        self.assertEqual(digest(child), child_before)
        self.assertEqual(yaml.safe_load(model_path.read_text())["scm"]["AOD"]["DrawGraph"], 0)
        # A recursive model would not be a finite circuit: reject before making
        # any native-readable root or model copy.
        doc["scm"]["Scheme"]["Objects"][-1]["Params"]["FileName"] = "source.scm"
        self.source.write_text(yaml.safe_dump(doc), encoding="utf-8")
        with self.assertRaisesRegex(EngineError, "cycle"):
            prepare_copy(self.source, self.root / "cycle.scm")
        self.assertFalse((self.root / "cycle.scm").exists())
        doc["scm"]["Scheme"]["Objects"][-1]["Params"]["FileName"] = "missing.scm"
        self.source.write_text(yaml.safe_dump(doc), encoding="utf-8")
        with self.assertRaisesRegex(EngineError, "missing"):
            prepare_copy(self.source, self.root / "missing.scm")


_APP = Path(os.environ.get("FASTMEAN_APP_DIR", str(Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1")))
_NATIVE_AVAILABLE = os.name == "nt" and (_APP / "Fastmean.exe").is_file()


@unittest.skipUnless(_NATIVE_AVAILABLE, "Installed FASTMEAN is required for native numeric regression tests.")
class NativeEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-native-test-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "rc.scm"
        self.engine = Engine(_APP, self.root / "jobs")

    def tearDown(self):
        self.temporary.cleanup()

    def test_native_rc_ac_matches_analytic_response(self):
        create_circuit(example_circuit(), self.source)
        before = digest(self.source)
        result = self.engine.run_ac(self.source, ["db(U(out)/U(in))", "phs(U(out)/U(in))"], 1, 1e6, 31)
        self.assertEqual(result["row_count"], 31)
        for frequency, magnitude, phase in result["rows"]:
            w_tau = 2 * math.pi * frequency * .001
            self.assertAlmostEqual(magnitude, -10 * math.log10(1 + w_tau ** 2), delta=1e-7)
            self.assertAlmostEqual(phase, -math.degrees(math.atan(w_tau)), delta=1e-7)
        self.assertEqual(digest(self.source), before)
        self.assertTrue(Path(result["csv_path"]).is_file())
        self.assertEqual(Path(result["plot_path"]).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["source_sha256"], before)
        self.assertEqual(manifest["returncode"], 0)

    def test_existing_russian_si_literals_match_native_rc_response(self):
        create_circuit(example_circuit(), self.source)
        doc = yaml.safe_load(self.source.read_text())
        for obj in doc["scm"]["Scheme"]["Objects"]:
            if obj["Name"] == "R1":
                obj["Params"]["R"] = "1к"
            elif obj["Name"] == "C1":
                obj["Params"]["C"] = "1мк"
            elif obj["Name"] == "U1":
                obj["Params"]["AC"]["F"] = "1к"
                obj["Params"]["DC"]["TFR"] = "1н"
        self.source.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        before = digest(self.source)
        result = self.engine.run_ac(self.source, ["db(U(out)/U(in))"], 1, 1000, 4)
        for frequency, magnitude in result["rows"]:
            self.assertAlmostEqual(magnitude, -10 * math.log10(1 + (2 * math.pi * frequency * .001) ** 2), delta=1e-7)
        self.assertEqual(digest(self.source), before)
        changes = result["source_models"][0]["numeric_normalizations"]
        self.assertEqual({item["field"] for item in changes}, {"R", "C", "AC.F", "DC.TFR"})

    def test_native_rc_dc_step_matches_charging_curve(self):
        spec = example_circuit()
        spec["components"][0]["waveform"] = {"kind": "dc"}
        create_circuit(spec, self.source)
        before = digest(self.source)
        result = self.engine.run_transient(self.source, ["U(in)", "U(out)"], .005, 1e-5, 1e-5)
        self.assertGreaterEqual(result["row_count"], 501)
        self.assertAlmostEqual(result["rows"][0][0], 0)
        self.assertAlmostEqual(result["rows"][-1][0], .005)
        errors = [abs(row[2] - (1 - math.exp(-row[0] / .001))) for row in result["rows"]]
        # Native voltage-source TFR=1 ns produces a small, documented ramp.
        self.assertLess(max(errors), 2e-5)
        self.assertAlmostEqual(result["rows"][-1][2], 1 - math.exp(-5), delta=2e-5)
        self.assertEqual(digest(self.source), before)

    def test_native_netlist_export_contains_actual_component_values(self):
        create_circuit(example_circuit(), self.source)
        result = self.engine.export_netlist(self.source)
        self.assertTrue(Path(result["path"]).is_file())
        self.assertTrue(result["text"].strip())
        self.assertIn("R1", result["text"])
        self.assertIn("C1", result["text"])
        self.assertIn("U1", result["text"])
        self.assertEqual(result["engine"]["name"], "FASTMEAN native CLI")

    def test_saved_linear_scale_is_overridden_by_explicit_sampling_request(self):
        create_circuit(example_circuit(), self.source)
        doc = yaml.safe_load(self.source.read_text())
        doc["scm"]["FD"]["ScaleX"] = 1
        # Stale saved graph expressions must not override explicit MCP signals.
        doc["scm"]["FD"]["Expressions"] = [{"plot": 1, "x": "f", "y": "U(missing_node)"}]
        self.source.write_text(yaml.safe_dump(doc), encoding="utf-8")
        before = digest(self.source)
        result = self.engine.run_ac(self.source, ["mag(U(out)/U(in))"], 1, 1000, 4)
        for observed, expected in zip([r[0] for r in result["rows"]], [1, 10, 100, 1000]):
            self.assertAlmostEqual(observed, expected, delta=1e-8)
        linear = self.engine.run_ac(self.source, ["mag(U(out)/U(in))"], 1, 1000, 4, scale="linear")
        self.assertEqual([r[0] for r in linear["rows"]], [1, 334, 667, 1000])
        self.assertEqual(linear["sampling"], "linear")
        self.assertEqual(digest(self.source), before)

    def test_stored_component_ic_is_preserved_and_transient_starts_at_zero(self):
        spec = example_circuit()
        spec["components"][0]["waveform"] = {"kind": "dc"}
        spec["components"][2]["initial_condition"] = .25
        create_circuit(spec, self.source)
        doc = yaml.safe_load(self.source.read_text())
        doc["scm"]["TD"]["IPNum"] = 2
        doc["scm"]["TD"]["IP"][0]["StartTime"] = .002
        doc["scm"]["TD"]["IP"].append(dict(doc["scm"]["TD"]["IP"][0]))
        self.source.write_text(yaml.safe_dump(doc), encoding="utf-8")
        before = digest(self.source)
        result = self.engine.run_transient(self.source, ["U(out)"], .005, 1e-5)
        self.assertEqual(result["rows"][0], [0., .25])
        errors = [abs(row[1] - (1 - .75 * math.exp(-row[0] / .001))) for row in result["rows"]]
        self.assertLess(max(errors), 2e-5)
        private = yaml.safe_load((Path(result["working_dir"]) / "circuit.scm").read_text())
        self.assertEqual(private["scm"]["TD"]["IPNum"], 1)
        self.assertEqual(private["scm"]["TD"]["IP"][0]["StartTime"], 0)
        self.assertEqual(digest(self.source), before)

    def test_native_relative_subcircuit_keeps_divider_gain_after_packaging(self):
        models = self.root / "models"
        models.mkdir()
        child = models / "divider.scm"
        create_circuit(example_circuit(), self.source)
        doc = yaml.safe_load(self.source.read_text())
        child_doc = yaml.safe_load(self.source.read_text())
        common = {"X": 1200, "Y": 800, "Rot": 0, "FlipV": 0, "FlipH": 0, "active_property_page": 0}
        def wire(a, ap, b, bp):
            return {"obj1": {"ID": a, "pin": ap}, "obj2": {"ID": b, "pin": bp}}
        # Native pins may terminate one wire each. Use CON pins for junctions;
        # repeated wires on the same PORT pin silently split the native node.
        child_doc["scm"]["Scheme"]["Objects"] = [
            {**common, "ID": 1, "Type": 1000, "Name": "R1", "Params": {"R": 1000}},
            {**common, "ID": 2, "Type": 1000, "Name": "R2", "Params": {"R": 1000}},
            {**common, "ID": 3, "Type": 400, "Name": "IN", "Rot": 2},
            {**common, "ID": 4, "Type": 400, "Name": "OUT"},
            {**common, "ID": 5, "Type": 300, "Name": "CON1"},
            {**common, "ID": 6, "Type": 200, "Name": "GND1"}]
        child_doc["scm"]["Scheme"]["Wires"] = [wire(1, 1, 3, 1), wire(1, 2, 5, 1),
            wire(2, 1, 5, 4), wire(4, 1, 5, 3), wire(2, 2, 6, 1)]
        child.write_text(yaml.safe_dump(child_doc, sort_keys=False), encoding="utf-8")
        scheme = doc["scm"]["Scheme"]
        voltage = next(item for item in scheme["Objects"] if item["Type"] == 2010)
        voltage["ID"] = 1
        scheme["Objects"] = [voltage,
            {**common, "ID": 2, "Type": 200, "Name": "GND1"},
            {**common, "ID": 3, "Type": 400, "Name": "IN"},
            {**common, "ID": 10, "Type": 7100, "Name": "DIV1", "Params": {
                "FileName": "models\\divider.scm", "Pins": {"Left": ["IN"], "Top": None, "Right": ["OUT"], "Bottom": None}}},
            {**common, "ID": 11, "Type": 400, "Name": "OUT", "X": 1400},
            {**common, "ID": 12, "Type": 300, "Name": "CON1"}]
        scheme["Wires"] = [wire(1, 1, 2, 1), wire(1, 2, 12, 1),
                           wire(3, 1, 12, 2), wire(10, 1, 12, 3), wire(10, 2, 11, 1)]
        self.source.write_text(yaml.safe_dump(doc), encoding="utf-8")
        before, model_before = digest(self.source), digest(child)
        result = self.engine.run_ac(self.source, ["mag(U(OUT)/U(IN))"], 1, 1000, 4)
        self.assertTrue(all(abs(row[1] - .5) < 1e-9 for row in result["rows"]))
        self.assertEqual(len(result["source_models"]), 2)
        self.assertEqual(digest(self.source), before)
        self.assertEqual(digest(child), model_before)


if __name__ == "__main__":
    unittest.main()
