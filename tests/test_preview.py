"""Preview contracts for actual wired SCM data, not a synthetic screenshot."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
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

    def test_implicit_bend_is_rejected_instead_of_inventing_a_wire_path(self):
        data = yaml.safe_load(self.source.read_text(encoding="utf-8"))
        connector = next(o for o in data["scm"]["Scheme"]["Objects"] if o["Type"] == 300)
        connector["X"] += 10
        connector["Y"] += 10
        self.rewrite(data)
        with self.assertRaisesRegex(PreviewError, "implicit native wire bend"):
            render_schematic(self.source, self.root / "must-not-exist")


if __name__ == "__main__":
    unittest.main()
