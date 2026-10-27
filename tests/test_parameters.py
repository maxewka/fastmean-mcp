"""Native parameter grammar and lossless portable updates, without evaluation."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.annotations import annotate_circuit
from fastmean_mcp.parameters import edit_parameters, inspect_parameters
from fastmean_mcp.schematic import SchemeError, _load, _write_document, create_circuit, example_circuit

REPO = Path(__file__).resolve().parents[1]


class ParameterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source.scm"
        create_circuit(example_circuit(), self.source)
        self.output = self.root / "edited.scm"

    def note(self, text, document=None):
        if document is None:
            _, document, _ = _load(self.source)
        objects = document["scm"]["Scheme"]["Objects"]
        objects.append({"ID": max(o["ID"] for o in objects)+1, "Type": 900,
            "Name": "NOTE"+str(len(objects)), "X": 0, "Y": 2000, "Params": {"Text": text}})
        _write_document(document, self.source, overwrite=True)
        return document

    def test_literal_spans_keep_comments_quotes_crlf_labels_and_case(self):
        text = '.param\r\nGain = 2k ".set Gain=99; % is quoted"; % Gain=7\r\ngain=3;\r\n'
        document = self.note(text)
        self.note('Ordinary explanation: .parameter Gain=99; "unrelated"')
        before = self.source.read_bytes()
        result = edit_parameters(self.source, {"Gain": "4k", "gain": -2}, self.output)
        _, after, _ = _load(self.output)
        notes = [o["Params"]["Text"] for o in after["scm"]["Scheme"]["Objects"] if o["Type"] == 900]
        self.assertEqual(notes[0], text.replace("2k", "4000").replace("gain=3", "gain=-2"))
        self.assertIn('Ordinary explanation: .parameter Gain=99; "unrelated"', notes)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(result["source_unchanged"])
        self.assertEqual({p["name"]:p["value_si"] for p in result["root_parameters"]["parameters"]}, {"Gain":4000,"gain":-2})

    def test_ambiguous_or_nonliteral_targets_do_not_publish(self):
        _, baseline, _ = _load(self.source)
        for text in ('.parameter A=2*3;', '.parameter A=1; A=2;',
                     '.parameter A=1;\n.define A=3;', '.parameter A=1;\n.set A=4;',
                     '.parameter A=1;\n.global A=5;', '.parameter A=1 "unterminated',
                     '.parameter A=1 "label"+2;', '.parameter A()=1;', '.parameter A=1e-999;'):
            with self.subTest(text=text):
                self.note(text, copy.deepcopy(baseline))
                with self.assertRaises(SchemeError):
                    edit_parameters(self.source, {"A":2}, self.output)
                self.assertFalse(self.output.exists())
        self.note('.parameter A=1;', copy.deepcopy(baseline))
        for value in (True, float("nan"), float("inf"), "1; exit;", "1e-999", "1e-999999999999999999999999", {}):
            with self.subTest(value=value), self.assertRaises(SchemeError):
                edit_parameters(self.source, {"A":value}, self.output)
        with self.assertRaises(SchemeError):
            edit_parameters(self.source, {"a":2}, self.output)

    def test_direct_passive_bindings_and_set_overrides_are_checked(self):
        annotated = self.root / "annotated.scm"
        annotate_circuit(self.source, annotated, parameters={"Resistance":1000}, bindings={"R1":"Resistance"})
        for value in (0, -1):
            with self.subTest(value=value), self.assertRaisesRegex(SchemeError, "positive"):
                edit_parameters(annotated, {"Resistance":value}, self.output)
        self.source = annotated
        document = self.note('.set R1.R=99;')
        self.assertFalse(inspect_parameters(document)["parameters"][0]["editable"])
        with self.assertRaisesRegex(SchemeError, "overrides"):
            edit_parameters(self.source, {"Resistance":2000}, self.output)

    def test_snapshot_guard_rejects_resaved_source(self):
        self.note('.parameter Gain=1;')
        digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.source.write_bytes(self.source.read_bytes()+b"\r\n")
        with self.assertRaisesRegex(SchemeError,"Source changed"):
            edit_parameters(self.source,{"Gain":2},self.output,expected_source_sha256=digest)
        self.assertFalse(self.output.exists())

    def test_published_amplifier_keeps_all_bindings_models_formulas_and_wires(self):
        source = REPO / "examples/four-bjt-amplifier/Amplifier_4BJT.scm"
        original_bytes = source.read_bytes()
        _, before, _ = _load(source)
        model_bytes = {p.name:p.read_bytes() for p in (source.parent/"models").glob("*.scm")}
        result = edit_parameters(source, {"Rload":2, "Rf":"3k", "Vrail":40}, self.output)
        _, after, _ = _load(self.output)
        before_objects = before["scm"]["Scheme"]["Objects"]
        after_objects = after["scm"]["Scheme"]["Objects"]
        declarations = next(o for o in after_objects if o["ID"] == 152)["Params"]["Text"]
        expected = copy.deepcopy(before)
        target = next(o for o in expected["scm"]["Scheme"]["Objects"] if o["ID"] == 152)
        target["Params"]["Text"] = declarations
        self.assertEqual(after, expected)
        self.assertEqual(source.read_bytes(), original_bytes)
        self.assertEqual(len(result["dependency_paths"]),4)
        self.assertEqual({p.name:p.read_bytes() for p in (self.root/"models").glob("*.scm")},model_bytes)
        parameters = result["root_parameters"]["parameters"]
        self.assertEqual(sum(len(p["bindings"]) for p in parameters),12)
        self.assertEqual(len(after["scm"]["TD"]["Expressions"]),5)
        self.assertEqual(after["scm"]["FD"]["Expressions"],[])
        self.assertEqual(len([o for o in after_objects if o["Type"] == 900]),11)

    def test_child_global_conflict_is_rejected_before_files_exist(self):
        from fastmean_mcp.hierarchy import create_project
        from test_hierarchy import project_spec
        project = create_project(project_spec(), self.root/"project")
        self.source = Path(project["path"])
        self.note('.parameter Gain=2;')
        child = self.source.parent/"models/RES.scm"
        _, document, _ = _load(child)
        previous = self.source
        self.source = child
        self.note('.global Gain=99;', document)
        self.source = previous
        with self.assertRaisesRegex(SchemeError, "child .global"):
            edit_parameters(self.source, {"Gain":4}, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root/"models").exists())


if __name__ == "__main__":
    unittest.main()
