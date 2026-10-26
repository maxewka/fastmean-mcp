"""Offline storage/rendering fixtures; these do not simulate a native solver.

Native provenance records here exercise the saved-run contract only. Actual
FASTMEAN numerical correctness remains covered by the native integration suite.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp.artifacts import ArtifactError, ArtifactStore, MAX_READ_BYTES
from fastmean_mcp.plotting import PlotError, _decimate, clip_window, measure, prepare_plot, render_plot


def publish_numeric_fixture(root: Path, name="numeric-fixture", analysis="transient", rows=None, columns=None, contents=None):
    """Publish a labeled protocol fixture, never a fake executable/solver."""
    job = root / name
    job.mkdir(parents=True)
    columns = columns or (["f", "db(U(out)/U(in))"] if analysis == "ac" else ["t", "U(out)", "I(RL)"])
    rows = rows if rows is not None else [[0, 0, 0], [1, 2, -1], [3, 2, 1]]
    if contents is None:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
        contents = stream.getvalue().encode("utf-8-sig")
    csv_path = job / "data.csv"
    csv_path.write_bytes(contents)
    native = job / "native_data.txt"
    native.write_text("Offline saved-run storage fixture, not a native calculation.\n", encoding="utf-8")
    manifest = {"status": "completed", "analysis": analysis, "columns": columns, "row_count": len(rows),
                "engine": {"name": "FASTMEAN native CLI", "sha256": "0" * 64},
                "fixture": "offline storage/protocol fixture; no solver was executed",
                "request": {"scale": "log"} if analysis == "ac" else {"stop": rows[-1][0], "step": 1},
                "source_sha256": "1" * 64,
                "csv_sha256": hashlib.sha256(contents).hexdigest(),
                "native_data_sha256": hashlib.sha256(native.read_bytes()).hexdigest()}
    (job / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return ArtifactStore(root).publish({"analysis": analysis, "working_dir": str(job),
                                       "csv_path": str(csv_path), "columns": columns, "row_count": len(rows)})


class PlottingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-plot-test-")
        self.root = Path(self.temporary.name) / "runs"
        self.record = publish_numeric_fixture(self.root)
        self.store = ArtifactStore(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_interpolated_window_and_time_weighting_use_adaptive_samples(self):
        x, y, interpolated = clip_window([0., 1., 3.], [0., 2., 2.], [.5, 2.])
        self.assertEqual(x, [.5, 1., 2.])
        self.assertEqual(y, [1., 2., 2.])
        self.assertEqual(interpolated, 2)
        values = measure(x, y, ["mean", "rms", "min", "max", "peak", "peak_to_peak"])
        self.assertAlmostEqual(values["mean"], 11 / 6)
        self.assertAlmostEqual(values["rms"], math.sqrt(3.5))
        self.assertEqual({key: values[key] for key in ("min", "max", "peak", "peak_to_peak")},
                         {"min": 1., "max": 2., "peak": 2., "peak_to_peak": 1.})
        self.assertNotAlmostEqual(values["rms"], math.sqrt(sum(v * v for v in y) / len(y)))

    def test_display_and_measurement_windows_scaling_and_guides_are_independent(self):
        plan = prepare_plot(self.store, self.record["run_id"], panels=[
            {"signal": "I(RL)", "unit": "mA", "scale": 1000, "metrics": ["rms", "peak"], "guides": ["mean"]}],
            display_window=[1, 2], measurement_window=[.5, 2.5], x_unit="ms")
        self.assertEqual(plan["series"][0]["x"], [1., 2.])
        self.assertEqual(plan["spec"]["x_scale"], 1000)
        signal = plan["measurements"]["signals"][0]
        self.assertEqual(signal["sample_count"], 3)
        self.assertEqual(signal["interpolated_boundaries"], 2)
        self.assertEqual(signal["display_metrics"]["peak"], 1000 * signal["metrics"]["peak"])
        self.assertIn("mean", signal["metrics"])
        self.assertEqual(plan["spec"]["measurement_window"], [.5, 2.5])
        self.assertIn("csv_sha256", plan["provenance"])

    def test_invalid_options_fail_before_rendering_or_job_creation(self):
        invalid = [
            {"display_window": [0, 4]}, {"display_window": [2, 1]}, {"measurement_window": [1, 1]},
            {"display_window": [False, 2]}, {"measurement_window": [0, math.inf]},
            {"x_unit": "Hz"}, {"title": "a\nsecond line"}, {"subtitle": "x" * 241},
            {"panels": []}, {"panels": [{"signal": "U(out)"}] * 13},
            {"panels": [{"signal": "U(out)"}, {"signal": "U(out)"}]},
            {"panels": [{"signal": "U(out)*I(RL)"}]},
            {"panels": [{"signal": "U(out)", "path": "C:/outside"}]},
            *({"panels": [{"signal": "U(out)", "scale": value}]} for value in (True, 0, -1, math.nan, math.inf, 1e308)),
            {"panels": [{"signal": "U(out)", "metrics": ["rms", "rms"]}]},
            {"panels": [{"signal": "U(out)", "guides": ["exec"]}]},
            {"panels": [{"signal": "U(out)", "color": "red;import"}]},
            {"panels": [{"signal": "U(out)", "unit": "x" * 25}]},
        ]
        before = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(PlotError):
                prepare_plot(self.store, self.record["run_id"], **options)
        self.assertEqual(sorted(path.relative_to(self.root) for path in self.root.rglob("*")), before)

    def test_ac_keeps_log_axis_and_rejects_time_measurements(self):
        record = publish_numeric_fixture(self.root, "ac-fixture", "ac", rows=[[1, -1], [10, -3], [100, -20]])
        plan = prepare_plot(self.store, record["run_id"], x_unit="kHz")
        self.assertEqual(plan["spec"]["x_axis_scale"], "log")
        self.assertEqual(plan["measurements"]["signals"][0]["metrics"], {})
        with self.assertRaisesRegex(PlotError, "transient"):
            prepare_plot(self.store, record["run_id"], panels=[{"signal": "db(U(out)/U(in))", "metrics": ["rms"]}])

    def test_graphical_decimation_preserves_bucket_peak_and_metric_samples(self):
        x = list(range(30000))
        y = [0.] * len(x)
        y[12347], y[23987] = 1e6, -1e6
        plotted_x, plotted_y = _decimate(x, y)
        self.assertLessEqual(len(plotted_x), 6000)
        self.assertEqual((min(plotted_y), max(plotted_y)), (-1e6, 1e6))
        self.assertEqual((plotted_x[0], plotted_x[-1]), (0, 29999))
        self.assertGreater(measure(x, y, ["rms"])["rms"], 0)

    def test_extreme_but_finite_rms_does_not_overflow_squaring(self):
        self.assertEqual(measure([0, 1], [1e300, 1e300], ["rms"])["rms"], 1e300)

    def test_render_and_persistence_produce_registered_png_svg_spec_metrics(self):
        plan = prepare_plot(self.store, self.record["run_id"], panels=[
            {"signal": "U(out)", "label": "Выход", "unit": "В", "metrics": ["rms", "mean"], "guides": ["mean"]}],
            title="Native exported values", subtitle="Offline rendering test fixture", x_unit="ms")
        job = self.root / "chart-fixture"
        job.mkdir()
        with patch("subprocess.Popen", side_effect=AssertionError("Rendering must not start a process")):
            result = render_plot(plan, job)
        record = self.store.publish(result)
        reopened = ArtifactStore(self.root)
        self.assertEqual(reopened.get_run(record["run_id"]), record)
        self.assertTrue(reopened.read_artifact(record["run_id"], "plot.png").startswith(b"\x89PNG\r\n\x1a\n"))
        svg = reopened.read_artifact(record["run_id"], "plot.svg").decode("utf-8")
        self.assertIn("Выход", svg)
        self.assertIn("no native GUI capture", svg)
        saved_spec = json.loads(reopened.read_artifact(record["run_id"], "chart-spec.json"))
        saved_metrics = json.loads(reopened.read_artifact(record["run_id"], "measurements.json"))
        self.assertEqual(saved_spec, plan["spec"])
        self.assertEqual(saved_metrics, plan["measurements"])
        self.assertLess((job / "plot.png").stat().st_size, 4_000_000)
        with self.assertRaisesRegex(ArtifactError, "original native"):
            prepare_plot(reopened, record["run_id"])

    def test_server_returns_image_without_engine_or_app_discovery(self):
        from fastmean_mcp import server
        with patch.dict("os.environ", {"FASTMEAN_OUTPUT_DIR": str(self.root), "FASTMEAN_APP_DIR": str(self.root / "absent-app")}), \
                patch.object(server, "engine", side_effect=AssertionError("No simulation")), \
                patch.object(server, "app_dir", side_effect=AssertionError("No native installation needed")):
            response = server.fastmean_plot(self.record["run_id"])
            self.assertFalse(response.is_error)
            self.assertTrue(any(item.type == "image" for item in response.content))
            reopened = server.fastmean_get_result(response.structured_content["run_id"])
            self.assertTrue(any(item.type == "image" for item in reopened.content))

    def test_long_accepted_heading_stays_inside_the_rendered_canvas(self):
        from matplotlib.figure import Figure
        plan = prepare_plot(self.store, self.record["run_id"], panels=[{"signal": "U(out)"}],
                            title="W" * 160, subtitle="W" * 240)
        original = Figure.savefig
        bounds = []

        def inspect_saved(figure, path, **kwargs):
            original(figure, path, **kwargs)
            if kwargs.get("format") == "png":
                box = figure._suptitle.get_window_extent(figure.canvas.get_renderer())
                bounds.append((box, figure.bbox.width, figure.bbox.height))

        job = self.root / "long-heading"
        job.mkdir()
        with patch.object(Figure, "savefig", inspect_saved):
            render_plot(plan, job)
        self.assertTrue(bounds)
        for box, width, height in bounds:
            self.assertGreaterEqual(box.x0, 0)
            self.assertLessEqual(box.x1, width)
            self.assertGreaterEqual(box.y0, 0)
            self.assertLessEqual(box.y1, height)


class NativeTableSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-chart-security-")
        self.root = Path(self.temporary.name) / "runs"
        self.record = publish_numeric_fixture(self.root)
        self.store = ArtifactStore(self.root)
        self.csv = self.root / self.record["run_id"] / "data.csv"

    def tearDown(self):
        self.temporary.cleanup()

    def test_csv_and_manifest_same_size_changes_are_rejected(self):
        self.csv.write_bytes(self.csv.read_bytes().replace(b"1,2,-1", b"1,3,-1"))
        with self.assertRaisesRegex(ArtifactError, "SHA256"):
            self.store.load_native_data(self.record["run_id"])
        manifest = self.csv.parent / "manifest.json"
        manifest.write_bytes(manifest.read_bytes().replace(b"completed", b"untrusted"))
        with self.assertRaisesRegex(ArtifactError, "changed"):
            self.store.load_native_data(self.record["run_id"])

    def test_large_table_uses_manifest_hash_without_expanding_public_read_limit(self):
        count = 256
        contents = ("t,U(out)\n" + "".join(f"{index},0." + "0" * 40000 + "1\n" for index in range(count))).encode()
        record = publish_numeric_fixture(self.root, "large-fixture", rows=[[i, 0] for i in range(count)],
                                         columns=["t", "U(out)"], contents=contents)
        artifact = next(item for item in record["artifacts"] if item["name"] == "data.csv")
        self.assertGreater(artifact["size"], MAX_READ_BYTES)
        self.assertNotIn("sha256", artifact)
        with self.assertRaisesRegex(ArtifactError, "8 MiB"):
            self.store.read_artifact(record["run_id"], "data.csv")
        table = self.store.load_native_data(record["run_id"])
        self.assertEqual(table["row_count"], count)
        self.assertEqual(table["values"][0][-1], count - 1)
        large_csv = self.root / record["run_id"] / "data.csv"
        with large_csv.open("r+b") as stream:
            stream.seek(-2, 2)
            stream.write(b"2")
        with self.assertRaisesRegex(ArtifactError, "SHA256"):
            self.store.load_native_data(record["run_id"])

    def test_unpublished_paths_and_non_numeric_or_invalid_axes_are_rejected(self):
        for run_id in ("../numeric-fixture", "C:/outside", "unpublished"):
            with self.subTest(run_id=run_id), self.assertRaises((ArtifactError, OSError)):
                self.store.load_native_data(run_id)
        cases = [([[0, 1], [0, 2]], ["t", "U(out)"]),
                 ([[0, 1], [-1, 2]], ["t", "U(out)"]),
                 ([[0, 1], [1, math.nan]], ["t", "U(out)"]),
                 ([[0, 1, 2], [1, 2, 3]], ["t", "U(out)", "U(out)"])]
        for index, (rows, columns) in enumerate(cases):
            record = publish_numeric_fixture(self.root, f"bad-{index}", rows=rows, columns=columns)
            with self.subTest(rows=rows), self.assertRaises(ArtifactError):
                self.store.load_native_data(record["run_id"])

    def test_linked_csv_cannot_escape_or_reenter_the_registered_job(self):
        target = self.csv.parent / "original.csv"
        self.csv.rename(target)
        try:
            self.csv.symlink_to(target)
        except OSError as error:
            self.skipTest(f"Creating symlinks is unavailable: {error}")
        with self.assertRaisesRegex(ArtifactError, "Linked"):
            self.store.load_native_data(self.record["run_id"])


if __name__ == "__main__":
    unittest.main()
