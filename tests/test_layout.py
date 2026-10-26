"""Regressions for visually ambiguous wires and user placement constraints."""
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.layout import LayoutError, _split_overlapping_edges
from fastmean_mcp.schematic import SchemeError, create_circuit, example_circuit


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_native_adapter_reversal_cannot_reuse_a_junction_direction(self):
        graph={(1048,860):{(1040,860),(1048,892)},
               (1040,860):{(1048,860),(1060,860)},
               (1060,860):{(1040,860)},(1048,892):{(1048,860)}}
        normalized=_split_overlapping_edges(graph)
        self.assertEqual(normalized[(1040,860)],{(1048,860)})
        self.assertEqual(normalized[(1048,860)],{(1040,860),(1060,860),(1048,892)})
        for point, neighbors in normalized.items():
            directions={((p[0]>point[0])-(p[0]<point[0]),(p[1]>point[1])-(p[1]<point[1])) for p in neighbors}
            self.assertEqual(len(directions),len(neighbors))

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

    def test_compact_layout_reduces_area_without_changing_electrical_nodes(self):
        def partitions(result):
            groups = {}
            for component in result["components"]:
                for pin, node in enumerate(component["native_pin_nodes"], 1):
                    groups.setdefault(node, set()).add((component["name"], pin))
            return {frozenset(group) for group in groups.values()}

        for kind in ("rc_lowpass", "rlc_lowpass", "voltage_divider"):
            with self.subTest(kind=kind):
                spec = example_circuit(kind)
                spec["layout"] = {"density": "standard"}
                standard = create_circuit(spec, self.root / (kind + "_standard.scm"))
                spec["layout"]["density"] = "compact"
                compact = create_circuit(spec, self.root / (kind + "_compact.scm"))
                self.assertEqual(partitions(standard), partitions(compact))
                self.assertEqual(standard["analysis"], compact["analysis"])
                self.assertEqual(standard["ports"], compact["ports"])
                def area(result):
                    left, top, right, bottom = result["layout"]["bounds"]
                    return (right-left)*(bottom-top)
                self.assertLess(area(compact), area(standard) * .85)
                self.assertEqual(compact["spec"]["layout"]["density"], "compact")

    def test_compact_default_preserves_explicit_placement(self):
        spec = example_circuit()
        spec["layout"] = {"placements": {"R1": {"x": 920, "y": 1000, "rotation": 0}}}
        result = create_circuit(spec, self.root / "placed.scm")
        self.assertEqual(result["layout"]["density"], "compact")
        self.assertEqual(result["layout"]["positions"]["R1"], spec["layout"]["placements"]["R1"])

    def test_unknown_density_is_rejected_before_writing(self):
        for density in ("tiny", None, [], True):
            spec = example_circuit()
            spec["layout"] = {"density": density}
            target = self.root / "invalid_density.scm"
            with self.subTest(density=density), self.assertRaisesRegex(LayoutError, "density"):
                create_circuit(spec, target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
