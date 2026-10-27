"""Connectivity and preservation regressions for the full insertable catalogue."""
import copy
from collections import Counter
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.annotations import annotate_circuit
from fastmean_mcp.element_catalog import entries, get_geometry, normalize_parameters
from fastmean_mcp.parameters import edit_parameters
from fastmean_mcp.relayout import relayout_circuit
from fastmean_mcp.schematic import SchemeError, _load, _write_document, create_circuit, read_scheme
from fastmean_mcp.wires import wire_path


def catalog_fixture(kind, parameters=None):
    """Expose independent terminal nets, with ordinary external ports only."""
    params = normalize_parameters(kind, parameters)
    count = len(get_geometry(kind, params)["base_pin_positions"])
    terminals = [f"pin{i}" for i in range(1, count + 1)]
    if kind in {"U", "I"}:
        terminals = ["drive", "0"]
        dut = {"kind": kind, "name": "DUT", "nodes": terminals, "value": 1}
    else:
        dut = {"kind": kind, "name": "DUT", "nodes": terminals}
        if kind in {"R", "C", "L"}:
            dut["value"] = params[kind]
        else:
            dut["parameters"] = params
    active = list(dict.fromkeys(node for node in terminals if node != "0"))
    components = [dut] + [{"kind": "R", "name": f"LOAD{i}", "nodes": [node, "0"], "value": 1000}
                          for i, node in enumerate(active, 1)]
    return {"components": components, "ports": {"IN": active[0], "OUT": active[-1]},
            "analysis": {"input": "IN", "output": "OUT"}}


class CatalogAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fm-catalog-authoring-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def assert_physical_connections(self, result, spec):
        objects = {obj["ID"]: obj for obj in result["objects"]}
        _, document, _ = _load(result["path"])
        wires = document["scm"]["Scheme"]["Wires"]
        self.assertGreater(len(wires), 0)
        endpoints = Counter((wire[end]["ID"], wire[end]["pin"])
                            for wire in wires for end in ("obj1", "obj2"))
        parts = {part["name"]: part for part in result["components"]}
        for expected in spec["components"]:
            part = parts[expected["name"]]
            self.assertEqual(part["nodes"], [result["node_mapping"][node] for node in expected["nodes"]])
            count = len(expected["nodes"])
            for pin in range(1, count + 1):
                self.assertEqual(endpoints[part["native_id"], pin], 1,
                                 f"{expected['name']} terminal {pin} must have one physical wire")
        for wire in wires:
            points = wire_path(wire, objects)
            self.assertGreaterEqual(len(points), 2)
            self.assertTrue(all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:])))
        self.assertEqual(sum(obj["Type"] == 400 for obj in objects.values()), 2)

    def test_every_ordinary_primitive_has_real_connected_terminal_routes(self):
        ordinary = [entry for entry in entries() if not entry["internal"] and entry["kind"] != "X"]
        self.assertEqual(len(ordinary), 43)
        for entry in ordinary:
            with self.subTest(kind=entry["kind"]):
                spec = catalog_fixture(entry["kind"])
                original = copy.deepcopy(spec)
                result = create_circuit(spec, self.root / f"{entry['kind']}.scm")
                self.assert_physical_connections(result, spec)
                self.assertEqual(spec, original)

    def test_dynamic_terminal_counts_are_connected_and_survive_relayout(self):
        for kind, parameters, count in (("AND", {"N": 8}, 9), ("SUM", {"N": 5}, 7),
                                         ("DFF", {"HasRS": 1}, 6), ("JK", {"HasRS": 1}, 7)):
            with self.subTest(kind=kind):
                spec = catalog_fixture(kind, parameters)
                original = self.root / f"dynamic-{kind}.scm"
                result = create_circuit(spec, original)
                self.assertEqual(len(result["components"][0]["nodes"]), count)
                self.assert_physical_connections(result, spec)
                _, document, _ = _load(original)
                document["scm"]["TD"]["Expressions"] = [{"plot": 1, "x": "t", "y": "U(OUT)"}]
                document["scm"]["FD"]["Expressions"] = [{"plot": 1, "x": "f", "y": "db(U(OUT)/U(IN))"}]
                document["scm"]["General"].update(HPos=99999,VPos=99999)
                _write_document(document, original, overwrite=True)
                before = original.read_bytes()
                destination = self.root / f"relayout-{kind}.scm"
                moved = relayout_circuit(original, destination)
                _, after, _ = _load(destination)
                self.assertLess(after["scm"]["General"]["HPos"],99999)
                self.assertLess(after["scm"]["General"]["VPos"],99999)
                self.assertEqual(original.read_bytes(), before)
                old_parts = {part["name"]: part for part in read_scheme(original)["components"]}
                for part in read_scheme(destination)["components"]:
                    old = old_parts[part["name"]]
                    self.assertEqual(part["parameters"], old["parameters"])
                    self.assertEqual(part["native_pin_nodes"], [moved["node_mapping"][node] for node in old["native_pin_nodes"]])
                for section in ("TD", "FD", "AOD", "SOD", "DCOP"):
                    self.assertEqual(document["scm"][section], after["scm"][section])

    def test_catalog_relayout_refuses_numeric_node_probes_before_writing(self):
        source = self.root / "numeric.scm"
        create_circuit(catalog_fixture("TR3"), source)
        _, document, _ = _load(source)
        document["scm"]["TD"]["Expressions"] = [{"plot": 1, "x": "t", "y": "U(17)"}]
        _write_document(document, source, overwrite=True)
        before = source.read_bytes()
        destination = self.root / "unsafe.scm"
        with self.assertRaisesRegex(SchemeError, "Numeric node-voltage"):
            relayout_circuit(source, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(source.read_bytes(), before)

    def test_scalar_transformer_and_source_bindings_remain_shared_after_parameter_edit(self):
        spec = {"components": [
            {"kind": "U", "name": "VIN", "nodes": ["input", "0"], "value": 1,
             "waveform": {"kind": "pulse", "frequency": 1000, "high": 2, "low": 0}},
            {"kind": "TR3", "name": "T1", "nodes": ["input", "0", "a", "0", "b", "0"],
             "parameters": {"n1": 2, "n2": 3}},
            {"kind": "R", "name": "RA", "nodes": ["a", "0"], "value": 1000},
            {"kind": "R", "name": "RB", "nodes": ["b", "0"], "value": 1000}],
            "ports": {"IN": "input", "OUT": "a", "AUX": "b"}}
        source = self.root / "transformer.scm"
        create_circuit(spec, source)
        before = source.read_bytes()
        annotated = self.root / "bound.scm"
        annotate_circuit(source, annotated, parameters={"RatioA": 2, "RatioB": 3, "DriveFreq": 1000},
                         bindings={"T1": {"n1": "RatioA", "n2": "RatioB"},
                                   "VIN": {"PULSE.F": "DriveFreq"}})
        bound = annotated.read_bytes()
        edited = self.root / "changed.scm"
        edit_parameters(annotated, {"RatioA": 4, "DriveFreq": 2000}, edited)
        _, document, _ = _load(edited)
        objects = {obj["Name"]: obj for obj in document["scm"]["Scheme"]["Objects"]}
        self.assertEqual(objects["T1"]["Params"]["n1"], "RatioA")
        self.assertEqual(objects["T1"]["Params"]["n2"], "RatioB")
        self.assertEqual(objects["VIN"]["Params"]["PULSE"]["F"], "DriveFreq")
        declarations = "\n".join(obj.get("Params", {}).get("Text", "") for obj in objects.values() if obj["Type"] == 900)
        self.assertIn('RatioA=4 "RatioA";', declarations)
        self.assertIn('RatioB=3 "RatioB";', declarations)
        self.assertIn('DriveFreq=2000 "DriveFreq";', declarations)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(annotated.read_bytes(), bound)

    def test_dll_contacts_cannot_be_used_as_ordinary_ports(self):
        spec = catalog_fixture("NOT")
        spec["port_types"] = {"IN": "digital_in", "OUT": "digital_out"}
        destination = self.root / "unbound-digital.scm"
        with self.assertRaisesRegex(SchemeError, "external DLL"):
            create_circuit(spec, destination)
        self.assertFalse(destination.exists())
