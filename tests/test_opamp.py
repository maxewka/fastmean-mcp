"""Three-terminal native op-amps: geometry, authoring and native polarity."""
from __future__ import annotations

import copy
import csv
import hashlib
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fastmean_mcp.native_geometry import body_bounds, pin_directions, pin_positions
from fastmean_mcp.preview import _draw_native_component, render_schematic
from fastmean_mcp.schematic import SchemeError, _normalize_components, create_circuit, parse_value, read_scheme


def amplifier(gain=2.5, negative=False, feedback=False):
    return {
        "components": [
            {"kind": "U", "name": "VIN", "nodes": ["input", "0"], "value": 1,
             "waveform": {"kind": "sine", "frequency": 1000, "phase": -90}},
            {"kind": "OPAMP", "name": "OA1", "nodes": ["0" if negative else "input",
                "input" if negative else "output" if feedback else "0", "output"], "parameters": {"k": gain}},
            {"kind": "R", "name": "RL", "nodes": ["output", "0"], "value": 1000},
        ],
        "ports": {"IN": "input", "OUT": "output"},
        "analysis": {"input": "IN", "output": "OUT"},
    }


class OpampAuthoringTests(unittest.TestCase):
    def test_native_triangle_has_two_distinct_inputs_and_ground_referenced_output(self):
        anchors = [
            {1: (974, 792), 2: (974, 808), 3: (1026, 800)},
            {1: (1008, 774), 2: (992, 774), 3: (1000, 826)},
            {1: (1026, 808), 2: (1026, 792), 3: (974, 800)},
            {1: (992, 826), 2: (1008, 826), 3: (1000, 774)},
        ]
        for rotation, expected in enumerate(anchors):
            with self.subTest(rotation=rotation):
                obj = {"Type": 6400, "X": 1000, "Y": 800, "Rot": rotation, "Name": "OA1", "Params": {"k": 2.5}}
                self.assertEqual(pin_positions(obj), expected)
                self.assertEqual(pin_directions(obj)[1], pin_directions(obj)[2])
                self.assertEqual(tuple(-v for v in pin_directions(obj)[1]), pin_directions(obj)[3])
                self.assertEqual(body_bounds(obj), (976, 782, 1024, 818) if rotation % 2 else (982, 776, 1018, 824))

        # Inspect the actual preview primitive, including input polarity; an
        # arbitrary four-terminal box would pass a connectivity-only test.
        from matplotlib.figure import Figure
        from matplotlib.patches import Polygon
        axis = Figure().subplots()
        obj["Rot"] = 0
        _draw_native_component(axis, obj, "k=2.5")
        self.assertEqual(len(axis.patches), 1)
        self.assertIsInstance(axis.patches[0], Polygon)
        self.assertEqual(set(map(tuple, axis.patches[0].get_xy())), {(982, 776), (982, 824), (1018, 800)})
        signs = {label.get_text(): label.get_position() for label in axis.texts if label.get_text() in {"+", "−"}}
        self.assertLess(signs["+"][1], signs["−"][1])
        self.assertEqual(len(axis.lines), 3)

    def test_generated_opamp_retains_native_three_pin_order_and_renderable_real_wires(self):
        with tempfile.TemporaryDirectory(prefix="fm-opamp-") as directory:
            path = Path(directory) / "finite_gain.scm"
            result = create_circuit(amplifier(), path)
            item = next(item for item in read_scheme(path)["components"] if item["name"] == "OA1")
            self.assertEqual(item["native_type"], 6400)
            self.assertEqual(item["native_pin_nodes"], ["IN", "0", "OUT"])
            self.assertEqual(item["pin_roles"], ["noninverting", "inverting", "output"])
            self.assertEqual(item["parameters"], {"k": 2.5})
            self.assertIn("no supply rails", item["model_limitations"])
            self.assertTrue(item["supported_for_generation"])
            preview = render_schematic(path, Path(directory) / "preview")
            self.assertEqual(preview["component_count"], 3)
            self.assertFalse(preview["approximate_wire_routes"])
            svg = Path(preview["svg_path"]).read_text("utf-8")
            self.assertIn("OA1", svg)
            self.assertIn("k=2.5", svg)
            self.assertEqual(result["spec"]["components"][1]["nodes"], ["input", "0", "output"])

    def test_gain_is_explicit_finite_numeric_and_terminal_count_is_exact(self):
        base = {"kind": "OPAMP", "name": "OA1", "nodes": ["input", "0", "output"], "parameters": {"k": "100М"}}
        normalized, _, _ = _normalize_components([base], {})
        self.assertEqual(normalized[0]["_native_params"], {"k": 1e8})
        for patch in ({"nodes": ["input", "0"]}, {"nodes": ["input", "0", "output", "0"]},
                      {"parameters": {"k": float("inf")}}, {"parameters": {"k": True}},
                      {"parameters": {"k": "gain_parameter"}}, {"parameters": {"k": 5, "GBW": 1e6}},
                      {"value": 5}, {"parameters": {}}):
            with self.subTest(patch=patch), self.assertRaises(SchemeError):
                _normalize_components([{**copy.deepcopy(base), **patch}], {})

    def test_public_twenty_part_filter_uses_automatic_stages_and_saved_parameter_formulas(self):
        from fastmean_mcp.annotations import annotate_circuit
        example = Path(__file__).resolve().parents[1]/"examples"/"mfb-filter"/"specification.py"
        spec, notes = runpy.run_path(str(example))["make_spec"]()
        self.assertNotIn("layout", spec)
        self.assertEqual(len(spec["components"]), 20)
        self.assertEqual(sum(part["kind"] == "OPAMP" for part in spec["components"]), 3)
        with tempfile.TemporaryDirectory(prefix="fm-mfb-") as directory:
            original = Path(directory)/"filter.scm"
            created = create_circuit(spec, original)
            digest = hashlib.sha256(original.read_bytes()).hexdigest()
            positions = created["layout"]["positions"]
            opamps = [positions[f"OA{number}"] for number in range(1, 4)]
            self.assertTrue(all(a["x"] < b["x"] for a, b in zip(opamps, opamps[1:])))
            self.assertEqual(len({part["y"] for part in opamps}), 1)
            annotated = Path(directory)/"annotated.scm"
            annotate_circuit(original, annotated, **notes)
            circuit = read_scheme(annotated)
            parts = {part["name"]: part for part in circuit["components"]}
            self.assertEqual(parts["R1A"]["value"], "RBASE")
            self.assertEqual(parts["C1C"]["value"], "CAP1C")
            self.assertEqual(parts["OA3"]["value"], 1e8)
            self.assertEqual([entry["y"] for entry in circuit["analysis"]["FD"]["Expressions"]], notes["fd_signals"])
            texts = [obj["Params"]["Text"] for obj in circuit["objects"] if obj["Type"] == 900]
            self.assertTrue(any(text.startswith(".parameter") for text in texts))
            self.assertTrue(any("overall gain [dB]" in text for text in texts))
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), digest)


