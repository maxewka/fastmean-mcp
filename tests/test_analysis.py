"""Typed command boundaries and calibrated transforms; native proof is separate."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from fastmean_mcp.analysis import (command_prelude, configure_initial_conditions,
    parameter_target, run_summary, spectrum_from_rows, validate_initial_conditions)
from fastmean_mcp.engine import Engine, EngineError, validate_signal
from fastmean_mcp.hierarchy import create_project
from fastmean_mcp.schematic import _load, _write_document, create_circuit, example_circuit
from tests.test_hierarchy import project_spec


class AnalysisCommandTests(unittest.TestCase):
    def test_definitions_are_individual_math_records_and_preserve_order(self):
        definitions = [{"name":"period","expression":"1/VIN.F"},
            {"name":"power","arguments":["voltage","current"],"expression":"voltage*current"},
            {"name":"constant","arguments":[],"expression":3}]
        original = copy.deepcopy(definitions)
        script, record = command_prelude(definitions,{"SUB.R1.R":"2k","load":"period*2"})
        self.assertIn("define power(voltage,current)=voltage*current;\n",script)
        self.assertIn("define constant()=3;\n",script)
        self.assertTrue(script.endswith("set load=period*2;\n"))
        self.assertEqual(record["overrides"]["SUB.R1.R"],"2k")
        self.assertEqual(definitions,original)
        self.assertEqual(validate_signal("constant()+U(SUB.A.OUT)"),"constant()+U(SUB.A.OUT)")

    def test_commands_paths_and_separators_never_enter_math_records(self):
        for expression in ('1;exit;', '"file.scm"', 'x\nset y=1', 'open(x)',
                           'x%ignored', 'x=1', 'x\\path', 'x[0]'):
            with self.subTest(expression=expression),self.assertRaises(EngineError):
                command_prelude([{"name":"gain","expression":expression}])
        for target in ('A..R','../R','R;exit','R.FileName="x"','A.open.R','R\nset'):
            with self.subTest(target=target),self.assertRaises(EngineError):
                parameter_target(target)
        for definitions in ([{"name":"t","expression":1}],
            [{"name":"gain","expression":1,"extra":"script"}],
            [{"name":"gain","arguments":["x","x"],"expression":"x"}],
            [{"name":"gain","expression":True}],
            [{"name":"gain","expression":1}]*65):
            with self.subTest(definitions=definitions),self.assertRaises(EngineError):
                command_prelude(definitions)

    def test_initial_conditions_accept_only_modes_or_finite_component_values(self):
        self.assertEqual(validate_initial_conditions({"AMP.C1":"3m"}),{"AMP.C1":.003})
        for value in ('file',{},[],{"C1":float('nan')},{"../C1":0},{"C1":True}):
            with self.subTest(value=value),self.assertRaises(EngineError):
                validate_initial_conditions(value)


class AnalysisJobTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fm-analysis-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        app = self.root/"app"
        app.mkdir()
        (app/"Fastmean.exe").write_bytes(b"unit fixture; never execute")
        self.engine = Engine(app,self.root/"jobs")
        self.source = self.root/"source.scm"
        self.spec = example_circuit()
        self.spec["components"][0].pop("waveform",None)
        create_circuit(self.spec,self.source)

    def test_requested_ic_changes_only_packaged_model_and_retains_source_hash(self):
        project = project_spec()
        project["models"]["RES"]["circuit"]["components"][0] = {
            "kind":"C","name":"C1","nodes":["p","n"],"value":"1u"}
        made = create_project(project,self.root/"project")
        source = Path(made["path"])
        original = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.parent.rglob('*.scm')}
        job,manifest = self.engine._job(source,"transient")
        configure_initial_conditions(self.engine,job,manifest,{"FIRST.A.C1":.7})
        changed = []
        for asset in manifest["source_models"]:
            _,document,_ = _load(Path(asset["private_path"]))
            changed.extend(o["Params"]["IC"] for o in document["scm"]["Scheme"]["Objects"]
                if o.get("Name")=="C1")
        self.assertIn(.7,changed)
        self.assertEqual(changed.count(.7),1)
        self.assertIn(0,changed)
        self.assertEqual(original,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in original})

    def test_non_dc_source_requires_explicit_bias_before_any_native_launch(self):
        spec = example_circuit()
        create_circuit(spec,self.root/"sine.scm")
        with patch.object(self.engine,"_execute") as execute:
            with self.assertRaisesRegex(EngineError,"explicit source_values"):
                self.engine.run_dc(self.root/"sine.scm",["U(out)"])
            execute.assert_not_called()

    def test_dc_private_copy_removes_source_ramps_and_returns_only_native_row(self):
        original = self.source.read_bytes()
        def native(job,manifest,script,cancelled):
            _,document,_ = _load(job/"circuit.scm")
            self.assertEqual(document["scm"]["TD"]["SVD"]["IC"],2)
            source = next(o for o in document["scm"]["Scheme"]["Objects"] if o["Type"]==2010)
            self.assertEqual(source["Params"]["DC"]["TFR"],0)
            self.assertEqual(source["Params"]["DC"]["Delay"],0)
            self.assertIn("sim tmax=0",script)
            (job/"native_data.txt").write_text("0 2\n",encoding="ascii")
        with patch.object(self.engine,"_execute",side_effect=native):
            result = self.engine.run_dc(self.source,["U(out)"])
        self.assertEqual(result["values"],{"U(out)":2.})
        self.assertIn("Native DC operating-point",result["dc_method"])
        self.assertEqual(self.source.read_bytes(),original)

    def test_transient_filter_and_state_export_are_generated_not_caller_scripts(self):
        def native(job,manifest,script,cancelled):
            self.assertIn("write after 0.00050000000000000001;",script)
            self.assertIn("sv2scheme=yes;",script)
            self.assertIn('save_as "final_state.scm";',script)
            (job/"native_data.txt").write_text("0.000501 1\n0.001 2\n",encoding="ascii")
            shutil_source = job/"circuit.scm"
            (job/"final_state.scm").write_bytes(shutil_source.read_bytes())
        with patch.object(self.engine,"_execute",side_effect=native):
            result = self.engine.run_transient(self.source,["U(out)"],stop=.001,
                step=1e-5,sample_after=.0005,initial_conditions="zero",state2scheme=True)
        self.assertTrue(Path(result["final_state_path"]).is_file())
        self.assertEqual(result["axis_validation"]["native_write_after"],.0005)
        self.assertEqual(result["rows"][0][0],.000501)

    def test_sweep_retains_independent_native_curve_tables_and_last_row_summary(self):
        calls,paths = [],[]
        def ac(path,**arguments):
            paths.append(Path(path))
            calls.append(arguments)
            folder = self.root/f"curve{len(calls)}"
            folder.mkdir()
            (folder/"data.csv").write_text("f,U(out)\n10,.5\n100,.2\n",encoding="utf8")
            (folder/"manifest.json").write_text("{}",encoding="utf8")
            return {"csv_path":str(folder/"data.csv"),"manifest_path":str(folder/"manifest.json"),
                "working_dir":str(folder),"columns":["f","U(out)"],"row_count":2,"rows":[[10,.5],[100,.2]]}
        with patch.object(self.engine,"run_ac",side_effect=ac):
            result = self.engine.run_parameter_sweep(self.source,"R1.R",[1000,2000],
                analysis="ac",settings={"fmin":10,"fmax":100,"points":2},overrides={"gain":3})
        self.assertEqual([c["overrides"] for c in calls],[{"gain":3,"R1.R":1000.},{"gain":3,"R1.R":2000.}])
        self.assertEqual(result["rows"],[[1000.,.2],[2000.,.2]])
        self.assertEqual(paths,[Path(result["working_dir"])/"circuit.scm"]*2)
        self.assertTrue(all(Path(c["csv_path"]).is_relative_to(Path(result["working_dir"])) for c in result["curves"]))

    def test_native_harmonic_postprocessing_requires_independent_time_coverage(self):
        def native(job,manifest,script,cancelled):
            self.assertIn('write "native_transient.txt" t U(out);',script)
            (job/"native_data.txt").write_text("0 0 1 1 -90\n",encoding="ascii")
            (job/"native_transient.txt").write_text("0 0\n.01 1\n",encoding="ascii")
        with patch.object(self.engine,"_execute",side_effect=native):
            result = self.engine.run_harmonics(self.source,"U(out)",[1000],[.005,.01])
        self.assertEqual(result["harmonics"],[{"frequency_hz":1000.,"real":0.,"imaginary":1.,"magnitude":1.,"phase_degrees":-90.}])
        self.assertTrue(result["axis_validation"]["coverage_verified"])
        self.assertEqual(result["transient_row_count"],2)

    def test_native_summary_wraps_ordinary_expressions_and_keeps_a_separate_time_axis(self):
        def native(job,manifest,script,cancelled):
            self.assertIn("last(rms(U(out)))",script)
            self.assertIn('write "native_coverage.txt" t;',script)
            (job/"native_data.txt").write_text("0 .707\n",encoding="ascii")
            (job/"native_coverage.txt").write_text("0\n.01\n",encoding="ascii")
        with patch.object(self.engine,"_execute",side_effect=native):
            result = run_summary(self.engine,self.source,["rms(U(out))"])
        self.assertEqual(result["values"],{"rms(U(out))":.707})
        self.assertEqual(result["columns"][0],"evaluation_index")
        self.assertTrue(result["axis_validation"]["coverage_verified"])

    def test_postprocessing_sweep_routes_to_summary_instead_of_incomplete_td(self):
        calls = []
        def summary(engine,path,signals,**arguments):
            calls.append(arguments)
            folder = self.root/f"summary{len(calls)}"
            folder.mkdir()
            (folder/"data.csv").write_text("evaluation_index,last(rms(U(out)))\n0,.707\n",encoding="utf8")
            (folder/"manifest.json").write_text("{}",encoding="utf8")
            return {"csv_path":str(folder/"data.csv"),"manifest_path":str(folder/"manifest.json"),
                "working_dir":str(folder),"columns":["evaluation_index",signals[0]],"row_count":1,"rows":[[0,.707]]}
        with patch("fastmean_mcp.analysis.run_summary",side_effect=summary),patch.object(self.engine,"run_transient") as transient:
            result = self.engine.run_parameter_sweep(self.source,"R1.R",[1000,2000],
                signals=["last(rms(U(out)))"],settings={"stop":.01,"step":1e-6})
            transient.assert_not_called()
        self.assertEqual(len(calls),2)
        self.assertEqual(result["rows"],[[1000.,.707],[2000.,.707]])

    def test_native_fft_requires_its_own_domain_and_validates_exported_bins(self):
        with self.assertRaisesRegex(EngineError,"separate request"):
            run_summary(self.engine,self.source,["MAG(FFT(U(out)))","rms(U(out))"])
        def native(job,manifest,script,cancelled):
            _,document,_ = _load(job/"circuit.scm")
            self.assertEqual(document["scm"]["TD"]["FFT"],1)
            self.assertIn('write "native_data.txt" f',script)
            (job/"native_data.txt").write_text("0 0\n250 1\n500 0\n",encoding="ascii")
            (job/"native_coverage.txt").write_text("0\n.01\n",encoding="ascii")
        with patch.object(self.engine,"_execute",side_effect=native):
            result = run_summary(self.engine,self.source,["MAG(FFT(U(out)))"],
                fft={"window":[.005,.009],"points":16,"harmonics":2})
        self.assertEqual(result["analysis"],"native_fft")
        self.assertAlmostEqual(result["frequency_resolution_hz"],250)
        self.assertEqual(result["row_count"],3)


class SpectrumCalibrationTests(unittest.TestCase):
    def test_peak_and_psd_scaling_for_dc_sine_and_nyquist(self):
        points, rate = 1024,1024.
        time = np.arange(points+1)/rate
        signal = 2+3*np.cos(2*np.pi*64*time)+.5*np.cos(np.pi*rate*time)
        rows,sampling = spectrum_from_rows(np.column_stack((time,signal)).tolist(),[0,1],points,"rectangular")
        data = np.asarray(rows)
        self.assertAlmostEqual(data[0,1],2.,delta=1e-12)
        self.assertAlmostEqual(data[64,1],3.,delta=1e-12)
        self.assertAlmostEqual(data[-1,1],.5,delta=1e-12)
        self.assertAlmostEqual(data[:,5].sum()*sampling["frequency_resolution_hz"],4+9/2+.25,delta=1e-11)

    def test_repeated_native_event_uses_right_limit_and_retains_finite_bins(self):
        rows,sampling = spectrum_from_rows([[0,0],[.5,0],[.5,1],[1,1]],[0,1],16,"hann")
        self.assertTrue(np.isfinite(rows).all())
        self.assertEqual(sampling["native_repeated_timestamp_rows"],1)
        for points,window in ((15,"hann"),(32,"unsupported"),(True,"hann")):
            with self.subTest(points=points,window=window),self.assertRaises(EngineError):
                spectrum_from_rows([[0,0],[1,1]],[0,1],points,window)

    def test_switching_edge_preserves_both_limits_instead_of_creating_a_ramp(self):
        rows,_ = spectrum_from_rows([[0,0],[.5,0],[.5,1],[1,1]],[0,1],16,"rectangular")
        self.assertAlmostEqual(rows[0][1],.5,delta=1e-12)
        self.assertAlmostEqual(sum(row[5] for row in rows),.5,delta=1e-12)


if __name__ == "__main__":
    unittest.main()
