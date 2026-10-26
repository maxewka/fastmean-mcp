"""Publication boundaries, persistence and bounded numeric artifact access."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.artifacts import ArtifactError, ArtifactStore, MAX_READ_BYTES, MAX_RESPONSE_BYTES, bounded_result


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-artifacts-test-")
        self.base = Path(self.temporary.name)
        self.root = self.base / "runs"
        self.store = ArtifactStore(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def job(self, name="run-1"):
        path = self.root / name
        path.mkdir(parents=True)
        return path

    def table(self, job, count=501):
        path = job / "data.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["t", "U(out)"])
            writer.writerows((index, index / 2) for index in range(count))
        return path

    def test_constructor_and_discovery_do_not_create_output_root(self):
        self.assertFalse(self.root.exists())
        self.assertEqual(self.store.list_runs()["count"], 0)
        self.assertFalse(self.root.exists())

    def test_publish_bounds_response_retains_raw_and_survives_restart(self):
        job = self.job()
        self.table(job)
        (job / "out").write_text("p*" * 25000, encoding="utf-8")
        result = {"working_dir": str(job), "analysis": "ac", "rows": [[i, i] for i in range(100)],
                  "raw_output": "p*" * 25000, "nested": {"text": "x" * 50000}}
        published = self.store.publish(result)
        self.assertEqual(published["run_id"], "run-1")
        self.assertEqual(published["resource_uri"], "fastmean://runs/run-1")
        self.assertNotIn("rows", published)
        self.assertEqual(len(published["preview_rows"]), 8)
        self.assertTrue(published["truncated"])
        self.assertLessEqual(len(json.dumps(published).encode()), MAX_RESPONSE_BYTES)
        full = json.loads((job / "mcp-result-full.json").read_text(encoding="utf-8"))
        self.assertEqual(full, result)
        reopened = ArtifactStore(self.root)
        self.assertEqual(reopened.get_run("run-1"), published)
        self.assertEqual(reopened.read_artifact("run-1", "out"), (job / "out").read_bytes())
        self.assertIn("sha256", next(a for a in published["artifacts"] if a["name"] == "out"))
        self.assertEqual(reopened.list_runs()["count"], 1)

    def test_traversal_unknown_file_and_outside_job_are_rejected(self):
        job = self.job()
        (job / "secret.txt").write_text("not published", encoding="utf-8")
        self.store.publish({"working_dir": str(job)})
        for name in ("../run-1", r"..\run-1", "..", "/absolute", r"C:\absolute", "a/b"):
            with self.subTest(run_id=name), self.assertRaises((ArtifactError, OSError)):
                self.store.get_run(name)
        for name in ("secret.txt", "../secret.txt", r"..\secret.txt"):
            with self.subTest(name=name), self.assertRaises((ArtifactError, OSError)):
                self.store.read_artifact("run-1", name)
        outside = self.base / "outside"
        outside.mkdir()
        with self.assertRaises(ArtifactError): self.store.publish({"working_dir": str(outside)})

    def test_declared_artifact_in_nested_job_directory_is_readable(self):
        job = self.job()
        nested = job / "preview"
        nested.mkdir()
        svg = nested / "custom.svg"
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        result = self.store.publish({"working_dir": str(job), "svg_path": str(svg)})
        entry = next(item for item in result["artifacts"] if item["name"] == "custom.svg")
        self.assertEqual(entry["mime_type"], "image/svg+xml")
        self.assertEqual(self.store.read_artifact("run-1", "custom.svg"), svg.read_bytes())

    def test_nested_declarations_survive_trimming_and_duplicate_basenames(self):
        job = self.job()
        declarations = []
        for index in range(2):
            folder = job / str(index)
            folder.mkdir()
            svg = folder / ("a" * 124 + ".svg")
            svg.write_text(f"<svg><!--{index}--></svg>", encoding="utf-8")
            declarations.append({"large": "x" * 50000, "svg_path": str(svg)})
        result = self.store.publish({"working_dir": str(job), "models": declarations})
        entries = [item for item in result["artifacts"] if item["mime_type"] == "image/svg+xml"]
        self.assertEqual(len(entries), 2)
        self.assertNotEqual(entries[0]["name"], entries[1]["name"])
        for item in entries:
            self.assertLessEqual(len(item["name"]), 128)
            self.assertTrue(self.store.read_artifact("run-1", item["name"]).startswith(b"<svg>"))

    def test_csv_pagination_and_argument_limits(self):
        job = self.job()
        self.table(job)
        self.store.publish({"working_dir": str(job), "analysis": "transient"})
        page = self.store.read_data("run-1", offset=200, limit=200)
        self.assertEqual(page["columns"], ["t", "U(out)"])
        self.assertEqual(page["rows"][0], [200., 100.])
        self.assertEqual(page["rows"][-1], [399., 199.5])
        self.assertEqual(page["next_offset"], 400)
        last = self.store.read_data("run-1", offset=500)
        self.assertEqual(last["rows"], [[500., 250.]])
        self.assertFalse(last["has_more"])
        self.assertIsNone(last["next_offset"])
        for arguments in ({"offset": -1}, {"offset": 1000001}, {"offset": True}, {"limit": 501}, {"limit": 0}):
            with self.subTest(arguments=arguments), self.assertRaises(ArtifactError):
                self.store.read_data("run-1", **arguments)

    def test_nonfinite_or_ragged_csv_is_rejected(self):
        job = self.job()
        path = job / "data.csv"
        for contents in ("t,y\n0,nan\n", "t,y\n0,1,2\n", "t,y\n0,no\n"):
            path.write_text(contents, encoding="utf-8")
            self.store.publish({"working_dir": str(job)})
            with self.subTest(contents=contents), self.assertRaises(ArtifactError):
                self.store.read_data("run-1")

    def test_csv_header_byte_budget_and_bounded_run_discovery(self):
        job = self.job()
        (job / "data.csv").write_text("\u0416" * 5000 + ",y\n0,1\n", encoding="utf-8")
        self.store.publish({"working_dir": str(job), "origin": "\u0416" * 16000})
        with self.assertRaisesRegex(ArtifactError, "header"):
            self.store.read_data("run-1")
        for index in range(1, 12):
            job = self.job(f"extra-{index}")
            self.store.publish({"working_dir": str(job), "origin": "\u0416" * 16000})
        result = self.store.list_runs(limit=100)
        self.assertEqual(result["count"], 12)
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False).encode("utf-8")), MAX_RESPONSE_BYTES)

    def test_symlink_escape_is_not_published_or_read(self):
        job = self.job()
        outside = self.base / "outside.csv"
        outside.write_text("private", encoding="utf-8")
        try: (job / "data.csv").symlink_to(outside)
        except OSError as error: self.skipTest(f"Creating symlinks is unavailable: {error}")
        result = self.store.publish({"working_dir": str(job), "csv_path": str(job / "data.csv")})
        self.assertNotIn("data.csv", {a["name"] for a in result["artifacts"]})
        with self.assertRaises((ArtifactError, OSError)): self.store.read_artifact("run-1", "data.csv")

    def test_large_binary_requires_local_file_and_discovery_ignores_unrecognized_records(self):
        job = self.job()
        (job / "plot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * MAX_READ_BYTES)
        self.store.publish({"working_dir": str(job)})
        with self.assertRaisesRegex(ArtifactError, "8 MiB"):
            self.store.read_artifact("run-1", "plot.png")
        stranger = self.job("unrelated")
        (stranger / "mcp-result.json").write_text('{"run_id":"unrelated"}', encoding="utf-8")
        self.assertEqual(self.store.list_runs()["count"], 1)

    def test_read_only_budget_limits_large_arrays_depth_and_strings(self):
        value = {"objects": [{"name": f"R{i}", "text": "x" * 20000} for i in range(1000)],
                 "layout": {"segments": list(range(10000))}}
        result = bounded_result(value)
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(json.dumps(result).encode()), MAX_RESPONSE_BYTES)
        self.assertEqual(len(value["objects"]), 1000)
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
