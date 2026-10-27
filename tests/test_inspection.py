"""Critical fields, complete pagination, nested large values and snapshot reads."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp.inspection import inspect_circuit
from fastmean_mcp.schematic import SchemeError, _load, _write_document, create_circuit, example_circuit

REPO = Path(__file__).resolve().parents[1]


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root/"source.scm"
        create_circuit(example_circuit(), self.source)

    def test_amplifier_keeps_parameters_ports_and_all_saved_formulas(self):
        source = REPO/"examples/four-bjt-amplifier/Amplifier_4BJT.scm"
        for include in (False, True):
            with self.subTest(include_objects=include):
                result = inspect_circuit(source, include)
                self.assertEqual(set(result["ports"]),{"IN","OUT","VPP","VNN"})
                self.assertEqual(len(result["analysis"]["TD"]["Expressions"]),5)
                self.assertEqual(result["analysis"]["FD"]["Expressions"],[])
                self.assertEqual(len(result["root_parameters"]["parameters"]),7)
                self.assertEqual(len(result["texts"]),11)
                self.assertEqual(len(result["components"]),result["component_count"])
                self.assertEqual(sum(len(p["bindings"]) for p in result["root_parameters"]["parameters"]),12)
                self.assertLessEqual(len(json.dumps(result,ensure_ascii=False).encode()),128*1024)
                self.assertNotIn("parameters",result["components"][0])

    def test_complete_object_and_wire_pages_can_be_reassembled(self):
        _, document, _ = _load(self.source)
        for section, expected in (("objects",document["scm"]["Scheme"]["Objects"]),
                                  ("wires",document["scm"]["Scheme"]["Wires"])):
            offset, items, digest = 0, [], None
            while True:
                result = inspect_circuit(self.source, section=section, limit=2, offset=offset,
                                         expected_source_sha256=digest)
                digest = result["source_sha256"]
                items.extend(result["data"])
                page = result["page"]
                self.assertEqual(page["returned_count"],len(result["data"]))
                if not page["has_more"]:
                    break
                self.assertGreater(page["next_offset"],offset)
                offset = page["next_offset"]
            self.assertEqual(items,expected)

    def test_large_native_object_is_readable_by_property_without_recursive_cuts(self):
        _, document, _ = _load(self.source)
        objects = document["scm"]["Scheme"]["Objects"]
        index = next(i for i,o in enumerate(objects) if o["Type"] == 2010)
        waveform = list(range(25000))
        objects[index]["Params"]["USER"]["U"]["x"] = waveform
        _write_document(document,self.source,overwrite=True)
        summary = inspect_circuit(self.source,True)
        self.assertIn("analysis",summary)
        self.assertIn("ports",summary)
        with self.assertRaisesRegex(SchemeError,"detail_path"):
            inspect_circuit(self.source,section="objects",offset=index,limit=1)
        actual = []
        for offset in range(0,len(waveform),1000):
            result=inspect_circuit(self.source,section="objects",offset=offset,limit=1000,
                detail_path=[index,"Params","USER","U","x"])
            actual.extend(result["data"])
        self.assertEqual(actual,waveform)

    def test_text_chunks_keep_unicode_and_comment_characters(self):
        _, document, _ = _load(self.source)
        text='Русский текст; % комментарий\r\n'*60
        document["scm"]["Scheme"]["Objects"].append({"ID":999,"Type":900,"Name":"NOTE","Params":{"Text":text}})
        _write_document(document,self.source,overwrite=True)
        chunks=[]
        offset=0
        while True:
            result=inspect_circuit(self.source,section="texts",detail_path=[0,"Params","Text"],offset=offset,limit=137)
            chunks.append(result["data"])
            if not result["page"]["has_more"]:break
            offset=result["page"]["next_offset"]
        self.assertEqual(''.join(chunks),text)

    def test_changed_source_and_invalid_paths_do_not_create_output_files(self):
        digest=inspect_circuit(self.source)["source_sha256"]
        self.source.write_bytes(self.source.read_bytes()+b"\r\n")
        with self.assertRaisesRegex(SchemeError,"Source changed"):
            inspect_circuit(self.source,expected_source_sha256=digest)
        for path in ([False],["missing"],[0,"Params","../../outside"]):
            with self.subTest(path=path),self.assertRaises(SchemeError):
                inspect_circuit(self.source,section="objects",detail_path=path)
        self.assertEqual({p.name for p in self.root.iterdir()},{"source.scm"})


if __name__ == "__main__":unittest.main()
