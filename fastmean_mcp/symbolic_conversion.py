"""Verified linear FASTMEAN-to-CIRSYM conversion, without an algebra solver.

The numerical values in CIRSYM input are defaults for formal element symbols.
Linear multiports are expanded into exact controlled-source equivalents. Their
parameter substitutions are explicit and never alter retained native output.
"""
from __future__ import annotations

import copy
import re
from typing import Any


SUPPORTED_KINDS = frozenset({"R", "C", "L", "U", "I", "G", "E", "F", "H",
                             "OPAMP", "TR", "TR3", "GYR", "SUM", "UNI"})
_ALIASES = {"V": "U", "VCCS": "G", "VCVS": "E", "CCCS": "F", "CCVS": "H",
            "TRANSFORMER": "TR", "TR2": "TR", "GYRATOR": "GYR", "SUMMATOR": "SUM",
            "UNISTOR": "UNI", "OA": "OPAMP"}
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_ANALYSES = {"voltage", "current", "transfer", "impedance", "admittance"}


def symbolic_capabilities() -> dict[str, Any]:
    return {"component_kinds": sorted(SUPPORTED_KINDS), "analyses": sorted(_ANALYSES),
            "native_primitive_prefixes": {"U": "E", "I": "J", "E": "K", "G": "G", "F": "F", "H": "H"},
            "initial_conditions": "zero only", "value_expressions": "numeric SI values only; native defaults do not parse arithmetic",
            "hierarchy": "native flattened netlist with explicit leaf component kinds",
            "multiple_sources": "supported for output equations; normalization requires one independent source",
            "current_probes": "series sensors in R/C/L/U/I/UNI branches; positive from first public node to second"}


def component_kinds_from_export(exported):
    """Follow only the validated private models in a native export manifest."""
    from pathlib import Path
    from .schematic import _load,KINDS
    records=exported.get("source_models") or []
    if not records:
        raise ValueError("Native export has no validated model provenance.")
    allowed={Path(record["private_path"]).resolve() for record in records}
    result={}
    def visit(path,prefix,active,child=False):
        path=Path(path).resolve()
        if path not in allowed or path in active or len(active)>32:
            raise ValueError("Symbolic hierarchy escapes its private manifest or recurses actively.")
        _,document,_=_load(path)
        for obj in document["scm"]["Scheme"].get("Objects") or []:
            tid=obj["Type"];name=str(obj.get("Name",""))
            if tid in {200,300,400,410,420,900} or child and name.startswith("_"):
                continue
            qualified=prefix+name
            if tid==7100:
                params=obj.get("Params") or {}
                if set(params)-{"FileName","Pins"}:
                    raise ValueError("Symbolic instance parameter overrides are not supported.")
                visit(path.parent/params["FileName"],qualified+".",active|{path},True)
            else:
                if len(result)>=10000 or qualified in result:
                    raise ValueError("Native symbolic hierarchy exceeds limits or has ambiguous names.")
                result[qualified]=KINDS.get(tid,f"TYPE_{tid}")
    visit(records[0]["private_path"],"",set())
    return result


def _kind(value: Any) -> str:
    name = str(value).upper()
    return _ALIASES.get(name, name)


def _value(value: Any) -> float:
    from .symbolic import _parse_value
    return _parse_value(value)


def _parameters(component: dict, keys: tuple[str, ...]) -> dict[str, float]:
    name = component["name"]
    supplied = component.get("parameters")
    if supplied is None:
        if len(keys) != 1:
            raise ValueError(f"{name}: parameters must contain exactly {', '.join(keys)}")
        return {keys[0]: _value(component.get("value"))}
    if "value" in component or not isinstance(supplied, dict) or set(supplied) != set(keys):
        raise ValueError(f"{name}: supply value or parameters containing exactly {', '.join(keys)}")
    return {key: _value(supplied[key]) for key in keys}


