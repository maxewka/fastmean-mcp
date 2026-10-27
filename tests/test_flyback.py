"""The advertised flyback workflow must work through the actual MCP protocol."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fastmean_mcp import server
from fastmean_mcp.engine import _normalize_numeric_literals
from fastmean_mcp.schematic import SchemeError, create_circuit, example_circuit, read_scheme


class FlybackAuthoringTests(unittest.TestCase):
    def test_imported_switch_unicode_literals_keep_expressions_untouched(self):
        objects = [{"Name": "TR1", "Type": 6101, "Params": {"n": "2к"}},
                   {"Name": "SW1", "Type": 6600, "Params": {"Ron": "50м", "Roff": "10М",
                    "Uon": "порог", "Uoff": 2, "unknown": "10к"}}]
        changes = _normalize_numeric_literals({"scm": {"Scheme": {"Objects": objects}}})
        self.assertEqual(len(changes), 3)
        self.assertEqual(objects[0]["Params"]["n"], 2000)
        self.assertEqual(objects[1]["Params"], {"Ron": .05, "Roff": 1e7,
                         "Uon": "порог", "Uoff": 2, "unknown": "10к"})

    def test_example_uses_native_parts_and_exposes_terminal_semantics(self):
        spec = server.fastmean_example("flyback")
        self.assertEqual(example_circuit("flyback_converter"), spec)
        self.assertIn("flyback", server.fastmean_status()["power_electronics"]["example"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flyback.scm"
            create_circuit(spec, path)
            circuit = read_scheme(path)
            parts = {part["name"]: part for part in circuit["components"]}
            self.assertEqual(parts["TR1"]["native_type"], 6101)
            self.assertEqual(parts["SW1"]["native_type"], 6600)
            self.assertEqual(parts["TR1"]["nodes"][:3], ["in", "drain", "0"])
            self.assertEqual(parts["SW1"]["nodes"], ["gate", "0", "drain", "0"])
            self.assertEqual(parts["LM"]["nodes"], ["in", "drain"])
            self.assertEqual(parts["DOUT"]["nodes"][0], parts["TR1"]["nodes"][3])
            self.assertEqual(parts["DOUT"]["nodes"][1], "out")
            self.assertEqual(set(circuit["ports"]), {"in", "out", "drain", "gate"})
            self.assertEqual(circuit["analysis"]["TD"]["IP"][0]["EPS"], 1e-5)

    def test_invalid_saved_transient_accuracy_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for value in (0, -.001, .2, True, float("nan"), "t/10"):
                with self.subTest(eps=value):
                    spec = example_circuit()
                    spec["analysis"]["transient"]["eps"] = value
                    path = Path(directory) / "invalid.scm"
                    with self.assertRaises(SchemeError):
                        create_circuit(spec, path)
                    self.assertFalse(path.exists())


APP = Path(os.environ.get("FASTMEAN_APP_DIR", ""))
if not (APP / "Fastmean.exe").is_file():
    APP = Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1"
ENABLED = (os.name == "nt" and os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1"
           and (APP / "Fastmean.exe").is_file())


@unittest.skipUnless(ENABLED, "Requires Windows FASTMEAN and FASTMEAN_MCP_NATIVE_TEST=1")
class FlybackNativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_switching_energy_transfer_and_event_plot_through_stdio(self):
        with tempfile.TemporaryDirectory(prefix="fm-flyback-") as directory:
            parameters = StdioServerParameters(command=sys.executable,
                args=["-X", "utf8", "-m", "fastmean_mcp"],
                env=dict(os.environ, FASTMEAN_APP_DIR=str(APP), FASTMEAN_OUTPUT_DIR=directory))
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()

                    async def call(name, arguments):
                        result = await client.call_tool(name, arguments, read_timeout_seconds=90.0)
                        self.assertFalse(result.is_error, str(result.content)[:1800])
                        return result

                    spec = (await call("fastmean_example", {"kind": "flyback"})).structured_content
                    created = (await call("fastmean_create_circuit", {"spec": spec})).structured_content
                    source = Path(created["path"])
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    signals = ["U(out)", "U(drain)", "I(LM)", "I(DOUT)", "U(gate)"]
                    run = (await call("fastmean_transient", {"path": str(source), "signals": signals,
                        "stop": .01, "step": 1e-7, "eps": 1e-5, "timeout": 60})).structured_content
                    chart = await call("fastmean_plot", {"run_id": run["run_id"],
                        "display_window": [.00994, .01], "measurement_window": [.009, .01],
                        "panels": [{"signal": signal, "metrics": ["mean", "min", "max"]} for signal in signals]})
                    self.assertTrue(any(item.type == "image" for item in chart.content))
                    metrics = chart.structured_content["measurements"]["signals"][0]["metrics"]
                    # Ideal CCM estimate is 24*0.4/(1-0.4)=16 V; the native
                    # diode drop and finite switch resistance lower it.
                    self.assertGreater(metrics["mean"], 15)
                    self.assertLess(metrics["mean"], 16)
                    manifest = json.loads((Path(run["working_dir"]) / "manifest.json").read_text("utf-8"))
                    self.assertTrue(manifest["axis_validation"]["coverage_verified"])
                    # Independently examine original native rows, not rendered
                    # or decimated graph samples, to verify flyback phasing.
                    rows = [[float(value) for value in line.split()] for line in
                            (Path(run["working_dir"]) / "native_data.txt").read_text().splitlines() if line.strip()]
                    self.assertTrue(all(a[0] <= b[0] for a, b in zip(rows, rows[1:])))
                    self.assertEqual(sum(a[0] == b[0] for a, b in zip(rows, rows[1:])),
                                     manifest["axis_validation"]["repeated_timestamp_rows"])
                    on = [r for r in rows if r[0] > .00994 and r[5] > 4.9 and r[1] > 0]
                    off = [r for r in rows if r[0] > .00994 and r[5] < .1 and r[1] > 0]
                    self.assertGreater(len(on), 50)
                    self.assertGreater(len(off), 50)
                    # Ignore the instantaneous two-sided switching event itself.
                    self.assertGreater(sum(r[2] < .2 and abs(r[4]) < 1e-4 for r in on) / len(on), .95)
                    self.assertGreater(sum(r[2] > 35 and r[4] > .5 for r in off) / len(off), .95)
                    rising, falling = [], []
                    for a, b in zip(rows, rows[1:]):
                        if a[0] <= .00994 or b[0] <= a[0]:
                            continue
                        if a[5] > 4.9 and b[5] > 4.9:
                            rising.append(b[3] > a[3])
                        if a[5] < .1 and b[5] < .1:
                            falling.append(b[3] < a[3])
                    self.assertGreater(sum(rising) / len(rising), .95)
                    self.assertGreater(sum(falling) / len(falling), .95)
                    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
