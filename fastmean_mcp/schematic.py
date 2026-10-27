"""Read and author FASTMEAN 5.x text SCM files without starting FASTMEAN.

Creation supports R/C/L/U/I, fixed native diode, controlled-source, ideal
transformer and voltage-controlled switch primitives, and named native
subcircuit instances. Names used by the native analysis engine
are ASCII identifiers. Existing UTF-8 and Windows-1251 diagrams, including
Russian labels, can be read without rewriting.

Native templates were checked against FASTMEAN 6.1 bundled examples and the
successfully opened RC_formula_test.scm. A wire stores object ID and terminal
number, not a pixel endpoint. New diagrams use adjacent symbols and orthogonal
wires through native junctions. Named ports are reserved for external signals
and analysis probes, rather than repeated on every component terminal.
"""
from __future__ import annotations

import copy
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

import yaml

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_COMPONENTS = 200
TYPE_IDS = {"R": 1000, "C": 1001, "L": 1002, "U": 2010,
            "D": 1101, "G": 6000, "E": 6001, "F": 6002, "TR": 6101, "SW": 6600, "X": 7100,
            "I": 3010, "GND": 200, "CON": 300, "PORT": 400, "TEXT": 900}
KINDS = {value: key for key, value in TYPE_IDS.items()}
PIN_COUNTS = {1000: 2, 1001: 2, 1002: 2, 2010: 2, 3010: 2,
              1101: 2, 6000: 4, 6001: 4, 6002: 4, 6101: 4, 6600: 4,
              200: 1, 300: 4, 400: 1, 900: 0}
CREATE_KINDS = frozenset({"R", "C", "L", "U", "I", "D", "G", "E", "F", "TR", "SW", "X"})
EDIT_KINDS = frozenset({"R", "C", "L", "U", "I"})
_SIDES = ("Left", "Top", "Right", "Bottom")
_KIND_ALIASES = {"V": "U", "DIODE": "D", "VCCS": "G", "VCVS": "E", "CCCS": "F", "SUB": "X",
                 "TRANSFORMER": "TR", "VCSWITCH": "SW"}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMBER = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-zµμА-Яа-я]*)$")
_MULTIPLIERS = {"": 1., "k": 1e3, "K": 1e3, "M": 1e6, "meg": 1e6,
                "Meg": 1e6, "MEG": 1e6, "G": 1e9, "T": 1e12,
                "m": 1e-3, "u": 1e-6, "µ": 1e-6, "μ": 1e-6,
                "n": 1e-9, "p": 1e-12, "f": 1e-15,
                "к": 1e3, "К": 1e3, "М": 1e6, "Г": 1e9,
                "м": 1e-3, "мк": 1e-6, "н": 1e-9, "п": 1e-12, "ф": 1e-15}


class SchemeError(ValueError):
    """Invalid, unsupported or unsafe SCM input/specification."""


class _UniqueLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise SchemeError("YAML aliases are unsupported in SCM input.")
        return super().compose_node(parent, index)


