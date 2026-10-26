from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastmean_mcp.symbolic import cirsym_from_fastmean_netlist, netlist_from_spec, parse_native_output, run_symbolic


NATIVE_RC_OUTPUT = """% --- Converted from FASTMEAN netlist ---
R_R1=1000;
c_C1=1e-06;
E_U1=1;
% Output: U_symbolic_probe2 (2,0)
U_symbolic_probe2 =
(
E_U1
)
/
(
p*(c_C1*(R_R1))+(1)
);
% Execution time: 00 hour 00 min. 00.01 sec.
"""
RC_NETLIST = "--- RC test ---\nR_R1 1 2 1000\nc_C1 2 0 1e-6\nE_U1 0 1 1\nU_symbolic_probe2 2 0\n.END\n"
NATIVE_EXPORTED_RC = "* Created in FASTMEAN 6.1\nR1 1 2 1k\nC1 2 0 1u 0\nU1 0 1 AC 1 1k 0 -1 0\nIN 1\nOUT 2\n"


class NativeOutputTests(unittest.TestCase):
    def test_parse_native_multiline_formula_retains_algebra(self):
        parsed = parse_native_output(NATIVE_RC_OUTPUT)
        self.assertEqual(parsed["parameters"], {"R_R1": "1000", "c_C1": "1e-06", "E_U1": "1"})
        self.assertEqual(parsed["equations"], [{"name": "U_symbolic_probe2", "expression": "(E_U1)/(p*(c_C1*(R_R1))+(1))"}])

    def test_constant_native_output_is_an_equation_not_a_parameter(self):
        parsed = parse_native_output("% Output: U_OUT (1,0)\nU_OUT=1;\n")
        self.assertEqual(parsed["equations"], [{"name": "U_OUT", "expression": "1"}])
        self.assertEqual(parsed["parameters"], {})


class NativeConversionTests(unittest.TestCase):
    def test_exported_native_rc_retains_topology_and_source_polarity(self):
        converted = cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC)
        lines = converted["netlist"].splitlines()
        self.assertIn("R_R1 1 2 1000", lines)
        capacitor = next(line.split() for line in lines if line.startswith("c_C1 "))
        self.assertEqual(capacitor[:3], ["c_C1", "2", "0"])
        self.assertEqual(float(capacitor[3]), 1e-6)
        self.assertIn("E_U1 0 1 1", lines)
        self.assertIn("U_symbolic_output 2 0", lines)
        self.assertNotIn("U_symbolic_input 1 0", lines)
        self.assertEqual(converted["input_parameter"], "E_U1")
        self.assertEqual(converted["transfer_relation"], "U_symbolic_output/E_U1")

    def test_spec_and_native_source_conventions_produce_same_polarity(self):
        spec = {"components": [
            {"kind": "R", "name": "R1", "nodes": ["in", "out"], "value": "1k"},
            {"kind": "C", "name": "C1", "nodes": ["out", "0"], "value": "1u"},
            {"kind": "U", "name": "U1", "nodes": ["in", "0"], "value": 1},
        ]}
        converted = netlist_from_spec(spec, input_node="in")
        self.assertIn("E_U1 0 1 1", converted["netlist"].splitlines())
        self.assertEqual(converted["node_map"], {"0": 0, "in": 1, "out": 2})

    def test_unknown_renamed_element_is_rejected_instead_of_guessing_kind(self):
        with self.assertRaisesRegex(ValueError, "component_kinds"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC.replace("R1 ", "load "))
        converted = cirsym_from_fastmean_netlist(
            NATIVE_EXPORTED_RC.replace("R1 ", "load "),
            component_kinds={"load": "R", "C1": "C", "U1": "U"},
        )
        self.assertIn("R_load 1 2 1000", converted["netlist"].splitlines())

    def test_nonzero_initial_conditions_are_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, "initial conditions"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC.replace("C1 2 0 1u 0", "C1 2 0 1u 2"))

    def test_unknown_component_is_not_ignored(self):
        with self.assertRaisesRegex(ValueError, "cannot infer"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC + "D1 2 0 model\n")

    def test_multiple_sources_are_not_given_an_unverified_transfer_formula(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC + "U2 0 2 DC 1 -1 0\n")

    def test_arbitrary_internal_input_node_is_not_treated_as_source_amplitude(self):
        with self.assertRaisesRegex(ValueError, "positive node"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC, input="OUT")

    def test_truncated_component_is_not_mistaken_for_a_port(self):
        with self.assertRaisesRegex(ValueError, "missing terminals"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC.replace("R1 1 2 1k", "R1 1"))

    def test_direct_spec_does_not_discard_capacitor_initial_voltage(self):
        spec = {"components": [
            {"kind": "U", "name": "U1", "nodes": ["in", "0"], "value": 1},
            {"kind": "R", "name": "R1", "nodes": ["in", "out"], "value": 1000},
            {"kind": "C", "name": "C1", "nodes": ["out", "0"], "value": "1u", "initial_condition": 5},
        ]}
        with self.assertRaisesRegex(ValueError, "initial conditions"):
            netlist_from_spec(spec, input_node="in")

    def test_direct_spec_uses_the_active_sine_amplitude_override(self):
        spec = {"components": [
            {"kind": "U", "name": "U1", "nodes": ["in", "0"], "value": 1,
             "waveform": {"kind": "sine", "amplitude": 3, "frequency": "1k"}},
            {"kind": "R", "name": "R1", "nodes": ["in", "out"], "value": 1000},
            {"kind": "C", "name": "C1", "nodes": ["out", "0"], "value": "1u"},
        ]}
        converted = netlist_from_spec(spec, input_node="in")
        self.assertIn("E_U1 0 1 3", converted["netlist"].splitlines())

    def test_zero_input_amplitude_is_not_returned_as_a_division_by_zero_transfer(self):
        text = NATIVE_EXPORTED_RC.replace("U1 0 1 AC 1 1k", "U1 0 1 AC 0 1k")
        with self.assertRaisesRegex(ValueError, "nonzero"):
            cirsym_from_fastmean_netlist(text)
        converted = cirsym_from_fastmean_netlist(text, input=None)
        self.assertIsNone(converted["input_parameter"])
        self.assertIn("E_U1 0 1 0", converted["netlist"].splitlines())

    def test_floating_island_is_rejected_before_native_singular_analysis(self):
        with self.assertRaisesRegex(ValueError, "floating"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC + "R2 3 4 1000\n")

    def test_native_port_names_are_exact_and_not_casefolded_into_another_node(self):
        with self.assertRaisesRegex(ValueError, "not a native port"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC, input="in")
        with self.assertRaisesRegex(ValueError, "positive node"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC + "in 2\n", input="in")

    def test_repeated_identical_port_is_allowed_but_conflicting_mapping_is_not(self):
        self.assertEqual(cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC + "IN 1\n")["ports"]["IN"], 1)
        with self.assertRaisesRegex(ValueError, "inconsistent nodes"):
            cirsym_from_fastmean_netlist(NATIVE_EXPORTED_RC + "IN 2\n")


