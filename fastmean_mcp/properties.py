"""Validate native property patches and publish source-preserving SCM copies.

Electrical expressions remain native expressions: this module does not evaluate
unknown variables/functions. Literal values, structural enums, tables and saved
analysis bounds are validated before the annotation transaction is published.
"""
from __future__ import annotations

import copy
import math
import re

from .schematic import SchemeError, _analysis_defaults, parse_value

MAX_TABLE_ITEMS = 4096
_FILE_FIELDS = {"FileName", "Pins", "ICReadFileName", "SVWriteFileName"}
_NATIVE_FUNCTIONS = frozenset("cos sin tan cot acos asin atan cosh sinh tanh coth ln lg db re im mag ph phs exp abs sqrt pow limit max min floor round mod wnd last avg rms fft ift tmag tph tre tim u i p w".split())


def _literal(value):
    try:
        return parse_value(value)
    except (ValueError, TypeError):
        return None


def _leaf(value, template, label):
    from .analysis import math_expression
    if isinstance(template, bool):
        if not isinstance(value, bool):
            raise SchemeError(f"{label} must be boolean.")
        return value
    if isinstance(template, (int, float, str)):
        if isinstance(value, str):
            numeric = _literal(value)
            return numeric if numeric is not None else math_expression(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise SchemeError(f"{label} must be finite mathematical data.")
        return value
    raise SchemeError(f"Unsupported native property shape at {label}.")


def merge_parameters(original, patch, label="parameters", depth=0):
    """Merge declared fields only; domain-specific validation follows below."""
    if depth > 16 or not isinstance(original, dict) or not isinstance(patch, dict) or len(patch) > 256:
        raise SchemeError(f"{label} requires a bounded mapping, with at most 16 nesting levels.")
    result = copy.deepcopy(original)
    for key, value in patch.items():
        if not isinstance(key, str) or key not in original:
            raise SchemeError(f"Unknown native parameter: {label}.{key}")
        path = label+"."+key
        if key in _FILE_FIELDS:
            raise SchemeError(f"{path} is a project/file interface, not an editable numeric parameter.")
        old = original[key]
        if isinstance(old, dict):
            result[key] = merge_parameters(old, value, path, depth+1)
        elif isinstance(old, list):
            minimum = 0 if key == "Expressions" else 1
            if not isinstance(value, list) or not minimum <= len(value) <= MAX_TABLE_ITEMS:
                raise SchemeError(f"{path} needs {minimum} to {MAX_TABLE_ITEMS} entries.")
            prototype = old[0] if old else {"plot": 1, "x": "t", "y": "t"} if key == "Expressions" else 0
            result[key] = []
            for index, item in enumerate(value):
                template = old[index] if index < len(old) else prototype
                result[key].append(merge_parameters(template, item, path, depth+1)
                    if isinstance(template, dict) else _leaf(item, template, path))
        elif key == "Component":
            from .analysis import parameter_target
            result[key] = "" if value == "" else parameter_target(value)
        elif key in {"On", "FD", "PER", "DrawGraph", "ShowTransStat", "SVWriteFlag", "SV2SchemeFlag", "SVPredictFlag"}:
            result[key] = _integer(value, path, 0, 1, boolean=True)
        else:
            result[key] = _leaf(value, old, path)
    if isinstance(result.get("x"), list) and isinstance(result.get("y"), list):
        _curve(result, label)
    return result


def _integer(value, label, minimum, maximum, *, boolean=False):
    if boolean and isinstance(value, bool):
        return int(value)
    # Integer-typed native serializers do not accept mathematical expressions.
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise SchemeError(f"{label} must be an integer from {minimum} to {maximum}.")
    return value


def _point_count(value, label, minimum, maximum):
    """Saved point-count fields accept native SI/math expressions, not enums."""
    from .engine import validate_signal
    if isinstance(value, bool):
        raise SchemeError(f"{label} must be an integer count or native mathematical expression.")
    literal = _literal(value)
    if literal is None:
        validate_signal(value)
    elif int(literal) != literal or not minimum <= literal <= maximum:
        raise SchemeError(f"{label} requires an integer count from {minimum} to {maximum}.")


def _curve(value, label, limit=MAX_TABLE_ITEMS):
    x, y = value.get("x"), value.get("y")
    if not isinstance(x, list) or not isinstance(y, list) or len(x) != len(y) or not 2 <= len(x) <= limit:
        raise SchemeError(f"{label} needs matching x/y arrays with 2 to {limit} points.")
    xs, ys = [_literal(item) for item in x], [_literal(item) for item in y]
    if any(item is None for item in xs+ys) or any(a >= b for a, b in zip(xs, xs[1:])):
        raise SchemeError(f"{label} needs finite numeric coordinates and strictly increasing x.")


def _positive_literals(parameters):
    for key in ("R", "C", "L", "Ron", "n", "n1", "n2", "Ri", "Rc", "Re", "Rb", "Len", "F", "ScaleT"):
        number = _literal(parameters.get(key))
        if number is not None and number <= 0:
            raise SchemeError(f"{key} must be positive.")
    for key in ("Delay", "L0", "R0", "C0", "G0"):
        number = _literal(parameters.get(key))
        if number is not None and number < 0:
            raise SchemeError(f"{key} must be nonnegative.")
    for lower, upper in (("Ron", "Roff"), ("Uoff", "Uon"), ("Uh2l", "Ul2h")):
        a, b = _literal(parameters.get(lower)), _literal(parameters.get(upper))
        if a is not None and b is not None and a > b:
            raise SchemeError(f"{lower} must not exceed {upper}.")
    for lower, upper in (("Ulow", "Uhigh"), ("UInMin", "UInMax"), ("UOutMin", "UOutMax")):
        a, b = _literal(parameters.get(lower)), _literal(parameters.get(upper))
        if a is not None and b is not None and a >= b:
            raise SchemeError(f"{upper} must exceed {lower}.")
    for key, maximum in (("alpha", 1), ("K", 100)):
        number = _literal(parameters.get(key))
        if number is not None and not 0 <= number <= maximum:
            raise SchemeError(f"{key} is outside its native range.")


def _source_parameters(original, merged, patch, current):
    from .source_waveforms import MODES, _aliases, source_parameters
    _integer(merged.get("ST"), "ST", 1, 5)
    aliases = _aliases(current)
    reverse = {native: public for public, native in aliases.items() if public != "delay_periods"}
    for kind, (_, section) in MODES.items():
        if section not in patch:
            continue
        part = merged[section]
        waveform = {"kind": kind}
        for native, value in part.items():
            public = "delay_periods" if native == "Delay" and kind in {"sine", "pulse", "triangle"} else reverse.get(native)
            if public is None:
                continue
            if native in {"FD", "PER"}:
                waveform[public] = _integer(value, section+"."+native, 0, 1, boolean=True)
            elif native == "NP":
                literal = _literal(value)
                if literal is not None:
                    waveform[public] = literal
            elif public == "points":
                _curve(value, section+"."+native)
                waveform[public] = list(map(list, zip(value["x"], value["y"])))
            else:
                literal = _literal(value)
                if literal is not None:
                    waveform[public] = literal
        # The dedicated waveform adapter is authoritative for native mode and
        # literal field bounds. Unknown expressions were retained, not evaluated.
        source_parameters(1, waveform, current=current)
    return merged


def _component_parameters(obj, patch):
    from .element_catalog import get_element, get_geometry, normalize_parameters
    original = obj["Params"]
    merged = merge_parameters(original, patch, str(obj.get("Name")))
    if obj["Type"] in {2010, 3010}:
        return _source_parameters(original, merged, patch, obj["Type"] == 3010)
    try:
        entry = get_element(obj["Type"])
    except KeyError as error:
        raise SchemeError("This native element has no declared editable catalog schema.") from error
    if entry.get("service"):
        raise SchemeError("Diagram interfaces and TEXT use their dedicated authoring tools.")
    for key in patch:
        if key not in entry["parameter_schema"]:
            raise SchemeError(f"{entry['kind']}.{key} is not a declared editable electrical parameter.")
    for key, schema in entry["parameter_schema"].items():
        if key not in merged:
            continue
        value, category = merged[key], schema["type"]
        if 6900 <= obj["Type"] <= 6920 and key in patch and category == "number" and _literal(value) is None:
            raise SchemeError("Native logical-element parameters require numeric literals, not expressions.")
        if category == "integer":
            _integer(value, key, schema.get("minimum", -2147483648), schema.get("maximum", 2147483647))
            if "enum" in schema and value not in schema["enum"]:
                raise SchemeError(f"{key} is outside its native enum.")
        elif category in {"number_array", "integer_array"}:
            count = merged[schema["length_parameter"]]
            if not isinstance(value, list) or len(value) != count:
                raise SchemeError(f"{key} must have exactly {count} entries.")
            if category == "integer_array" and any(type(item) is not int or item not in schema["enum"] for item in value):
                raise SchemeError(f"{key} contains an invalid native integer flag.")
        elif category == "curve":
            _curve(value, key, schema["max_points"])
    if get_geometry(obj["Type"], original) != get_geometry(obj["Type"], merged):
        raise SchemeError("Geometry-changing properties require creating a new circuit/project so terminal wiring stays correct.")
    _positive_literals(merged)
    if entry["kind"] == "LINE":
        _integer(merged["n"], "LINE.n", 1, 1000)
    # Catalog normalization is also exercised when every field is numeric.
    def numeric(value):
        if isinstance(value, dict):
            return all(numeric(child) for child in value.values())
        if isinstance(value, list):
            return all(numeric(child) for child in value)
        return _literal(value) is not None
    catalog_values = {key: merged[key] for key in entry["defaults"] if key in merged}
    if numeric(catalog_values):
        normalize_parameters(obj["Type"], catalog_values)
    return merged


def _validate_analysis(section, current):
    from .engine import MAX_AC_POINTS, MAX_SIGNALS, MAX_TRANSIENT_STEPS, validate_signal
    if section in {"TD", "FD"}:
        expressions = current.get("Expressions", [])
        if not isinstance(expressions, list) or len(expressions) > MAX_SIGNALS:
            raise SchemeError("Saved analyses support at most 30 expressions.")
        for item in expressions:
            _integer(item.get("plot"), "plot", 1, MAX_SIGNALS)
            validate_signal(item.get("x"))
            validate_signal(item.get("y"))
        _integer(current["ExprRowOffset"], "ExprRowOffset", 0, MAX_SIGNALS)
        for key in ("ParamSweep", "FFT"):
            _integer(current[key], key, 0, 1)
        psd = current.get("PSD", [])
        if not isinstance(psd, list) or len(psd) > 5:
            raise SchemeError("Native saved parameter sweep supports at most five simultaneous descriptors.")
        for item in psd:
            _integer(item["On"], "PSD.On", 0, 1)
            _integer(item["ParamIndex"], "PSD.ParamIndex", 0, 1000)
            _integer(item["NumPts"], "PSD.NumPts", 2, MAX_AC_POINTS)
            _integer(item["SweepType"], "PSD.SweepType", 1, 3)
            if current["ParamSweep"] and item["On"] and not item["Component"]:
                raise SchemeError("An enabled saved sweep needs a component/variable target.")
            if item["SweepType"] == 2:
                for key in ("StartVal", "EndVal"):
                    literal = _literal(item[key])
                    if literal is not None and literal <= 0 and current["ParamSweep"] and item["On"]:
                        raise SchemeError("A logarithmic saved parameter sweep needs positive endpoints.")
        fft = current["FFTD"]
        _integer(fft["PointNum"], "FFTD.PointNum", 2, 262144)
        _integer(fft["ShowPointNum"], "FFTD.ShowPointNum", 1, fft["PointNum"])
        _integer(fft["window_type"], "FFTD.window_type", 0, 4)
        _integer(fft["GraphType"], "FFTD.GraphType", 1, 4)
        a, b = _literal(fft["StartVal"]), _literal(fft["EndVal"])
        if any(value is not None and value < 0 and value != -1 for value in (a, b)):
            raise SchemeError("FFT endpoints must be nonnegative or the native automatic sentinel -1.")
        if a is not None and b is not None and a >= 0 and b >= 0 and a >= b:
            raise SchemeError("FFT end must exceed start.")
    if section == "FD":
        _point_count(current["NumPts"], "FD.NumPts", 2, MAX_AC_POINTS)
        _integer(current["ScaleX"], "FD.ScaleX", 1, 2)
        _integer(current["ScaleY"], "FD.ScaleY", 1, 2)
        for key in ("AvailScaleX", "AvailScaleY"):
            _integer(current[key], key, 0, 3)
        a, b = _literal(current["StartFreq"]), _literal(current["EndFreq"])
        if a is not None and a <= 0 or b is not None and b <= 0 or a is not None and b is not None and b <= a:
            raise SchemeError("Saved FD requires 0 < start < end.")
    elif section == "TD":
        intervals = current["IP"]
        _integer(current["IPNum"], "TD.IPNum", 1, min(len(intervals), 100))
        if len(intervals) > 100:
            raise SchemeError("Saved TD supports at most 100 bounded intervals.")
        for interval in intervals:
            _point_count(interval["NumPts"], "TD.NumPts", 1, MAX_TRANSIENT_STEPS)
            _integer(interval["PtsStepFl"], "TD.PtsStepFl", 1, 2)
            _integer(interval["GraphType"], "TD.GraphType", 1, 4)
            start, end, step, eps = [_literal(interval[key]) for key in ("StartTime", "EndTime", "TimeStep", "EPS")]
            if start is not None and start < 0 or end is not None and end <= 0 or step is not None and step <= 0:
                raise SchemeError("Saved TD times require nonnegative start and positive end/step.")
            if start is not None and end is not None and end <= start:
                raise SchemeError("Saved TD end must exceed start.")
            if eps is not None and not 0 < eps <= .1:
                raise SchemeError("Saved TD requires 0 < EPS <= .1.")
        _integer(current["IC"], "TD.IC", 0, 3)
        svd = current["SVD"]
        _integer(svd["IC"], "SVD.IC", 0, 3)
        for key in ("SVWriteFlag", "SV2SchemeFlag", "SVPredictFlag"):
            _integer(svd[key], key, 0, 1)
    elif section == "AOD":
        for key in ("DrawGraph", "ShowTransStat"):
            _integer(current[key], key, 0, 1)
        _integer(current["AvailMemory"], "AOD.AvailMemory", 1, 2147483647)
    elif section == "DCOP":
        _integer(current["Digit"], "DCOP.Digit", 1, 17)
        for key in ("CountNV", "CountSV", "CountUR", "CountIR", "CountUI", "CountIU"):
            _integer(current[key], key, 0, 1)


def _merge_style(original, patch, label="SOD"):
    if not isinstance(patch, dict) or set(patch)-set(original):
        raise SchemeError("Unknown native style property.")
    result = copy.deepcopy(original)
    for key, value in patch.items():
        name = label+"."+key
        if isinstance(original[key], dict):
            result[key] = _merge_style(original[key], value, name)
        elif key.startswith("Color"):
            if not isinstance(value, str) or re.fullmatch(r"[A-Fa-f0-9]{8}", value) is None:
                raise SchemeError(f"{name} must be eight hexadecimal native color digits.")
            result[key] = value
        elif key == "lfFaceName":
            if not isinstance(value, str) or not 1 <= len(value) <= 100 or any(ord(c) < 32 for c in value):
                raise SchemeError("Font names must be bounded plain text.")
            result[key] = value
        elif key.startswith("lf"):
            low, high = (-3600, 3600) if key in {"lfEscapement", "lfOrientation"} else (-1000, 1000) if key == "lfHeight" else (0, 1000) if key in {"lfWidth", "lfWeight"} else (0, 1) if key in {"lfItalic", "lfUnderline", "lfStrikeOut"} else (0, 255)
            result[key] = _integer(value, name, low, high)
        elif key in {"ShowID", "ShowParam", "ShowNodes"}:
            result[key] = _integer(value, name, 0, 1, boolean=True)
        else:
            literal = _literal(value)
            if literal is None:
                raise SchemeError(f"{name} must be a finite native style value.")
            result[key] = literal
    return result


def edit_properties(source_path, output_path, updates=None, analysis=None, definitions=None):
    from .analysis import command_prelude
    from .annotations import _copy_circuit, _text_objects, _RESERVED
    from .parameters import _declarations
    updates = {} if updates is None else updates
    analysis = {} if analysis is None else analysis
    if not isinstance(updates, dict) or len(updates) > 200:
        raise SchemeError("updates must map at most 200 root component names to parameter patches.")
    if not isinstance(analysis, dict) or set(analysis)-{"TD", "FD", "AOD", "SOD", "DCOP"}:
        raise SchemeError("analysis supports saved TD, FD, AOD, SOD and DCOP settings.")
    _, validated = command_prelude(definitions)
    definitions = validated["definitions"]
    lines = [item["name"] + ("("+",".join(item["arguments"])+")" if "arguments" in item else "")
             + "=" + item["expression"] + ";" for item in definitions]
    block = ".define\r\n" + "\r\n".join(lines) if lines else None
    changed = []

    def transform(document):
        objects = document["scm"]["Scheme"].get("Objects") or []
        names = {}
        for obj in objects:
            names.setdefault(obj.get("Name"), []).append(obj)
        declarations, _ = _declarations(document)
        reserved = set(_RESERVED) | _NATIVE_FUNCTIONS | {str(name).casefold() for name in names}
        reserved.update(item["name"].casefold() for item in declarations)
        for item in definitions:
            if item["name"].casefold() in reserved:
                raise SchemeError(f"Definition {item['name']!r} collides with a native symbol or existing declaration.")
            reserved.add(item["name"].casefold())
        for name, patch in updates.items():
            matches = names.get(name, [])
            if len(matches) != 1 or not isinstance(matches[0].get("Params"), dict):
                raise SchemeError(f"Component {name!r} is missing, ambiguous or has no parameters.")
            obj = matches[0]
            obj["Params"] = _component_parameters(obj, patch)
            changed.append(name)
        defaults = _analysis_defaults()
        for section, patch in analysis.items():
            current = {**copy.deepcopy(defaults[section]), **copy.deepcopy(document["scm"].get(section) or {})}
            current = _merge_style(current, patch) if section == "SOD" else merge_parameters(current, patch, section)
            _validate_analysis(section, current)
            document["scm"][section] = current
        if block:
            # Size the actual multiline definition text, never a placeholder.
            _text_objects(document, {}, [block], {})

    result = _copy_circuit(source_path, output_path, root_transform=transform)
    if block:
        result["texts"].append(block)
        result["text_count"] += 1
    result.update(updated_components=changed, updated_analysis_sections=list(analysis), definition_count=len(lines))
    return result