def _normalize(component: dict, numbers: list[int]) -> dict:
    from .symbolic import _voltage_value
    kind, name = component["kind"], component["name"]
    expected = 6 if kind == "TR3" else 4 if kind in {"G", "E", "F", "H", "TR", "GYR"} else 3 if kind == "OPAMP" else 2
    parameters = {}
    if kind == "SUM":
        raw = component.get("parameters")
        if not isinstance(raw, dict) or set(raw) != {"N", "k"} or type(raw["N"]) is not int or not 1 <= raw["N"] <= 5:
            raise ValueError(f"{name}: SUM requires integer N in 1..5 and a numeric k list")
        if not isinstance(raw["k"], list) or len(raw["k"]) != raw["N"]:
            raise ValueError(f"{name}: SUM coefficient count must equal N")
        parameters = {"N": raw["N"], "k": [_value(k) for k in raw["k"]]}
        expected = raw["N"] + 2
    if len(numbers) != expected:
        raise ValueError(f"component {name} must have exactly {expected} nodes in native pin order")
    if expected == 2 and numbers[0] == numbers[1]:
        raise ValueError(f"component {name} connects a terminal pair to itself")
    if kind in {"TR", "TR3"} and (numbers[0] == numbers[1] or numbers[2] == numbers[3]):
        raise ValueError(f"component {name} connects a winding to itself")
    if kind == "TR3" and numbers[4] == numbers[5]:
        raise ValueError(f"component {name} connects a winding to itself")
    if kind in {"R", "C", "L"}:
        value = _value(component.get("value"))
        if value <= 0:
            raise ValueError(f"{kind} component {name} must have a positive value")
        if kind in {"C", "L"} and _value(component.get("initial_condition", 0)) != 0:
            raise ValueError(f"{kind} component {name} has nonzero initial conditions; zero-state symbolic analysis would discard them")
    elif kind in {"U", "I"}:
        value = _voltage_value(component)
    elif kind != "SUM":
        keys = {"G": ("g",), "E": ("k",), "F": ("h",), "H": ("r",), "OPAMP": ("k",),
                "TR": ("n",), "TR3": ("n1", "n2"), "GYR": ("S",), "UNI": ("S",)}[kind]
        parameters = _parameters(component, keys)
        if kind in {"TR", "TR3"} and any(v <= 0 for v in parameters.values()):
            raise ValueError(f"{name}: transformer ratios must be positive")
        value = next(iter(parameters.values()))
    else:
        value = None
    if kind not in {"U", "I"} and "waveform" in component:
        raise ValueError(f"{kind} component {name} cannot have a source waveform")
    return {"name": name, "kind": kind, "nodes": numbers, "value": value, "parameters": parameters}


def _edges(component: dict) -> list[tuple[int, int]]:
    kind, nodes = component["kind"], component["nodes"]
    if kind == "OPAMP":
        return [(nodes[0], nodes[1]), (nodes[2], 0)]
    if kind == "SUM":
        return [(n, nodes[1]) for n in nodes if n != nodes[1]]
    return list(zip(nodes[::2], nodes[1::2]))


