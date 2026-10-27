"""Native property schema checks and source-preserving publication."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp.annotations import annotate_circuit
from fastmean_mcp.element_catalog import get_element
from fastmean_mcp.hierarchy import create_project
from fastmean_mcp.properties import _component_parameters, edit_properties
from fastmean_mcp.schematic import _load, _write_document, create_circuit, example_circuit
from tests.test_hierarchy import project_spec


class PropertyValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fm-properties-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root/"original.scm"
        create_circuit(example_circuit(), self.source)

    def edit(self, **arguments):
        folder = self.root/f"edit-{len(list(self.root.iterdir()))}"
        folder.mkdir()
        return edit_properties(self.source, folder/"circuit.scm", **arguments)

    def test_literal_parameter_and_source_bounds_reject_before_publication(self):
        original = self.source.read_bytes()
        for updates in ({"R1":{"R":-1}}, {"C1":{"C":0}}, {"U1":{"ST":999}},
                        {"U1":{"ST":True}}, {"U1":{"AC":{"F":0}}},
                        {"U1":{"PULSE":{"K":101}}}, {"U1":{"AC":{"NP":0}}},
                        {"U1":{"USER":{"ScaleT":0}}}):
            with self.subTest(updates=updates),self.assertRaises(ValueError):
                self.edit(updates=updates)
        self.assertEqual(self.source.read_bytes(),original)
        self.assertFalse(list(self.root.glob("edit-*/*.scm")))

    def test_catalog_structural_enums_arrays_and_geometry_are_checked(self):
        for kind, bad in (("AND", {"N":3,"InpInv":[0,0,0]}),
                          ("SUM", {"N":3,"k":[1,1,1]}),
                          ("DFF", {"HasRS":1}), ("JK", {"HasRS":1}),
                          ("MOSFET", {"Model":4}), ("AND", {"InpInv":[0,2]}),
                          ("SUM", {"k":[1]}), ("AND", {"Uhigh":"level"})):
            entry = get_element(kind)
            obj = {"Type":entry["typeid"],"Name":"X1","Params":entry["defaults"]}
            with self.subTest(kind=kind,bad=bad),self.assertRaises(ValueError):
                _component_parameters(obj,bad)
        obj = {"Type":7000,"Name":"SUM1","Params":get_element("SUM")["defaults"]}
        self.assertEqual(_component_parameters(obj,{"k":[2,3]})["k"],[2,3])

    def test_unknown_native_electrical_expressions_are_preserved_without_evaluation(self):
        annotated = self.root/"parameters.scm"
        annotate_circuit(self.source,annotated,parameters={"RBASE":1000},bindings={"R1":"RBASE"})
        self.source = annotated
        result = self.edit(updates={"C1":{"IC":.7},"R1":{"R":"RBASE*2"}})
        _,document,_ = _load(result["path"])
        objects = {obj["Name"]:obj for obj in document["scm"]["Scheme"]["Objects"]}
        self.assertEqual(objects["R1"]["Params"]["R"],"RBASE*2")
        self.assertEqual(objects["C1"]["Params"]["IC"],.7)

    def test_source_mode_tables_and_omitted_fields_use_the_waveform_contract(self):
        _,before,_ = _load(self.source)
        source = next(obj for obj in before["scm"]["Scheme"]["Objects"] if obj["Name"]=="U1")
        result = self.edit(updates={"U1":{"ST":5,"USER":{"U":{"x":[0,.001,.002],"y":[0,2,0]},"PER":True}}})
        _,after,_ = _load(result["path"])
        changed = next(obj for obj in after["scm"]["Scheme"]["Objects"] if obj["Name"]=="U1")
        self.assertEqual(changed["Params"]["ST"],5)
        self.assertEqual(changed["Params"]["USER"]["PER"],1)
        self.assertEqual(changed["Params"]["AC"],source["Params"]["AC"])
        for points in ({"x":[0,0],"y":[1,2]}, {"x":[0,1],"y":["invalidExpression",2]}):
            with self.subTest(points=points),self.assertRaises(ValueError):
                self.edit(updates={"U1":{"USER":{"U":points}}})

    def test_native_source_delay_validation_is_mode_aware_for_voltage_and_current(self):
        from fastmean_mcp.source_waveforms import MODES, source_parameters
        for current in (False, True):
            original = source_parameters(1, None, current=current)
            obj = {"Type":3010 if current else 2010,"Name":"SOURCE","Params":original}
            for kind, (mode, section) in MODES.items():
                with self.subTest(current=current,kind=kind):
                    with patch("fastmean_mcp.source_waveforms.source_parameters",wraps=source_parameters) as validate:
                        changed = _component_parameters(obj,{"ST":mode,section:{"Delay":.25}})
                    self.assertEqual(changed[section]["Delay"],.25)
                    waveform = validate.call_args.args[1]
                    expected = "delay_periods" if kind in {"sine","pulse","triangle"} else "delay"
                    self.assertEqual(waveform[expected],.25)
                    self.assertNotIn("delay" if kind in {"sine","pulse","triangle"} else "delay_periods",waveform)

    def test_native_radio_pulse_duration_accepts_fractional_periods(self):
        result = self.edit(updates={"U1":{"AC":{"FD":1,"NP":1.5}}})
        _, document, _ = _load(result["path"])
        source = next(obj for obj in document["scm"]["Scheme"]["Objects"] if obj["Name"]=="U1")
        self.assertEqual(source["Params"]["AC"]["NP"],1.5)

    def test_saved_analysis_integer_enums_ranges_and_interval_counts_are_checked(self):
        bad = [
            {"FD":{"StartFreq":1000,"EndFreq":10}}, {"FD":{"NumPts":0}}, {"FD":{"ScaleX":999}},
            {"TD":{"IPNum":1.5}}, {"TD":{"IPNum":2}}, {"TD":{"IP":[{"TimeStep":0}]}},
            {"TD":{"IP":[{"EndTime":-1}]}}, {"TD":{"IP":[{"EPS":2}]}},
            {"TD":{"FFT":2}}, {"TD":{"FFTD":{"PointNum":1}}},
            {"TD":{"FFTD":{"window_type":99}}}, {"TD":{"FFTD":{"StartVal":.02,"EndVal":.01}}},
            {"FD":{"PSD":[{"NumPts":1}]}}, {"TD":{"ParamSweep":1}},
            {"DCOP":{"Digit":0}}, {"AOD":{"AvailMemory":-1}},
        ]
        for analysis in bad:
            with self.subTest(analysis=analysis),self.assertRaises(ValueError):
                self.edit(analysis=analysis)

    def test_saved_graph_formulas_empty_traces_and_math_settings_remain_supported(self):
        result = self.edit(analysis={"FD":{"StartFreq":"cutoff/100","EndFreq":"cutoff*100","Expressions":[]},
            "TD":{"IP":[{"EndTime":"duration","TimeStep":"duration/1000","EPS":"1u"}]}})
        _,document,_ = _load(result["path"])
        self.assertEqual(document["scm"]["FD"]["Expressions"],[])
        self.assertEqual(document["scm"]["FD"]["StartFreq"],"cutoff/100")
        self.assertEqual(document["scm"]["TD"]["IP"][0]["TimeStep"],"duration/1000")
        result = self.edit(analysis={"FD":{"Expressions":[{"plot":2,"x":"f","y":"MAG(U(out))"}]}})
        _,document,_ = _load(result["path"])
        self.assertEqual(document["scm"]["FD"]["Expressions"],[{"plot":2,"x":"f","y":"MAG(U(out))"}])

    def test_interval_row_patches_keep_omitted_fields_from_the_same_row(self):
        _,document,_ = _load(self.source)
        first = document["scm"]["TD"]["IP"][0]
        second = {**first,"StartTime":.005,"EndTime":.01,"TimeStep":2e-5}
        document["scm"]["TD"]["IP"] = [first,second]
        document["scm"]["TD"]["IPNum"] = 2
        _write_document(document,self.source,overwrite=True)
        result = self.edit(analysis={"TD":{"IP":[{}, {"EPS":"1u"}]}})
        _,after,_ = _load(result["path"])
        observed = after["scm"]["TD"]["IP"][1]
        self.assertEqual((observed["StartTime"],observed["EndTime"],observed["TimeStep"]),(.005,.01,2e-5))
        self.assertEqual(observed["EPS"],1e-6)

    def test_existing_si_and_unknown_point_count_expressions_are_not_rejected(self):
        _,document,_ = _load(self.source)
        document["scm"]["TD"]["IP"][0]["NumPts"] = "1.5к"
        document["scm"]["FD"]["NumPts"] = "frequency_points"
        _write_document(document,self.source,overwrite=True)
        result = self.edit(analysis={"TD":{"IP":[{"EPS":"1u"}]},"FD":{"ScaleX":1}})
        _,after,_ = _load(result["path"])
        self.assertEqual(after["scm"]["TD"]["IP"][0]["NumPts"],"1.5к")
        self.assertEqual(after["scm"]["FD"]["NumPts"],"frequency_points")

    def test_styles_accept_native_colors_and_font_names_but_not_numeric_expressions(self):
        result = self.edit(analysis={"SOD":{"ColorID":"000000FF","FontID":{"lfFaceName":"Times New Roman","lfCharSet":204}}})
        _,document,_ = _load(result["path"])
        self.assertEqual(document["scm"]["SOD"]["FontID"]["lfFaceName"],"Times New Roman")
        for style in ({"ColorID":"banana"}, {"FontID":{"lfHeight":1e10}}, {"FontID":{"lfCharSet":"sin(t)"}}):
            with self.subTest(style=style),self.assertRaises(ValueError):
                self.edit(analysis={"SOD":style})

    def test_definitions_reject_reserved_duplicate_and_existing_names(self):
        annotated = self.root/"parameters.scm"
        annotate_circuit(self.source,annotated,parameters={"RBASE":1000})
        self.source = annotated
        for definitions in ([{"name":"t","expression":1}], [{"name":"U","arguments":["x"],"expression":"x"}],
            [{"name":"RBASE","expression":2}], [{"name":"R1","expression":2}], [{"name":"last","expression":2}],
            [{"name":"gain","expression":1},{"name":"gain","expression":2}],
            [{"name":"gain","expression":"1;exit;"}]):
            with self.subTest(definitions=definitions),self.assertRaises(ValueError):
                self.edit(definitions=definitions)

    def test_actual_multiline_definition_block_sets_canvas_bounds_and_retains_source(self):
        original = self.source.read_bytes()
        definitions = [{"name":f"gain{index}","expression":index+1} for index in range(64)]
        result = self.edit(definitions=definitions)
        _,document,_ = _load(result["path"])
        note = next(obj for obj in document["scm"]["Scheme"]["Objects"] if obj["Type"]==900)
        self.assertEqual(len(note["Params"]["Text"].splitlines()),65)
        self.assertGreaterEqual(document["scm"]["General"]["SHeight"],note["Y"]+22*65+120)
        self.assertEqual(result["text_count"],1)
        self.assertEqual(result["definition_count"],64)
        self.assertEqual(self.source.read_bytes(),original)

    def test_portable_child_models_remain_unchanged_and_late_failure_rolls_back(self):
        made = create_project(project_spec(),self.root/"project")
        self.source = Path(made["path"])
        original = {p:p.read_bytes() for p in self.source.parent.rglob("*.scm")}
        result = self.edit(updates={"RL":{"R":5000}})
        _,document,_ = _load(result["path"])
        copied_models = [Path(path) for path in result["dependency_paths"]]
        self.assertEqual(sorted(p.read_bytes() for p in copied_models),sorted(content for p,content in original.items() if p!=self.source))
        destination = self.root/"rollback"
        destination.mkdir()
        sentinel = destination/"sentinel.txt"
        sentinel.write_text("unrelated",encoding="utf8")
        import os
        real_link = os.link
        calls = 0
        def fail_after_one(src,dst):
            nonlocal calls
            calls += 1
            if calls==2:
                raise OSError("injected publication failure")
            return real_link(src,dst)
        with patch("fastmean_mcp.annotations.os.link",side_effect=fail_after_one):
            with self.assertRaises(OSError):
                edit_properties(self.source,destination/"circuit.scm",updates={"RL":{"R":6000}})
        self.assertEqual(list(destination.iterdir()),[sentinel])
        self.assertEqual({p:p.read_bytes() for p in original},original)


if __name__ == "__main__":
    unittest.main()
