"""Active instance topology, private test fixtures and conservative pin mapping."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastmean_mcp.hierarchy import create_project
from fastmean_mcp.schematic import _load, _write_document
from fastmean_mcp.topology import TopologyError, check_transient_project, voltage_loop


def topology_spec(test_fixture=False):
    components = [{"kind":"C","name":"CBR","nodes":["p","n"],"value":"1u"}]
    components.append({"kind":"U","name":"_TEST","nodes":["p","n"],"value":1,
                       "waveform":{"kind":"sine","frequency":1000}} if test_fixture else
                      {"kind":"C","name":"CLOAD","nodes":["n","0"],"value":"1u"})
    root = [{"kind":"U","name":"U1","nodes":["input","0"],"value":1,
             "waveform":{"kind":"sine","frequency":1000}}]
    if test_fixture:
        root.extend([{"kind":"R","name":"R1","nodes":["input","output"],"value":"1k"},
                     {"kind":"X","name":"STAGE","model":"CAP","connections":{"P":"output","N":"0"}}])
    else:
        root.extend([{"kind":"X","name":"STAGE","model":"CAP","connections":{"P":"input","N":"output"}},
                     {"kind":"R","name":"RL","nodes":["output","0"],"value":"1k"}])
    return {"models":{"CAP":{"pins":{"Left":["P"],"Right":["N"]},
            "circuit":{"components":components,"ports":{"P":"p","N":"n"}}}},
            "circuit":{"components":root,"ports":{"IN":"input","OUT":"output"},
                       "analysis":{"input":"IN","output":"OUT"}}}


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def project(self, spec):
        result = create_project(spec,self.root/"project")
        return Path(result["path"]),[{"private_path":str(p)} for p in (self.root/"project").rglob("*.scm")]

    def test_cross_boundary_cycle_is_found_with_qualified_component_names(self):
        path,assets=self.project(topology_spec())
        with self.assertRaises(TopologyError) as error:
            check_transient_project(path,assets)
        self.assertEqual(set(error.exception.loop),{"U1","STAGE.CBR","STAGE.CLOAD"})
        self.assertEqual(error.exception.model_path,path)

    def test_two_level_cycle_and_repeated_definition_do_not_share_internal_nodes(self):
        spec=topology_spec()
        spec["models"]["WRAP"]={"pins":{"Left":["P"],"Right":["N"]},"circuit":{
            "components":[{"kind":"X","name":"INNER","model":"CAP","connections":{"P":"p","N":"n"}}],
            "ports":{"P":"p","N":"n"}}}
        spec["circuit"]["components"][1]["model"]="WRAP"
        path,assets=self.project(spec)
        with self.assertRaises(TopologyError) as error:
            check_transient_project(path,assets)
        self.assertIn("STAGE.INNER.CBR",error.exception.loop)
        # A separate root, with a series resistor, removes the U/C-only loop.
        other=self.root/"separate"
        spec["circuit"]["components"][1]["connections"]["P"]="after_r"
        spec["circuit"]["components"].append({"kind":"R","name":"RS","nodes":["input","after_r"],"value":100})
        # A second instance of the same model has its own internal node scope.
        spec["circuit"]["components"].append({"kind":"X","name":"SECOND","model":"WRAP","connections":{"P":"after_r","N":"second_out"}})
        result=create_project(spec,other)
        report=check_transient_project(result["path"],[{"private_path":str(p)} for p in other.rglob("*.scm")])
        self.assertEqual(report["status"],"passed")
        self.assertEqual(report["expanded_instances"],5)
        self.assertEqual(report["checked_edges"],5)

    def test_test_only_child_sources_are_excluded_but_root_test_sources_are_active(self):
        path,assets=self.project(topology_spec(True))
        report=check_transient_project(path,assets)
        self.assertEqual(report["status"],"passed")
        self.assertEqual(report["ignored_test_component_count"],1)
        self.assertEqual(report["ignored_test_components"][0]["name"],"_TEST")
        self.assertEqual(report["checked_edges"],2)
        with self.assertRaises(TopologyError) as error:
            check_transient_project(path.parent/"models/CAP.scm",assets)
        self.assertIn("_TEST",error.exception.loop)

    def test_ignored_child_instance_does_not_activate_its_invalid_descendant(self):
        spec=topology_spec(True)
        spec["models"]["BAD"]=copy.deepcopy(spec["models"]["CAP"])
        spec["models"]["BAD"]["circuit"]["components"][1]["name"]="ACTIVE_SOURCE"
        spec["models"]["CAP"]["circuit"]["components"].append({"kind":"X","name":"_UNUSED","model":"BAD","connections":{"P":"p","N":"n"}})
        path,assets=self.project(spec)
        report=check_transient_project(path,assets)
        self.assertEqual(report["status"],"passed")
        self.assertEqual(len(report["checked_models"]),2)
        self.assertEqual(report["ignored_test_component_count"],2)

    def test_unknown_interface_and_expansion_budget_are_reported_as_partial(self):
        path,assets=self.project(topology_spec())
        with patch("fastmean_mcp.topology.MAX_INSTANCES",1):
            report=check_transient_project(path,assets)
        self.assertEqual(report["status"],"partial")
        self.assertFalse(report["complete"])
        self.assertIn("limit",report["skipped_interfaces"][0]["reason"])
        child=path.parent/"models/CAP.scm"
        _,document,_=_load(child)
        next(o for o in document["scm"]["Scheme"]["Objects"] if o["Type"]==400 and o["Name"]=="P")["Rot"]=0
        _write_document(document,child,overwrite=True)
        report=check_transient_project(path,assets)
        self.assertEqual(report["status"],"partial")
        self.assertEqual(report["skipped_interfaces"][0]["instance"],"STAGE")
        next(o for o in document["scm"]["Scheme"]["Objects"] if o["Type"]==400 and o["Name"]=="P")["Rot"]=2
        _write_document(document,child,overwrite=True)
        _,root_document,_=_load(path)
        next(o for o in root_document["scm"]["Scheme"]["Objects"] if o["Type"]==7100)["Params"]["Actual"]={"unverified":1}
        _write_document(root_document,path,overwrite=True)
        report=check_transient_project(path,assets)
        self.assertEqual(report["status"],"partial")
        self.assertIn("overrides",report["skipped_interfaces"][0]["reason"])

    def test_pure_capacitor_cycles_remain_accepted(self):
        self.assertIsNone(voltage_loop([("C",1,2,"C1"),("C",2,3,"C2"),("C",3,1,"C3")]))
        self.assertEqual(set(voltage_loop([("C",1,2,"C1"),("C",2,3,"C2"),("U",3,1,"U1")])),{"C1","C2","U1"})

    def test_same_file_is_root_only_in_the_initial_context(self):
        from tests.test_hierarchy import self_test_project_spec
        path, assets = self.project(self_test_project_spec())
        report = check_transient_project(path, assets)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["expanded_instances"], 2)
        self.assertEqual(report["checked_edges"], 1)
        self.assertEqual(report["ignored_test_component_count"], 3)
        report = check_transient_project(path.parent / "models/DEVICE.scm", assets)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["expanded_instances"], 2)
        self.assertEqual(report["checked_edges"], 1)
        self.assertEqual(report["ignored_test_component_count"], 3)


if __name__ == "__main__":unittest.main()
