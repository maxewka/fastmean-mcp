"""Offline regression fixtures for ordered native switching-event samples.

These tables exercise parsing, persistence and measurement, not a solver.
Native converter calculations are checked separately by native integration tests.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp.artifacts import ArtifactStore
from fastmean_mcp.engine import Engine, EngineError
from fastmean_mcp.plotting import PlotError, _decimate, clip_window, measure, prepare_plot
from fastmean_mcp.schematic import create_circuit, example_circuit


class TransientEventTests(unittest.TestCase):
    def test_jump_integral_has_no_artificial_ramp_or_event_duration(self):
        x, y, interpolated = clip_window([0, 1, 1, 1, 2], [0, 0, 100, 2, 2], [0, 2])
        self.assertEqual(x, [0, 1, 1, 1, 2])
        self.assertEqual(y, [0, 0, 100, 2, 2])
        self.assertEqual(interpolated, 0)
        values = measure(x, y, ["mean", "rms", "peak"])
        self.assertEqual(values["mean"], 1)
        self.assertAlmostEqual(values["rms"], math.sqrt(2))
        self.assertEqual(values["peak"], 100)

    def test_exact_boundaries_keep_all_event_states_and_correct_integral_sides(self):
        x, y = [0, 1, 1, 2, 2, 3], [0, 0, 2, 2, -10, -10]
        clipped_x, clipped_y, interpolated = clip_window(x, y, [1, 2])
        self.assertEqual(clipped_x, [1, 1, 2, 2])
        self.assertEqual(clipped_y, [0, 2, 2, -10])
        self.assertEqual(interpolated, 0)
        self.assertEqual(measure(clipped_x, clipped_y, ["mean", "rms", "peak"]),
                         {"mean": 2, "rms": 2, "peak": 10})
        self.assertEqual(clip_window(x, y, [1.25, 1.75]), ([1.25, 1.75], [2, 2], 2))
        self.assertEqual(clip_window(x, y, [.5, 2.5]),
                         ([.5, 1, 1, 2, 2, 2.5], [0, 0, 2, 2, -10, -10], 2))

    def test_zero_duration_extreme_does_not_underflow_finite_duration_rms(self):
        values = measure([0, 1, 1, 1, 2], [0, 0, 1e300, 2, 2], ["mean", "rms", "peak"])
        self.assertEqual(values["mean"], 1)
        self.assertAlmostEqual(values["rms"], math.sqrt(2))
        self.assertEqual(values["peak"], 1e300)

    def test_decimation_retains_jump_pairs_even_when_neither_is_bucket_extremum(self):
        x, y = list(range(30000)), [0.] * 30000
        x[12345] = x[12344]
        y[12344], y[12345] = 1., 2.
        y[12342], y[12348] = -100., 100.
        xs, ys = _decimate(x, y)
        self.assertLessEqual(len(xs), 6000)
        at = xs.index(12344)
        self.assertEqual(xs[at:at + 2], [12344, 12344])
        self.assertEqual(ys[at:at + 2], [1., 2.])
        self.assertEqual((min(ys), max(ys)), (-100., 100.))

    def test_overdense_event_plot_requests_zoom_instead_of_erasing_jumps(self):
        x = [i // 2 for i in range(8000)]
        y = [i % 2 for i in range(8000)]
        with self.assertRaisesRegex(PlotError, "shorter display_window"):
            _decimate(x, y)

    def test_native_completion_storage_and_plot_preserve_ordered_event_rows(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-events-") as temporary:
            root = Path(temporary)
            app = root / "app"
            app.mkdir()
            (app / "Fastmean.exe").write_bytes(b"Offline existence fixture; never executed")
            source = root / "source.scm"
            create_circuit(example_circuit(), source)
            engine = Engine(app, root / "runs")
            job, manifest = engine._job(source, "transient")
            manifest["request"] = {"stop": 2, "step": .1}
            rows = [[0, 0], [1, 0], [1, 2], [2, 2]]
            native = job / "native_data.txt"
            native.write_text("\n".join(" ".join(map(str, row)) for row in rows), encoding="ascii")
            original = native.read_bytes()
            def fixture_render(path, *args):
                path.write_bytes(b"Offline parser test; not a rendered image")
            with patch("fastmean_mcp.engine._plot_file", side_effect=fixture_render), \
                    patch("subprocess.Popen", side_effect=AssertionError("No native solver in offline fixture")):
                result = engine._complete_data(job, manifest, ["U(out)"], "t", 10)
            self.assertEqual(result["rows"], rows)
            self.assertEqual(native.read_bytes(), original)
            self.assertEqual(result["axis_validation"]["repeated_timestamp_rows"], 1)
            with (job / "data.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv.reader(stream))[2:4], [["1.0", "0.0"], ["1.0", "2.0"]])
            saved = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "completed")
            store = ArtifactStore(root / "runs")
            record = store.publish(result)
            table = store.load_native_data(record["run_id"])
            self.assertEqual(list(table["values"][0]), [0, 1, 1, 2])
            self.assertEqual(table["provenance"]["repeated_timestamp_rows"], 1)
            plan = prepare_plot(store, record["run_id"], panels=[{"signal": "U(out)", "metrics": ["mean", "rms"]}])
            self.assertEqual(plan["series"][0], {"x": [0, 1, 1, 2], "y": [0, 0, 2, 2]})
            self.assertEqual(plan["measurements"]["signals"][0]["metrics"]["mean"], 1)
            self.assertIn("zero-duration", plan["measurements"]["method"]["simultaneous_samples"])

    def test_decreasing_td_and_duplicate_ac_are_still_rejected(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-events-invalid-") as temporary:
            root = Path(temporary)
            app = root / "app"
            app.mkdir()
            (app / "Fastmean.exe").write_bytes(b"Offline existence fixture; never executed")
            source = root / "source.scm"
            create_circuit(example_circuit(), source)
            engine = Engine(app, root / "runs")
            for analysis, axis, rows, request in (
                ("transient", "t", [0, 1, .5, 2], {"stop": 2}),
                ("ac", "f", [1, 1, 2], {"fmin": 1, "fmax": 2, "points": 3, "scale": "linear"}),
            ):
                with self.subTest(analysis=analysis):
                    job, manifest = engine._job(source, analysis)
                    manifest["request"] = request
                    (job / "native_data.txt").write_text("\n".join(f"{t} 1" for t in rows), encoding="ascii")
                    with patch("fastmean_mcp.engine._plot_file") as render:
                        with self.assertRaises(EngineError):
                            engine._complete_data(job, manifest, ["U(out)"], axis, 10)
                        render.assert_not_called()


if __name__ == "__main__":
    unittest.main()
