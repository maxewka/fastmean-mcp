"""Connectivity, preservation and safety tests for native SCM authoring."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from fastmean_mcp.schematic import (
    SchemeError, create_circuit, edit_component_values, example_circuit,
    normalize_node, parse_value, read_scheme,
)


class SchematicTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_rc_roundtrip_preserves_voltage_polarity_and_three_nets(self):
        path = self.root / "Проверка RC.scm"
        created = create_circuit(example_circuit(), path)
        loaded = read_scheme(path)
        components = {c["name"]: c for c in loaded["components"]}
        self.assertEqual(components["U1"]["nodes"], ["in", "0"])
        self.assertEqual(components["U1"]["native_pin_nodes"], ["0", "in"])
        self.assertEqual(components["R1"]["nodes"], ["in", "out"])
        self.assertEqual(components["C1"]["nodes"], ["out", "0"])
        self.assertEqual({n["name"] for n in loaded["nodes"]}, {"0", "in", "out"})
        self.assertEqual(loaded["ports"]["in"], "in")
        self.assertEqual(loaded["analysis"]["FD"]["Expressions"][0]["y"], "db(U(out)/U(in))")
        self.assertEqual(created["spec"]["components"][1]["value"], 1000)
        self.assertFalse(loaded["warnings"])
        self.assertNotIn(b"\xef\xbb\xbf", path.read_bytes()[:3])
        self.assertIn(b"\r\n", path.read_bytes())

    def test_all_examples_have_expected_linear_elements_and_port_topology(self):
        for kind, count in [("rc_lowpass", 3), ("rlc_lowpass", 4), ("voltage_divider", 3)]:
            with self.subTest(kind=kind):
                result = create_circuit(example_circuit(kind), self.root / f"{kind}.scm")
                loaded = read_scheme(result["path"])
                self.assertEqual(loaded["component_count"], count)
                self.assertEqual(loaded["unsupported_type_ids"], [])
                self.assertEqual(set(loaded["ports"]), {"in", "out"})
                port_objects = [o for o in loaded["objects"] if o["Type"] == 400]
                self.assertEqual(sorted(o["Name"] for o in port_objects), ["in", "out"])
                self.assertTrue(all(c["supported_for_generation"] for c in loaded["components"]))
                for c in loaded["components"]:
                    self.assertNotEqual(*c["nodes"])

    def test_branching_node_connects_more_than_four_terminals(self):
        # More than four terminals must use a connected physical bus with
        # several junctions, without a repeated-label port on every component.
        spec = {"components": [{"type": "U", "name": "V1", "nodes": ["bus", "gnd"], "value": 5}]
                + [{"type": "R", "name": f"R{i}", "nodes": ["bus", "ground"], "value": f"{i}k"}
                   for i in range(1, 8)]}
        result = create_circuit(spec, self.root / "parallel.scm")
        bus = next(n for n in result["nodes"] if n["name"] == "bus")
        component_ids = {c["native_id"] for c in result["components"]}
        self.assertEqual(sum(t["object_id"] in component_ids for t in bus["terminals"]), 8)
        self.assertEqual({n["name"] for n in result["nodes"]}, {"0", "bus"})

    def test_value_edits_preserve_geometry_wires_unknown_objects_and_original(self):
        original = self.root / "original.scm"
        create_circuit(example_circuit(), original)
        data = yaml.safe_load(original.read_text(encoding="utf-8"))
        # Existing unsupported component data must survive a supported value edit.
        data["scm"]["Scheme"]["Objects"].append({"ID": 100, "Type": 6615, "Name": "MOS1", "X": 9, "Y": 8,
                                                 "Params": {"model": "uninterpreted"}})
        original.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        before = original.read_bytes()
        output = self.root / "edited.scm"
        result = edit_component_values(original, {"R1": "2k", "C1": "470n"}, output)
        after = yaml.safe_load(output.read_text(encoding="utf-8"))
        self.assertEqual(original.read_bytes(), before)
        self.assertEqual(data["scm"]["Scheme"]["Wires"], after["scm"]["Scheme"]["Wires"])
        self.assertEqual(data["scm"]["Scheme"]["Objects"][-1], after["scm"]["Scheme"]["Objects"][-1])
        self.assertIn(6615, result["unsupported_type_ids"])
        self.assertEqual(next(c for c in result["components"] if c["name"] == "R1")["value"], 2000)
        with self.assertRaises(SchemeError):
            edit_component_values(original, {"MOS1": 1}, self.root / "bad.scm")
        self.assertFalse((self.root / "bad.scm").exists())

    def test_no_overwrite_without_explicit_opt_in(self):
        path = self.root / "existing.scm"
        create_circuit(example_circuit(), path)
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            create_circuit(example_circuit("voltage_divider"), path)
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            edit_component_values(path, {"R1": 123}, path)
        self.assertEqual(path.read_bytes(), original)
        create_circuit(example_circuit("voltage_divider"), path, overwrite=True)
        self.assertNotEqual(path.read_bytes(), original)

    def test_native_on_keys_survive_edit_without_changing_global_yaml_loader(self):
        source = self.root / "native-on.scm"
        create_circuit(example_circuit(), source)
        text = source.read_text(encoding="utf-8")
        text += "\nPSD:\n  On: true\n  Off: false\n  Label: Yes\n"
        source.write_text(text, encoding="utf-8")
        output = self.root / "native-on-edited.scm"
        edit_component_values(source, {"R1": 2000}, output)
        from fastmean_mcp.schematic import _UniqueLoader
        native = yaml.load(output.read_text(encoding="utf-8"), Loader=_UniqueLoader)
        self.assertEqual(native["PSD"], {"On": True, "Off": False, "Label": "Yes"})
        self.assertIn("  On: true", source.read_text(encoding="utf-8"))
        self.assertEqual(yaml.safe_load("On: Yes"), {True: True})

    def test_utf8_and_cp1251_labels_are_decoded_without_data_loss(self):
        seed = self.root / "seed.scm"
        create_circuit(example_circuit(), seed)
        doc = yaml.safe_load(seed.read_text(encoding="utf-8"))
        doc["scm"]["Scheme"]["Objects"].append({"ID": 55, "Type": 900, "Name": "Текст1",
                                                 "Params": {"Text": "Проверка напряжения"}})
        text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
        for encoding in ("utf-8", "cp1251", "utf-16"):
            with self.subTest(encoding=encoding):
                path = self.root / f"input-{encoding}.scm"
                path.write_bytes(text.encode(encoding))
                loaded = read_scheme(path)
                self.assertEqual(loaded["objects"][-1]["Params"]["Text"], "Проверка напряжения")

    def test_corrupt_wire_id_and_duplicate_yaml_key_are_rejected(self):
        path = self.root / "broken.scm"
        create_circuit(example_circuit(), path)
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["scm"]["Scheme"]["Wires"][0]["obj1"]["ID"] = 999
        path.write_text(yaml.safe_dump(doc), encoding="utf-8")
        with self.assertRaisesRegex(SchemeError, "absent object"):
            read_scheme(path)
        path.write_text("scm:\n  Scheme: {}\n  Scheme: {}\n", encoding="utf-8")
        with self.assertRaisesRegex(SchemeError, "Duplicate YAML"):
            read_scheme(path)
        path.write_bytes(b"\x04\0\0\0legacy binary SCM")
        with self.assertRaisesRegex(SchemeError, "binary"):
            read_scheme(path)

    def test_invalid_specs_fail_before_creating_output(self):
        invalid_specs = []
        spec = example_circuit(); spec["components"][1]["nodes"] = ["islandA", "islandB"]; invalid_specs.append(spec)
        spec = example_circuit(); spec["components"][1]["name"] = "U1"; invalid_specs.append(spec)
        spec = example_circuit(); spec["components"][1]["value"] = -1; invalid_specs.append(spec)
        spec = example_circuit(); spec["components"][1]["nodes"] = ["in", "in"]; invalid_specs.append(spec)
        spec = example_circuit(); spec["components"][1]["type"] = "MOS"; spec["components"][1].pop("kind"); invalid_specs.append(spec)
        spec = example_circuit(); spec["components"][0]["kind"] = "UNSUPPORTED"; invalid_specs.append(spec)
        spec = example_circuit(); spec["components"][1]["nodes"] = ["IN", "out"]; invalid_specs.append(spec)
        spec = example_circuit(); spec["analysis"]["frequency"]["stop"] = 1; invalid_specs.append(spec)
        spec = example_circuit(); spec["ports"] = {"BAD": "absent"}; invalid_specs.append(spec)
        spec = example_circuit(); spec["components"][0]["waveform"] = {"kind": "sine", "frequency": 0}; invalid_specs.append(spec)
        for index, spec in enumerate(invalid_specs):
            path = self.root / f"invalid{index}.scm"
            with self.subTest(index=index), self.assertRaises(SchemeError):
                create_circuit(spec, path)
            self.assertFalse(path.exists())

    def test_si_parser_distinguishes_milli_mega_and_russian_units(self):
        for text, expected in {"1m": .001, "1M": 1e6, "2.2meg": 2.2e6, "4к": 4000,
                               "470н": 470e-9, "10мк": 10e-6, "1µ": 1e-6}.items():
            with self.subTest(text=text):
                self.assertAlmostEqual(parse_value(text), expected)
        for value in (True, float("nan"), float("inf"), "1kOhm", "R1.R", "1; exit;"):
            with self.subTest(value=value), self.assertRaises(SchemeError):
                parse_value(value)
        self.assertEqual(normalize_node("GND"), "0")
        with self.assertRaises(SchemeError):
            normalize_node("узел")


if __name__ == "__main__":
    unittest.main()
