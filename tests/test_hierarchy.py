"""Portable hierarchy, atomic publication and native nested-model regressions."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp import hierarchy
from fastmean_mcp.hierarchy import create_project, inspect_definition
from fastmean_mcp.schematic import SchemeError, create_circuit, example_circuit, read_scheme


def project_spec() -> dict:
    resistor = {"pins": {"Left": ["P"], "Right": ["N"]},
                "circuit": {"components": [{"kind": "R", "name": "R1", "nodes": ["p", "n"], "value": "1k"}],
                            "ports": {"P": "p", "N": "n"}}}
    pair = {"pins": {"Left": ["P"], "Right": ["N"]},
            "circuit": {"components": [
                {"kind": "X", "name": "A", "model": "RES", "connections": {"P": "p", "N": "middle"}},
                {"kind": "X", "name": "B", "model": "RES", "connections": {"P": "middle", "N": "n"}}],
                "ports": {"P": "p", "N": "n"}}}
    return {"name": "Два экземпляра вложенной подсхемы", "models": {"PAIR": pair, "RES": resistor},
            "circuit": {"components": [
                {"kind": "U", "name": "U1", "nodes": ["input", "0"], "value": 1,
                 "waveform": {"kind": "sine", "amplitude": 1, "frequency": 1000}},
                {"kind": "X", "name": "FIRST", "model": "PAIR", "connections": {"P": "input", "N": "junction"}},
                {"kind": "X", "name": "SECOND", "model": "PAIR", "connections": {"P": "junction", "N": "output"}},
                {"kind": "R", "name": "RL", "nodes": ["output", "0"], "value": "4k"}],
                "ports": {"IN": "input", "OUT": "output"}, "analysis": {"input": "IN", "output": "OUT"}}}


def fake_author(spec, path, *, model_context, subcircuit, interface_pins=None):
    """A small writer for testing transaction boundaries independently of layout."""
    Path(path).write_text(json.dumps({"spec": spec, "context": model_context, "subcircuit": subcircuit}), encoding="utf-8")
    return {"warnings": [], "ports": spec.get("ports", {}),
            "objects": [{"Type": 400, "Name": name} for name in spec.get("ports", {})]}


def asymmetric_pin_spec() -> dict:
    # JSON ports intentionally uses B,C,E while the native side order is B,E,C.
    # A native slot swap would ground C and leave the output undriven.
    return {"models": {"DEVICE": {
        "pins": {"Left": ["B"], "Top": ["E"], "Bottom": ["C"]},
        "circuit": {"components": [
            {"kind": "R", "name": "RBC", "nodes": ["b", "c"], "value": "1k"},
            {"kind": "R", "name": "RCE", "nodes": ["c", "e"], "value": "2k"}],
            "ports": {"B": "b", "C": "c", "E": "e"}}}},
        "circuit": {"components": [
            {"kind": "U", "name": "U1", "nodes": ["input", "0"], "value": 1,
             "waveform": {"kind": "sine", "amplitude": 1, "frequency": 1000}},
            {"kind": "X", "name": "DEVICE1", "model": "DEVICE", "connections": {"B": "input", "C": "output", "E": "0"}},
            {"kind": "R", "name": "RLOAD", "nodes": ["output", "0"], "value": "2k"}],
            "ports": {"IN": "input", "OUT": "output"}, "analysis": {"input": "IN", "output": "OUT"}}}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HierarchyTransactions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.destination = self.root / "project"

    def tearDown(self):
        self.temporary.cleanup()

    def test_relative_references_spec_preservation_and_manifest_hashes(self):
        spec = project_spec()
        before = copy.deepcopy(spec)
        with patch.object(hierarchy, "create_circuit", side_effect=fake_author) as author:
            result = create_project(spec, self.destination)
        self.assertEqual(spec, before)
        self.assertEqual(Path(result["project_dir"]), self.destination)
        self.assertEqual([call.args[1].name for call in author.call_args_list], ["RES.scm", "PAIR.scm", "main.scm"])
        root = json.loads((self.destination / "main.scm").read_text())
        child = json.loads((self.destination / "models" / "PAIR.scm").read_text())
        self.assertFalse(root["subcircuit"])
        self.assertTrue(child["subcircuit"])
        self.assertEqual(root["context"]["RES"]["path"], "models/RES.scm")
        self.assertEqual(child["context"]["RES"]["path"], "RES.scm")
        self.assertEqual(root["context"]["PAIR"]["pins"], {"Left": ["P"], "Top": [], "Right": ["N"], "Bottom": []})
        self.assertEqual(json.loads(Path(result["spec_path"]).read_text(encoding="utf-8")), before)
        manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
        self.assertFalse(manifest["parameter_overrides_supported"])
        self.assertEqual(manifest["root"], "main.scm")
        self.assertEqual(len(manifest["files"]), 7)
        for item in manifest["files"]:
            path = self.destination / item["path"]
            self.assertFalse(Path(item["path"]).is_absolute())
            self.assertNotIn("..", Path(item["path"]).parts)
            self.assertEqual(digest(path), item["sha256"])
            self.assertEqual(path.stat().st_size, item["bytes"])
        for model in result["models"]:
            self.assertEqual(digest(Path(model["path"])), model["sha256"])
        self.assertEqual(result["manifest_sha256"], digest(Path(result["manifest_path"])))
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["project"])

    def test_hierarchy_errors_precede_staging_and_authoring(self):
        cases = []
        bad = project_spec(); bad["models"]["res"] = copy.deepcopy(bad["models"]["RES"]); cases.append((bad, "model name"))
        for name in ("../escape", "CON", "NUL", "COM1"):
            bad = project_spec(); bad["models"][name] = bad["models"].pop("RES"); cases.append((bad, "Model name"))
        bad = project_spec(); bad["models"]["RES"]["pins"]["Left"] = None; cases.append((bad, "list"))
        for name in ("_private", "123", "B;exit"):
            bad = project_spec(); bad["models"]["RES"]["pins"]["Left"] = [name]; cases.append((bad, "pin names"))
        bad = project_spec(); bad["models"]["RES"]["pins"]["Right"] = ["p"]; cases.append((bad, "ambiguous pin"))
        bad = project_spec(); bad["models"]["RES"]["circuit"]["ports"]["EXTRA"] = "p"; cases.append((bad, "ports"))
        bad = project_spec(); bad["models"]["PAIR"]["circuit"]["components"][0]["model"] = "MISSING"; cases.append((bad, "unknown"))
        bad = project_spec(); bad["models"]["PAIR"]["circuit"]["components"][0]["model"] = "PAIR"; cases.append((bad, "cycle"))
        bad = project_spec(); bad["models"]["PAIR"]["circuit"]["components"][0].update(kind="SUB", model="PAIR"); cases.append((bad, "cycle"))
        bad = project_spec(); bad["circuit"]["components"][1]["parameters"] = {"R": 2}; cases.append((bad, "parameter overrides"))
        bad = project_spec(); del bad["circuit"]["components"][1]["connections"]["N"]; cases.append((bad, "connections"))
        bad = project_spec(); bad["circuit"]["components"][0]["value"] = float("nan"); cases.append((bad, "finite"))
        for spec, message in cases:
            with self.subTest(message=message, spec=spec), patch.object(hierarchy, "create_circuit") as author:
                with self.assertRaisesRegex(SchemeError, message):
                    create_project(spec, self.destination)
                author.assert_not_called()
                self.assertEqual(list(self.root.iterdir()), [])

    def test_generation_failure_removes_only_owned_stage(self):
        sentinel = self.root / "keep.txt"
        sentinel.write_text("user data")
        calls = 0

        def fail_after_first(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SchemeError("Unsupported physical model geometry")
            return fake_author(*args, **kwargs)

        with patch.object(hierarchy, "create_circuit", side_effect=fail_after_first):
            with self.assertRaisesRegex(SchemeError, "physical model geometry"):
                create_project(project_spec(), self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(sentinel.read_text(), "user data")
        self.assertEqual(list(self.root.iterdir()), [sentinel])

    def test_unintended_generated_test_port_cannot_change_model_interface(self):
        def unexpected_port(*args, **kwargs):
            result = fake_author(*args, **kwargs)
            result["ports"] = {**result["ports"], "accidental_analysis_output": "n"}
            return result

        with patch.object(hierarchy, "create_circuit", side_effect=unexpected_port):
            with self.assertRaisesRegex(SchemeError, "generated native ports"):
                create_project(project_spec(), self.destination)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_generated_native_pin_slot_reordering_cannot_be_published(self):
        def reordered_ports(*args, **kwargs):
            result = fake_author(*args, **kwargs)
            result["objects"] = list(reversed(result["objects"]))
            return result

        with patch.object(hierarchy, "create_circuit", side_effect=reordered_ports):
            with self.assertRaisesRegex(SchemeError, "PORT object order"):
                create_project(asymmetric_pin_spec(), self.destination)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_destination_and_empty_directory_race_are_never_overwritten(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep.txt"
        sentinel.write_text("original")
        with patch.object(hierarchy, "create_circuit") as author:
            with self.assertRaises(FileExistsError):
                create_project(project_spec(), self.destination)
            author.assert_not_called()
        self.assertEqual(sentinel.read_text(), "original")
        racing_destination = self.root / "race"
        publish = hierarchy._publish_directory

        def create_rival(stage, target):
            target.mkdir()
            publish(stage, target)

        with patch.object(hierarchy, "create_circuit", side_effect=fake_author), \
                patch.object(hierarchy, "_publish_directory", side_effect=create_rival):
            with self.assertRaises((FileExistsError, PermissionError)):
                create_project(project_spec(), racing_destination)
        self.assertEqual(list(racing_destination.iterdir()), [])
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["project", "race"])

    def test_inspection_reports_native_test_only_elements_without_inventing_pin_sides(self):
        source = self.root / "original.scm"
        create_circuit(example_circuit(), source)
        from fastmean_mcp.schematic import _load, _write_document
        _, document, _ = _load(source)
        objects = document["scm"]["Scheme"]["Objects"]
        next(obj for obj in objects if obj.get("Name") == "R1")["Name"] = "_Rtest"
        next(obj for obj in objects if obj.get("Type") == 400 and obj.get("Name") == "in")["Name"] = "_private"
        _write_document(document, source, overwrite=True)
        before = source.read_bytes()
        result = inspect_definition(source)
        self.assertEqual(result["external_ports"], ["out"])
        self.assertEqual(result["private_ports"], ["_private"])
        self.assertEqual(result["test_only_components"], ["_Rtest"])
        self.assertIsNone(result["pin_sides"])
        self.assertEqual(result["sha256"], digest(source))
        self.assertEqual(source.read_bytes(), before)


class HierarchyAuthoring(unittest.TestCase):
    def test_child_port_layout_matches_native_slots_not_input_mapping_order(self):
        from fastmean_mcp.schematic import _load
        spec = asymmetric_pin_spec()
        original = copy.deepcopy(spec)
        with tempfile.TemporaryDirectory() as temporary:
            result = create_project(spec, Path(temporary) / "project")
            model = next(item for item in result["models"] if item["name"] == "DEVICE")
            _, document, _ = _load(model["path"])
            ports = [obj["Name"] for obj in document["scm"]["Scheme"]["Objects"] if obj["Type"] == 400]
            self.assertEqual(ports, ["B", "E", "C"])
            by_name = {obj["Name"]: obj for obj in document["scm"]["Scheme"]["Objects"] if obj["Type"] == 400}
            self.assertEqual({name: by_name[name]["Rot"] for name in ports}, {"B": 2, "E": 3, "C": 1})
            self.assertEqual(model["native_port_order"], ports)
            self.assertEqual(spec, original)
            saved = json.loads(Path(result["spec_path"]).read_text(encoding="utf-8"))
            self.assertEqual(list(saved["models"]["DEVICE"]["circuit"]["ports"]), ["B", "C", "E"])
            root = read_scheme(result["path"])
            block = next(item for item in root["components"] if item["native_type"] == 7100)
            self.assertEqual(block["pin_names"], ["B", "E", "C"])
            self.assertEqual(block["connections"], {"B": "IN", "E": "0", "C": "OUT"})

    def test_manual_child_port_on_wrong_native_side_is_rejected(self):
        spec = asymmetric_pin_spec()
        spec["models"]["DEVICE"]["circuit"]["layout"] = {"ports": {"E": {"x": 900, "y": 1400, "rotation": 1}}}
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            with self.assertRaisesRegex(ValueError, "rotation|PORT|interface"):
                create_project(spec, target)
            self.assertFalse(target.exists())

    def test_floating_nested_models_roundtrip_and_relative_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            result = create_project(project_spec(), target)
            root = read_scheme(result["path"])
            pair = read_scheme(target / "models" / "PAIR.scm")
            resistor = read_scheme(target / "models" / "RES.scm")
            self.assertEqual({c["name"] for c in root["components"]}, {"U1", "FIRST", "SECOND", "RL"})
            self.assertNotIn("0", {node["name"] for node in resistor["nodes"]})
            self.assertEqual(set(resistor["ports"]), {"P", "N"})
            self.assertEqual(set(pair["ports"]), {"P", "N"})
            for summary, prefix in ((root, "models/"), (pair, "")):
                instances = [c for c in summary["components"] if c["native_type"] == 7100]
                self.assertEqual(len(instances), 2)
                for component in instances:
                    self.assertEqual(len(component["native_pin_nodes"]), 2)
                    reference = component["parameters"]["FileName"].replace("\\", "/")
                    self.assertTrue(reference.startswith(prefix))
                    self.assertFalse(Path(reference).is_absolute())
                    self.assertNotIn("..", Path(reference).parts)


class NativeComponentNormalization(unittest.TestCase):
    def test_public_normalized_spec_remains_reusable_without_compiler_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = create_circuit(example_circuit(), root / "first.scm")
            self.assertTrue(all(not key.startswith("_native_") for item in first["spec"]["components"] for key in item))
            second = create_circuit(first["spec"], root / "second.scm")
            self.assertEqual([item["nodes"] for item in first["components"]], [item["nodes"] for item in second["components"]])
            self.assertEqual(first["analysis"]["FD"]["Expressions"], second["analysis"]["FD"]["Expressions"])

    def test_fixed_native_templates_preserve_terminal_order_gain_and_diode_parameters(self):
        from fastmean_mcp.schematic import _normalize_components
        components = [
            {"kind": "D", "name": "D1", "nodes": ["b", "e"],
             "parameters": {"Ron": "10m", "Roff": "50M", "Uon": .7}},
            {"kind": "VCCS", "name": "Gm", "nodes": ["b", "e", "c", "e"], "value": "-40m"},
            {"kind": "VCVS", "name": "EV", "nodes": ["a", "0", "b", "0"], "parameters": {"k": 2}},
            {"kind": "CCCS", "name": "FI", "nodes": ["a", "b", "c", "0"], "value": -100}]
        items, nodes, _ = _normalize_components(components, {})
        self.assertEqual([item["_native_type"] for item in items], [1101, 6000, 6001, 6002])
        self.assertEqual([item["_native_params"] for item in items],
                         [{"Ron": .01, "Roff": 50e6, "Uon": .7}, {"g": -.04}, {"k": 2}, {"h": -100}])
        for raw, item in zip(components, items):
            self.assertEqual(item["_native_nodes"], raw["nodes"])
        self.assertEqual(nodes, {"0", "a", "b", "c", "e"})

    def test_model_side_order_has_dynamic_pin_count_and_exact_connections(self):
        from fastmean_mcp.schematic import _model_context, _normalize_components, _summarize
        context = _model_context({"NPN": {"pins": {"Bottom": ["E"], "Left": ["B"], "Top": ["C"]},
                                          "path": "models/NPN.scm"}})
        item = _normalize_components([{"kind": "X", "name": "Q1", "model": "NPN",
                                       "connections": {"E": "gnd", "C": "collector", "B": "base"}}], context)[0][0]
        self.assertEqual(item["_native_nodes"], ["base", "collector", "0"])
        self.assertEqual(item["_native_type"], 7100)
        self.assertEqual(set(item["_native_params"]), {"FileName", "Pins"})
        document = {"scm": {"Scheme": {"Objects": [
            {"ID": 1, "Type": 7100, "Name": "Q1", "Params": item["_native_params"]},
            {"ID": 2, "Type": 200, "Name": "GND1"}],
            "Wires": [{"obj1": {"ID": 1, "pin": 3}, "obj2": {"ID": 2, "pin": 1}}]}}}
        summary = _summarize(document, Path("model.scm"), "utf-8")
        component = summary["components"][0]
        self.assertEqual(component["pin_names"], ["B", "C", "E"])
        self.assertEqual(len(component["native_pin_nodes"]), 3)
        self.assertEqual(component["connections"]["E"], "0")
        self.assertTrue(component["supported_for_generation"])
        document["scm"]["Scheme"]["Wires"][0]["obj1"]["pin"] = 4
        with self.assertRaisesRegex(SchemeError, "Invalid terminal"):
            _summarize(document, Path("model.scm"), "utf-8")

    def test_unverified_or_injectable_parameters_and_model_paths_are_rejected(self):
        from fastmean_mcp.schematic import _model_context, _normalize_components
        invalid = [
            {"kind": "D", "name": "D1", "nodes": ["a", "b"], "parameters": {"Ron": .1, "Roff": "50M"}},
            {"kind": "D", "name": "D1", "nodes": ["a", "b"], "parameters": {"Ron": 0, "Roff": "50M", "Uon": .7}},
            {"kind": "G", "name": "G1", "nodes": ["a", "0", "b", "0"], "value": ".parameter X=1"},
            {"kind": "E", "name": "E1", "nodes": ["a", "0", "b", "0"], "parameters": {"r": 2}},
            {"kind": "F", "name": "F1", "nodes": ["a", "0", "b", "0"], "value": 2, "parameters": {"h": 2}}]
        for component in invalid:
            with self.subTest(component=component), self.assertRaises(SchemeError):
                _normalize_components([component], {})
        for reference in ("../outside.scm", "C:/outside.scm", "//server/model.scm", "models/../../outside.scm", "https://example/model.scm"):
            with self.subTest(reference=reference), self.assertRaises(SchemeError):
                _model_context({"MODEL": {"pins": {"Left": ["IN"]}, "path": reference}})


class HierarchyServerContract(unittest.TestCase):
    def test_project_publication_uses_direct_job_and_registers_nested_specs(self):
        from fastmean_mcp import server
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / "runs"
            with patch.dict(os.environ, {"FASTMEAN_OUTPUT_DIR": str(output), "FASTMEAN_APP_DIR": str(output / "absent-app")}), \
                    patch.object(hierarchy, "create_circuit", side_effect=fake_author):
                result = server.fastmean_create_project(project_spec(), name="editable")
                job = Path(result["working_dir"])
                self.assertEqual(job.parent, output)
                self.assertEqual(Path(result["project_dir"]).parent, job)
                self.assertEqual(result["analysis"], "create_project")
                paths = {item["relative_path"] for item in result["artifacts"]}
                self.assertTrue({"editable/main.scm", "editable/models/RES.scm", "editable/models/PAIR.scm",
                                 "editable/project.spec.json", "editable/main.spec.json",
                                 "editable/models/RES.spec.json", "editable/models/PAIR.spec.json",
                                 "editable/project.manifest.json"} <= paths)
                spec_artifact = next(item for item in result["artifacts"] if item["relative_path"] == "editable/project.spec.json")
                original = json.loads(server.store().read_artifact(result["run_id"], spec_artifact["name"]))
                self.assertEqual(original, project_spec())

    def test_explicit_open_packages_relative_models_with_hashes_without_real_gui(self):
        from fastmean_mcp import server
        from fastmean_mcp.schematic import _load, _write_document
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            app = root / "fake-app"
            app.mkdir()
            (app / "Fastmean.exe").write_bytes(b"test fixture; never executed")
            (root / "models").mkdir()
            child = root / "models" / "child.scm"
            source = root / "root.scm"
            create_circuit(example_circuit(), child)
            create_circuit(example_circuit(), source)
            _, document, _ = _load(source)
            document["scm"]["Scheme"]["Objects"].append({"ID": 999, "Type": 7100, "Name": "MODEL1",
                "Params": {"FileName": "models/child.scm", "Pins": {"Left": ["in"], "Right": ["out"]}}})
            _write_document(document, source, overwrite=True)
            before = {source: source.read_bytes(), child: child.read_bytes()}
            with patch.dict(os.environ, {"FASTMEAN_OUTPUT_DIR": str(root / "runs"), "FASTMEAN_APP_DIR": str(app)}), \
                    patch.object(server.subprocess, "Popen") as launch:
                launch.return_value.pid = 12345
                result = server.fastmean_open(str(source))
                launch.assert_called_once()
                command = launch.call_args.args[0]
                self.assertEqual(command, [str((app / "Fastmean.exe").resolve()), "-o", result["path"]])
                self.assertNotIn("-s", command)
                self.assertEqual(len(result["source_models"]), 2)
                for item in result["source_models"]:
                    self.assertEqual(digest(Path(item["source_path"])), item["source_sha256"])
                    self.assertEqual(digest(Path(item["private_path"])), item["private_sha256"])
                _, copied, _ = _load(result["path"])
                reference = next(obj for obj in copied["scm"]["Scheme"]["Objects"] if obj["Type"] == 7100)["Params"]["FileName"]
                self.assertTrue(Path(reference).is_file())
                self.assertTrue(Path(reference).is_relative_to(Path(result["working_dir"])))
                manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "opened")
                self.assertFalse(manifest["analysis_requested"])
                self.assertEqual({item["relative_path"] for item in result["artifacts"] if item["name"].endswith(".scm")},
                                 {str(Path(item["private_path"]).relative_to(Path(result["working_dir"]))).replace("\\", "/")
                                  for item in result["source_models"]})
            for path, raw in before.items():
                self.assertEqual(path.read_bytes(), raw)


@unittest.skipUnless(os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1", "opt-in native hierarchy regression")
class NativeHierarchy(unittest.TestCase):
    def test_asymmetric_three_pin_model_exports_and_solves_without_collector_emitter_swap(self):
        from fastmean_mcp.engine import Engine
        app = Path(os.environ.get("FASTMEAN_APP_DIR", str(Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1")))
        if not (app / "Fastmean.exe").is_file():
            self.skipTest("FASTMEAN executable not installed")
        with tempfile.TemporaryDirectory(prefix="fastmean-pin-order-") as temporary:
            root = Path(temporary).resolve()
            project = create_project(asymmetric_pin_spec(), root / "project")
            engine = Engine(app, root / "jobs")
            exported = engine.export_netlist(project["path"])["text"]
            lines = [line.split() for line in exported.splitlines() if line.strip()]
            def terminals(name):
                alternatives = {name.casefold(), name.split("_", 1)[-1].casefold()}
                return next(fields[1:3] for fields in lines if fields[0].casefold() in alternatives)
            source = terminals("E_U1")
            load = terminals("R_RLOAD")
            output = next(node for node in load if node != "0")
            self.assertEqual(set(terminals("R_DEVICE1.RBC")), {source[1], output})
            self.assertEqual(set(terminals("R_DEVICE1.RCE")), {output, "0"})
            response = engine.run_ac(project["path"], ["mag(U(OUT)/U(IN))"], 1, 1000, 4)
            for _, magnitude in response["rows"]:
                self.assertAlmostEqual(magnitude, .5, delta=1e-9)

    def test_repeated_two_level_models_have_independent_native_nodes_and_half_gain(self):
        from fastmean_mcp.engine import Engine
        app = Path(os.environ.get("FASTMEAN_APP_DIR", str(Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1")))
        if not (app / "Fastmean.exe").is_file():
            self.skipTest("FASTMEAN executable not installed")
        with tempfile.TemporaryDirectory(prefix="fastmean-hierarchy-") as temporary:
            root = Path(temporary).resolve()
            project = create_project(project_spec(), root / "project")
            sources = {path: path.read_bytes() for path in (root / "project").rglob("*") if path.is_file()}
            engine = Engine(app, root / "jobs")
            result = engine.run_ac(project["path"], ["mag(U(OUT)/U(IN))"], 1, 10000, 5)
            self.assertEqual(result["row_count"], 5)
            for _, magnitude in result["rows"]:
                self.assertAlmostEqual(magnitude, .5, delta=1e-9)
            self.assertEqual(len(result["source_models"]), 3)
            exported = engine.export_netlist(project["path"])["text"]
            for name in ("FIRST.A.R1", "FIRST.B.R1", "SECOND.A.R1", "SECOND.B.R1"):
                self.assertIn(name, exported)
            for path, contents in sources.items():
                self.assertEqual(path.read_bytes(), contents)


if __name__ == "__main__":
    unittest.main()
