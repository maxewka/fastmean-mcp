"""All five native U/I waveform modes, with bounded numeric PWL tables."""
from __future__ import annotations

import copy

MODES = {"dc": (1, "DC"), "sine": (2, "AC"), "pulse": (3, "PULSE"),
         "triangle": (4, "TRIANG"), "pwl": (5, "USER")}
ALIASES = {"triangular": "triangle", "triang": "triangle", "user": "pwl", "custom": "pwl"}
MAX_PWL_POINTS = 4096


def _aliases(current=False):
    q = "I" if current else "U"
    return {"amplitude": q+"0", "frequency": "F", "phase": "PHI0", "delay": "Delay",
            "high": q+"MAX", "low": q+"MIN", "duty_percent": "K", "rise_time": "TFR",
            "finite_duration": "FD", "periods": "NP", "delay_periods":"Delay", "time_scale": "ScaleT",
            "scale": "Scale"+q, "offset": "Offset"+q, "periodic": "PER", "points": q}


def source_parameters(value, waveform, *, current=False):
    from .schematic import SchemeError, parse_value
    q = "I" if current else "U"
    params = {"ST": 1, "DC": {q+"0": value, "Delay": 0, "TFR": "1n"},
        "AC": {q+"0": value, "F": 1000, "PHI0": 0, "FD": 0, "NP": 1, "Delay": 0},
        "PULSE": {"F": 1000, "K": 50, q+"MAX": value, q+"MIN": 0, "TFR": "1n", "Delay": 0},
        "TRIANG": {"F": 1000, "K": 50, q+"MAX": value, q+"MIN": 0, "Delay": 0},
        "USER": {"ScaleT": 1, "Scale"+q: 1, "Offset"+q: 0, "Delay": 0, "PER": 0, "NP": 1,
                 q: {"x": [0, .05, .5, .55, 1], "y": [0, 1, 1, 0, 0]}}}
    if waveform is None:
        return params
    if not isinstance(waveform, dict):
        raise SchemeError("waveform must be a mapping.")
    kind = ALIASES.get(str(waveform.get("kind", "dc")).lower(), str(waveform.get("kind", "dc")).lower())
    if kind not in MODES:
        raise SchemeError("Supported source waveforms: dc, sine, pulse, triangle, pwl.")
    if "delay_periods" in waveform and (kind not in {"sine","pulse","triangle"} or "delay" in waveform):
        raise SchemeError("delay_periods is an alternative to delay in seconds for sine/pulse/triangle.")
    params["ST"], section = MODES[kind]
    target, aliases = params[section], _aliases(current)
    for key, raw in waveform.items():
        if key == "kind":
            continue
        native = aliases.get(key)
        if native not in target:
            raise SchemeError(f"Unsupported {kind} waveform field: {key}")
        if key == "points":
            if not isinstance(raw, list) or not 2 <= len(raw) <= MAX_PWL_POINTS:
                raise SchemeError(f"PWL points needs 2 to {MAX_PWL_POINTS} [time,value] pairs.")
            points = []
            for point in raw:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise SchemeError("Every PWL point must be a [time,value] pair.")
                points.append([parse_value(v) for v in point])
            if any(a[0] >= b[0] for a,b in zip(points, points[1:])):
                raise SchemeError("PWL times must be strictly increasing.")
            target[native] = {"x": [p[0] for p in points], "y": [p[1] for p in points]}
            continue
        if key in {"periodic", "finite_duration"}:
            if not isinstance(raw, bool) and not (type(raw) is int and raw in (0,1)):
                raise SchemeError(f"{key} must be a boolean.")
            target[native] = int(raw)
            continue
        numeric = parse_value(raw)
        if native in {"F", "TFR", "ScaleT"} and numeric <= 0:
            raise SchemeError(f"{key} must be positive.")
        if native == "Delay" and numeric < 0:
            raise SchemeError("delay cannot be negative.")
        if native == "K" and not 0 < numeric < 100:
            raise SchemeError("duty_percent must be between 0 and 100.")
        if native == "NP" and not 0 < numeric <= 1000000:
            raise SchemeError("periods must be positive and at most 1000000; fractional sine periods are supported.")
        target[native] = numeric
    if kind in {"sine","pulse","triangle"} and "delay" in waveform:
        # These three native modes measure Delay in periods, not seconds.
        target["Delay"] *= parse_value(target["F"])
    return params


def patch_source(parameters, value, waveform, *, current=False):
    """Update only requested fields; keep inactive modes and omitted fields."""
    requested=copy.deepcopy(waveform)
    if isinstance(requested,dict):
        if "kind" not in requested:
            requested["kind"]=describe_source(parameters,current=current)[1]["kind"]
        requested_kind=str(requested["kind"]).lower()
        requested_kind=ALIASES.get(requested_kind,requested_kind)
        if requested_kind in {"sine","pulse","triangle"} and "delay" in requested and "frequency" not in requested:
            requested["frequency"]=(parameters.get(MODES[requested_kind][1]) or {}).get("F",1000)
    template = source_parameters(value, requested, current=current)
    mode = template["ST"]
    section = next(section for number,section in MODES.values() if number == mode)
    result = copy.deepcopy(parameters)
    existing = result.get(section) or {}
    from .schematic import SchemeError
    if not isinstance(existing, dict):
        raise SchemeError(f"Source has invalid {section} parameters.")
    target = {**template[section], **existing}
    q = "I" if current else "U"
    base_key = q+"MAX" if section in {"PULSE", "TRIANG"} else q+"0" if section != "USER" else "Scale"+q
    if section != "USER":
        target[base_key] = value
    aliases = _aliases(current)
    for key in waveform or {}:
        if key != "kind":
            target[aliases[key]] = copy.deepcopy(template[section][aliases[key]])
    result.update({"ST": mode, section: target})
    return result


def describe_source(parameters, *, current=False):
    mode = parameters.get("ST")
    kind, section = next(((k,s) for k,(n,s) in MODES.items() if n == mode), ("unsupported", ""))
    active, q = parameters.get(section) or {}, "I" if current else "U"
    result = {"kind": kind}
    for public,native in _aliases(current).items():
        if native not in active:
            continue
        value = active[native]
        if public=="delay_periods" and mode not in {2,3,4}:continue
        if public=="delay" and mode in {2,3,4}:
            from .schematic import parse_value
            try:value=parse_value(value)/parse_value(active["F"])
            except (ValueError,ZeroDivisionError):continue
        if public == "points":
            if isinstance(value,dict) and isinstance(value.get("x"),list) and isinstance(value.get("y"),list):
                value = [list(pair) for pair in zip(value["x"],value["y"])]
        elif public in {"periodic", "finite_duration"}:
            value = bool(value)
        result[public] = copy.deepcopy(value)
    value = active.get(q+"MAX" if mode in {3,4} else "Scale"+q if mode == 5 else q+"0")
    return value, result
