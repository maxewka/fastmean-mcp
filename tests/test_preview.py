"""Preview contracts for actual wired SCM data, not a synthetic screenshot."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import warnings
import xml.etree.ElementTree as ET

import yaml

from fastmean_mcp.preview import ORIGIN, PreviewError, render_schematic
from fastmean_mcp.schematic import create_circuit, example_circuit


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-preview-test-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "rc_lowpass.scm"
        create_circuit(example_circuit(), self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def rewrite(self, document):
        self.source.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def test_wired_rc_has_two_ports_valid_images_and_preserves_source(self):
        before = self.source.read_bytes()
        result = render_schematic(self.source, self.root / "previews")
        self.assertEqual(result["origin"], ORIGIN)
        self.assertEqual(result["port_count"], 2)
        self.assertEqual(result["component_count"], 3)
        self.assertGreaterEqual(result["wire_count"], 7)
        self.assertGreaterEqual(result["junction_count"], 2)
        self.assertFalse(result["approximate_wire_routes"])
        self.assertEqual(Path(result["png_path"]).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        svg = Path(result["svg_path"])
        self.assertEqual(ET.parse(svg).getroot().tag, "{http://www.w3.org/2000/svg}svg")
        text = svg.read_text(encoding="utf-8")
        for label in ("R1", "C1", "U1", "in", "out", "1 kΩ", "1 µF", ORIGIN):
            self.assertIn(label, text)
        self.assertEqual(self.source.read_bytes(), before)

    def test_each_render_uses_fresh_files(self):
        first = render_schematic(self.source, self.root / "previews")
        png = Path(first["png_path"])
        digest = hashlib.sha256(png.read_bytes()).hexdigest()
        second = render_schematic(self.source, self.root / "previews")
        self.assertNotEqual(first["png_path"], second["png_path"])
        self.assertNotEqual(first["svg_path"], second["svg_path"])
        self.assertEqual(hashlib.sha256(png.read_bytes()).hexdigest(), digest)

    def test_unsupported_model_is_rejected_before_output_creation(self):
        data = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        data["scm"]["Scheme"]["Objects"].append({"ID": 9999, "Type": 6615,
            "Name": "MOS1", "X": 1500, "Y": 1500, "Rot": 0})
        self.rewrite(data)
        destination = self.root / "must-not-exist"
        with self.assertRaisesRegex(PreviewError, "Unsupported preview model"):
            render_schematic(self.source, destination)
        self.assertFalse(destination.exists())

    def test_unsupported_implicit_bend_is_rejected_instead_of_guessed(self):
        data = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        connector = next(o for o in data["scm"]["Scheme"]["Objects"] if o["Type"] == 300)
        connector["Rot"] = 2
        self.rewrite(data)
        with self.assertRaisesRegex(PreviewError, "implicit native wire bend"):
            render_schematic(self.source, self.root / "must-not-exist")

    def test_parameter_identifier_is_displayed_literally_without_evaluation(self):
        data = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        resistor = next(obj for obj in data["scm"]["Scheme"]["Objects"] if obj["Type"] == 1000)
        resistor["Params"]["R"] = "R0"
        self.rewrite(data)
        before = self.source.read_bytes()
        result = render_schematic(self.source, self.root / "parameters")
        self.assertIn("R0 Ω", Path(result["svg_path"]).read_text(encoding="utf-8"))
        self.assertEqual(self.source.read_bytes(), before)
        for expression in ("R0*2", "__import__('os')", "x;exit"):
            resistor["Params"]["R"] = expression
            self.rewrite(data)
            with self.subTest(expression=expression), self.assertRaises(PreviewError):
                render_schematic(self.source, self.root / "invalid-parameter")
        self.assertFalse((self.root / "invalid-parameter").exists())

    def test_native_crlf_text_is_rendered_as_lines_without_mutating_scm(self):
        data = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        data["scm"]["Scheme"]["Objects"].append({"ID": 900, "Type": 900, "Name": "NOTES", "X": 800, "Y": 1600,
            "Params": {"Text": ".parameter\r\nR0=1000;\r\nExplanation\rFinal line"}})
        self.rewrite(data)
        original = self.source.read_bytes()
        with warnings.catch_warnings(record=True) as messages:
            warnings.simplefilter("always")
            result = render_schematic(self.source, self.root / "crlf-text")
        self.assertFalse(any("Glyph 13" in str(item.message) for item in messages))
        for text in (".parameter", "R0=1000;", "Explanation", "Final line"):
            self.assertIn(text, Path(result["svg_path"]).read_text(encoding="utf-8"))
        self.assertEqual(self.source.read_bytes(), original)

    def test_native_primitives_and_three_pin_block_use_exact_geometry(self):
        from fastmean_mcp.native_geometry import pin_positions
        from fastmean_mcp.preview import _anchor, _model
        data = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        data["scm"]["General"]["Scale"] = 100
        base = {"Y": 1500, "Rot": 0, "FlipH": 0, "FlipV": 0}
        additions = [
            {**base, "ID": 900, "Type": 1101, "Name": "D1", "X": 1600, "Params": {"Ron": .01, "Roff": 1e9, "Uon": .7}},
            {**base, "ID": 901, "Type": 6000, "Name": "Gm", "X": 1900, "Params": {"g": -.04}},
            {**base, "ID": 902, "Type": 6001, "Name": "EV", "X": 2200, "Params": {"k": 2}},
            {**base, "ID": 903, "Type": 6002, "Name": "FI", "X": 2500, "Params": {"h": 100}},
            {**base, "ID": 904, "Type": 7100, "Name": "Q1", "X": 2800, "Params": {
                "FileName": "models/NPN.scm", "Pins": {"Left": ["B"], "Top": ["C"], "Bottom": ["E"]}}}]
        data["scm"]["Scheme"]["Objects"].extend(additions)
        self.rewrite(data)
        model = _model(self.source)
        for source in additions:
            obj = model["objects"][source["ID"]]
            for pin, expected in pin_positions(obj).items():
                self.assertEqual(_anchor(obj, pin), expected)
        before = self.source.read_bytes()
        result = render_schematic(self.source, self.root / "native")
        self.assertEqual(result["component_count"], 8)
        self.assertFalse(result["approximate_wire_routes"])
        svg = Path(result["svg_path"]).read_text(encoding="utf-8")
        for label in ("D1", "Gm", "EV", "FI", "Q1", "NPN", "g=-40 mS", "k=2", "h=100", "Uon=700 mV"):
            self.assertIn(label, svg)
        self.assertEqual(self.source.read_bytes(), before)

    def test_subcircuit_custom_scale_style_and_flips_are_not_guessed(self):
        data = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        block = {"ID": 900, "Type": 7100, "Name": "Q1", "X": 1800, "Y": 1500, "Rot": 0,
                 "Params": {"FileName": "NPN.scm", "Pins": {"Left": ["B"], "Top": ["C"], "Bottom": ["E"]}}}
        data["scm"]["Scheme"]["Objects"].append(block)
        data["scm"]["General"]["Scale"] = 80
        self.rewrite(data)
        destination = self.root / "invalid-style"
        with self.assertRaisesRegex(PreviewError, "Scale100"):
            render_schematic(self.source, destination)
        data["scm"]["General"]["Scale"] = 100
        data["scm"]["SOD"]["FontID"]["lfWeight"] = 700
        self.rewrite(data)
        with self.assertRaisesRegex(PreviewError, "default caption fonts"):
            render_schematic(self.source, destination)
        data["scm"]["SOD"]["FontID"]["lfWeight"] = 400
        block["FlipH"] = 1
        self.rewrite(data)
        with self.assertRaisesRegex(PreviewError, "Flipped"):
            render_schematic(self.source, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
