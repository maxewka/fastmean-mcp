from __future__ import annotations

import copy
import os
from pathlib import Path
import tempfile
import unittest

import yaml

from fastmean_mcp.relayout import relayout_circuit
from fastmean_mcp.schematic import SchemeError, _analysis_defaults, _source_params, read_scheme


def old_port_grid() -> dict:
    """The former component-grid representation, independent of new layout.py."""
    objects, wires = [], []
    oid = 1
    rows = [
        (2010, "U1", ["0", "in"], _source_params(1, {"kind": "sine", "amplitude": 3, "frequency": "1k", "phase": 30})),
        (1000, "R1", ["in", "mid"], {"R": 100}),
        (1002, "L1", ["mid", "out"], {"L": "10m", "IC": 0}),
        (1001, "C1", ["out", "0"], {"C": "1u", "IC": 0.25}),
    ]
    for row, (tid, name, nodes, params) in enumerate(rows):
        component_id = oid
        objects.append({"ID": oid, "Type": tid, "Name": name, "X": 800 + row * 320, "Y": 800,
                        "Rot": 0, "FlipV": 0, "FlipH": 0, "Params": params, "active_property_page": 0})
        oid += 1
        for pin, node in enumerate(nodes, 1):
            objects.append({"ID": oid, "Type": 200 if node == "0" else 400,
                            "Name": f"GND{oid}" if node == "0" else node,
                            "X": 800 + row * 320 + pin * 80, "Y": 920,
                            "Rot": 0, "FlipV": 0, "FlipH": 0})
            wires.append({"obj1": {"ID": component_id, "pin": pin}, "obj2": {"ID": oid, "pin": 1}})
            oid += 1
    analysis = _analysis_defaults()
    analysis["TD"]["IP"][0]["EndTime"] = 0.013
    analysis["FD"]["NumPts"] = 37
    analysis["FD"]["Expressions"] = [{"plot": 1, "x": "f", "y": "db(U(out)/U(in))"}]
    return {"scm": {"MajorVersion": 5, "MinorVersion": 1,
                    "General": {"Scale": 100, "HPos": 1200, "VPos": 1000, "SWidth": 3000, "SHeight": 3000},
                    "Special": {"LangVersion": 2},
                    "Scheme": {"MajorSchVer": 3, "MinorSchVer": 0, "Objects": objects, "Wires": wires},
                    **analysis}}


class RelayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "old-grid.scm"
        self.destination = self.root / "human.scm"
        self.document = old_port_grid()

    def save_source(self):
        self.source.write_text(yaml.safe_dump(self.document, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return self.source.read_bytes()

    def test_replaces_internal_stub_ports_with_real_wires_and_preserves_model(self):
        original_bytes = self.save_source()
        before = read_scheme(self.source)
        result = relayout_circuit(self.source, self.destination)
        after = read_scheme(self.destination)
        self.assertEqual(self.source.read_bytes(), original_bytes)
        self.assertEqual({obj["Name"] for obj in after["objects"] if obj["Type"] == 400}, {"in", "out"})
        self.assertEqual(sum(obj["Type"] == 400 for obj in after["objects"]), 2)
        self.assertIn("mid", result["removed_internal_ports"])
        self.assertGreater(after["wire_count"], 0)
        self.assertTrue(result["source_unchanged"])
        original_components = {item["name"]: item for item in before["components"]}
        for component in after["components"]:
            previous = original_components[component["name"]]
            self.assertEqual(component["parameters"], previous["parameters"])
            self.assertEqual(component["native_pin_nodes"], [result["node_mapping"][node] for node in previous["native_pin_nodes"]])
        final_document = yaml.safe_load(self.destination.read_text(encoding="utf8"))
        for section in ("TD", "FD", "AOD", "SOD", "DCOP"):
            self.assertEqual(final_document["scm"][section], self.document["scm"][section])
        self.assertEqual(after["components"][0]["waveform"]["amplitude"], 3)
        self.assertEqual(after["components"][-1]["parameters"]["IC"], 0.25)

    def test_define_annotation_and_parameter_expression_are_retained(self):
        self.document["scm"]["Scheme"]["Objects"][3]["Params"]["R"] = "Rload"
        text = ".define\nRload=100;\nVmid=U(mid);"
        self.document["scm"]["Scheme"]["Objects"].append({"ID": 1000, "Type": 900, "Name": "TEXT1",
                                                                  "X": 50, "Y": 50, "Params": {"Text": text, "Color": "00008000"}})
        self.save_source()
        result = relayout_circuit(self.source, self.destination)
        notes = [obj for obj in result["objects"] if obj["Type"] == 900]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["Params"]["Text"], text)
        self.assertEqual(notes[0]["Params"]["Color"], "00008000")
        self.assertNotEqual(notes[0]["ID"], 1000)
        self.assertEqual(result["components"][1]["value"], "Rload")
        self.assertIn("mid", result["external_ports"])

    def test_plain_explanatory_u_of_time_is_not_treated_as_a_node(self):
        self.document["scm"]["Scheme"]["Objects"].append({"ID": 1000, "Type": 900, "Name": "TEXT1", "X": 0, "Y": 0,
                                                                  "Params": {"Text": "Output waveform U(t)"}})
        self.save_source()
        result = relayout_circuit(self.source, self.destination)
        self.assertEqual(set(result["external_ports"]), {"in", "out"})

    def test_numeric_voltage_references_are_rejected_without_publishing(self):
        self.document["scm"]["FD"]["Expressions"][0]["y"] = "U(17)"
        original = self.save_source()
        with self.assertRaisesRegex(SchemeError, "Numeric"):
            relayout_circuit(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.source.read_bytes(), original)

    def test_unsupported_component_is_rejected_before_destination_is_created(self):
        self.document["scm"]["Scheme"]["Objects"].append({"ID": 1000, "Type": 1100, "Name": "NLR1", "X": 0, "Y": 0})
        self.save_source()
        with self.assertRaisesRegex(SchemeError, "unsupported native"):
            relayout_circuit(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_existing_destination_and_original_are_never_overwritten(self):
        original = self.save_source()
        self.destination.write_bytes(b"keep this file")
        with self.assertRaises(FileExistsError):
            relayout_circuit(self.source, self.destination)
        self.assertEqual(self.destination.read_bytes(), b"keep this file")
        with self.assertRaisesRegex(SchemeError, "original"):
            relayout_circuit(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), original)

    def test_native_analysis_references_to_an_extra_test_point_remain_valid(self):
        self.document["scm"]["TD"]["Expressions"].append({"plot": 2, "x": "t", "y": "U(mid)-U(R1)"})
        self.save_source()
        result = relayout_circuit(self.source, self.destination)
        self.assertEqual(set(result["external_ports"]), {"in", "mid", "out"})
        self.assertEqual(sum(obj["Type"] == 400 for obj in result["objects"]), 3)

    def test_private_staging_directory_is_removed_after_success(self):
        self.save_source()
        relayout_circuit(self.source, self.destination)
        self.assertEqual({path.name for path in self.root.iterdir()}, {"old-grid.scm", "human.scm"})


@unittest.skipUnless(os.name == "nt" and os.environ.get("FASTMEAN_RELAYOUT_NATIVE") == "1", "opt-in native FASTMEAN comparison")
class NativeRelayoutTests(unittest.TestCase):
    def test_old_grid_and_physical_wires_have_the_same_native_ac_response(self):
        from fastmean_mcp.engine import Engine
        installation = Path(os.environ.get("FASTMEAN_APP_DIR", str(Path(os.environ["LOCALAPPDATA"]) / "FASTMEAN 6.1")))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "old.scm"
            old.write_text(yaml.safe_dump(old_port_grid(), sort_keys=False), encoding="utf8")
            new = root / "new.scm"
            relayout_circuit(old, new)
            engine = Engine(installation, root / "native-runs")
            first = engine.run_ac(old, ["mag(U(out)/U(in))"], 10, 10000, 7)
            second = engine.run_ac(new, ["mag(U(out)/U(in))"], 10, 10000, 7)
            self.assertEqual(first["row_count"], second["row_count"])
            for a, b in zip(first["rows"], second["rows"]):
                self.assertAlmostEqual(a[0], b[0], places=8)
                self.assertAlmostEqual(a[1], b[1], places=10)


if __name__ == "__main__":
    unittest.main()
