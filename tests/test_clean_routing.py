"""Native geometry and complexity regressions across reusable circuit families.

These are portable compiler tests. They do not run a simulator or claim native
analysis; the MCP/native benchmark suite validates the resulting SCM separately.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import tempfile
import unittest

from fastmean_mcp.layout import LayoutError, Terminal, _Router, _split_overlapping_edges
from fastmean_mcp.captions import CAPTION_TYPES, caption_bounds, native_component_captions, native_component_value
from fastmean_mcp.annotations import annotate_circuit
from fastmean_mcp.hierarchy import create_project
from fastmean_mcp.schematic import _load, create_circuit, read_scheme
from fastmean_mcp.wires import wire_path


EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "four-bjt-alpha.input.json"
PUBLIC_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "four-bjt-amplifier" / "project.input.json"


def evidence(path):
    _,document,_ = _load(path)
    scheme = document["scm"]["Scheme"]
    objects = {o["ID"]:o for o in scheme["Objects"]}
    degrees = Counter()
    lines = []
    for wire in scheme["Wires"]:
        degrees.update(end["ID"] for end in (wire["obj1"],wire["obj2"]))
        path = wire_path(wire,objects)
        lines.extend(tuple(sorted((a,b))) for a,b in zip(path,path[1:]))
    lengths = [abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in lines]
    return {"objects":objects,"wires":scheme["Wires"],"lines":sorted(lines),
            "cons":sum(o["Type"]==300 for o in objects.values()),
            "waypoints":sum(o["Type"]==300 and degrees[oid]==2 for oid,o in objects.items()),
            "dangling":sum(o["Type"]==300 and degrees[oid]<2 for oid,o in objects.items()),
            "length":sum(lengths),"short_legs":sum(length<20 for length in lengths)}


def partitions(components, input_spec=False):
    nets = defaultdict(set)
    for component in components:
        nodes = component["nodes"] if input_spec else component["native_pin_nodes"]
        if input_spec and component["kind"] == "U": nodes = nodes[::-1]
        for pin,node in enumerate(nodes,1): nets[node].add((component["name"],pin))
    return {frozenset(terminals) for terminals in nets.values()}


def caption_hits(actual):
    hits = []
    for obj in actual["objects"].values():
        if obj["Type"] not in CAPTION_TYPES: continue
        for caption in native_component_captions(obj,native_component_value(obj)):
            left,top,right,bottom = caption_bounds(caption)
            for a,b in actual["lines"]:
                if a[1] == b[1]:
                    hit = top <= a[1] <= bottom and max(min(a[0],b[0]),left) <= min(max(a[0],b[0]),right)
                else:
                    hit = left <= a[0] <= right and max(min(a[1],b[1]),top) <= min(max(a[1],b[1]),bottom)
                if hit: hits.append((obj["Name"],caption["text"],a,b))
    return hits


class CleanRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fm-routing-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_direct_native_midpoint_uses_no_routing_cons(self):
        spec = {"components":[
            {"kind":"R","name":"A","nodes":["p","m"],"value":100},
            {"kind":"R","name":"B","nodes":["m","n"],"value":100}],
            "ports":{"P":"p","N":"n"},"analysis":{"input":"P","output":"N"},
            "layout":{"placements":{"A":{"x":600,"y":800},"B":{"x":1000,"y":960}},
                      "ports":{"P":{"x":400,"y":800,"rotation":2},
                               "N":{"x":1200,"y":960,"rotation":0}}}}
        target = self.root / "midpoint.scm"
        result = create_circuit(spec,target,subcircuit=True)
        actual = evidence(target)
        self.assertEqual(actual["cons"],0)
        self.assertEqual(len(actual["wires"]),3)
        self.assertEqual(partitions(result["components"]),partitions(spec["components"],True))
        self.assertIn(((800,800),(800,960)),actual["lines"])

    def test_exact_diode_pin_coordinates_survive_all_four_rotations(self):
        for rotation in range(4):
            with self.subTest(rotation=rotation):
                direction = ((1,0),(0,1),(-1,0),(0,-1))[rotation]
                dx,dy = direction
                placements = {f"D{i}":{"x":800+i*160*dx,"y":800+i*160*dy,"rotation":rotation}
                              for i in range(3)}
                spec = {"components":[{"kind":"D","name":f"D{i}","nodes":[f"n{i}",f"n{i+1}"],
                                       "parameters":{"Ron":.1,"Roff":1e9,"Uon":.65}} for i in range(3)],
                        "ports":{"P":"n0","N":"n3"},
                        "analysis":{"input":"P","output":"N"},
                        "layout":{"placements":placements,"ports":{
                            "P":{"x":800-160*dx,"y":800-160*dy,"rotation":(rotation+2)%4},
                            "N":{"x":800+480*dx,"y":800+480*dy,"rotation":rotation}}}}
                target = self.root / f"diodes-{rotation}.scm"
                result = create_circuit(spec,target,subcircuit=True)
                actual = evidence(target)
                self.assertEqual(actual["cons"],0)
                self.assertEqual(len(actual["wires"]),4)
                self.assertEqual(partitions(result["components"]),partitions(spec["components"],True))

    def test_four_bjt_equivalents_have_bounded_real_native_complexity(self):
        models = json.loads(EXAMPLE.read_text(encoding="utf-8"))["models"]
        for name,model in models.items():
            with self.subTest(model=name):
                target = self.root / f"{name}.scm"
                spec = copy.deepcopy(model["circuit"])
                ordered_ports = [pin for side in ("Left","Top","Right","Bottom") for pin in model["pins"][side]]
                spec["ports"] = {pin:spec["ports"][pin] for pin in ordered_ports}
                result = create_circuit(spec,target,
                                        subcircuit=True,interface_pins=model["pins"])
                actual = evidence(target)
                # Baseline N:22CON/15waypoints/4052units/7shortlegs;
                # P:27CON/18waypoints/4824units/8shortlegs, plus dangling stubs.
                n_type = name.startswith("N")
                self.assertLessEqual(actual["cons"],15 if n_type else 20)
                self.assertLessEqual(actual["waypoints"],10 if n_type else 15)
                self.assertLessEqual(actual["length"],3400 if n_type else 4150)
                self.assertLessEqual(actual["short_legs"],2 if n_type else 3)
                self.assertEqual(actual["dangling"],0)
                self.assertEqual(caption_hits(actual),[])
                self.assertEqual(partitions(result["components"]),partitions(model["circuit"]["components"],True))
                ports = [o["Name"] for o in actual["objects"].values() if o["Type"]==400]
                self.assertEqual(ports,[pin for side in ("Left","Top","Right","Bottom")
                                        for pin in model["pins"][side]])

    def test_fixed_geometry_does_not_depend_on_component_order_or_internal_net_names(self):
        models = json.loads(EXAMPLE.read_text(encoding="utf-8"))["models"]
        for name in ("NOUT","POUT"):
            with self.subTest(model=name):
                model = models[name]
                spec = copy.deepcopy(model["circuit"])
                first = self.root / f"{name}-first.scm"
                create_circuit(spec,first,subcircuit=True,interface_pins=model["pins"])
                spec["components"].reverse()
                rename = {node:f"internal_{index}" for index,node in enumerate(spec["layout"]["nodes"])
                          if node not in spec["ports"].values()}
                for component in spec["components"]:
                    component["nodes"] = [rename.get(node,node) for node in component["nodes"]]
                spec["layout"]["nodes"] = {rename.get(node,node):point
                                           for node,point in spec["layout"]["nodes"].items()}
                second = self.root / f"{name}-second.scm"
                create_circuit(spec,second,subcircuit=True,interface_pins=model["pins"])
                self.assertEqual(evidence(first)["lines"],evidence(second)["lines"])

    def test_public_beta_equivalents_keep_five_junctions_and_at_most_three_waypoints(self):
        # Native numerical alpha/beta equivalence is checked separately. This
        # portable regression checks the published beta geometry and terminals.
        models = json.loads(PUBLIC_EXAMPLE.read_text(encoding="utf-8"))["models"]
        self.assertEqual(set(models),{"NOUT","POUT","NDRV","PDRV"})
        for name,model in models.items():
            with self.subTest(model=name):
                spec = copy.deepcopy(model["circuit"])
                ordered_ports = [pin for side in ("Left","Top","Right","Bottom")
                                 for pin in model["pins"][side]]
                spec["ports"] = {pin:spec["ports"][pin] for pin in ordered_ports}
                target = self.root / f"beta-{name}.scm"
                result = create_circuit(spec,target,subcircuit=True,interface_pins=model["pins"])
                actual = evidence(target)
                self.assertEqual(len(result["components"]),7)
                self.assertLessEqual(actual["cons"],8)
                self.assertLessEqual(actual["waypoints"],3)
                self.assertEqual(actual["cons"]-actual["waypoints"],5)
                self.assertEqual(actual["dangling"],0)
                self.assertEqual(caption_hits(actual),[])
                self.assertEqual(partitions(result["components"]),partitions(spec["components"],True))

    def test_full_public_amplifier_routes_with_every_primitive_caption_clear(self):
        # The populated root sheet has many distinct label bounds. Its complete
        # authoring path must remain routable, not only the seven-part models.
        spec = json.loads(PUBLIC_EXAMPLE.read_text(encoding="utf-8"))
        before = copy.deepcopy(spec)
        result = create_project(spec,self.root / "full-amplifier")
        actual = evidence(result["path"])
        root = read_scheme(result["path"])
        expected = []
        for component in spec["circuit"]["components"]:
            item = copy.deepcopy(component)
            if item["kind"] == "X":
                model = spec["models"][item["model"]]
                item["nodes"] = [item["connections"][pin]
                                 for side in ("Left","Top","Right","Bottom") for pin in model["pins"][side]]
            expected.append(item)
        self.assertEqual(spec,before)
        self.assertEqual(len(root["components"]),len(expected))
        self.assertEqual(partitions(root["components"]),partitions(expected,True))
        self.assertEqual(actual["dangling"],0)
        self.assertEqual(caption_hits(actual),[])
        # Published annotations replace numeric captions with named parameter
        # references. Inspect those actual longer strings as well as the base
        # drawing; clearing only the original numeric labels is insufficient.
        request = json.loads((PUBLIC_EXAMPLE.parent / "annotation.request.json").read_text(encoding="utf-8"))
        request.pop("path",None)
        annotation_dir = self.root / "annotated-amplifier"
        annotation_dir.mkdir()
        annotated_path = annotation_dir / "Amplifier.scm"
        annotate_circuit(result["path"],annotated_path,**request)
        self.assertEqual(caption_hits(evidence(annotated_path)),[])
        self.assertEqual(partitions(read_scheme(annotated_path)["components"]),partitions(root["components"]))

    def test_outward_lead_joins_existing_tree_without_a_small_loop(self):
        terminals = [Terminal(1,1,"n",(100,100),(1,0)),
                     Terminal(2,1,"n",(300,100),(-1,0)),
                     Terminal(3,1,"n",(200,80),(0,1))]
        router = _Router([],terminals,{"n":(500,500)},600)
        graph = _split_overlapping_edges(router.route()["n"])
        router.graphs["n"] = graph
        router.validate_geometry()
        # A tree has exactly V-1 undirected edges, including compressed leads.
        self.assertEqual(sum(map(len,graph.values()))//2,len(graph)-1)
        self.assertEqual({p for p,links in graph.items() if len(links)==1},
                         {terminal.point for terminal in terminals})

    def test_local_grounds_are_real_native_one_wire_pairs_in_every_orientation(self):
        for rotation in range(4):
            with self.subTest(rotation=rotation):
                dx,dy = ((-1,0),(0,-1),(1,0),(0,1))[rotation]
                spec = {"components":[{"kind":"R","name":"R1","nodes":["P","0"],"value":100}],
                        "ports":{"P":"P"},"analysis":{"input":"P","output":"P"},
                        "layout":{"ground_style":"local", "placements":{
                            "R1":{"x":800,"y":800,"rotation":rotation}},"ports":{
                            "P":{"x":800+200*dx,"y":800+200*dy,"rotation":(rotation+2)%4}}}}
                target = self.root / f"ground-{rotation}.scm"
                result = create_circuit(spec,target)
                actual = evidence(target)
                grounds = [o for o in actual["objects"].values() if o["Type"]==200]
                self.assertEqual(len(grounds),1)
                wires = [w for w in actual["wires"] if grounds[0]["ID"] in {w["obj1"]["ID"],w["obj2"]["ID"]}]
                self.assertEqual(len(wires),1)
                path = wire_path(wires[0],actual["objects"])
                self.assertEqual(len(path),2)
                self.assertEqual(abs(path[0][0]-path[1][0])+abs(path[0][1]-path[1][1]),80)
                self.assertEqual(result["layout"]["ground_style"],"local")
                self.assertEqual(next(c for c in result["components"] if c["name"]=="R1")["native_pin_nodes"][1],"0")

    def test_local_parallel_branches_share_electrical_ground_without_a_physical_rail(self):
        spec = {"components":[{"kind":"R","name":f"R{i}","nodes":["P","0"],"value":100+i}
                              for i in range(3)],"ports":{"P":"P"},
                "analysis":{"input":"P","output":"P"},"layout":{"ground_style":"local",
                "placements":{f"R{i}":{"x":600+i*240,"y":800,"rotation":1} for i in range(3)}}}
        target = self.root / "local-parallel.scm"
        result = create_circuit(spec,target)
        actual = evidence(target)
        ground_ids = {o["ID"] for o in actual["objects"].values() if o["Type"]==200}
        self.assertEqual(len(ground_ids),3)
        ground_wires = [w for w in actual["wires"]
                        if ground_ids & {w["obj1"]["ID"],w["obj2"]["ID"]}]
        self.assertEqual(len(ground_wires),3)
        for wire in ground_wires:
            ends = {wire["obj1"]["ID"],wire["obj2"]["ID"]}
            self.assertEqual(sum(actual["objects"][oid]["Type"]==1000 for oid in ends),1)
        self.assertEqual(partitions(result["components"]),partitions(spec["components"],True))

    def test_invalid_ground_style_and_local_explicit_rail_are_rejected(self):
        for style in (None,True,[],"separate"):
            spec = {"components":[{"kind":"R","name":"R1","nodes":["P","0"],"value":100}],
                    "ports":{"P":"P"},"layout":{"ground_style":style}}
            with self.subTest(style=style),self.assertRaisesRegex(LayoutError,"ground_style"):
                create_circuit(spec,self.root / "invalid.scm")
        spec["layout"] = {"ground_style":"local","routes":{"0":[[[800,800],[1000,800]]]}}
        with self.assertRaisesRegex(LayoutError,"Explicit ground routes"):
            create_circuit(spec,self.root / "invalid-rail.scm")

    def test_four_unit_component_port_node_and_route_coordinates_are_preserved(self):
        spec = {"components":[{"kind":"R","name":"R1","nodes":["p","m"],"value":100},
                              {"kind":"R","name":"R2","nodes":["m","n"],"value":200}],
                "ports":{"P":"p","N":"n"},"layout":{
                    "placements":{"R1":{"x":604,"y":804,"rotation":0},
                                  "R2":{"x":844,"y":804,"rotation":0}},
                    "ports":{"P":{"x":404,"y":804,"rotation":2},
                             "N":{"x":1044,"y":804,"rotation":0}},
                    "nodes":{"m":{"x":724,"y":804}},
                    "routes":{"m":[[[664,804],[784,804]]]}}}
        target = self.root / "fine-grid.scm"
        result = create_circuit(spec,target,subcircuit=True)
        self.assertEqual(result["layout"]["positions"],spec["layout"]["placements"])
        self.assertEqual(evidence(target)["cons"],0)
        for field in ("placements","ports","nodes","routes"):
            bad = copy.deepcopy(spec)
            if field == "placements": bad["layout"][field]["R1"]["x"] = 605
            elif field == "ports": bad["layout"][field]["P"]["x"] = 405
            elif field == "nodes": bad["layout"][field]["m"]["x"] = 725
            else: bad["layout"][field]["m"][0][0][0] = 665
            with self.subTest(field=field),self.assertRaisesRegex(LayoutError,"multiples of 4"):
                create_circuit(bad,self.root / f"invalid-{field}.scm",subcircuit=True)

    def test_fine_grid_aligns_both_asymmetric_source_columns_without_adapters(self):
        spec = {"components":[
            {"kind":"D","name":"D1","nodes":["p","a"],"parameters":{"Ron":.1,"Roff":1e9,"Uon":.65}},
            {"kind":"R","name":"R1","nodes":["d","q"],"value":100},
            {"kind":"F","name":"F1","nodes":["a","b","c","d"],"value":-.5}],
            "ports":{"P":"p","Q":"q","B":"b","C":"c"},
            "layout":{"placements":{"D1":{"x":1024,"y":600,"rotation":1},
                                      "R1":{"x":1048,"y":1000,"rotation":1},
                                      "F1":{"x":1040,"y":800,"rotation":0}},
                      "ports":{"P":{"x":1024,"y":400,"rotation":3},
                               "Q":{"x":1048,"y":1200,"rotation":1},
                               "B":{"x":1024,"y":1000,"rotation":1},
                               "C":{"x":1048,"y":400,"rotation":3}}}}
        target = self.root / "fine-native-columns.scm"
        result = create_circuit(spec,target,subcircuit=True)
        actual = evidence(target)
        self.assertEqual(actual["cons"],0)
        self.assertEqual(len(actual["wires"]),6)
        self.assertTrue(all(a[0]==b[0] for a,b in actual["lines"]))
        self.assertEqual(partitions(result["components"]),partitions(spec["components"],True))
        self.assertEqual(caption_hits(actual),[])

    def test_explicit_node_anchor_inside_a_component_is_rejected_before_writing(self):
        spec = {"components":[{"kind":"R","name":"R1","nodes":["p","m"],"value":100},
                              {"kind":"R","name":"R2","nodes":["m","n"],"value":100}],
                "ports":{"P":"p","N":"n"},"layout":{
                    "placements":{"R1":{"x":604,"y":804},"R2":{"x":844,"y":804}},
                    "ports":{"P":{"x":404,"y":804,"rotation":2},
                             "N":{"x":1044,"y":804,"rotation":0}},
                    "nodes":{"m":{"x":604,"y":804}}}}
        target = self.root / "blocked-anchor.scm"
        with self.assertRaisesRegex(LayoutError,"Explicit node anchor.*component body"):
            create_circuit(spec,target,subcircuit=True)
        self.assertFalse(target.exists())

    def test_rotated_local_ground_bars_cannot_overlap_another_component(self):
        spec = {"components":[{"kind":"R","name":"R1","nodes":["p","0"],"value":100},
                              {"kind":"R","name":"R2","nodes":["p","q"],"value":100}],
                "ports":{"p":"p","q":"q"},"layout":{"ground_style":"local",
                    "placements":{"R1":{"x":600,"y":800,"rotation":0},
                                  "R2":{"x":752,"y":800,"rotation":1}},
                    "ports":{"p":{"x":400,"y":800,"rotation":2},
                             "q":{"x":752,"y":1000,"rotation":1}}}}
        target = self.root / "blocked-ground.scm"
        with self.assertRaisesRegex(LayoutError,"ground glyph overlaps a component"):
            create_circuit(spec,target)
        self.assertFalse(target.exists())

    def test_facing_parallel_branches_share_a_balanced_middle_output_rail(self):
        spec = {"components":[
            {"kind":"R","name":"R1","nodes":["p","out"],"value":100},
            {"kind":"R","name":"R2","nodes":["out","n"],"value":100},
            {"kind":"C","name":"C1","nodes":["p","out"],"value":1e-9},
            {"kind":"C","name":"C2","nodes":["out","n"],"value":1e-9}],
            "ports":{"P":"p","N":"n","OUT":"out"},"layout":{
                "placements":{"R1":{"x":920,"y":900,"rotation":1},
                              "R2":{"x":920,"y":1140,"rotation":1},
                              "C1":{"x":1240,"y":900,"rotation":1},
                              "C2":{"x":1240,"y":1140,"rotation":1}},
                "ports":{"P":{"x":760,"y":800,"rotation":2},
                         "N":{"x":1440,"y":1220,"rotation":0},
                         "OUT":{"x":1440,"y":1020,"rotation":0}}}}
        target = self.root / "balanced-divider.scm"
        result = create_circuit(spec,target,subcircuit=True)
        actual = evidence(target)
        # The long shared rail runs through the middle output, with symmetric
        # native 80-unit vertical leads from both upper and lower components.
        self.assertIn(((920,1020),(1240,1020)),actual["lines"])
        self.assertIn(((1240,1020),(1440,1020)),actual["lines"])
        self.assertEqual(partitions(result["components"]),partitions(spec["components"],True))

    def test_automatic_wires_route_around_horizontal_resistor_and_capacitor_values(self):
        for kind,value in (("R",10000),("C",.01)):
            with self.subTest(kind=kind):
                spec = {"components":[
                    {"kind":kind,"name":"VALUE_LABEL","nodes":["p","n"],"value":value},
                    {"kind":"R","name":"UPPER_BRANCH","nodes":["q","r"],"value":100}],
                    "ports":{"P":"p","N":"n","Q":"q","R":"r"},
                    "layout":{"placements":{"VALUE_LABEL":{"x":800,"y":800,"rotation":0},
                                              "UPPER_BRANCH":{"x":1000,"y":600,"rotation":0}},
                              "ports":{"P":{"x":600,"y":800,"rotation":2},
                                       "N":{"x":1000,"y":800,"rotation":0},
                                       "Q":{"x":600,"y":776,"rotation":2},
                                       "R":{"x":1200,"y":600,"rotation":0}}}}
                target = self.root / f"caption-clearance-{kind}.scm"
                result = create_circuit(spec,target,subcircuit=True)
                actual = evidence(target)
                self.assertEqual(caption_hits(actual),[])
                self.assertEqual(partitions(result["components"]),partitions(spec["components"],True))
                # A free opposing-pin midpoint route would run (600,776) →
                # (780,776), through the lower component's value caption.
                self.assertNotIn(((600,776),(780,776)),actual["lines"])

    def test_shared_source_caption_values_match_preview_for_dc_sine_and_pulse(self):
        from fastmean_mcp.preview import _source_label
        from fastmean_mcp.schematic import _source_params
        for tid in (2010,3010):
            for waveform in (None,{"kind":"sine","amplitude":.01,"frequency":2000},
                             {"kind":"pulse","high":.002,"low":-.001,"frequency":1000}):
                with self.subTest(tid=tid,waveform=waveform):
                    obj={"Type":tid,"Params":_source_params(.003,waveform,current=tid==3010)}
                    self.assertEqual(native_component_value(obj),_source_label(obj))


if __name__ == "__main__": unittest.main()
