"""Readable functional stages without changing analysis or native pin identity."""
import copy
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.hierarchy import create_project
from fastmean_mcp.native_geometry import body_bounds
from fastmean_mcp.schematic import _load, create_circuit, read_scheme
from tests.test_hierarchy import project_spec, self_test_project_spec
from tests.test_power_primitives import switch_spec, transformer_spec


class FunctionalLayoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def model(self, spec, name):
        result = create_project(spec,self.root/name)
        model = self.root/name/"models/DEVICE.scm"
        _,document,_ = _load(model)
        objects = document["scm"]["Scheme"]["Objects"]
        return document,objects

    def test_self_test_model_is_compact_and_keeps_saved_plot_and_timing_settings(self):
        spec = self_test_project_spec()
        spec["models"]["DEVICE"]["circuit"]["analysis"] = {
            "output":"P","transient":{"stop":"7m","step":"2u","eps":"1u"},
            "frequency":{"start":3,"stop":3000,"points":13}}
        before = copy.deepcopy(spec)
        document,objects = self.model(spec,"self_test")
        self.assertEqual(spec,before)
        components = [o for o in objects if o["Type"] not in {200,300,400,900}]
        self.assertLessEqual(max(o["Y"] for o in components)-min(o["Y"] for o in components),400)
        self.assertEqual(document["scm"]["TD"]["Expressions"],[{"plot":1,"x":"t","y":"U(P)"}])
        self.assertEqual(document["scm"]["FD"]["Expressions"],
            [{"plot":1,"x":"f","y":"db(U(P))"},{"plot":2,"x":"f","y":"phs(U(P))"}])
        interval = document["scm"]["TD"]["IP"][0]
        self.assertEqual((interval["EndTime"],interval["TimeStep"],interval["EPS"]),(.007,2e-6,1e-6))
        frequency = document["scm"]["FD"]
        self.assertEqual((frequency["StartFreq"],frequency["EndFreq"],frequency["NumPts"]),(3,3000,13))

    def test_series_boxes_follow_interface_direction_without_unnecessary_junctions(self):
        result = create_project(project_spec(),self.root/"pair")
        path = Path(result["path"]).parent/"models/PAIR.scm"
        _,document,_ = _load(path)
        objects = document["scm"]["Scheme"]["Objects"]
        boxes = {o["Name"]:o for o in objects if o["Type"]==7100}
        self.assertLess(boxes["A"]["X"],boxes["B"]["X"])
        self.assertEqual(boxes["A"]["Y"],boxes["B"]["Y"])
        self.assertEqual(sum(o["Type"]==300 for o in objects),0)
        self.assertEqual(sum(o["Type"]==400 for o in objects),2)
        inspected = read_scheme(path)
        a,b = inspected["components"]
        self.assertEqual(a["connections"]["N"],b["connections"]["P"])

    def test_test_only_shortcut_does_not_displace_the_active_signal_chain(self):
        spec = {"components":[
            {"kind":"R","name":"_BYPASS","nodes":["p","n"],"value":"1M"},
            {"kind":"R","name":"R1","nodes":["p","a"],"value":"1k"},
            {"kind":"R","name":"R2","nodes":["a","b"],"value":"1k"},
            {"kind":"R","name":"R3","nodes":["b","n"],"value":"1k"}],
            "ports":{"P":"p","N":"n"}}
        result = create_circuit(spec,self.root/"chain.scm",subcircuit=True,
            interface_pins={"Left":["P"],"Right":["N"]})
        positions = result["layout"]["positions"]
        self.assertLess(positions["R1"]["x"],positions["R2"]["x"])
        self.assertLess(positions["R2"]["x"],positions["R3"]["x"])
        self.assertEqual(len({positions[n]["y"] for n in ("R1","R2","R3")}),1)
        self.assertEqual(result["layout"]["spine_selection"],"interface")

    def test_native_power_stages_are_adjacent_to_their_connected_source_and_load(self):
        for factory,kind in ((transformer_spec,"TR"),(switch_spec,"SW")):
            for reverse in (False,True):
                with self.subTest(kind=kind,reverse=reverse):
                    spec = factory()
                    spec.pop("layout")
                    spec["analysis"] = {"input":"in","output":"out"}
                    device = next(c for c in spec["components"] if c["kind"]==kind)
                    if reverse:
                        device["nodes"][2:] = list(reversed(device["nodes"][2:]))
                    result = create_circuit(spec,self.root/f"{kind}-{reverse}.scm")
                    positions = result["layout"]["positions"]
                    stage = positions[device["name"]]
                    self.assertGreater(stage["x"],positions["VIN"]["x"])
                    self.assertLess(stage["x"],positions["RL"]["x"])
                    self.assertLessEqual(abs(stage["y"]-positions["RL"]["y"]),200)
                    native = next(c for c in result["components"] if c["kind"]==kind)
                    self.assertEqual(native["native_pin_nodes"],[result["node_mapping"][n] for n in device["nodes"]])
                    _,document,_ = _load(result["path"])
                    objects = document["scm"]["Scheme"]["Objects"]
                    bounds = []
                    for obj in objects:
                        if obj["Type"]==1000 or obj["Type"]==2010:
                            bounds.append((obj["X"]-30,obj["Y"]-30,obj["X"]+30,obj["Y"]+30))
                        elif obj["Type"] in {6101,6600}: bounds.append(body_bounds(obj))
                    for port in (o for o in objects if o["Type"]==400):
                        self.assertFalse(any(l<=port["X"]<=r and t<=port["Y"]<=b for l,t,r,b in bounds))

    def test_manual_power_stage_positions_and_rotations_remain_exact(self):
        for factory,name in ((transformer_spec,"TR1"),(switch_spec,"SW1")):
            for rotation in range(4):
                spec = factory(rotation=rotation)
                result = create_circuit(spec,self.root/f"manual-{name}-{rotation}.scm")
                self.assertEqual(result["layout"]["positions"][name],spec["layout"]["placements"][name])

    def test_feedback_branches_do_not_replace_the_amplifier_in_the_signal_row(self):
        spec = {"components":[
            {"kind":"U","name":"VIN","nodes":["input","0"],"value":1},
            {"kind":"R","name":"R1","nodes":["input","a"],"value":"10k"},
            {"kind":"R","name":"RFB","nodes":["a","output"],"value":"10k"},
            {"kind":"R","name":"R3","nodes":["a","minus"],"value":"10k"},
            {"kind":"C","name":"CFB","nodes":["minus","output"],"value":"10n"},
            {"kind":"C","name":"C2","nodes":["a","0"],"value":"10n"},
            {"kind":"OPAMP","name":"OA1","nodes":["0","minus","output"],"parameters":{"k":1e5}},
            {"kind":"R","name":"RL","nodes":["output","0"],"value":"10k"}],
            "ports":{"IN":"input","OUT":"output"},"analysis":{"input":"IN","output":"OUT"}}
        original = copy.deepcopy(spec)
        result = create_circuit(spec,self.root/"feedback.scm")
        positions = result["layout"]["positions"]
        self.assertLess(positions["R1"]["x"],positions["R3"]["x"])
        self.assertLess(positions["R3"]["x"],positions["OA1"]["x"])
        self.assertEqual(positions["R1"]["y"],positions["R3"]["y"])
        self.assertLess(positions["RFB"]["y"],positions["R3"]["y"])
        self.assertLess(positions["CFB"]["y"],positions["R3"]["y"])
        self.assertEqual(positions["OA1"]["rotation"],0)
        amplifier = next(c for c in result["components"] if c["name"]=="OA1")
        self.assertEqual(amplifier["native_pin_nodes"],["0",result["node_mapping"]["minus"],"OUT"])
        self.assertEqual(spec,original)


if __name__=="__main__":unittest.main()