APP = Path(os.environ.get("FASTMEAN_APP_DIR", ""))
if not (APP / "Fastmean.exe").is_file():
    APP = Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1"
if not (APP / "Fastmean.exe").is_file():
    APP = Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.0"
ENABLED = (os.name == "nt" and os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1"
           and (APP / "Fastmean.exe").is_file())


@unittest.skipUnless(ENABLED, "Requires Windows FASTMEAN and FASTMEAN_MCP_NATIVE_TEST=1")
class OpampNativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_ac_and_transient_polarity_and_feedback_through_real_stdio(self):
        inverting = amplifier(gain=1e5)
        inverting["components"][1]["nodes"] = ["0", "sum", "output"]
        inverting["components"].extend([
            {"kind": "R", "name": "RIN", "nodes": ["input", "sum"], "value": 10000},
            {"kind": "R", "name": "RFB", "nodes": ["sum", "output"], "value": 20000},
        ])
        cases = [("plus", amplifier(), 2.5), ("minus", amplifier(negative=True), -2.5),
                 ("follower", amplifier(gain=1e15, feedback=True), 1e15/(1+1e15)),
                 ("inverting", inverting, -2/(1+3/1e5))]
        with tempfile.TemporaryDirectory(prefix="fm-native-opamp-") as directory:
            parameters = StdioServerParameters(command=sys.executable,
                args=["-X", "utf8", "-m", "fastmean_mcp"],
                env=dict(os.environ, FASTMEAN_APP_DIR=str(APP), FASTMEAN_OUTPUT_DIR=directory))
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()

                    async def call(name, arguments):
                        result = await client.call_tool(name, arguments, read_timeout_seconds=90.0)
                        self.assertFalse(result.is_error, str(result.content)[:1800])
                        return result.structured_content

                    for name, spec, expected in cases:
                        with self.subTest(case=name):
                            made = await call("fastmean_create_circuit", {"spec": spec, "name": name})
                            path = Path(made["path"])
                            digest = hashlib.sha256(path.read_bytes()).hexdigest()
                            native = await call("fastmean_export_netlist", {"path": str(path), "timeout": 10})
                            line = next(line for line in native["text"].splitlines() if line.startswith("OA1 "))
                            self.assertEqual(len(line.split()), 5)
                            self.assertEqual(parse_value(line.split()[-1]), spec["components"][1]["parameters"]["k"])
                            ac = await call("fastmean_ac", {"path": str(path), "fmin": 10, "fmax": 10000,
                                "points": 4, "signals": ["RE(U(OUT)/U(IN))", "IM(U(OUT)/U(IN))"], "timeout": 10})
                            with Path(ac["csv_path"]).open(encoding="utf-8-sig", newline="") as stream:
                                rows = list(csv.reader(stream))[1:]
                            self.assertEqual(len(rows), 4)
                            for row in rows:
                                self.assertAlmostEqual(float(row[1]), expected, delta=2e-10)
                                self.assertAlmostEqual(float(row[2]), 0, delta=1e-12)
                            td = await call("fastmean_transient", {"path": str(path), "stop": .0005,
                                "step": 1e-5, "signals": ["U(IN)", "U(OUT)"], "timeout": 10})
                            with Path(td["csv_path"]).open(encoding="utf-8-sig", newline="") as stream:
                                rows = list(csv.reader(stream))[1:]
                            self.assertGreater(len(rows), 30)
                            self.assertGreater(max(abs(float(row[1])) for row in rows), .9)
                            self.assertLess(max(abs(float(row[2])-expected*float(row[1])) for row in rows), 2e-10)
                            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