def _render(components: list[dict], probe, output, input, *, analysis: str, output_reference,
            output_element: str | None, input_source: str | None) -> dict[str, Any]:
    from .symbolic import _require_grounded_graph
    if analysis not in _ANALYSES:
        raise ValueError("analysis must be one of " + ", ".join(sorted(_ANALYSES)))
    _require_grounded_graph([edge for c in components for edge in _edges(c)])
    sources = [c for c in components if c["kind"] in {"U", "I"}]
    if not sources:
        raise ValueError("native symbolic analysis requires at least one independent source")
    normalize = analysis in {"transfer", "impedance", "admittance"} or input is not None or input_source is not None
    source = None
    if normalize:
        if len(sources) != 1:
            raise ValueError("normalization requires exactly one independent source; use input=None and analysis='voltage' or 'current' for multi-input equations")
        source = sources[0]
        if input_source is not None and source["name"] != input_source:
            raise ValueError(f"input_source {input_source!r} does not name the independent source")
        if source["value"] == 0:
            raise ValueError("a transfer-function input amplitude must be nonzero; use input=None for the native output equation only")
        if analysis == "voltage" and input is not None:
            node = probe(input, "input")
            if source["kind"] != "U" or source["nodes"] != [node, 0]:
                raise ValueError("transfer-function input must be the positive node of the single independent voltage source, whose negative terminal must be grounded")
        if analysis == "impedance" and source["kind"] != "I":
            raise ValueError("impedance requires an independent current source (Z=U/J)")
        if analysis == "admittance" and source["kind"] != "U":
            raise ValueError("admittance requires an independent voltage source (Y=I/E)")
    current = analysis in {"current", "admittance"} or output_element is not None
    if analysis == "impedance" and current:
        raise ValueError("impedance requires a voltage output, not output_element")
    if analysis == "admittance" and output_element is None:
        output_element = source["name"]
    max_node = max(n for c in components for n in c["nodes"])
    def auxiliary() -> int:
        nonlocal max_node
        max_node += 1
        if max_node > 2_147_483_647:
            raise ValueError("no native node numbers remain for a series probe or linear equivalent")
        return max_node
    work = copy.deepcopy(components)
    if current:
        branch = next((c for c in work if c["name"] == output_element), None)
        if branch is None or branch["kind"] not in {"R", "C", "L", "U", "I", "UNI"}:
            raise ValueError("output_element must name a two-terminal R/C/L/U/I/UNI branch")
        first, second = branch["nodes"]
        middle = auxiliary()
        branch["nodes"][1] = middle
        # A driving-point Y uses current delivered by its voltage test source.
        delivered = analysis == "admittance" and branch["name"] == source["name"]
        sensor = (second, middle) if delivered else (middle, second)
        observable = {"kind": "current", "element": branch["name"], "nodes": [first, second],
                      "positive_direction": "source-delivered current" if delivered else "first public node to second"}
        equation = "I1"
    else:
        first = probe(output, "output")
        second = 0 if str(output_reference).lower() in {"0", "gnd", "ground"} else probe(output_reference, "output_reference")
        if first == second:
            raise ValueError("output and output_reference must be different nodes")
        sensor = (first, second)
        observable = {"kind": "voltage", "nodes": [first, second], "positive_direction": "first node minus reference"}
        equation = "U1"
    lines = ["--- Converted for the native FASTMEAN CIRSYM worker ---", ""]
    used: set[str] = set()
    alias_counts={}
    aliases={}
    substitutions, physical = {}, {}
    def emit(prefix: str, suffix: str, nodes: list[int], value=None, physical_name=None) -> str:
        # The native worker conflates some long names with equal prefixes.
        # Short numbered identifiers avoid that loss of component identity.
        alias_counts[prefix]=alias_counts.get(prefix,0)+1
        if alias_counts[prefix]>999:
            raise ValueError("Native CIRSYM supports at most 999 uniquely aliased elements per type.")
        name = prefix + str(alias_counts[prefix])
        aliases[name]=suffix
        if name.casefold() in used:
            raise ValueError(f"generated CIRSYM parameter collision: {name}")
        used.add(name.casefold())
        tail = "" if value is None else f" {value:.17g}"
        lines.append(name + " " + " ".join(map(str, nodes)) + tail)
        if physical_name is not None:
            substitutions[name] = physical_name
        return name
    for c in work:
        kind, original, n, value, p = c["kind"], c["name"], c["nodes"], c["value"], c["parameters"]
        safe = original if _NAME.fullmatch(original) else "component_" + str(work.index(c) + 1)
        native_names = []
        if kind in {"R", "C", "L", "U", "I"}:
            prefix = {"R": "R", "C": "c", "L": "L", "U": "E", "I": "J"}[kind]
            native_names.append(emit(prefix, safe, list(reversed(n)) if kind == "U" else n, value))
            physical[native_names[0]] = value
        elif kind in {"G", "E", "F", "H"}:
            native_names.append(emit("K" if kind == "E" else kind, safe, [n[3], n[2], n[0], n[1]], value))
            physical[native_names[0]] = value
        elif kind == "OPAMP":
            native_names.append(emit("K", safe, [0, n[2], n[0], n[1]], value))
            physical[native_names[0]] = value
        elif kind == "UNI":
            parameter = "S_" + safe
            physical[parameter] = value
            native_names.append(emit("G", safe, [n[0], n[1], n[0], 0], value, parameter))
        elif kind == "GYR":
            parameter = "S_" + safe
            physical[parameter] = value
            native_names.extend([emit("G", safe + "_reverse", n, value, parameter),
                                 emit("G", safe + "_forward", [n[3], n[2], n[0], n[1]], value, parameter)])
        elif kind in {"TR", "TR3"}:
            for index in range(1 if kind == "TR" else 2):
                ratio = p["n" if kind == "TR" else "n" + str(index + 1)]
                parameter = ("n_" if kind == "TR" else "n" + str(index + 1) + "_") + safe
                physical[parameter] = ratio
                internal = auxiliary()
                high, low = n[2 + 2 * index:4 + 2 * index]
                suffix = safe + "_" + str(index + 1)
                native_names.extend([emit("K", suffix, [low, internal, n[0], n[1]], 1 / ratio, "1/" + parameter),
                                     emit("F", suffix, [n[0], n[1], internal, high], 1 / ratio, "1/" + parameter)])
        elif kind == "SUM":
            previous = n[1]
            for index, coefficient in enumerate(p["k"]):
                following = n[0] if index == p["N"] - 1 else auxiliary()
                parameter = "k" + str(index + 1) + "_" + safe
                physical[parameter] = coefficient
                native_names.append(emit("K", safe + "_" + str(index + 1), [previous, following, n[index + 2], n[1]], coefficient, parameter))
                previous = following
        c["native_name"], c["native_names"] = native_names[0], native_names
    input_parameter = next((c["native_name"] for c in work if source and c["name"] == source["name"]), None)
    lines.extend(["", f"{equation} {sensor[0]} {sensor[1]}", "", ".END", ""])
    for original, compiled in zip(components, work):
        original["native_name"], original["native_names"] = compiled["native_name"], compiled["native_names"]
    quantity = "Z" if analysis == "impedance" else "Y" if analysis == "admittance" else "H" if input_parameter else "I" if current else "U"
    units = "ohm" if quantity == "Z" else "siemens" if quantity == "Y" else "A" if quantity == "I" else "V" if quantity == "U" else (
        "A/A" if current and source["kind"] == "I" else "A/V" if current else "V/A" if source["kind"] == "I" else "V/V")
    return {"netlist": "\r\n".join(line for line in lines if line), "components": components, "output_equation": equation,
            "input_parameter": input_parameter, "transfer_relation": equation + "/" + input_parameter if input_parameter else None,
            "observable": observable, "analysis": analysis, "function_name": quantity + "(p)", "units": units,
            "parameter_substitutions": substitutions, "symbolic_parameters": physical,
            "native_aliases": aliases,
            "analysis_mode": "native multi-input single-output polynomial" if len(sources) > 1 else "native single-input single-output polynomial"}


