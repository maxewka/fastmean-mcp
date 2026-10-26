"""Regressions for visually ambiguous wires and user placement constraints."""
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.layout import LayoutError
from fastmean_mcp.schematic import SchemeError, create_circuit, example_circuit


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_distinct_net_overlapping_routes_rejected_before_writing(self):
        spec = example_circuit()
        spec["layout"] = {
            "placements": {"U1": {"x": 600, "y": 1400, "rotation": 3},
                           "R1": {"x": 1000, "y": 1000, "rotation": 0},
                           "C1": {"x": 1400, "y": 1400, "rotation": 1}},
            "routes": {
                "in": [[[960,1000],[920,1000],[920,800],[600,800],[600,1360]],
                       [[800,1000],[800,800]]],
                "out": [[[1040,1000],[1120,1000],[1120,800],[600,800],
                         [600,760],[1400,760],[1400,1360]]],
            },
        }
        destination = self.root / "ambiguous.scm"
        with self.assertRaisesRegex(LayoutError, "different nodes overlap"):
            create_circuit(spec, destination)
        self.assertFalse(destination.exists())

    def test_distinct_centers_do_not_allow_overlapping_component_bodies(self):
        spec = example_circuit()
        spec["layout"] = {"placements": {
            "R1": {"x": 1000, "y": 1000, "rotation": 0},
            "C1": {"x": 1000, "y": 1020, "rotation": 0},
        }}
        destination = self.root / "overlap.scm"
        with self.assertRaisesRegex(LayoutError, "bodies overlap"):
            create_circuit(spec, destination)
        self.assertFalse(destination.exists())

    def test_normalized_port_collisions_and_ground_analysis_are_rejected(self):
        for ports in ({" in ": "in", "in": "in"}, {"IN": "in"}, ["in", "in"]):
            spec = example_circuit()
            spec["ports"] = ports
            with self.subTest(ports=ports), self.assertRaises(SchemeError):
                create_circuit(spec, self.root / "invalid.scm")
        spec = example_circuit()
        spec["analysis"]["output"] = "0"
        with self.assertRaisesRegex(SchemeError, "non-ground"):
            create_circuit(spec, self.root / "ground.scm")

    def test_whitespace_aliases_normalize_before_analysis(self):
        spec = example_circuit()
        spec["ports"] = {" INPUT ": " in ", " OUTPUT ": " out "}
        spec["analysis"].update(input=" INPUT ", output=" OUTPUT ")
        result = create_circuit(spec, self.root / "aliases.scm")
        self.assertEqual(set(result["ports"]), {"INPUT", "OUTPUT"})
        self.assertEqual(result["analysis"]["FD"]["Expressions"][0]["y"],
                         "db(U(OUTPUT)/U(INPUT))")

    def test_numeric_graph_nodes_need_named_external_aliases(self):
        spec = example_circuit("voltage_divider")
        for component in spec["components"]:
            component["nodes"] = [{"in": "17", "out": "31"}.get(n, n)
                                  for n in component["nodes"]]
        spec["ports"] = ["17", "31"]
        spec["analysis"].update(input="17", output="31")
        with self.assertRaisesRegex(SchemeError, "port alias"):
            create_circuit(spec, self.root / "numeric.scm")
        self.assertFalse((self.root / "numeric.scm").exists())
        spec["ports"] = {"IN": "17", "OUT": "31"}
        spec["analysis"].update(input="IN", output="OUT")
        result = create_circuit(spec, self.root / "named.scm")
        self.assertEqual(result["ports"], {"IN": "IN", "OUT": "OUT"})
        self.assertEqual(result["analysis"]["FD"]["Expressions"][0]["y"],
                         "db(U(OUT)/U(IN))")


if __name__ == "__main__":
    unittest.main()
