"""Transformer and switch authoring, isolation and native terminal contracts."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.native_geometry import body_bounds, pin_directions, pin_positions
from fastmean_mcp.schematic import SchemeError, create_circuit, read_scheme


def transformer_spec(rotation=0, reverse=False):
    return {"components": [
        {"kind": "U", "name": "VIN", "nodes": ["in", "0"], "value": 10},
        {"kind": "TR", "name": "TR1", "nodes": ["in", "0", "0", "out"] if reverse else ["in", "0", "out", "0"], "parameters": {"n": 2}},
        {"kind": "R", "name": "RL", "nodes": ["out", "0"], "value": 10}],
        "ports": ["in", "out"], "layout": {"placements": {"TR1": {"x": 1200, "y": 1000, "rotation": rotation}}}}


def switch_spec(control=5, rotation=0):
    return {"components": [
        {"kind": "U", "name": "VIN", "nodes": ["in", "0"], "value": 10},
        {"kind": "U", "name": "VC", "nodes": ["ctl", "0"], "value": control},
        {"kind": "SW", "name": "SW1", "nodes": ["ctl", "0", "in", "out"],
         "parameters": {"Uon": 2, "Uoff": 1, "Ron": .1, "Roff": "1M"}},
        {"kind": "R", "name": "RL", "nodes": ["out", "0"], "value": 10}],
        "ports": ["in", "out", "ctl"], "layout": {"placements": {"SW1": {"x": 1400, "y": 1000, "rotation": rotation}}}}


class PowerPrimitiveAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fm-power-test-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rotations_preserve_pair_order_parameters_and_physical_connectivity(self):
        for factory, kind, tid in ((transformer_spec, "TR", 6101), (switch_spec, "SW", 6600)):
            for rotation in range(4):
                with self.subTest(kind=kind, rotation=rotation):
                    spec = factory(rotation=rotation)
                    before = copy.deepcopy(spec)
                    result = create_circuit(spec, self.root / f"{kind}{rotation}.scm")
                    item = next(c for c in read_scheme(result["path"])["components"] if c["kind"] == kind)
                    expected = next(c for c in spec["components"] if c["kind"] == kind)
                    self.assertEqual(item["native_type"], tid)
                    self.assertEqual(item["native_pin_nodes"], [result["node_mapping"][n] for n in expected["nodes"]])
                    self.assertEqual(item["nodes"], item["native_pin_nodes"])
                    self.assertTrue(item["supported_for_generation"])
                    self.assertEqual(spec, before)
                    self.assertGreater(result["wire_count"], 0)

    def test_aliases_and_explicit_ratio_have_one_canonical_serialization(self):
        spec = transformer_spec()
        spec["components"][1].update(kind="TRANSFORMER", value="2")
        del spec["components"][1]["parameters"]
        result = create_circuit(spec, self.root / "tr.scm")
        transformer = next(c for c in result["components"] if c["kind"] == "TR")
        self.assertEqual(transformer["parameters"], {"n": 2.0})
        self.assertEqual(transformer["pin_roles"], ["primary_dot", "primary_undotted", "secondary_dot", "secondary_undotted"])
        spec = switch_spec()
        spec["components"][2]["kind"] = "VCSWITCH"
        result = create_circuit(spec, self.root / "sw.scm")
        switch = next(c for c in result["components"] if c["kind"] == "SW")
        self.assertEqual(switch["parameters"]["Roff"], 1e6)
        self.assertEqual(switch["pin_roles"], ["control_positive", "control_negative", "switch_1", "switch_2"])

    def test_transformer_coupling_does_not_ground_a_floating_secondary(self):
        spec = transformer_spec()
        spec["components"][1]["nodes"][-1] = "return"
        spec["components"][2]["nodes"][-1] = "return"
        with self.assertRaisesRegex(SchemeError, "Floating circuit island"):
            create_circuit(spec, self.root / "floating-tr.scm")
        self.assertFalse((self.root / "floating-tr.scm").exists())

    def test_switch_control_does_not_ground_a_floating_power_branch(self):
        spec = switch_spec()
        spec["components"][0]["nodes"][-1] = "return"
        spec["components"][3]["nodes"][-1] = "return"
        with self.assertRaisesRegex(SchemeError, "Floating circuit island"):
            create_circuit(spec, self.root / "floating-sw.scm")

    def test_invalid_native_parameters_fail_before_file_creation(self):
        invalid = [
            (transformer_spec(), 1, {"n": 0}),
            (transformer_spec(), 1, {"n": -2}),
            (transformer_spec(), 1, {"n": float("inf")}),
            (switch_spec(), 2, {"Ron": 0, "Roff": 1e6, "Uon": 2, "Uoff": 1}),
            (switch_spec(), 2, {"Ron": 1, "Roff": .1, "Uon": 2, "Uoff": 1}),
            (switch_spec(), 2, {"Ron": .1, "Roff": 1e6, "Uon": 1, "Uoff": 2}),
            (switch_spec(), 2, {"Ron": .1, "Roff": 1e6, "Uon": 2}),
        ]
        for index, (spec, component, params) in enumerate(invalid):
            with self.subTest(params=params):
                spec["components"][component]["parameters"] = params
                path = self.root / f"bad{index}.scm"
                with self.assertRaises(SchemeError):
                    create_circuit(spec, path)
                self.assertFalse(path.exists())

    def test_native_geometry_includes_actual_lead_offsets_and_exit_directions(self):
        tr = {"Type": 6101, "X": 1000, "Y": 800, "Rot": 0}
        self.assertEqual(pin_positions(tr), {1: (976, 768), 2: (976, 832), 3: (1024, 768), 4: (1024, 832)})
        self.assertEqual(pin_directions(tr), {1: (-1, 0), 2: (-1, 0), 3: (1, 0), 4: (1, 0)})
        self.assertEqual(body_bounds(tr), (984, 776, 1016, 824))
        sw = {"Type": 6600, "X": 1000, "Y": 800, "Rot": 0}
        self.assertEqual(pin_positions(sw), {1: (984, 772), 2: (984, 828), 3: (1016, 772), 4: (1016, 828)})
        self.assertEqual(pin_directions(sw), {1: (0, -1), 2: (0, 1), 3: (0, -1), 4: (0, 1)})
        self.assertEqual(body_bounds(sw), (980, 780, 1020, 820))


if __name__ == "__main__":
    unittest.main()