def netlist_from_spec(spec: dict[str, Any], output_node: str = "out", input_node: str | None = None, *,
                      analysis: str = "voltage", output_reference: str = "0", output_element: str | None = None,
                      input_source: str | None = None) -> dict[str, Any]:
    """Convert a flat shared spec using verified CIRSYM signs and equivalents."""
    from .symbolic import _node
    if not isinstance(spec, dict) or not isinstance(spec.get("components"), list) or not spec["components"]:
        raise ValueError("spec.components must be a nonempty list")
    numbers, names, components = {"0": 0}, set(), []
    for raw in spec["components"]:
        if not isinstance(raw, dict):
            raise ValueError("each component must be an object")
        kind = _kind(raw.get("kind", raw.get("type", "")))
        if "kind" in raw and "type" in raw and kind != _kind(raw["type"]):
            raise ValueError("component kind and type disagree")
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"native symbolic conversion does not support {kind!r}; linear subcircuits need native flattened save_netlist and leaf kinds")
        name = raw.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("native component names must be ASCII letters/digits/underscores and start with a letter or underscore")
        if name.casefold() in names:
            raise ValueError(f"duplicate component name: {name}")
        names.add(name.casefold())
        nodes = raw.get("nodes")
        if not isinstance(nodes, (list, tuple)):
            raise ValueError(f"component {name} needs a nodes list")
        mapped = []
        for value in nodes:
            node = _node(value)
            if node not in numbers:
                numbers[node] = len(numbers)
            mapped.append(numbers[node])
        components.append(_normalize(dict(raw, kind=kind), mapped))
    def probe(value, role):
        node = _node(value)
        if node not in numbers or node == "0":
            raise ValueError(f"{role} node {value!r} must be an existing nonground circuit node")
        return numbers[node]
    result = _render(components, probe, output_node, input_node, analysis=analysis, output_reference=output_reference,
                     output_element=output_element, input_source=input_source)
    result["node_map"] = numbers
    return result