# FASTMEAN uses ordinary mapping keys such as PSD.On. YAML 1.1's resolver
# interprets On/Off/Yes/No as booleans, corrupting those keys on a value edit.
# Copy the resolver lists so the change remains local to SCM loading.
_UniqueLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in resolvers
          if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _unique_mapping(loader: yaml.SafeLoader, node: Any, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise SchemeError("Complex YAML mapping keys are unsupported.") from error
        if duplicate:
            raise SchemeError(f"Duplicate YAML mapping key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


class _IndentedDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def parse_value(value: Any) -> float:
    """Parse a finite SI number, including explicit case-sensitive suffixes.

    M means mega; m means milli. Russian engineering suffixes are accepted on
    input, but generated native YAML stores numeric SI values without suffixes.
    """
    if isinstance(value, bool):
        raise SchemeError("A boolean is not an electrical value.")
    if isinstance(value, (int, float)):
        try:
            result = float(value)
        except OverflowError as error:
            raise SchemeError("Electrical value is outside the finite numeric range.") from error
    elif isinstance(value, str):
        match = _NUMBER.fullmatch(value.strip())
        if not match or match[2] not in _MULTIPLIERS:
            raise SchemeError(f"Unsupported electrical value {value!r}; use a number or SI suffix.")
        result = float(match[1]) * _MULTIPLIERS[match[2]]
    else:
        raise SchemeError("Electrical values must be numbers or SI strings.")
    if not math.isfinite(result):
        raise SchemeError("Electrical values must be finite.")
    return result


def normalize_node(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SchemeError("Node names must be strings or integer labels.")
    name = str(value).strip()
    if name.casefold() in {"0", "gnd", "ground"}:
        return "0"
    if not name or (not name.isdecimal() and not IDENTIFIER.fullmatch(name)):
        raise SchemeError(f"Invalid node {name!r}; use an ASCII identifier or an integer.")
    return name


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise SchemeError(f"{label} must be an ASCII identifier (letters, digits, underscore).")
    return value


def _decode(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise SchemeError(f"SCM file exceeds {MAX_FILE_BYTES} bytes.")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text, encoding = raw.decode("utf-16"), "utf-16"
    else:
        try:
            text, encoding = raw.decode("utf-8-sig"), "utf-8"
        except UnicodeDecodeError:
            try:
                text, encoding = raw.decode("cp1251", errors="strict"), "windows-1251"
            except UnicodeDecodeError as error:
                raise SchemeError("Unsupported text encoding or legacy binary SCM; expected UTF-8 or Windows-1251 text.") from error
    if "\x00" in text or not text.lstrip().startswith("scm:"):
        raise SchemeError("Only the FASTMEAN text SCM format is supported; this may be an old binary SCM.")
    return text, encoding


def _load(path: str | Path) -> tuple[Path, dict, str]:
    source = Path(path).expanduser().resolve(strict=True)
    text, encoding = _decode(source)
    try:
        document = yaml.load(text, Loader=_UniqueLoader)
    except (yaml.YAMLError, RecursionError) as error:
        raise SchemeError(f"Invalid SCM YAML: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("scm"), dict):
        raise SchemeError("SCM must contain a mapping named 'scm'.")
    body = document["scm"]
    if not isinstance(body.get("Scheme"), dict):
        raise SchemeError("SCM has no Scheme mapping.")
    objects = body["Scheme"].get("Objects") or []
    wires = body["Scheme"].get("Wires") or []
    if not isinstance(objects, list) or not isinstance(wires, list):
        raise SchemeError("Scheme.Objects and Scheme.Wires must be lists.")
    if len(objects) > 10000 or len(wires) > 50000:
        raise SchemeError("SCM exceeds supported object/wire limits.")
    return source, document, encoding


class _Union:
    def __init__(self):
        self.parent: dict[tuple[int, int], tuple[int, int]] = {}

    def find(self, item: tuple[int, int]) -> tuple[int, int]:
        self.parent.setdefault(item, item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            previous = self.parent[item]
            self.parent[item] = root
            item = previous
        return root

    def join(self, a: tuple[int, int], b: tuple[int, int]) -> None:
        self.parent[self.find(a)] = self.find(b)


def _subcircuit_pin_names(obj: dict) -> list[str]:
    """Native numbering follows Left, Top, Right, Bottom, in list order."""
    params = obj.get("Params") or {}
    pins = params.get("Pins") if isinstance(params, dict) else None
    if pins is None:
        return []  # Preserve inspection of legacy/partially specified objects.
    if not isinstance(pins, dict) or set(pins) - set(_SIDES):
        raise SchemeError("A native subcircuit Pins field must contain side lists.")
    result = []
    for side in _SIDES:
        names = pins.get(side)
        if names is None:  # Native saved files use null for empty sides.
            names = []
        if not isinstance(names, list) or any(not isinstance(name, str) or not name for name in names):
            raise SchemeError("A native subcircuit pin must have a nonempty name.")
        result.extend(names)
    if len(result) > 64:
        raise SchemeError("A native subcircuit exceeds 64 inspected pins.")
    return result


def _pin_count(obj: dict) -> int:
    return len(_subcircuit_pin_names(obj)) if obj.get("Type") == 7100 else PIN_COUNTS.get(obj.get("Type"), 0)


def _summarize(document: dict, path: Path, encoding: str) -> dict:
    body = document["scm"]
    scheme = body["Scheme"]
    objects = scheme.get("Objects") or []
    wires = scheme.get("Wires") or []
    by_id: dict[int, dict] = {}
    uf = _Union()
    port_terminals: dict[str, tuple[int, int]] = {}
    ground: tuple[int, int] | None = None
    warnings = []
    for obj in objects:
        if not isinstance(obj, dict) or not isinstance(obj.get("ID"), int) or isinstance(obj["ID"], bool):
            raise SchemeError("Each SCM object needs an integer ID.")
        oid = obj["ID"]
        if oid <= 0 or not isinstance(obj.get("Type"), int) or isinstance(obj["Type"], bool):
            raise SchemeError("SCM object IDs must be positive and Type must be an integer.")
        if oid in by_id:
            raise SchemeError(f"Duplicate object ID {oid}.")
        by_id[oid] = obj
        kind = obj.get("Type")
        for pin in range(1, _pin_count(obj) + 1):
            uf.find((oid, pin))
        if kind == 300:
            for pin in range(2, 5):
                uf.join((oid, 1), (oid, pin))
        elif kind == 200:
            if ground is None:
                ground = (oid, 1)
            else:
                uf.join(ground, (oid, 1))
        elif kind == 400:
            name = str(obj.get("Name", ""))
            if not name:
                raise SchemeError("A PORT object has no node label.")
            if name in port_terminals:
                uf.join(port_terminals[name], (oid, 1))
            else:
                port_terminals[name] = (oid, 1)
    for wire in wires:
        ends = []
        if not isinstance(wire, dict):
            raise SchemeError("Wire must be a mapping.")
        for key in ("obj1", "obj2"):
            end = wire.get(key)
            if not isinstance(end, dict):
                raise SchemeError(f"Wire has no {key} endpoint.")
            oid, pin = end.get("ID"), end.get("pin")
            if oid not in by_id or isinstance(oid, bool):
                raise SchemeError(f"Wire refers to absent object {oid}.")
            endpoint_object = by_id[oid]
            if endpoint_object.get("Type") == 7100:
                endpoint_params = endpoint_object.get("Params") or {}
                limit = _pin_count(endpoint_object) if endpoint_params.get("Pins") is not None else 64
            else:
                limit = PIN_COUNTS.get(endpoint_object.get("Type"), 64)
            if not isinstance(pin, int) or isinstance(pin, bool) or not 1 <= pin <= limit:
                raise SchemeError(f"Invalid terminal {oid}:{pin}.")
            ends.append((oid, pin))
        uf.join(*ends)

    roots: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for terminal in list(uf.parent):
        roots.setdefault(uf.find(terminal), []).append(terminal)
    labels: dict[tuple[int, int], list[str]] = {}
    for name, terminal in port_terminals.items():
        labels.setdefault(uf.find(terminal), []).append(name)
    ground_root = uf.find(ground) if ground else None
    names = {}
    used = {"0"}
    unnamed = 1
    for root, terminals in sorted(roots.items(), key=lambda item: min(item[1])):
        if root == ground_root:
            name = "0"
        elif labels.get(root):
            name = labels[root][0]
        else:
            while f"n{unnamed}" in used or f"n{unnamed}" in port_terminals:
                unnamed += 1
            name = f"n{unnamed}"
            unnamed += 1
        if name in used and name != "0":
            raise SchemeError("Ambiguous node labels in SCM.")
        used.add(name)
        names[root] = name

    components = []
    unsupported = set()
    for obj in objects:
        tid, oid = obj.get("Type"), obj["ID"]
        if tid in {200, 300, 400, 900}:
            continue
        kind = KINDS.get(tid)
        native_nodes = [names[uf.find((oid, pin))] for pin in range(1, _pin_count(obj) + 1)]
        params = copy.deepcopy(obj.get("Params") or {})
        item = {"name": str(obj.get("Name", f"object_{oid}")), "type": kind or f"TYPE_{tid}",
                "kind": kind or f"TYPE_{tid}", "native_id": oid, "native_type": tid,
                "native_pin_nodes": native_nodes, "parameters": params,
                "supported_for_generation": kind in CREATE_KINDS}
        if kind in {"R", "C", "L"}:
            item["nodes"] = native_nodes
            item["value"] = params.get(kind)
        elif kind in {"U", "I"}:
            current = kind == "I"
            item["nodes"] = native_nodes if current else list(reversed(native_nodes))
            if current:
                item["polarity"] = "positive_current_from_node1_to_node2"
                # Retain the legacy R/C/L/U-only symbolic/relayout guard.
                unsupported.add(tid)
            mode = params.get("ST")
            active = params.get({1: "DC", 2: "AC", 3: "PULSE"}.get(mode, "")) or {}
            quantity = "I" if current else "U"
            item["value"] = active.get(quantity + ("MAX" if mode == 3 else "0"))
            aliases = {quantity+"0": "amplitude", "F": "frequency", "PHI0": "phase", "Delay": "delay",
                       "TFR": "rise_time", quantity+"MAX": "high", quantity+"MIN": "low", "K": "duty_percent"}
            item["waveform"] = {"kind": {1: "dc", 2: "sine", 3: "pulse"}.get(mode, "unsupported"),
                                **{public: copy.deepcopy(active[native]) for native, public in aliases.items() if native in active}}
        elif kind in {"D", "G", "E", "F", "TR", "SW", "X"}:
            item["nodes"] = native_nodes
            # This compatibility field is also the R/C/L/U-only relayout guard.
            # Native analysis supports these objects without flattening them in
            # Python; symbolic/relayout support must be checked independently.
            unsupported.add(tid)
            if kind in {"G", "E", "F"}:
                item["value"] = params.get({"G": "g", "E": "k", "F": "h"}[kind])
                item["terminal_order"] = "native_pins_1_2_3_4"
            elif kind == "D":
                item["terminal_order"] = "native_pins_1_2"
                item["pin_roles"] = ["anode", "cathode"]
            elif kind == "TR":
                item["value"] = params.get("n")
                item["terminal_order"] = "primary_1_primary_2_secondary_1_secondary_2"
                item["pin_roles"] = ["primary_dot", "primary_undotted", "secondary_dot", "secondary_undotted"]
                item["voltage_relation"] = "V(primary_1,primary_2) = n * V(secondary_1,secondary_2)"
                item["energy_storage"] = "none; add a separate magnetizing inductance for flyback"
            elif kind == "SW":
                item["terminal_order"] = "control_1_control_2_switch_1_switch_2"
                item["pin_roles"] = ["control_positive", "control_negative", "switch_1", "switch_2"]
                item["control_voltage"] = "V(control_1)-V(control_2)"
            else:
                pin_names = _subcircuit_pin_names(obj)
                item["pin_names"] = pin_names
                item["connections"] = dict(zip(pin_names, native_nodes))
                item["model_path"] = params.get("FileName")
        else:
            item["nodes"] = []
            unsupported.add(tid)
        components.append(item)
    if ground is None:
        warnings.append("No ground object is present; native analyses may reject a floating circuit.")
    node_summary = [{"name": names[root], "aliases": labels.get(root, []),
                     "terminals": [{"object_id": oid, "pin": pin} for oid, pin in sorted(terminals)]}
                    for root, terminals in roots.items()]
    return {"path": str(path), "encoding": encoding, "format": "FASTMEAN text SCM",
            "version": {"major": body.get("MajorVersion"), "minor": body.get("MinorVersion")},
            "components": components, "component_count": len(components),
            "objects": copy.deepcopy(objects), "wire_count": len(wires),
            "nodes": sorted(node_summary, key=lambda item: item["name"]),
            "ports": {name: names[uf.find(t)] for name, t in port_terminals.items()},
            "analysis": {key: copy.deepcopy(body[key]) for key in ("TD", "FD", "AOD", "SOD", "DCOP") if key in body},
            "unsupported_type_ids": sorted(unsupported), "warnings": warnings}


def read_scheme(path: str | Path) -> dict:
    """Return native objects, electrical nodes and raw analysis settings.

    Unsupported nonlinear objects are reported, never silently interpreted as
    supported components. Old binary SCM files are rejected explicitly.
    """
    source, document, encoding = _load(path)
    return _summarize(document, source, encoding)


def _source_params(value: float, waveform: dict | None, *, current: bool = False) -> dict:
    # Exact parameter groups from bundled Type2010 U sources. ST 1/2/3 are the
    # observed DC / sinusoidal / pulse modes in bundled examples.
    params = {"ST": 1, "DC": {"U0": value, "Delay": 0, "TFR": "1n"},
              "AC": {"U0": value, "F": 1000, "PHI0": 0, "FD": 0, "NP": 1, "Delay": 0},
              "PULSE": {"F": 1000, "K": 50, "UMAX": value, "UMIN": 0, "TFR": "1n", "Delay": 0},
              "TRIANG": {"F": 1000, "K": 50, "UMAX": value, "UMIN": 0, "Delay": 0},
              "USER": {"ScaleT": 1, "ScaleU": 1, "OffsetU": 0, "Delay": 0, "PER": 0, "NP": 1,
                       "U": {"x": [0, .05, .5, .55, 1], "y": [0, 1, 1, 0, 0]}}}
    def final_parameters():
        if not current:
            return params
        renames = {"U0":"I0", "UMAX":"IMAX", "UMIN":"IMIN", "ScaleU":"ScaleI", "OffsetU":"OffsetI", "U":"I"}
        def rename(value):
            return {renames.get(key,key):rename(item) for key,item in value.items()} if isinstance(value,dict) else value
        return rename(params)
    if waveform is None:
        return final_parameters()
    if not isinstance(waveform, dict):
        raise SchemeError("waveform must be a mapping.")
    kind = str(waveform.get("kind", "dc")).lower()
    if kind not in {"dc", "sine", "pulse"}:
        raise SchemeError("Supported voltage waveforms: dc, sine, pulse.")
    params["ST"] = {"dc": 1, "sine": 2, "pulse": 3}[kind]
    target = params[{"dc": "DC", "sine": "AC", "pulse": "PULSE"}[kind]]
    aliases = {"amplitude": "U0", "frequency": "F", "phase": "PHI0", "delay": "Delay",
               "high": "UMAX", "low": "UMIN", "duty_percent": "K", "rise_time": "TFR"}
    for key, value_item in waveform.items():
        if key == "kind":
            continue
        native_key = aliases.get(key)
        if native_key not in target:
            raise SchemeError(f"Unsupported {kind} waveform field: {key}")
        numeric = parse_value(value_item)
        if native_key in {"F", "TFR"} and numeric <= 0:
            raise SchemeError(f"{key} must be positive.")
        if native_key == "Delay" and numeric < 0:
            raise SchemeError("delay cannot be negative.")
        if native_key == "K" and not 0 < numeric < 100:
            raise SchemeError("duty_percent must be between 0 and 100.")
        target[native_key] = numeric
    return final_parameters()


def _object(oid: int, kind: str, name: str, x: int, y: int,
            params: dict | None = None) -> dict:
    obj = {"ID": oid, "Type": TYPE_IDS[kind], "Name": name, "X": x, "Y": y,
           "Rot": 3 if kind == "U" else 0, "FlipV": 0,
           "FlipH": 1 if kind == "U" else 0, "active_property_page": 0}
    if params is not None:
        obj["Params"] = params
    return obj


def _font(face: str, height: int = 100) -> dict:
    return {"lfHeight": height, "lfWidth": 0, "lfEscapement": 0, "lfOrientation": 0,
            "lfWeight": 400, "lfItalic": 0, "lfUnderline": 0, "lfStrikeOut": 0,
            "lfCharSet": 1, "lfOutPrecision": 0, "lfClipPrecision": 0,
            "lfQuality": 0, "lfPitchAndFamily": 0, "lfFaceName": face}


def _analysis_defaults() -> dict:
    # Scalar/section names and defaults from the successfully opened RC test.
    sweep = [{"Component": "", "ParamIndex": 0, "StartVal": 0, "EndVal": 0,
              "NumPts": 10, "SweepType": 1, "On": 1 if i == 0 else 0} for i in range(5)]
    fft = {"StartVal": -1, "EndVal": -1, "PointNum": 100, "GraphType": 3,
           "ShowPointNum": 100, "window_type": 0}
    expressions = [{"plot": 1, "x": "t", "y": "U(out)"}]
    return {"TD": {"Expressions": expressions, "ExprRowOffset": 0, "IPNum": 1,
                   "IP": [{"StartTime": 0, "EndTime": .005, "TimeStep": .000001,
                           "NumPts": 100, "PtsStepFl": 2, "EPS": .001, "GraphType": 1}],
                   "IC": 0, "SVD": {"IC": 0, "ICReadFileName": "data.sv", "SVWriteFlag": 0,
                                     "SVWriteFileName": "data.sv", "SV2SchemeFlag": 0, "SVPredictFlag": 0},
                   "ParamSweep": 0, "PSD": copy.deepcopy(sweep), "FFT": 0, "FFTD": copy.deepcopy(fft)},
            "FD": {"StartFreq": 10, "EndFreq": 100000, "NumPts": 100, "ScaleX": 2,
                   "ScaleY": 1, "AvailScaleX": 3, "AvailScaleY": 3,
                   "Expressions": [{"plot": 1, "x": "f", "y": "db(U(out))"}],
                   "ExprRowOffset": 0, "ParamSweep": 0, "PSD": copy.deepcopy(sweep),
                   "FFT": 0, "FFTD": copy.deepcopy(fft)},
            "AOD": {"DrawGraph": 1, "AvailMemory": 536870912, "ShowTransStat": 0},
            "SOD": {"ShowID": 1, "ShowParam": 1, "ShowNodes": 0,
                    "FontID": _font("Times New Roman"), "FontParam": _font("Arial"),
                    "FontNodes": _font("Arial", 120), "ColorID": "00FF0000",
                    "ColorParam": "00FF0000", "ColorNodes": "00008000",
                    "Uh": 5, "Ul": 0, "Uh2l": 2.5, "Ul2h": 2.5},
            "DCOP": {"CountNV": 1, "CountSV": 0, "CountUR": 0, "CountIR": 0,
                     "CountUI": 0, "CountIU": 0, "Digit": 4}}


def _configure_analysis(defaults: dict, options: Any, nodes: set[str]) -> None:
    if options is None:
        return
    if not isinstance(options, dict):
        raise SchemeError("analysis must be a mapping.")
    if set(options) - {"output", "input", "transient", "frequency"}:
        raise SchemeError("analysis supports output, input, transient and frequency settings.")
    output = normalize_node(options.get("output", "out" if "out" in nodes else next(n for n in sorted(nodes) if n != "0")))
    if output not in nodes or output == "0":
        raise SchemeError("analysis.output must be an existing non-ground circuit node.")
    if not IDENTIFIER.fullmatch(output):
        raise SchemeError("analysis.output needs an ASCII named port alias for a numeric graph node.")
    inp = options.get("input")
    if inp is not None:
        inp = normalize_node(inp)
        if inp not in nodes or inp == "0":
            raise SchemeError("analysis.input must be an existing non-ground node.")
        if not IDENTIFIER.fullmatch(inp):
            raise SchemeError("analysis.input needs an ASCII named port alias for a numeric graph node.")
    ratio = f"U({output})" + (f"/U({inp})" if inp else "")
    defaults["TD"]["Expressions"] = [{"plot": 1, "x": "t", "y": f"U({output})"}]
    defaults["FD"]["Expressions"] = [{"plot": 1, "x": "f", "y": f"db({ratio})"},
                                          {"plot": 2, "x": "f", "y": f"phs({ratio})"}]
    transient = options.get("transient", {})
    frequency = options.get("frequency", {})
    if not isinstance(transient, dict) or not isinstance(frequency, dict):
        raise SchemeError("transient and frequency settings must be mappings.")
    if set(transient) - {"start", "stop", "step", "eps"} or set(frequency) - {"start", "stop", "points"}:
        raise SchemeError("Unsupported native analysis setting.")
    td = defaults["TD"]["IP"][0]
    for key, native in {"start": "StartTime", "stop": "EndTime", "step": "TimeStep", "eps": "EPS"}.items():
        if key in transient:
            td[native] = parse_value(transient[key])
    if td["StartTime"] < 0 or td["EndTime"] <= td["StartTime"] or td["TimeStep"] <= 0:
        raise SchemeError("Transient interval/step is invalid.")
    if not 0 < td["EPS"] <= .1:
        raise SchemeError("Transient eps must satisfy 0 < eps <= 0.1.")
    fd = defaults["FD"]
    for key, native in {"start": "StartFreq", "stop": "EndFreq"}.items():
        if key in frequency:
            fd[native] = parse_value(frequency[key])
    if fd["StartFreq"] <= 0 or fd["EndFreq"] <= fd["StartFreq"]:
        raise SchemeError("Frequency interval must have 0 < start < stop.")
    if "points" in frequency:
        points = frequency["points"]
        if isinstance(points, bool) or not isinstance(points, int) or not 2 <= points <= 100000:
            raise SchemeError("frequency.points must be an integer from 2 to 100000.")
        fd["NumPts"] = points


def _write_document(document: dict, destination: str | Path, overwrite: bool) -> Path:
    path = Path(destination).expanduser().absolute()
    if path.suffix.lower() != ".scm":
        raise SchemeError("Output filename must end in .scm.")
    if path.is_symlink():
        raise SchemeError("Refusing to write through a symbolic-link output file.")
    if path.exists() and not overwrite:
        raise FileExistsError(f"SCM already exists: {path}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {path.parent}")
    raw = yaml.dump(document, Dumper=_IndentedDumper, allow_unicode=True,
                    sort_keys=False, default_flow_style=False, width=120).replace("\n", "\r\n").encode("utf-8")
    if len(raw) > MAX_FILE_BYTES:
        raise SchemeError("Generated SCM exceeds the file size limit.")
    if not overwrite:
        with path.open("xb") as stream:
            stream.write(raw)
    else:
        fd, temporary = tempfile.mkstemp(prefix=".fastmean-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return path.resolve()


def _model_context(value: Any) -> dict[str, dict]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SchemeError("model_context must map model identifiers to pins and relative SCM paths.")
    result, used = {}, set()
    for name, definition in value.items():
        name = _identifier(name, "Model name")
        if name.casefold() in used:
            raise SchemeError("Model names cannot differ only by case.")
        used.add(name.casefold())
        if not isinstance(definition, dict) or set(definition) != {"pins", "path"}:
            raise SchemeError(f"{name}: model context requires exactly pins and path.")
        pins = definition["pins"]
        if not isinstance(pins, dict) or set(pins) - set(_SIDES):
            raise SchemeError(f"{name}: model pins must map native side names to lists.")
        canonical, labels = {}, set()
        for side in _SIDES:
            names = pins.get(side, [])
            if not isinstance(names, list):
                raise SchemeError(f"{name}: model pin sides must be lists, not null.")
            canonical[side] = []
            for label in names:
                if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", label):
                    raise SchemeError("Generated external pins must start with an ASCII letter.")
                if label.casefold() in labels:
                    raise SchemeError("Generated model pins must be unique, including case.")
                labels.add(label.casefold())
                canonical[side].append(label)
        if not 1 <= len(labels) <= 32:
            raise SchemeError("Generated models require 1 to 32 exposed pins.")
        reference = definition["path"]
        if not isinstance(reference, str) or not reference.isascii() or "\x00" in reference:
            raise SchemeError("Generated model paths must be relative ASCII SCM paths.")
        reference = reference.replace("\\", "/")
        parts = reference.split("/")
        if (reference.startswith("/") or ":" in reference or any(part in {"", ".", ".."} for part in parts)
                or not reference.lower().endswith(".scm")
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", reference)):
            raise SchemeError("Generated model paths must be portable relative SCM paths without traversal.")
        result[name] = {"pins": canonical, "path": reference}
    return result


def _normalize_components(components: list, context: dict[str, dict]) -> tuple[list[dict], set[str], dict[str, str]]:
    normalized, nodes, names, folded_nodes = [], set(), set(), {}
    for raw in components:
        if not isinstance(raw, dict):
            raise SchemeError("Each component must be a mapping.")
        alternatives = [_KIND_ALIASES.get(str(raw[key]).upper(), str(raw[key]).upper())
                        for key in ("kind", "type") if key in raw]
        if len(set(alternatives)) > 1:
            raise SchemeError("Component kind and type disagree.")
        kind = alternatives[0] if alternatives else ""
        if kind not in CREATE_KINDS:
            raise SchemeError(f"Generation of {kind!r} is unsupported. Supported: R, C, L, U/V, I, D, G/VCCS, E/VCVS, F/CCCS, TR, SW and X.")
        name = _identifier(raw.get("name"), "Component name")
        if name.casefold() in names:
            raise SchemeError(f"Duplicate component name: {name}")
        names.add(name.casefold())
        allowed = {"kind", "type", "name", "nodes", "value", "waveform", "initial_condition"}
        if kind == "X":
            allowed = {"kind", "type", "name", "model", "connections"}
        elif kind in {"D", "SW"}:
            allowed = {"kind", "type", "name", "nodes", "parameters"}
        elif kind in {"G", "E", "F", "TR"}:
            allowed = {"kind", "type", "name", "nodes", "value", "parameters"}
        if set(raw) - allowed:
            raise SchemeError(f"{name}: unsupported component properties; model parameter overrides are not generated.")
        item = {"kind": kind, "type": kind, "name": name}
        if kind == "X":
            model = raw.get("model")
            if not isinstance(model, str) or model not in context:
                raise SchemeError(f"{name}: unknown subcircuit model {model!r}.")
            definition = context[model]
            pin_names = [pin for side in _SIDES for pin in definition["pins"][side]]
            connections = raw.get("connections")
            if not isinstance(connections, dict) or set(connections) != set(pin_names):
                raise SchemeError(f"{name}: connections must map every model pin exactly.")
            terminals = [normalize_node(connections[pin]) for pin in pin_names]
            params = {"FileName": definition["path"], "Pins": copy.deepcopy(definition["pins"])}
            item.update({"model": model, "connections": dict(zip(pin_names, terminals))})
        else:
            count = 4 if kind in {"G", "E", "F", "TR", "SW"} else 2
            terminals = raw.get("nodes")
            if not isinstance(terminals, list) or len(terminals) != count:
                raise SchemeError(f"{name} must have exactly {count} node labels in native terminal order.")
            terminals = [normalize_node(node) for node in terminals]
            if count == 2 and terminals[0] == terminals[1]:
                raise SchemeError(f"{name} has both terminals on the same node.")
            if kind == "D":
                raw_params = raw.get("parameters")
                if not isinstance(raw_params, dict) or set(raw_params) != {"Ron", "Roff", "Uon"}:
                    raise SchemeError(f"{name}: diode parameters must be exactly Ron, Roff and Uon.")
                params = {key: parse_value(raw_params[key]) for key in ("Ron", "Roff", "Uon")}
                if params["Ron"] <= 0 or params["Roff"] < params["Ron"] or params["Uon"] < 0:
                    raise SchemeError(f"{name}: diode requires 0 < Ron <= Roff and Uon >= 0.")
                item["parameters"] = copy.deepcopy(params)
            elif kind == "SW":
                raw_params = raw.get("parameters")
                if not isinstance(raw_params, dict) or set(raw_params) != {"Ron", "Roff", "Uon", "Uoff"}:
                    raise SchemeError(f"{name}: switch parameters must be exactly Ron, Roff, Uon and Uoff.")
                params = {key: parse_value(raw_params[key]) for key in ("Ron", "Roff", "Uon", "Uoff")}
                if params["Ron"] <= 0 or params["Roff"] < params["Ron"] or params["Uoff"] > params["Uon"]:
                    raise SchemeError(f"{name}: switch requires 0 < Ron <= Roff and Uoff <= Uon.")
                if terminals[2] == terminals[3]:
                    raise SchemeError(f"{name}: switch power terminals must differ.")
                item["parameters"] = copy.deepcopy(params)
            elif kind in {"G", "E", "F", "TR"}:
                key = {"G": "g", "E": "k", "F": "h", "TR": "n"}[kind]
                if "parameters" in raw:
                    raw_params = raw["parameters"]
                    if "value" in raw or not isinstance(raw_params, dict) or set(raw_params) != {key}:
                        raise SchemeError(f"{name}: supply either value or the single numeric parameter {key}.")
                    value = parse_value(raw_params[key])
                else:
                    value = parse_value(raw.get("value"))
                item["value"], params = value, {key: value}
                if kind == "TR" and (value <= 0 or terminals[0] == terminals[1] or terminals[2] == terminals[3]):
                    raise SchemeError(f"{name}: transformer requires n > 0 and distinct terminals in each winding.")
            else:
                value = parse_value(raw.get("value"))
                if kind in {"R", "C", "L"} and value <= 0:
                    raise SchemeError(f"{name}: passive values must be positive.")
                item["value"] = value
                params = {kind: value}
                if kind in {"U", "I"}:
                    item["waveform"] = copy.deepcopy(raw.get("waveform"))
                    params = _source_params(value, item["waveform"], current=kind == "I")
                elif "waveform" in raw:
                    raise SchemeError(f"{name}: waveform is only valid for independent sources.")
                if kind in {"C", "L"}:
                    item["initial_condition"] = parse_value(raw.get("initial_condition", 0))
                    params["IC"] = item["initial_condition"]
                elif "initial_condition" in raw:
                    raise SchemeError("initial_condition is supported only for C and L.")
        for node in terminals:
            existing = folded_nodes.setdefault(node.casefold(), node)
            if existing != node:
                raise SchemeError(f"Ambiguous node casing: {existing} and {node}")
        item.update({"nodes": terminals, "_native_type": TYPE_IDS[kind], "_native_params": params,
                     "_native_nodes": list(reversed(terminals)) if kind == "U" else list(terminals)})
        nodes.update(terminals)
        normalized.append(item)
    return normalized, nodes, folded_nodes


def _validate_interface_ports(objects: list[dict], interface_pins: dict) -> list[str]:
    """Native expansion rebuilds pin order from child PORT sides/coordinates."""
    by_side = {side: [] for side in _SIDES}
    side_for_rotation = {2: "Left", 3: "Top", 0: "Right", 1: "Bottom"}
    for obj in objects:
        if obj.get("Type") != 400 or str(obj.get("Name", "")).startswith("_"):
            continue
        if obj.get("FlipH", 0) or obj.get("FlipV", 0):
            raise SchemeError("Generated subcircuit interface PORTs cannot be flipped.")
        side = side_for_rotation.get(obj.get("Rot", 0))
        if side is None:
            raise SchemeError("Generated subcircuit interface PORT has an invalid rotation.")
        axis = obj.get("Y" if side in {"Left", "Right"} else "X")
        if isinstance(axis, bool) or not isinstance(axis, int):
            raise SchemeError("Generated subcircuit PORT coordinates must be integers.")
        by_side[side].append((axis, obj.get("Name")))
    for side in _SIDES:
        values = by_side[side]
        if len({coordinate for coordinate, _ in values}) != len(values):
            raise SchemeError(f"Subcircuit {side} PORTs need distinct native ordering coordinates.")
        observed = [name for _, name in sorted(values)]
        if observed != interface_pins[side]:
            raise SchemeError(f"Native child PORT layout on {side} must match declared pins {interface_pins[side]}; got {observed}.")
    return [name for side in _SIDES for _, name in sorted(by_side[side])]


def create_circuit(spec: dict, path: str | Path, overwrite: bool = False, *,
                   model_context: dict | None = None, subcircuit: bool = False,
                   interface_pins: dict | None = None) -> dict:
    """Create an electrically connected native SCM from a node-based JSON spec.

    R/C/L/U/I use two nodes and value. D uses [anode,cathode] and fixed
    Ron/Roff/Uon parameters; G/E/F use four native-ordered pins and a numeric
    gain. TR uses [primary_dot,primary_undotted,secondary_dot,secondary_undotted]
    and n=Nprimary/Nsecondary. SW uses [control+,control-,switch1,switch2] and
    Ron/Roff/Uon/Uoff parameters. The two terminal pairs remain electrically
    separate in both primitives. X instances map named
    model pins through model_context. U nodes are [positive, negative], with
    native pins reversed. I nodes are [from,to]. Ground aliases are 0/gnd/ground. Floating subcircuit
    definitions retain exactly their declared ports without adding test points.
    Components are physically connected with orthogonal native wires; ports
    represent only declared external interfaces and analysis inputs/outputs.
    The function validates references and floating graph islands, but does not
    assert DC operating-point solvability (e.g. ideal voltage-source loops).
    """
    if not isinstance(spec, dict) or not isinstance(spec.get("components"), list):
        raise SchemeError("Circuit spec needs a components list.")
    if set(spec) - {"components", "ports", "analysis", "title", "name", "description", "layout"}:
        raise SchemeError("Unsupported circuit-spec fields; topology is expressed by component nodes.")
    if not 1 <= len(spec["components"]) <= MAX_COMPONENTS:
        raise SchemeError(f"Circuit must contain 1 to {MAX_COMPONENTS} components.")
    if not isinstance(subcircuit, bool):
        raise SchemeError("subcircuit must be a boolean.")
    if interface_pins is not None:
        if not subcircuit:
            raise SchemeError("interface_pins is only valid for a subcircuit definition.")
        interface_pins = _model_context({"_INTERFACE": {"pins": interface_pins, "path": "interface.scm"}})["_INTERFACE"]["pins"]
    context = _model_context(model_context)
    normalized, nodes, folded_nodes = _normalize_components(spec["components"], context)
    if not nodes - {"0"}:
        raise SchemeError("Circuit must contain a non-ground node.")
    if not subcircuit:
        if "0" not in nodes:
            raise SchemeError("Circuit must reference ground node 0.")
        adjacency = {node: set() for node in nodes}
        for item in normalized:
            terminals = item["nodes"]
            # Controlled-source control and output branches are electrically
            # separate. X is an opaque multiport here; its native definition
            # determines internal coupling and operating-point solvability.
            pairs = list(zip(terminals[::2], terminals[1::2])) if item["kind"] in {"G", "E", "F", "TR", "SW"} else list(zip(terminals, terminals[1:]))
            for a, b in pairs:
                adjacency[a].add(b)
                adjacency[b].add(a)
        reached, queue = {"0"}, ["0"]
        while queue:
            for other in adjacency[queue.pop()] - reached:
                reached.add(other)
                queue.append(other)
        if reached != nodes:
            raise SchemeError(f"Floating circuit island(s): {sorted(nodes - reached)}")

    raw_ports = spec.get("ports", {})
    if isinstance(raw_ports, list):
        port_items = [(name, name) for name in raw_ports]
    elif isinstance(raw_ports, dict):
        port_items = list(raw_ports.items())
    else:
        raise SchemeError("ports must be a node list or an alias-to-node mapping.")
    ports, port_spellings = {}, {}
    for alias, node in port_items:
        alias, node = normalize_node(alias), normalize_node(node)
        if alias == "0":
            raise SchemeError("A port alias cannot be ground.")
        if not IDENTIFIER.fullmatch(alias):
            raise SchemeError("A port alias must be an ASCII identifier, not a numeric node label.")
        if node not in nodes or node == "0":
            raise SchemeError(f"Port {alias} must reference an existing non-ground node.")
        if alias in nodes and alias != node:
            raise SchemeError(f"Port alias {alias} collides with another node name.")
        if (alias.casefold() in folded_nodes and folded_nodes[alias.casefold()] != alias
                and not (subcircuit and folded_nodes[alias.casefold()] == node)):
            raise SchemeError(f"Ambiguous port/node casing: {alias}")
        if alias.casefold() in port_spellings:
            raise SchemeError(f"Duplicate or ambiguous port alias: {alias}")
        ports[alias] = node
        port_spellings[alias.casefold()] = alias
    if interface_pins is not None and set(ports) != {pin for side in _SIDES for pin in interface_pins[side]}:
        raise SchemeError("Subcircuit ports must match interface_pins exactly.")
    analysis = _analysis_defaults()
    if spec.get("analysis") is not None and not isinstance(spec["analysis"], dict):
        raise SchemeError("analysis must be a mapping.")
    options = dict(spec.get("analysis") or {})
    for role in ("input", "output"):
        if options.get(role) is not None:
            options[role] = normalize_node(options[role])
            if subcircuit and options[role] not in ports:
                alias = next((alias for alias, node in ports.items() if node == options[role]), None)
                if alias is None:
                    raise SchemeError("Subcircuit analysis I/O must use declared external ports.")
                options[role] = alias
    if "output" not in options:
        options["output"] = (next(iter(ports)) if subcircuit and ports else
                             "out" if "out" in nodes else next(n for n in sorted(nodes) if n != "0"))
    _configure_analysis(analysis, options, nodes | set(ports))
    # Analysis node labels must exist in the native netlist. Give an explicit
    # test-point port to requested I/O only, never to every internal terminal.
    if not subcircuit:
        for role in ("input", "output"):
            name = options.get(role)
            if name is not None and name in nodes and name not in ports:
                ports[name] = name
    from .layout import build_layout
    layout_options = spec.get("layout") or {}
    if not isinstance(layout_options, dict) or set(layout_options) - {"placements", "nodes", "routes", "ports", "density", "ground_style"}:
        raise SchemeError("layout supports density, ground_style, placements, nodes, routes and external ports.")
    layout = build_layout(normalized, ports, options, layout_options.get("placements"),
                          node_positions=layout_options.get("nodes"), routes=layout_options.get("routes"),
                          port_positions=layout_options.get("ports"), density=layout_options.get("density", "compact"),
                          **({"ground_style":layout_options["ground_style"]} if "ground_style" in layout_options else {}),
                          **({"interface_pins": interface_pins} if interface_pins is not None else {}))
    objects, wires = layout["objects"], layout["wires"]
    if interface_pins is not None:
        _validate_interface_ports(objects, interface_pins)
    left, top, right, bottom = layout["bounds"]
    scale = max(15, min(100, int(100 * min(850/max(right-left, 1), 600/max(bottom-top, 1)))))
    if layout.get("requires_native_scale100"):
        scale = 100  # Native subcircuit caption sizing is zoom/font dependent.
    document = {"scm": {"MajorVersion": 5, "MinorVersion": 1,
                        "General": {"Scale": scale, "HPos": (left+right)//2,
                                    "VPos": (top+bottom)//2,
                                    "SWidth": max(3000, right+500),
                                    "SHeight": max(3000, bottom+500)},
                        "Special": {"LangVersion": 2},
                        "Scheme": {"MajorSchVer": 3, "MinorSchVer": 0,
                                   "Objects": objects, "Wires": wires}, **analysis}}
    # Validate the serialized electrical model before any filesystem mutation.
    summary = _summarize(document, Path(path).absolute(), "utf-8")
    if len(normalized) != len(summary["components"]):
        raise SchemeError("Internal component serialization validation failed.")
    node_mapping, reverse_mapping = {"0": "0"}, {"0": "0"}
    for expected, observed in zip(normalized, summary["components"]):
        if len(expected["nodes"]) != len(observed["nodes"]):
            raise SchemeError("Internal terminal-count validation failed.")
        for expected_node, observed_node in zip(expected["nodes"], observed["nodes"]):
            if node_mapping.setdefault(expected_node, observed_node) != observed_node or reverse_mapping.setdefault(observed_node, expected_node) != expected_node:
                raise SchemeError("Internal physical-wire connectivity validation failed.")
    for alias, node in ports.items():
        if summary["ports"].get(alias) != node_mapping[node]:
            raise SchemeError("External port connectivity validation failed.")
    written = _write_document(document, path, overwrite)
    summary["path"] = str(written)
    public_components = [{key: copy.deepcopy(value) for key, value in item.items()
                          if not key.startswith("_native_") and not (item["kind"] == "X" and key == "nodes")}
                         for item in normalized]
    summary["spec"] = {"components": public_components, "ports": ports, "analysis": options,
                       "layout": {**copy.deepcopy(layout_options), "density": layout["density"]}}
    summary["layout"] = {key: value for key, value in layout.items() if key not in {"objects", "wires", "component_ids"}}
    summary["node_mapping"] = node_mapping
    if subcircuit:
        summary["warnings"] = [warning for warning in summary["warnings"]
                               if warning != "No ground object is present; native analyses may reject a floating circuit."]
    summary["subcircuit"] = subcircuit
    if interface_pins is not None:
        summary["interface_pins"] = copy.deepcopy(interface_pins)
    return summary


def _apply_value_edits(document: dict, updates: dict) -> None:
    """Validate and apply root edits to an in-memory document only."""
    if not isinstance(updates, dict) or not updates:
        raise SchemeError("updates must map component names to new values.")
    objects = document["scm"]["Scheme"].get("Objects") or []
    by_name = {}
    for obj in objects:
        if "Name" in obj:
            by_name.setdefault(str(obj["Name"]), []).append(obj)
    for name, update in updates.items():
        if len(by_name.get(name, [])) != 1:
            raise SchemeError(f"Component {name!r} is absent or its name is ambiguous.")
        obj = by_name[name][0]
        kind = KINDS.get(obj.get("Type"))
        if kind not in EDIT_KINDS:
            raise SchemeError(f"Editing {name} of type {kind or obj.get('Type')} is unsupported.")
        patch = update if isinstance(update, dict) else {"value": update}
        if set(patch) - {"value", "waveform"} or "value" not in patch:
            raise SchemeError("Component edits support value and optional voltage waveform.")
        value = parse_value(patch["value"])
        if kind in {"R", "C", "L"}:
            if value <= 0 or "waveform" in patch:
                raise SchemeError("Passive edits require a positive value and no waveform.")
            obj.setdefault("Params", {})[kind] = value
        else:
            if "waveform" in patch:
                # Validate against the complete known native template, but do
                # not replace unrelated source modes, custom data or omitted
                # phase/delay settings when editing one waveform field.
                template = _source_params(value, patch["waveform"], current=kind == "I")
                params = copy.deepcopy(obj.get("Params") or {})
                section = {1: "DC", 2: "AC", 3: "PULSE"}[template["ST"]]
                existing = params.get(section) or {}
                if not isinstance(existing, dict):
                    raise SchemeError(f"Source {name} has invalid {section} parameters.")
                target = {**template[section], **existing}
                quantity = "I" if kind == "I" else "U"
                target[quantity + ("MAX" if section == "PULSE" else "0")] = value
                aliases = {"amplitude": quantity+"0", "frequency": "F", "phase": "PHI0",
                           "delay": "Delay", "high": quantity+"MAX", "low": quantity+"MIN",
                           "duty_percent": "K", "rise_time": "TFR"}
                for key in patch["waveform"] or {}:
                    if key != "kind":
                        native = aliases[key]
                        # Explicit waveform amplitude/high takes precedence
                        # over the base value, as it does during creation.
                        target[native] = template[section][native]
                params.update({"ST": template["ST"], section: target})
                obj["Params"] = params
            else:
                quantity = "I" if kind == "I" else "U"
                obj.setdefault("Params", {}).setdefault("DC", {})[quantity+"0"] = value
                obj["Params"].setdefault("AC", {})[quantity+"0"] = value
                if "PULSE" in obj["Params"]:
                    obj["Params"]["PULSE"][quantity+"MAX"] = value
                if "TRIANG" in obj["Params"]:
                    obj["Params"]["TRIANG"][quantity+"MAX"] = value


def edit_component_values(source_path: str | Path, updates: dict, output_path: str | Path,
                          overwrite: bool = False) -> dict:
    """Change supported root values while preserving topology and native data.

    updates maps names to numbers/SI strings or {value: ..., waveform: ...}.
    A hierarchical circuit is always published as a fresh portable dependency
    tree; existing SCM/model destinations cannot be overwritten or merged.
    """
    source, document, _ = _load(source_path)
    _summarize(document, source, "utf-8")
    _apply_value_edits(document, updates)
    if any(obj["Type"] == 7100 for obj in document["scm"]["Scheme"].get("Objects") or []):
        from .annotations import _copy_circuit
        # Validate edits before staging, then transform only the private root.
        # Copying just its YAML would strand models/*.scm in the source job.
        package = _copy_circuit(source, output_path,
                                root_transform=lambda staged: _apply_value_edits(staged, updates))
        result = read_scheme(package["path"])
        for key in ("working_dir", "source_path", "source_sha256", "source_unchanged",
                    "private_schematic_sha256", "source_models", "dependency_layout",
                    "portability_note", "preview_unsupported", "dependency_paths"):
            result[key] = package[key]
        result["edited_components"] = list(updates)
        return result
    _summarize(document, source, "utf-8")
    destination = _write_document(document, output_path, overwrite)
    result = _summarize(document, destination, "utf-8")
    result["edited_components"] = list(updates)
    return result


def example_circuit(kind: str = "rc_lowpass") -> dict:
    """Return a JSON-ready supported example; performs no file writes."""
    if kind in {"flyback", "flyback_converter"}:
        from .examples import flyback_circuit
        return flyback_circuit()
    if kind == "rc_lowpass":
        components = [{"kind": "U", "name": "U1", "nodes": ["in", "0"], "value": 1,
                       "waveform": {"kind": "sine", "frequency": "1k"}},
                      {"kind": "R", "name": "R1", "nodes": ["in", "out"], "value": "1k"},
                      {"kind": "C", "name": "C1", "nodes": ["out", "0"], "value": "1u"}]
    elif kind == "rlc_lowpass":
        components = [{"kind": "U", "name": "U1", "nodes": ["in", "0"], "value": 1,
                       "waveform": {"kind": "sine", "frequency": "1k"}},
                      {"kind": "R", "name": "R1", "nodes": ["in", "mid"], "value": 100},
                      {"kind": "L", "name": "L1", "nodes": ["mid", "out"], "value": "10m"},
                      {"kind": "C", "name": "C1", "nodes": ["out", "0"], "value": "1u"}]
    elif kind == "voltage_divider":
        components = [{"kind": "U", "name": "U1", "nodes": ["in", "0"], "value": 10,
                       "waveform": {"kind": "sine", "frequency": "1k"}},
                      {"kind": "R", "name": "R1", "nodes": ["in", "out"], "value": "1k"},
                      {"kind": "R", "name": "R2", "nodes": ["out", "0"], "value": "1k"}]
    else:
        raise SchemeError("Examples: rc_lowpass, rlc_lowpass, voltage_divider, flyback.")
    return {"components": components, "ports": ["in", "out"],
            "analysis": {"input": "in", "output": "out",
                         "transient": {"stop": "5m", "step": "1u"},
                         "frequency": {"start": 10, "stop": "100k", "points": 100}}}
