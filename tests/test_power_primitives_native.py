"""Opt-in real FASTMEAN checks of transformer ratio and controlled conduction."""
import os
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.engine import Engine
from fastmean_mcp.schematic import create_circuit
from test_power_primitives import switch_spec, transformer_spec


APP = Path(os.environ.get("FASTMEAN_APP_DIR", ""))
if not (APP / "Fastmean.exe").is_file():
    APP = Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1"
ENABLED = (os.name == "nt" and os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1"
           and (APP / "Fastmean.exe").is_file())


@unittest.skipUnless(ENABLED, "Requires Windows FASTMEAN and FASTMEAN_MCP_NATIVE_TEST=1")
class NativePowerPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fm-power-native-")
        self.root = Path(self.tmp.name)
        self.engine = Engine(APP, self.root / "jobs", timeout=15)

    def tearDown(self):
        self.engine.cancel()
        self.tmp.cleanup()

    def run_spec(self, spec, name):
        path = self.root / f"{name}.scm"
        create_circuit(spec, path)
        original = path.read_bytes()
        result = self.engine.run_transient(path, ["U(out)", "I(RL)"], stop=.0001, step=1e-6)
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(result["axis_validation"]["coverage_verified"])
        self.assertGreater(result["row_count"], 50)
        return result["rows"][-1]

    def test_transformer_ratio_winding_polarity_and_all_rotations(self):
        for rotation in range(4):
            for reverse in (False, True):
                with self.subTest(rotation=rotation, reverse=reverse):
                    row = self.run_spec(transformer_spec(rotation, reverse), f"tr{rotation}{reverse}")
                    self.assertAlmostEqual(row[1], -5 if reverse else 5, places=7)
                    self.assertAlmostEqual(row[2], -.5 if reverse else .5, places=7)

    def test_switch_control_sign_and_both_power_current_directions(self):
        for control in (-5, 5):
            for reverse in (False, True):
                with self.subTest(control=control, reverse=reverse):
                    spec = switch_spec(control, rotation=1 if reverse else 0)
                    if reverse:
                        spec["components"][2]["nodes"][2:] = ["out", "in"]
                    row = self.run_spec(spec, f"sw{control}{reverse}")
                    expected = 100 / (10 + (.1 if control > 0 else 1e6))
                    self.assertAlmostEqual(row[1], expected, places=7)
                    self.assertAlmostEqual(row[2], expected / 10, places=7)

    def test_diode_anode_cathode_polarity(self):
        for reverse in (False, True):
            spec = transformer_spec()
            spec.pop("layout")
            spec["components"][1] = {"kind": "D", "name": "D1", "nodes": ["out", "in"] if reverse else ["in", "out"],
                                     "parameters": {"Ron": .1, "Roff": 1e6, "Uon": .7}}
            row = self.run_spec(spec, f"diode{reverse}")
            # The native PWL model includes the finite off-state conductance.
            self.assertAlmostEqual(row[1], 100 / 1000010 if reverse else 9.20792086138614, places=7)

    def test_switch_retains_state_between_hysteresis_thresholds(self):
        spec = switch_spec()
        spec["components"][1]["waveform"] = {
            "kind": "pulse", "frequency": "10k", "high": 5, "low": 0,
            "duty_percent": 50, "rise_time": "20u"}
        spec["components"][2]["parameters"].update(Uon=3, Uoff=2)
        path = self.root / "hysteresis.scm"
        create_circuit(spec, path)
        original = path.read_bytes()
        result = self.engine.run_transient(path, ["U(ctl)", "U(out)"], stop=.0003, step=1e-6)
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(result["axis_validation"]["coverage_verified"])
        rising, falling = [], []
        for previous, current in zip(result["rows"], result["rows"][1:]):
            if current[0] <= previous[0] or not 2.2 < current[1] < 2.8:
                continue
            delta = current[1] - previous[1]
            if delta > 1e-4:
                rising.append(current[2])
            elif delta < -1e-4:
                falling.append(current[2])
        self.assertGreaterEqual(len(rising), 3)
        self.assertGreaterEqual(len(falling), 3)
        for output in rising:
            self.assertAlmostEqual(output, 100 / 1000010, places=6)
        for output in falling:
            self.assertAlmostEqual(output, 100 / 10.1, places=6)


if __name__ == "__main__":
    unittest.main()