def cirsym_from_fastmean_netlist(text: str, output: str = "OUT", input: str | None = "IN",
                               component_kinds: dict[str, str] | None = None, *, analysis: str = "voltage",
                               output_reference: str = "0", output_element: str | None = None,
                               input_source: str | None = None) -> dict[str, Any]:
    """Convert real native exported numeric defaults; never infer renamed parts."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("native FASTMEAN netlist text must be nonempty")
    if component_kinds is not None and not isinstance(component_kinds, dict):
        raise ValueError("component_kinds must map native instance names to component kinds")
    kinds = {str(k): _kind(v) for k, v in (component_kinds or {}).items()}
    ports, components, names, nodes = {}, [], set(), {0}
    def node(token, line):
        if not re.fullmatch(r"\d+", token) or int(token) > 2_147_483_647:
            raise ValueError(f"invalid native node {token!r} on line {line}")
        return int(token)
    canonical = r"(TR3|OPAMP|GYR|SUM|UNI|TR|[RCLUIGEFH])\d+"
    for line_number, line in enumerate(text.splitlines(), 1):
        fields = line.strip().split()
        if not fields or fields[0].startswith(("*", "%")):
            continue
        name = fields[0]
        if name.startswith("."):
            raise ValueError(f"native netlist directive {name!r} is unsupported for symbolic conversion (line {line_number})")
        if len(fields) == 2:
            if name in kinds or re.fullmatch(canonical, name, re.I):
                raise ValueError(f"native component {name!r} is missing terminals/value on line {line_number}")
            number = node(fields[1], line_number)
            if name in ports and ports[name] != number:
                raise ValueError(f"native port {name!r} maps to inconsistent nodes")
            ports[name] = number
            continue
        if len(fields) < 4:
            raise ValueError(f"unsupported native netlist row on line {line_number}: {line.strip()}")
        if name.casefold() in names:
            raise ValueError(f"duplicate native element name {name!r}")
        names.add(name.casefold())
        if component_kinds is not None:
            if name not in kinds:
                raise ValueError(f"native element {name!r} has no explicit component kind")
            kind = kinds[name]
        else:
            match = re.fullmatch(canonical, name, re.I)
            if match is None:
                raise ValueError(f"cannot infer the kind of renamed element {name!r}; supply component_kinds")
            kind = _kind(match[1])
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"native symbolic conversion does not support {kind!r} element {name!r}")
        count = 6 if kind == "TR3" else 4 if kind in {"G", "E", "F", "H", "TR", "GYR"} else 3 if kind == "OPAMP" else 2
        raw = {"name": name, "kind": kind}
        if kind == "SUM":
            # Native6.1 export: name N k1 ... kN output common input1 ... inputN.
            if len(fields) < 6 or not fields[1].isdigit():
                raise ValueError(f"unsupported native SUM declaration for {name!r}")
            size = int(fields[1])
            if not 1<=size<=5 or len(fields)!=2*size+4:
                raise ValueError(f"unsupported native SUM declaration for {name!r}")
            count = size + 2
            raw["parameters"] = {"N": size, "k": fields[2:2+size]}
        elif kind in {"U", "I"}:
            if len(fields) < 5 or fields[3].upper() not in {"DC", "AC"}:
                raise ValueError(f"native source {name!r} must use DC or AC; waveform Laplace transforms are not synthesized")
            raw["value"] = fields[4]
        elif kind in {"C", "L"}:
            if len(fields) not in {4, 5}:
                raise ValueError(f"unsupported extra parameters for native {kind} element {name!r}")
            raw.update(value=fields[3], initial_condition=fields[4] if len(fields) == 5 else 0)
        else:
            keys = ("n1", "n2") if kind == "TR3" else None
            if len(fields) != 1 + count + (2 if keys else 1):
                raise ValueError(f"unsupported extra parameters for native {kind} element {name!r}")
            if keys:
                raw["parameters"] = dict(zip(keys, fields[1 + count:]))
            else:
                raw["value"] = fields[-1]
        mapped = [node(token, line_number) for token in (fields[2+size:] if kind=="SUM" else fields[1:1 + count])]
        if kind == "U":
            mapped.reverse()  # Native save_netlist U is [negative, positive].
        nodes.update(mapped)
        components.append(_normalize(raw, mapped))
    if not components:
        raise ValueError("native FASTMEAN netlist contains no supported circuit elements")
    def probe(value, role):
        token = str(value)
        if token in ports:
            number = ports[token]
        elif re.fullmatch(r"\d+", token):
            number = int(token)
        else:
            raise ValueError(f"{role} {value!r} is not a native port or integer node")
        if number == 0 or number not in nodes:
            raise ValueError(f"{role} {value!r} must refer to an existing nonground circuit node")
        return number
    result = _render(components, probe, output, input, analysis=analysis, output_reference=output_reference,
                     output_element=output_element, input_source=input_source)
    result.update(ports=ports, conversion="native FASTMEAN save_netlist to CIRSYM; linear zero-state circuit")
    return result


def derive_symbolic_function(native: dict[str, Any], conversion: dict[str, Any]) -> dict[str, Any] | None:
    """Name/normalize a native expression and substitute equivalent parameters.

    This is token replacement and division, not simplification or a new solver.
    The original CIRSYM equations and defaults remain unchanged in ``native``.
    """
    if not native.get("ok"):
        return None
    equation = next((eq for eq in native.get("equations", []) if eq["name"] == conversion["output_equation"]), None)
    if equation is None:
        return None
    substitutions = conversion.get("parameter_substitutions", {})
    expression = re.sub(r"\b[A-Za-z_]\w*\b", lambda m: "(" + substitutions[m[0]] + ")" if m[0] in substitutions else m[0], equation["expression"])
    parameter = conversion.get("input_parameter")
    if parameter:
        expression = "(" + expression + ")/(" + parameter + ")"
    return {"name": conversion["function_name"], "expression": expression, "units": conversion["units"],
            "parameters": conversion["symbolic_parameters"], "native_equation": equation["name"],
            "input_parameter": parameter, "parameter_substitutions": substitutions,
            "origin": "Native CIRSYM equation with explicit linear-equivalent parameter substitutions and optional source-amplitude division"}
