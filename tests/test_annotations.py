"""Portable annotation transactions and native declaration/formula contracts."""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp import annotations
from fastmean_mcp.annotations import annotate_circuit
from fastmean_mcp.engine import EngineError, prepare_copy
from fastmean_mcp.schematic import SchemeError, _load, _write_document, create_circuit, example_circuit


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-annotations-test-")
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "original.scm"
        spec = example_circuit()
        spec["components"].append({"kind": "L", "name": "L1", "nodes": ["out", "0"],
                                   "value": ".01", "initial_condition": .002})
        create_circuit(spec, self.source)
        self.destination = self.root / "annotated.scm"

    def tearDown(self):
        self.temporary.cleanup()

    def change(self, document):
        _write_document(document, self.source, overwrite=True)

    def test_empty_signal_list_clears_only_the_requested_analysis(self):
        _, before, _ = _load(self.source)
        annotate_circuit(self.source, self.destination, fd_signals=[])
        _, after, _ = _load(self.destination)
        self.assertEqual(after['scm']['FD']['Expressions'], [])
        self.assertEqual(after['scm']['TD'], before['scm']['TD'])

    def test_parameters_notes_bindings_and_formulas_preserve_electrical_topology_and_settings(self):
        _, original, _ = _load(self.source)
        original["scm"]["TD"]["ParamSweep"] = 1
        original["scm"]["TD"]["FFT"] = 1
        original["scm"]["TD"]["SVD"]["SVWriteFileName"] = "original-setting.sv"
        original["scm"]["FD"]["StartFreq"] = 7
        original["scm"]["AOD"]["DrawGraph"] = 1
        self.change(original)
        before = digest(self.source)
        result = annotate_circuit(self.source, self.destination,
            parameters={"pR": "2k", "pC": "2u", "pL": "3m", "pV": 1.414},
            bindings={"R1": "pR", "C1": "pC", "L1": "pL", "U1": "pV"},
            descriptions=["Усиление: Ku = Uout / Uin", "Мощность нагрузки: P = Uout * Iout"],
            td_signals=["U(out)", "U(out) * I(R1)"], fd_signals=["db(U(out)/U(in))"])
        self.assertTrue(result["source_unchanged"])
        self.assertEqual(before, digest(self.source))
        self.assertEqual(result["parameters"], {"pR": 2000., "pC": 2e-6, "pL": .003, "pV": 1.414})
        self.assertEqual(result["formulas"], {"TD": ["U(out)", "U(out)*I(R1)"], "FD": ["db(U(out)/U(in))"]})
        self.assertEqual(result["dependency_paths"], [])
        self.assertEqual(result["source_sha256"], before)
        self.assertEqual(result["private_schematic_sha256"], digest(self.destination))
        _, observed, _ = _load(self.destination)
        self.assertTrue(all(type(obj[axis]) is int for obj in observed["scm"]["Scheme"]["Objects"] for axis in ("X", "Y")))
        self.assertEqual(original["scm"]["Scheme"]["Wires"], observed["scm"]["Scheme"]["Wires"])
        by_name = {obj["Name"]: obj for obj in observed["scm"]["Scheme"]["Objects"]}
        for name, key, parameter in (("R1", "R", "pR"), ("C1", "C", "pC"), ("L1", "L", "pL")):
            self.assertEqual(by_name[name]["Params"][key], parameter)
        self.assertEqual(by_name["L1"]["Params"]["IC"], .002)
        self.assertEqual(by_name["U1"]["Params"]["AC"]["U0"], "pV")
        old_u = next(obj for obj in original["scm"]["Scheme"]["Objects"] if obj["Name"] == "U1")
        self.assertEqual(by_name["U1"]["Params"]["DC"], old_u["Params"]["DC"])
        for section in ("TD", "FD"):
            for key, value in original["scm"][section].items():
                if key not in {"Expressions", "ExprRowOffset"}:
                    self.assertEqual(observed["scm"][section][key], value)
        for section in ("AOD", "SOD", "DCOP"):
            self.assertEqual(observed["scm"][section], original["scm"][section])
        notes = [obj for obj in observed["scm"]["Scheme"]["Objects"] if obj["Type"] == 900]
        self.assertEqual(len(notes), 3)
        for note in notes:
            self.assertIs(type(note["X"]), int)
            self.assertIs(type(note["Y"]), int)
            self.assertEqual(set(note["Params"]["Font"]), set(annotations._FONT))
            self.assertEqual(note["Params"]["Font"]["lfCharSet"], 204)
            self.assertEqual(note["Params"]["Color"], "00808000")
        self.assertIn('.parameter\r\npR=2000 "pR [ohm]";', notes[0]["Params"]["Text"])
        self.assertTrue(notes[0]["Params"]["Text"].endswith(";\r\n"))
        self.assertIn("Усиление", notes[1]["Params"]["Text"])

    def test_dc_amplitude_and_omitted_analysis_sections_are_preserved(self):
        _, document, _ = _load(self.source)
        voltage = next(obj for obj in document["scm"]["Scheme"]["Objects"] if obj["Type"] == 2010)
        voltage["Params"]["ST"] = 1
        del document["scm"]["AOD"]
        self.change(document)
        result = annotate_circuit(self.source, self.destination, {"pDC": -2}, {"U1": "pDC"})
        _, observed, _ = _load(self.destination)
        voltage_after = next(obj for obj in observed["scm"]["Scheme"]["Objects"] if obj["Type"] == 2010)
        self.assertEqual(voltage_after["Params"]["DC"]["U0"], "pDC")
        self.assertEqual(voltage_after["Params"]["AC"], voltage["Params"]["AC"])
        self.assertNotIn("AOD", observed["scm"])
        self.assertEqual(result["formulas"]["FD"], [item["y"] for item in document["scm"]["FD"]["Expressions"]])

    def test_long_parameter_names_are_split_into_bounded_native_text_blocks(self):
        parameters = {"pv" + str(index).zfill(2) + "a" * 60: index + 1 for index in range(16)}
        result = annotate_circuit(self.source, self.destination, parameters)
        self.assertGreater(len(result["texts"]), 2)
        for text in result["texts"]:
            self.assertLessEqual(len(text), 1000)
            self.assertTrue(text.startswith(".parameter\r\n"))
            self.assertTrue(text.endswith(";\r\n"))

    def test_notes_beyond_original_sheet_expand_canvas_without_moving_viewport_or_source(self):
        _, document, _ = _load(self.source)
        original_general = document["scm"]["General"]
        original_general.update({"SHeight": 3000, "SWidth": 2000, "HPos": 123, "VPos": 456})
        document["scm"]["Scheme"]["Objects"][0]["Y"] = 2940
        self.change(document)
        before = digest(self.source)
        notes = [f"Описание {index}\nUout = Ku * Uin" for index in range(11)]
        notes[-1] += "\n" + "W" * 240
        annotate_circuit(self.source, self.destination, descriptions=notes)
        _, observed, _ = _load(self.destination)
        general = observed["scm"]["General"]
        text_objects = [obj for obj in observed["scm"]["Scheme"]["Objects"] if obj["Type"] == 900]
        last = text_objects[-1]
        self.assertGreater(last["Y"], 3000)
        for note in text_objects:
            lines = note["Params"]["Text"].splitlines()
            self.assertGreaterEqual(general["SHeight"], note["Y"] + 22 * len(lines))
            self.assertGreaterEqual(general["SWidth"], note["X"] + 10 * max(map(len, lines)))
            self.assertIs(type(note["X"]), int)
            self.assertIs(type(note["Y"]), int)
        self.assertIs(type(general["SHeight"]), int)
        self.assertIs(type(general["SWidth"]), int)
        self.assertEqual((general["HPos"], general["VPos"]), (123, 456))
        self.assertEqual(digest(self.source), before)

    def test_invalid_requests_do_not_create_files(self):
        cases = [
            ({"parameters": {"bad;exit": 1}}, "ASCII"),
            ({"parameters": {"pR": True}}, "boolean"),
            ({"parameters": {"pR": float("nan")}}, "finite"),
            ({"parameters": {"pR": 1, "PR": 2}}, "collides"),
            ({"parameters": {"R1": 1}}, "collides"),
            ({"parameters": {"pi": 1}}, "collides"),
            ({"parameters": {"pR": 0}, "bindings": {"R1": "pR"}}, "positive"),
            ({"parameters": {"pR": 1}, "bindings": {"r1": "pR"}}, "missing"),
            ({"parameters": {"pR": 1}, "bindings": {"R1": "missing"}}, "declared"),
            ({"parameters": {"pR": 1}, "bindings": {"out": "pR"}}, "supports only"),
            ({"descriptions": [".parameter injected=1;"]}, "ordinary text"),
            ({"descriptions": ["Info\n.write secret.txt"]}, "ordinary text"),
            ({"descriptions": ["bad\x00text"]}, "ordinary text"),
            ({"descriptions": ["x" * 1001]}, "1000"),
            ({"td_signals": ["U(out);exit"]}, "separators"),
            ({"fd_signals": ["run(U(out))"]}, "keyword"),
            ({"td_signals": "U(out)"}, "0 to"),
        ]
        original_files = sorted(self.root.iterdir())
        for request, message in cases:
            with self.subTest(request=request):
                with self.assertRaisesRegex((SchemeError, EngineError), message):
                    annotate_circuit(self.source, self.destination, **request)
                self.assertEqual(sorted(self.root.iterdir()), original_files)

    def test_existing_definition_and_ambiguous_components_are_rejected(self):
        _, document, _ = _load(self.source)
        objects = document["scm"]["Scheme"]["Objects"]
        objects.append({"ID": 9997, "Type": 900, "Name": "ExistingDefinition", "X": 0, "Y": 0,
                        "Params": {"Text": ".define pR=100;"}})
        self.change(document)
        with self.assertRaisesRegex(SchemeError, "collides"):
            annotate_circuit(self.source, self.destination, {"pR": 1})
        duplicate = copy.deepcopy(next(obj for obj in objects if obj["Name"] == "R1"))
        duplicate["ID"] = 9998
        objects.append(duplicate)
        self.change(document)
        with self.assertRaisesRegex(SchemeError, "ambiguous"):
            annotate_circuit(self.source, self.destination, {"pv": 1}, {"R1": "pv"})
        self.assertFalse(self.destination.exists())

    def test_pulse_binding_is_rejected_and_source_cannot_be_overwritten(self):
        _, document, _ = _load(self.source)
        next(obj for obj in document["scm"]["Scheme"]["Objects"] if obj["Name"] == "U1")["Params"]["ST"] = 3
        self.change(document)
        before = digest(self.source)
        with self.assertRaisesRegex(SchemeError, "DC or sine"):
            annotate_circuit(self.source, self.destination, {"pv": 1}, {"U1": "pv"})
        with self.assertRaisesRegex(SchemeError, "original"):
            annotate_circuit(self.source, self.source, {"pv": 1})
        self.destination.write_text("user file")
        with self.assertRaises(FileExistsError):
            annotate_circuit(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "user file")
        self.assertEqual(digest(self.source), before)

    def hierarchy(self):
        models = self.root / "models"
        models.mkdir()
        child = models / "child.scm"
        grandchild = models / "grandchild.scm"
        shutil.copyfile(self.source, child)
        shutil.copyfile(self.source, grandchild)

        def add_model(path, filename, name):
            _, document, _ = _load(path)
            objects = document["scm"]["Scheme"]["Objects"]
            objects.append({"ID": max(obj["ID"] for obj in objects)+1, "Type": 7100, "Name": name,
                "X": 5000, "Y": 1000, "Rot": 0, "FlipH": 0, "FlipV": 0,
                "Params": {"FileName": filename, "Pins": {"Left": ["in"], "Top": [], "Right": ["out"], "Bottom": []}}})
            _write_document(document, path, overwrite=True)
        add_model(child, "grandchild.scm", "CHILD")
        add_model(self.source, "models/child.scm", "FIRST")
        add_model(self.source, "models/child.scm", "SECOND")
        return child, grandchild

    def test_nested_models_are_copied_once_and_remain_portable_after_moving(self):
        originals = (self.source,) + self.hierarchy()
        before = {path: digest(path) for path in originals}
        result = annotate_circuit(self.source, self.destination, {"pR": "2k"}, {"R1": "pR"})
        self.assertEqual(len(result["dependency_paths"]), 2)
        self.assertEqual(len(result["source_models"]), 3)
        self.assertTrue(all(digest(path) == before[path] for path in originals))
        for path in [self.destination] + [Path(value) for value in result["dependency_paths"]]:
            _, document, _ = _load(path)
            for obj in document["scm"]["Scheme"]["Objects"]:
                if obj["Type"] == 7100:
                    reference = obj["Params"]["FileName"]
                    self.assertFalse(Path(reference).is_absolute())
                    self.assertTrue((path.parent/reference).is_file())
        relocated = self.root / "relocated"
        relocated.mkdir()
        shutil.copyfile(self.destination, relocated/self.destination.name)
        dependencies = {Path(path).parent for path in result["dependency_paths"]}
        for directory in dependencies:
            shutil.copytree(directory, relocated/directory.name)
        moved = relocated/self.destination.name
        prepared = prepare_copy(moved, relocated/"validated.scm")
        self.assertTrue(prepared.is_file())
        self.assertEqual(digest(self.source), before[self.source])

    def test_fresh_output_directory_preserves_short_references_and_child_bytes(self):
        originals = (self.source,) + self.hierarchy()
        before = {path: digest(path) for path in originals}
        destination = self.root / "fresh"
        destination.mkdir()
        result = annotate_circuit(self.source, destination/"main.scm", {"pR": "2k"}, {"R1": "pR"})
        self.assertEqual(result["dependency_layout"], "original_relative_tree")
        self.assertFalse(result["preview_unsupported"])
        for item in result["source_models"]:
            old, new = Path(item["source_path"]), Path(item["private_path"])
            if old != self.source:
                self.assertEqual(new.relative_to(destination), old.relative_to(self.root))
                self.assertEqual(digest(new), before[old])
        _, root_document, _ = _load(result["path"])
        refs = [obj["Params"]["FileName"] for obj in root_document["scm"]["Scheme"]["Objects"] if obj["Type"] == 7100]
        self.assertEqual(refs, ["models/child.scm", "models/child.scm"])

    def test_unsafe_source_directive_rejects_before_publication(self):
        _, document, _ = _load(self.source)
        document["scm"]["Scheme"]["Objects"].append({"ID": 9999, "Type": 900, "Name": "Unsafe", "X": 0, "Y": 0,
                                                     "Params": {"Text": '.write "do-not-create.txt" U(out);'}})
        self.change(document)
        before = sorted(self.root.iterdir())
        with self.assertRaisesRegex(EngineError, "not permitted"):
            annotate_circuit(self.source, self.destination)
        self.assertEqual(sorted(self.root.iterdir()), before)

    def test_destination_race_keeps_other_file_and_rolls_back_only_owned_assets(self):
        self.hierarchy()
        real_link = os.link
        def racing_link(source, destination):
            if Path(destination) == self.destination:
                self.destination.write_text("other writer")
                raise FileExistsError("destination appeared")
            return real_link(source, destination)
        with patch.object(annotations.os, "link", side_effect=racing_link):
            with self.assertRaises(FileExistsError):
                annotate_circuit(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "other writer")
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["annotated.scm", "models", "original.scm"])


if __name__ == "__main__":
    unittest.main()