@unittest.skipUnless(os.name == "nt", "Windows native-worker contract")
class NativeInvocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "installed" / "FASTMEAN 6.1"
        engine = self.app / "symbolic"
        engine.mkdir(parents=True)
        (engine / "cirsymw.exe").write_bytes(b"fake executable used only with subprocess mock")
        (engine / "human.sym").write_bytes(b"private settings fixture")
        (engine / "cir").write_bytes(b"existing user's input must stay unchanged")
        (engine / "out").write_bytes(b"existing user's output must stay unchanged")
        self.originals = {f.name: f.read_bytes() for f in engine.iterdir()}

    def assert_installed_unchanged(self):
        self.assertEqual({f.name: f.read_bytes() for f in (self.app / "symbolic").iterdir()}, self.originals)

    def test_native_output_retained_with_private_cwd_and_original_executable(self):
        def native(command, **kwargs):
            # The launcher canonicalizes Windows DOS 8.3 TEMP aliases.
            self.assertEqual(Path(command[0]).resolve(),
                             (self.app / "symbolic" / "cirsymw.exe").resolve())
            cwd = Path(kwargs["cwd"])
            self.assertNotIn(self.app, cwd.parents)
            self.assertEqual((cwd / "cir").read_text(encoding="cp1251"), RC_NETLIST)
            self.assertEqual((cwd / "human.sym").read_bytes(), b"private settings fixture")
            (cwd / "out").write_bytes(NATIVE_RC_OUTPUT.encode("cp1251"))
            return subprocess.CompletedProcess(command, 0, b"native console output", b"")

        with patch("fastmean_mcp.symbolic.subprocess.run", side_effect=native):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results")
        self.assertTrue(result["ok"])
        self.assertEqual(result["raw_output"], NATIVE_RC_OUTPUT)
        self.assertEqual(Path(result["native_output_path"]).read_bytes(), NATIVE_RC_OUTPUT.encode("cp1251"))
        self.assert_installed_unchanged()

    def test_policy_block_is_an_honest_failure_without_synthetic_output(self):
        error = OSError("An Application Control policy has blocked this file")
        error.winerror = 4551
        with patch("fastmean_mcp.symbolic.subprocess.run", side_effect=error):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "blocked_by_application_control")
        self.assertEqual(result["equations"], [])
        self.assertEqual(result["raw_output"], "")
        self.assert_installed_unchanged()

    def test_timeout_retains_partial_diagnostics_and_is_not_success(self):
        error = subprocess.TimeoutExpired("cirsymw", 0.01, output=b"partial output")
        with patch("fastmean_mcp.symbolic.subprocess.run", side_effect=error):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results", timeout=0.01)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "timeout")
        self.assertEqual(result["stdout"], "partial output")
        self.assert_installed_unchanged()

    def test_exit_zero_without_output_does_not_reuse_installed_output(self):
        with patch("fastmean_mcp.symbolic.subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"", b"")):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "native_output_missing")
        self.assertEqual(result["raw_output"], "")
        self.assert_installed_unchanged()

    def test_output_under_installation_is_rejected_before_writing(self):
        with self.assertRaises(ValueError):
            run_symbolic(self.app, RC_NETLIST, self.app / "results")
        self.assert_installed_unchanged()

    def test_native_exit_zero_with_zero_denominator_is_a_singular_failure(self):
        # Actual CIRSYM output observed for a floating resistor island.
        native_text = "% Output: U_symbolic_output (2,0)\nU_symbolic_output=(E_U1*((0)))/((0));\n"
        def native(command, **kwargs):
            (Path(kwargs["cwd"]) / "out").write_bytes(native_text.encode("ascii"))
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with patch("fastmean_mcp.symbolic.subprocess.run", side_effect=native):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "native_singular_circuit")
        self.assertEqual(result["raw_output"], native_text)
        self.assertTrue(result["equations"])

    def test_tiny_nonzero_native_coefficient_is_not_classified_as_zero(self):
        native_text = "% Output: U_symbolic_output (2,0)\nU_symbolic_output=E_U1/(1e-1000);\n"
        def native(command, **kwargs):
            (Path(kwargs["cwd"]) / "out").write_bytes(native_text.encode("ascii"))
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with patch("fastmean_mcp.symbolic.subprocess.run", side_effect=native):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results")
        self.assertTrue(result["ok"])

    def test_pre_cancelled_event_does_not_create_a_process(self):
        event = threading.Event()
        event.set()
        with patch("fastmean_mcp.symbolic.subprocess.Popen") as launch:
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results", cancel_event=event)
        launch.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "cancelled")
        self.assertEqual(result["equations"], [])
        self.assert_installed_unchanged()

    def test_cancellation_kills_only_the_owned_worker_and_cannot_return_success(self):
        event = threading.Event()
        class OwnedWorker:
            pid, returncode, killed = 54321, None, False
            timeouts = []
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def poll(self): return self.returncode
            def kill(self):
                self.killed, self.returncode = True, -9
            def communicate(self, timeout=None):
                if self.killed:
                    return b"partial native output", b""
                self.timeouts.append(timeout)
                event.set()
                raise subprocess.TimeoutExpired("owned worker", timeout)
        worker = OwnedWorker()
        def launch(command, **kwargs):
            # Even a completed-looking native output must not turn cancellation
            # into success when the event was already requested.
            (Path(kwargs["cwd"]) / "out").write_bytes(NATIVE_RC_OUTPUT.encode("ascii"))
            return worker
        with patch("fastmean_mcp.symbolic.subprocess.Popen", side_effect=launch):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results", cancel_event=event)
        self.assertTrue(worker.killed)
        self.assertTrue(all(timeout <= .1 for timeout in worker.timeouts))
        self.assertEqual(result["pid"], worker.pid)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "cancelled")
        self.assertEqual(result["stdout"], "partial native output")
        self.assertTrue(result["equations"])
        self.assert_installed_unchanged()

    def test_cancellable_worker_still_honors_timeout_and_keeps_diagnostics(self):
        event = threading.Event()
        class OwnedWorker:
            pid, returncode, killed = 54322, None, False
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def poll(self): return self.returncode
            def kill(self):
                self.killed, self.returncode = True, -9
            def communicate(self, timeout=None):
                if self.killed:
                    return b"timeout diagnostics", b""
                time.sleep(min(timeout, .005))
                raise subprocess.TimeoutExpired("owned worker", timeout)
        worker = OwnedWorker()
        with patch("fastmean_mcp.symbolic.subprocess.Popen", return_value=worker):
            result = run_symbolic(self.app, RC_NETLIST, self.root / "results", timeout=.02, cancel_event=event)
        self.assertTrue(worker.killed)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "timeout")
        self.assertEqual(result["stdout"], "timeout diagnostics")
        self.assert_installed_unchanged()


if __name__ == "__main__":
    unittest.main()
