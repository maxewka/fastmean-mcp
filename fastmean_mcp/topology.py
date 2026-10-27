"""Conservative transient topology checks of active native project instances."""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path

from .schematic import SchemeError, _load, _summarize

SIDES = (("Left", 2, "Y"), ("Top", 3, "X"), ("Right", 0, "Y"), ("Bottom", 1, "X"))
MAX_INSTANCES = 2000
MAX_EDGES = 50000


class TopologyError(ValueError):
    def __init__(self, model_path, loop, report):
        self.model_path, self.loop, self.report = model_path, loop, report
        super().__init__("Closed ideal voltage-source/capacitor loop: " + ", ".join(loop))


class _Union:
    def __init__(self):
        self.parent = {}

    def find(self, value):
        self.parent.setdefault(value, value)
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            previous = self.parent[value]
            self.parent[value] = root
            value = previous
        return root

    def join(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def voltage_loop(edges):
    """Allow pure capacitor cycles; return a path for the first U/C cycle."""
    union, graph = _Union(), {}

    def add(a, b, name):
        graph.setdefault(a, []).append((b, name))
        graph.setdefault(b, []).append((a, name))
        union.join(a, b)

    for kind, a, b, name in edges:
        if kind == "C":
            add(a, b, name)
    for kind, a, b, name in edges:
        if kind != "U":
            continue
        if union.find(a) == union.find(b):
            todo, previous = deque([a]), {a: None}
            while todo and b not in previous:
                node = todo.popleft()
                for other, component in graph.get(node, []):
                    if other not in previous:
                        previous[other] = (node, component)
                        todo.append(other)
            loop, node = [name], b
            while previous[node] is not None:
                node, component = previous[node]
                loop.append(component)
            return loop
        add(a, b, name)
    return None


def _interface(instance, child):
    """Accept only the native side/order contract verified by our authoring API."""
    params = instance["parameters"]
    if params.get("Scm") or params.get("Actual"):
        return None, "Native instance overrides are outside the verified interface contract."
    pins = params.get("Pins")
    if not isinstance(pins, dict):
        return None, "Missing native Pins mapping."
    ports = [o for o in child["objects"] if o["Type"] == 400 and not o["Name"].startswith("_")]
    ordered = []
    for side, rotation, axis in SIDES:
        expected = pins.get(side) or []
        actual = [p for p in ports if p.get("Rot", 0) == rotation]
        if any(p.get("FlipV", 0) or p.get("FlipH", 0) or type(p.get(axis)) is not int for p in actual):
            return None, "Flipped or noninteger PORT geometry has not been verified."
        actual.sort(key=lambda p:p[axis])
        if [p["Name"] for p in actual] != expected or len({p[axis] for p in actual}) != len(actual):
            return None, "Native PORT side/coordinate order differs from the declared Pins mapping."
        ordered.extend(expected)
    if len(ordered) != len(ports) or len(ordered) != len(instance["native_pin_nodes"]):
        return None, "Native PORT count differs from instance terminal count."
    return list(zip(ordered, instance["native_pin_nodes"])), None


def check_transient_project(root_path, assets, check_cancelled=lambda: None):
    """Check local active loops and provable cross-instance connections.

    Unsupported interfaces and expansion limits are explicit partial coverage;
    they do not invent a pin mapping or reject otherwise supported native runs.
    """
    root = Path(root_path).resolve()
    records = {}
    for asset in assets:
        check_cancelled()
        path, document, encoding = _load(asset["private_path"])
        records[path] = _summarize(document, path, encoding)
    report = {"scope": "Active local U/C loops and cross-instance loops with verified native PORT geometry; other singularities are not checked",
              "checked_models": [], "ignored_test_components": [], "skipped_interfaces": [],
              "expanded_instances": 0, "checked_edges": 0, "complete": True,
              "ignored_test_component_count": 0}

    def active_components(path, root_context=False):
        return [c for c in records[path]["components"] if root_context or not c["name"].startswith("_")]

    def dependency(path, instance):
        reference = Path(instance["parameters"]["FileName"].replace("\\", os.sep))
        child = (path.parent/reference).resolve()
        if child not in records:
            raise SchemeError("Transient preflight dependency escaped the prepared project.")
        return child

    active, todo = set(), [(root, True)]
    while todo:
        check_cancelled()
        path, root_context = todo.pop()
        if (path, root_context) in active:
            continue
        active.add((path, root_context))
        components = active_components(path, root_context)
        for component in records[path]["components"]:
            if not root_context and component["name"].startswith("_"):
                report["ignored_test_component_count"] += 1
                if len(report["ignored_test_components"]) < 100:
                    report["ignored_test_components"].append({"model_path": str(path), "name": component["name"]})
        edges = [(c["kind"], *c["nodes"], c["name"]) for c in components if c["native_type"] in {1001, 2010}]
        loop = voltage_loop(edges)
        if loop:
            raise TopologyError(path, loop, report)
        if str(path) not in report["checked_models"]:
            report["checked_models"].append(str(path))
        todo.extend((dependency(path, c), False) for c in reversed(components) if c["native_type"] == 7100)

    union, edges = _Union(), []
    grounded = {path: any(o["Type"] == 200 for o in summary["objects"]) for path, summary in records.items()}

    def node(scope, name, path):
        return ("__global_ground__",) if name == "0" and grounded[path] else (scope, name)

    def skip(prefix, reason):
        report["complete"] = False
        if len(report["skipped_interfaces"]) < 100:
            report["skipped_interfaces"].append({"instance": ".".join(prefix), "reason": reason})

    def expand(path, scope=(), prefix=(), root_context=False):
        check_cancelled()
        if report["expanded_instances"] >= MAX_INSTANCES or len(edges) >= MAX_EDGES:
            skip(prefix, "Preflight expansion limit reached; native circuit was not changed.")
            return
        report["expanded_instances"] += 1
        for component in active_components(path, root_context):
            check_cancelled()
            name = (*prefix, component["name"])
            if component["native_type"] in {1001, 2010}:
                a, b = component["nodes"]
                edges.append((component["kind"], node(scope,a,path), node(scope,b,path), ".".join(name)))
            elif component["native_type"] == 7100:
                child = dependency(path, component)
                connections, reason = _interface(component, records[child])
                if connections is None:
                    skip(name, reason)
                    continue
                child_scope = (*scope, component["native_id"])
                for port, parent_node in connections:
                    union.join(node(scope,parent_node,path), node(child_scope,records[child]["ports"][port],child))
                expand(child, child_scope, name)
    expand(root, root_context=True)
    report["checked_edges"] = len(edges)
    loop = voltage_loop([(kind,union.find(a),union.find(b),name) for kind,a,b,name in edges])
    if loop:
        raise TopologyError(root, loop, report)
    report["status"] = "passed" if report["complete"] else "partial"
    return report
