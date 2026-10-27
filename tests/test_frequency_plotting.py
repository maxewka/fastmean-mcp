"""Registered native FFT and NumPy-spectrum chart provenance and integrity."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp.artifacts import ArtifactError, ArtifactStore
from fastmean_mcp.plotting import PlotError, prepare_plot, render_plot


def frequency_fixture(root, name, analysis, rows=None, columns=None):
    """Offline persistence fixture only; no native solver output is fabricated."""
    job = root/name
    job.mkdir(parents=True)
    rows = rows if rows is not None else [[0,1],[100,.5],[1000,.1]]
    columns = columns or ["f","amplitude_peak" if analysis=="spectrum" else "MAG(FFT(U(out)))"]
    primary = "spectrum.csv" if analysis=="spectrum" else "data.csv"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(columns)
    writer.writerows(rows)
    contents = stream.getvalue().encode("utf-8-sig")
    (job/primary).write_bytes(contents)
    source = job/("native_transient.csv" if analysis=="spectrum" else "native_data.txt")
    source.write_text("t,U(out)\n0,0\n1,1\n" if analysis=="spectrum" else "0 1\n100 .5\n1000 .1\n",encoding="ascii")
    source_key = "native_transient_csv_sha256" if analysis=="spectrum" else "native_data_sha256"
    manifest = {"analysis":analysis,"status":"completed","row_count":len(rows),"columns":columns,
        "engine":{"name":"FASTMEAN native CLI","sha256":"0"*64},"source_sha256":"1"*64,
        "request":{},"csv_sha256":hashlib.sha256(contents).hexdigest(),
        source_key:hashlib.sha256(source.read_bytes()).hexdigest(),
        "origin":"Do not trust this free-form origin instead of the typed analysis kind",
        "fixture":"offline registry fixture, not a native numerical calculation"}
    (job/"manifest.json").write_text(json.dumps(manifest),encoding="utf8")
    return ArtifactStore(root).publish({"working_dir":str(job),"analysis":analysis,
        "csv_path":str(job/primary),"native_transient_path":str(source) if analysis=="spectrum" else None,
        "columns":columns,"row_count":len(rows)}),job


class FrequencyPlotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fm-frequency-plot-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()/"runs"
        self.store = ArtifactStore(self.root)

    def test_both_frequency_kinds_keep_zero_bin_linear_axes_and_frequency_units(self):
        for analysis in ("native_fft","spectrum"):
            with self.subTest(analysis=analysis):
                record,_ = frequency_fixture(self.root,analysis,analysis)
                plan = prepare_plot(self.store,record["run_id"],x_unit="kHz",display_window=[0,500])
                self.assertTrue(plan["spec"]["frequency_domain"])
                self.assertEqual(plan["spec"]["x_axis_scale"],"linear")
                self.assertEqual(plan["spec"]["x_scale"],.001)
                self.assertEqual(plan["series"][0]["x"][0],0)
                self.assertEqual(plan["measurements"]["signals"][0]["metrics"],{})
                self.assertEqual(plan["provenance"]["axis_ordering"],"strictly_increasing")
                self.assertIn("verified_native_source",plan["provenance"])
                with self.assertRaises(PlotError):
                    prepare_plot(self.store,record["run_id"],x_unit="ms")
                for fields in ({"metrics":["rms"]},{"guides":["mean"]}):
                    with self.assertRaisesRegex(PlotError,"transient"):
                        prepare_plot(self.store,record["run_id"],panels=[{"signal":plan["spec"]["panels"][0]["signal"],**fields}])

    def test_rendered_units_titles_and_provenance_identify_native_and_numpy(self):
        from matplotlib.figure import Figure
        for analysis in ("native_fft","spectrum"):
            record,_ = frequency_fixture(self.root,"render-"+analysis,analysis)
            plan = prepare_plot(self.store,record["run_id"],x_unit="kHz")
            folder = self.root/("chart-"+analysis)
            folder.mkdir()
            captured=[]
            original = Figure.savefig
            def save(figure,path,**arguments):
                captured.append((figure.axes[-1].get_xlabel(),figure.axes[-1].get_xlim()))
                return original(figure,path,**arguments)
            with patch.object(Figure,"savefig",save),patch("subprocess.Popen",side_effect=AssertionError("No new native calculation")):
                result = render_plot(plan,folder)
            svg = Path(result["svg_path"]).read_text("utf8")
            self.assertIn("Frequency (kHz)",svg)
            self.assertTrue(all(label=="Frequency (kHz)" and limits[0]==0 for label,limits in captured))
            if analysis=="spectrum":
                self.assertIn("NumPy rFFT/PSD",svg)
                self.assertIn("not native FFT",svg)
                self.assertIn("NumPy",result["plot_provenance"])
                self.assertFalse(result["provenance"]["native_row_order_preserved"])
            else:
                self.assertIn("Native FASTMEAN FFT",svg)
                self.assertNotIn("NumPy",result["plot_provenance"])
            published = self.store.publish(result)
            with self.assertRaisesRegex(ArtifactError,"original native"):
                prepare_plot(self.store,published["run_id"])

    def test_primary_table_and_native_source_tampering_are_both_rejected(self):
        for analysis in ("native_fft","spectrum"):
            for source_change in (False,True):
                with self.subTest(analysis=analysis,source_change=source_change):
                    record,job = frequency_fixture(self.root,f"tamper-{analysis}-{source_change}",analysis)
                    name = ("native_transient.csv" if analysis=="spectrum" else "native_data.txt") if source_change else ("spectrum.csv" if analysis=="spectrum" else "data.csv")
                    path = job/name
                    raw = path.read_bytes()
                    # Same-size changes cannot hide behind catalog size checks.
                    path.write_bytes(raw.replace(b"1",b"2",1))
                    with self.assertRaisesRegex(ArtifactError,"SHA256"):
                        self.store.load_native_data(record["run_id"])

    def test_spectrum_requires_registered_source_and_never_follows_path_hints(self):
        record,job = frequency_fixture(self.root,"unpublished-source","spectrum")
        result_path = job/"mcp-result.json"
        result = json.loads(result_path.read_text("utf8"))
        result["artifacts"] = [a for a in result["artifacts"] if a["name"]!="native_transient.csv"]
        result["native_transient_path"] = str(self.root.parent/"outside.csv")
        result_path.write_text(json.dumps(result),encoding="utf8")
        with self.assertRaisesRegex(ArtifactError,"not published"):
            self.store.load_native_data(record["run_id"])

    def test_spectrum_paging_selects_spectrum_instead_of_retained_time_samples(self):
        record,_ = frequency_fixture(self.root,"paging","spectrum")
        page = self.store.read_data(record["run_id"],limit=2)
        self.assertEqual(page["csv_artifact"],"spectrum.csv")
        self.assertEqual(page["columns"],["f","amplitude_peak"])
        self.assertEqual(page["rows"],[[0.,1.],[100.,.5]])

    def test_frequency_axes_and_manifest_metadata_are_not_silently_reinterpreted(self):
        cases = [([[0,1],[0,2]],["f","amplitude_peak"]),
                 ([[-1,1],[1,2]],["f","amplitude_peak"]),
                 ([[0,1],[1,2]],["t","amplitude_peak"])]
        for analysis in ("native_fft","spectrum"):
            for index,(rows,columns) in enumerate(cases):
                with self.subTest(analysis=analysis,index=index):
                    record,_ = frequency_fixture(self.root,f"bad-{analysis}-{index}",analysis,rows,columns)
                    with self.assertRaises(ArtifactError):
                        self.store.load_native_data(record["run_id"])
        record,job = frequency_fixture(self.root,"mismatched-manifest","spectrum")
        manifest = job/"manifest.json"
        data = json.loads(manifest.read_text("utf8"))
        data["analysis"] = "native_fft"
        manifest.write_text(json.dumps(data),encoding="utf8")
        # Re-publication models valid JSON with contradictory metadata, not a
        # stale file digest; the analysis contract itself must reject it.
        self.store.publish({"analysis":"spectrum","working_dir":str(job),"csv_path":str(job/"spectrum.csv")})
        with self.assertRaisesRegex(ArtifactError,"completed"):
            self.store.load_native_data(record["run_id"])

    def test_main_csv_uses_manifest_hash_even_if_catalog_hash_was_omitted(self):
        record,job = frequency_fixture(self.root,"manifest-csv-hash","spectrum")
        path = job/"mcp-result.json"
        result = json.loads(path.read_text("utf8"))
        next(a for a in result["artifacts"] if a["name"]=="spectrum.csv").pop("sha256")
        path.write_text(json.dumps(result),encoding="utf8")
        self.assertEqual(self.store.load_native_data(record["run_id"])["row_count"],3)
        self.assertEqual(self.store.read_data(record["run_id"],limit=1)["rows"],[[0.,1.]])


if __name__ == "__main__":
    unittest.main()
