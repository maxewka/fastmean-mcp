"""Published 25-part layout + 4 explicit test fixtures: geometry and native QA.

Reference: Troels Gravesen Point75A v12, Fig.31 p.11. Only our functional
transcription is included. The optional oracle solves KCL independently of SCM
serialization and the native engine; it is validation, never an MCP solver.
"""
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.schematic import create_circuit, read_scheme, parse_value, _load

SPEC = Path(__file__).resolve().parents[1] / "examples" / "point75a" / "circuit.json"
NATIVE = os.name == "nt" and os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1"


class ReferenceLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fm-reference-")
        self.root = Path(self.temporary.name)
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.path = self.root / "Point75A.scm"
        self.result = create_circuit(self.spec, self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_29_elements_preserve_reference_positions_without_terminal_ports(self):
        scheme = read_scheme(self.path)
        self.assertEqual(scheme["component_count"], 29)
        self.assertEqual({c["name"] for c in scheme["components"]},
                         {c["name"] for c in self.spec["components"]})
        ports = [o for o in scheme["objects"] if o["Type"] == 400]
        self.assertEqual({p["Name"] for p in ports}, {"IN", "TW", "MID", "WOOF"})
        self.assertEqual(len(ports), 4)
        objects = {o["ID"]: o for o in scheme["objects"]}
        for obj in scheme["objects"]:
            if obj.get("Name") in self.spec["layout"]["placements"]:
                expected = self.spec["layout"]["placements"][obj["Name"]]
                self.assertEqual((obj["X"], obj["Y"], obj["Rot"]),
                                 (expected["x"], expected["y"], expected["rotation"]))
        pins = set()
        def anchor(endpoint):
            obj = objects[endpoint["ID"]]
            x, y = obj["X"], obj["Y"]
            if obj["Type"] in (1000, 1001, 1002, 2010):
                sign = -1 if endpoint["pin"] == 1 else 1
                dx, dy = ((40, 0), (0, 40), (-40, 0), (0, -40))[obj["Rot"]]
                return x + sign*dx, y + sign*dy
            return x, y
        _, document, _ = _load(self.path)
        for wire in document["scm"]["Scheme"]["Wires"]:
            for endpoint in (wire["obj1"], wire["obj2"]):
                pin = (endpoint["ID"], endpoint["pin"])
                self.assertNotIn(pin, pins, "Two wires must meet at a CON, not share a terminal")
                pins.add(pin)
            from fastmean_mcp.wires import wire_path
            points = wire_path(wire, objects)
            self.assertEqual(points[0], anchor(wire['obj1']))
            self.assertEqual(points[-1], anchor(wire['obj2']))
            for a, b in zip(points, points[1:]):
                self.assertTrue(a[0] == b[0] or a[1] == b[1], "Each native wire leg must be orthogonal")

    @unittest.skipUnless(NATIVE, "Set FASTMEAN_MCP_NATIVE_TEST=1 on Windows")
    def test_native_three_band_response_matches_independent_complex_kcl(self):
        import numpy as np
        from fastmean_mcp.engine import Engine
        from fastmean_mcp.server import app_dir
        signals = [f"{function}(U({node})/U(IN))" for node in ("TW", "MID", "WOOF")
                   for function in ("mag", "phs")]
        native = Engine(app_dir(), self.root / "native").run_ac(
            self.path, signals, 10, 40000, 101)
        unknown = sorted({n for c in self.spec["components"] for n in c["nodes"]} - {"0", "IN"})
        index = {n: i for i, n in enumerate(unknown)}
        maximum = 0
        for row in native["rows"]:
            s = 2j*math.pi*row[0]
            matrix = np.zeros((len(unknown), len(unknown)), dtype=complex)
            rhs = np.zeros(len(unknown), dtype=complex)
            for c in self.spec["components"]:
                kind, value = c.get("kind", c.get("type")), parse_value(c["value"])
                if kind == "U":
                    continue
                admittance = {"R": lambda: 1/value, "C": lambda: s*value,
                              "L": lambda: 1/(s*value)}[kind]()
                a, b = c["nodes"]
                for node, other in ((a, b), (b, a)):
                    if node not in index:
                        continue
                    i = index[node]
                    matrix[i, i] += admittance
                    if other in index:
                        matrix[i, index[other]] -= admittance
                    elif other == "IN":
                        rhs[i] += admittance
            values = np.linalg.solve(matrix, rhs)
            for position, node in enumerate(("TW", "MID", "WOOF")):
                magnitude, phase = row[1+2*position:3+2*position]
                actual = magnitude*np.exp(1j*math.radians(phase))
                expected = values[index[node]]
                error = abs(actual-expected)/max(abs(expected), 1e-10)
                maximum = max(maximum, error)
                self.assertLess(error, 1e-6, (row[0], node, actual, expected))
        self.assertEqual(len(native["rows"]), 101)
        print(f"Point75A: 101 frequencies, 3 complex responses; max relative error {maximum:.3g}")


if __name__ == "__main__":
    unittest.main()
