"""Observed FASTMEAN 6.1 native element contracts, separate from support claims.

The native deserialization factory accepts 56 type IDs: 52 canonical records
and four legacy source aliases. Six canonical records are diagram/interface
services. Parameter names come from native serializers and bundled examples.
Numeric defaults below are adapter templates, not claimed GUI defaults.
Geometry and numerical-test evidence are reported independently.
"""
from __future__ import annotations

import copy


_FACTORY_IDS = frozenset({200, 300, 400, 410, 420, 900, 1000, 1001, 1002, 1003, 1010, 1011,
    1100, 1101, 1110, 2000, 2001, 2010, 2011, 3001, 3002, 3010, 3011, 6000, 6001, 6002,
    6003, 6100, 6101, 6102, 6200, 6201, 6300, 6400, 6401, 6500, 6501, 6502, 6510, 6600,
    6610, 6615, 6700, 6800, 6900, 6901, 6902, 6903, 6910, 6911, 6912, 6913, 6914, 6920, 7000, 7100})
_LEGACY = {2000: 2010, 2001: 2010, 3001: 3010, 3002: 3010}
_SERVICES = frozenset({200, 300, 400, 410, 420, 900})
_QUANTITATIVE = frozenset({1000, 1001, 1002, 1003, 1101, 2010, 3010, 6000, 6001, 6002, 6003, 6100, 6101, 6400, 6600, 6910, 6911, 6912, 6913, 7000, 7100})
_TESTED = _FACTORY_IDS - _SERVICES - set(_LEGACY) - {2011, 3011}
_LOGIC_LEVELS = {"Uhigh": 5.0, "Ulow": 0.0, "Ul2h": 2.5, "Uh2l": 2.5}


def _geometry(points, directions, size):
    return {"base_pin_positions": dict(enumerate(points, 1)),
            "base_pin_directions": dict(enumerate(directions, 1)),
            "body_bounds": (-size[0]//2, -size[1]//2, size[0]//2, size[1]//2)}


_TWO = _geometry(((-40, 0), (40, 0)), ((-1, 0), (1, 0)), (40, 16))
_CONTROLLED = _geometry(((-16, -28), (-16, 28), (8, -28), (8, 28)),
                        ((0, -1), (0, 1), (0, -1), (0, 1)), (48, 40))
_OA = _geometry(((-26, -8), (-26, 8), (26, 0)), ((-1, 0), (-1, 0), (1, 0)), (36, 48))
_CATALOG = {}


def _add(typeid, kind, pins, defaults, *, aliases=(), geometry=None, symbol="box", stage_link=None,
         parameter_schema=None, note=""):
    schema = parameter_schema or {key: {"type": "number"} for key in defaults}
    _CATALOG[typeid] = {"typeid": typeid, "type_id": typeid, "kind": kind, "aliases": list(aliases),
        "pin_names": list(pins) if pins is not None else None,
        "pin_count": len(pins) if pins is not None else None,
        "defaults": copy.deepcopy(defaults), "parameter_schema": copy.deepcopy(schema),
        "default_source": "adapter_numeric_template", "preview_symbol": symbol, "preview_label": kind,
        "stage_link": stage_link, "base_pin_positions": None, "base_pin_directions": None, "body_bounds": None,
        "parameter_status": "native_serializer", "geometry_status": "pending",
        "native_tested": typeid in _TESTED,
        "native_validation": {"create_preview_export_transient_smoke": typeid in _TESTED,
                              "independent_quantitative_cases": typeid in _QUANTITATIVE,
                              "device_model_calibrated": False},
        "native_test_scope": "Native SDK acceptance of a bounded fixture; not exhaustive model verification" if typeid in _TESTED else "No native solver acceptance claimed",
        "service": typeid in _SERVICES, "internal": typeid in {2011, 3011},
        "evidence": ["FASTMEAN 6.1 native factory", "native parameter serializer"], "notes": note}
    if geometry:
        _CATALOG[typeid].update(copy.deepcopy(geometry))
        _CATALOG[typeid]["geometry_status"] = "native_pin_initializer"


_add(200, "GND", ["ground"], {}, symbol="ground")
_add(300, "CON", ["branch1", "branch2", "branch3", "branch4"], {}, symbol="junction")
_add(400, "PORT", ["node"], {}, symbol="port")
_add(410, "DIGITAL_IN", ["node"], {}, symbol="port", note="External DLL co-simulation input: Name=alias.pin binds a .dll declaration. Not an ordinary port; generation and native execution are blocked without validated plugin bindings.")
_add(420, "DIGITAL_OUT", ["node"], {}, symbol="port", note="External DLL co-simulation output: Name=alias.pin binds a .dll declaration. Ordinary logic/subcircuit interfaces use PORT400; DLL execution is unsupported.")
_CATALOG[410].update(_geometry([(-18,0)],[(-1,0)],(20,14)),geometry_status="native_pin_initializer")
_CATALOG[420].update(_geometry([(18,0)],[(1,0)],(20,14)),geometry_status="native_pin_initializer")
_add(900, "TEXT", [], {}, symbol="text", note="Text/style fields are handled by the annotation API, not electrical parameters.")
_add(1000, "R", ["terminal1", "terminal2"], {"R": 1000.0}, geometry=_TWO, symbol="resistor")
_add(1001, "C", ["terminal1", "terminal2"], {"C": 1e-6, "IC": 0.0}, geometry=_TWO, symbol="capacitor")
_add(1002, "L", ["terminal1", "terminal2"], {"L": 1e-3, "IC": 0.0}, geometry=_TWO, symbol="inductor")
_add(1003, "UNISTOR", ["terminal1", "terminal2"], {"S": 1.0}, aliases=("UNI",))
_curve_schema = {"type": "curve", "min_points": 2, "max_points": 1000, "coordinates": ["x", "y"]}
_add(1010, "NLC", ["terminal1", "terminal2"], {"IC": 0.0, "fn": {"x": [-1, 0, 1], "y": [-1e-6, 0, 1e-6]}},
     parameter_schema={"IC": {"type": "number"}, "fn": _curve_schema}, symbol="capacitor", note="Native nonlinear charge/voltage characteristic.")
_add(1011, "NLL", ["terminal1", "terminal2"], {"IC": 0.0, "fn": {"x": [-1, 0, 1], "y": [-1e-3, 0, 1e-3]}},
     parameter_schema={"IC": {"type": "number"}, "fn": _curve_schema}, symbol="inductor", aliases=("NLI",))
_add(1100, "NLR", ["terminal1", "terminal2"], {"fn": {"x": [-1, 0, 1], "y": [-.001, 0, .001]}},
     parameter_schema={"fn": _curve_schema}, symbol="resistor")
_add(1101, "D", ["anode", "cathode"], {"Ron": .01, "Roff": 1e8, "Uon": .7}, aliases=("DIODE",),
     geometry=_geometry(((-21, 0), (21, 0)), ((-1, 0), (1, 0)), (24, 24)), symbol="diode")
_add(1110, "FSW", ["terminal1", "terminal2"], {"F": 1000.0, "K": 50.0, "Ron": .01, "Roff": 1e8, "Delay": 0.0}, aliases=("SWITCH_F",))
_add(2010, "U", ["negative", "positive"], {}, aliases=("V",), geometry=_TWO, symbol="voltage_source",
     note="Waveform parameters belong to source_waveforms; native voltage pin order is negative,positive.")
_add(2011, "U_AUX", ["terminal1", "terminal2"], {}, symbol="voltage_source", note="Auxiliary source record; factory-observed, semantics not numerically verified.")
_add(3010, "I", ["from", "to"], {}, geometry=_TWO, symbol="current_source", note="Waveforms belong to source_waveforms.")
_add(3011, "I_AUX", ["terminal1", "terminal2"], {}, symbol="current_source", note="Auxiliary source record; factory-observed, semantics not numerically verified.")
for tid, kind, key, alias in ((6000, "G", "g", "VCCS"), (6001, "E", "k", "VCVS"),
                              (6002, "F", "h", "CCCS"), (6003, "H", "r", "CCVS")):
    _add(tid, kind, ["control1", "control2", "output1", "output2"], {key: 1.0}, aliases=(alias,),
         geometry=_CONTROLLED, stage_link=(1, 3), note="Native terminal order; retain native sign conventions.")
_add(6100, "GYR", ["port1a", "port1b", "port2a", "port2b"], {"S": 1.0}, aliases=("GYRATOR",), stage_link=(1, 3))
_add(6101, "TR", ["primary_dot", "primary_undotted", "secondary_dot", "secondary_undotted"], {"n": 1.0}, aliases=("TRANSFORMER",),
     geometry=_geometry(((-24, -32), (-24, 32), (24, -32), (24, 32)), ((-1, 0), (-1, 0), (1, 0), (1, 0)), (32, 48)), stage_link=(1, 3), symbol="transformer")
_add(6102, "TR3", ["primary1", "primary2", "secondary1a", "secondary1b", "secondary2a", "secondary2b"], {"n1": 1.0, "n2": 1.0},
     geometry=_geometry(((-24, -32), (-24, 32), (24, -56), (24, -8), (24, 8), (24, 56)), ((-1, 0), (-1, 0), (1, 0), (1, 0), (1, 0), (1, 0)), (32, 96)), stage_link=(1, 3), symbol="transformer")
_add(6200, "TUBE", ["native_pin1", "native_pin2", "native_pin3"], {"S": .001, "Ri": 100000.0},
     geometry=_geometry(((-28, 0), (0, -28), (-8, 28)), ((-1, 0), (0, -1), (0, 1)), (40, 40)))
_add(6201, "NMOS_SMALL", ["native_pin1", "native_pin2", "native_pin3"], {"S": .001, "Ri": 100000.0},
     geometry=_geometry(((-24, 8), (8, -24), (8, 24)), ((-1, 0), (0, -1), (0, 1)), (32, 32)), note="Native small-signal NMos model, distinct from Type6615 power MOSFET.")
_add(6300, "NPN", ["native_pin1", "native_pin2", "native_pin3"], {"alpha": .99, "Rc": 1e6, "Re": 1.0, "Rb": 1000.0},
     geometry=_geometry(((-28, -8), (0, 18), (28, -8)), ((-1, 0), (0, 1), (1, 0)), (40, 28)), note="Native transistor model, not arbitrary SPICE model import.")
_add(6400, "OPAMP", ["noninverting", "inverting", "output"], {"k": 1e8}, geometry=_OA, symbol="opamp", stage_link=(1, 3))
_add(6401, "OPAMP_SAT", ["noninverting", "inverting", "output"], {"k": 1e8, "Uhigh": 10.0, "Ulow": -10.0},
     geometry=_OA, symbol="opamp", stage_link=(1, 3))
_add(6500, "PWM", None, {"F": 1000.0, "K": 50.0, "UInMax": 1.0, "UInMin": 0.0, "UOutMax": 5.0, "UOutMin": 0.0})
_add(6501, "PAM1", None, {"F": 1000.0, "K": 50.0, "Delay": 0.0})
_add(6502, "PAM2", None, {"F": 1000.0, "K": 50.0, "Delay": 0.0})
_add(6510, "BALMOD", None, {"F": 1000.0})
_add(6600, "SW", ["control_positive", "control_negative", "switch1", "switch2"], {"Ron": .01, "Roff": 1e8, "Uon": 3.0, "Uoff": 2.0},
     aliases=("VCSWITCH",), geometry=_geometry(((-16, -28), (-16, 28), (16, -28), (16, 28)), ((0, -1), (0, 1), (0, -1), (0, 1)), (40, 40)), symbol="switch")
_add(6610, "THYRISTOR", None, {"Ron": .01, "Roff": 1e8, "Udrop": .7, "Uth": 1.0})
_add(6615, "MOSFET", None, {"Ron": .1, "Roff": 1e8, "Uth": 3.0, "Model": 1, "Sact": 1.0, "Ract": 100.0},
     parameter_schema={**{key: {"type": "number"} for key in ("Ron", "Roff", "Uth", "Sact", "Ract")}, "Model": {"type": "integer", "enum": [0, 1, 2]}})
_add(6700, "LINE", None, {"Type": 1, "Begins": 1, "Ends": 1, "L0": .000711, "R0": 200.0, "C0": 24e-9, "G0": .001, "Len": .3, "n": 50},
     aliases=("LONG_LINE",), parameter_schema={**{key: {"type": "number"} for key in ("L0", "R0", "C0", "G0", "Len")},
         **{key: {"type": "integer"} for key in ("Type", "Begins", "Ends", "n")}})
_add(6800, "BRIDGE", ["native_pin1", "native_pin2", "native_pin3", "native_pin4"], {"Ron": .01, "Roff": 1e8, "Uon": .7},
     aliases=("RECTIFIER",), geometry=_geometry(((-40, 0), (0, -40), (40, 0), (0, 40)), ((-1, 0), (0, -1), (1, 0), (0, 1)), (64, 64)))
_add(6900, "RS", None, _LOGIC_LEVELS)
for tid, kind in ((6901, "DFF"), (6902, "JK")):
    _add(tid, kind, None, {"HasRS": 0, "InvRS": 0, "InvClock": 0, **_LOGIC_LEVELS},
         parameter_schema={**{key: {"type": "number"} for key in _LOGIC_LEVELS},
                           **{key: {"type": "integer", "enum": [0, 1]} for key in ("HasRS", "InvRS", "InvClock")}})
_add(6903, "RSCLK", None, {"InvClock": 0, **_LOGIC_LEVELS},
     parameter_schema={"InvClock": {"type": "integer", "enum": [0, 1]}, **{key: {"type": "number"} for key in _LOGIC_LEVELS}})
_add(6910, "NOT", None, _LOGIC_LEVELS)
for tid, kind in ((6911, "AND"), (6912, "OR"), (6913, "XOR")):
    _add(tid, kind, None, {"Type": tid, "N": 2, "InpInv": [0, 0], "OutInv": 0, **_LOGIC_LEVELS},
         parameter_schema={"Type": {"type": "integer", "enum": [tid]}, "N": {"type": "integer", "minimum": 2, "maximum": 8},
             "InpInv": {"type": "integer_array", "length_parameter": "N", "enum": [0, 1]}, "OutInv": {"type": "integer", "enum": [0, 1]},
             **{key: {"type": "number"} for key in _LOGIC_LEVELS}})
_add(6914, "LATCH", None, _LOGIC_LEVELS)
_add(6920, "COMP", ["positive", "negative", "output"], _LOGIC_LEVELS, aliases=("COMPARATOR",), stage_link=(1, 3))
_add(7000, "SUM", None, {"N": 2, "k": [1.0, 1.0]}, aliases=("SUMMER",),
     parameter_schema={"N": {"type": "integer", "minimum": 1, "maximum": 5}, "k": {"type": "number_array", "length_parameter": "N"}})
_add(7100, "X", None, {}, aliases=("SUB",), symbol="subcircuit",
     note="Named model pins and portable dependencies belong to create_project; arbitrary FileName paths are not electrical parameters.")


# Fixed native constructor dimensions and pin-setup arithmetic. These are
# geometry evidence, independently of whether a numerical test has been run.
_STATIC = {
    1003: (((-22, 0), (22, 0)), ((-1, 0), (1, 0)), (26, 52)),
    1010: (((-14, 0), (14, 0)), ((-1, 0), (1, 0)), (10, 30)),
    1011: (((-29, 0), (29, 0)), ((-1, 0), (1, 0)), (40, 16)),
    1100: (((-29, 0), (29, 0)), ((-1, 0), (1, 0)), (40, 36)),
    1110: (((-29, 0), (29, 0)), ((-1, 0), (1, 0)), (40, 20)),
    6100: (((-16, -28), (-16, 28), (16, -28), (16, 28)), ((0, -1), (0, 1), (0, -1), (0, 1)), (48, 40)),
    6500: (((-32, 0), (0, 32), (32, 0)), ((-1, 0), (0, 1), (1, 0)), (48, 48)),
    6501: (((-32, 0), (0, 32), (32, 0)), ((-1, 0), (0, 1), (1, 0)), (48, 48)),
    6502: (((-32, 0), (0, 32), (32, 0)), ((-1, 0), (0, 1), (1, 0)), (48, 48)),
    6510: (((-32, 0), (0, 32), (32, 0)), ((-1, 0), (0, 1), (1, 0)), (48, 48)),
    6610: (((-21, 0), (21, 0), (16, 10)), ((-1, 0), (1, 0), (0, 1)), (24, 24)),
    6615: (((-20, 8), (8, -27), (8, 21)), ((-1, 0), (0, -1), (0, 1)), (32, 32)),
    6700: (((-61, -8), (-61, 8), (61, -8), (61, 8)), ((-1, 0), (-1, 0), (1, 0), (1, 0)), (90, 36)),
    6900: (((-32, -12), (-32, 12), (32, -12), (32, 12)), ((-1, 0), (-1, 0), (1, 0), (1, 0)), (40, 48)),
    6901: (((-32, -12), (-32, 12), (32, -12), (32, 12)), ((-1, 0), (-1, 0), (1, 0), (1, 0)), (40, 48)),
    6902: (((-32, -12), (-32, 0), (-32, 12), (32, -12), (32, 12)), ((-1, 0), (-1, 0), (-1, 0), (1, 0), (1, 0)), (40, 48)),
    6903: (((-32, -12), (-32, 0), (-32, 12), (32, -12), (32, 12)), ((-1, 0), (-1, 0), (-1, 0), (1, 0), (1, 0)), (40, 48)),
    6910: (((-24, 0), (24, 0)), ((-1, 0), (1, 0)), (16, 32)),
    6914: (((-28, -8), (0, 32), (28, -8)), ((-1, 0), (0, 1), (1, 0)), (32, 40)),
    6920: (((-26, -8), (-26, 8), (26, 0)), ((-1, 0), (-1, 0), (1, 0)), (36, 48)),
}
for _tid, _shape in _STATIC.items():
    _CATALOG[_tid].update(_geometry(*_shape))
    _CATALOG[_tid]["geometry_status"] = "native_pin_initializer"
    if _CATALOG[_tid]["pin_names"] is None:
        _CATALOG[_tid]["pin_names"] = [f"native_pin{pin}" for pin in range(1, len(_shape[0])+1)]
        _CATALOG[_tid]["pin_count"] = len(_shape[0])
_CATALOG[6510]["internal_pin_indices"] = [4]
_CATALOG[6510]["native_total_pin_count"] = 4
for _tid in (2011, 3011):
    _CATALOG[_tid]["notes"] = "Internal zero-size auxiliary source; not the USER source-waveform mode or an ordinary insertable source."
    _CATALOG[_tid]["geometry_status"] = "internal_not_placeable"
_CATALOG[7100]["geometry_status"] = "native_font_geometry_adapter"
for _tid in (1000, 1001, 1002, 2010, 3010):
    _CATALOG[_tid]["geometry_status"] = "legacy_generated_contract"
    _CATALOG[_tid]["notes"] += " Existing generated +/-40 terminal contract retained; raw constructor body dimensions differ from the active schematic view contract."
for _tid in (6911, 6912, 6913, 7000):
    _CATALOG[_tid]["geometry_status"] = "native_dynamic_pin_initializer"
for _tid in (6500, 6501, 6502, 6510):
    _CATALOG[_tid]["pin_names"] = ["input", "common", "output"]
    _CATALOG[_tid]["stage_link"] = (1, 3)
_CATALOG[6610]["pin_names"] = ["anode", "cathode", "gate"]
_CATALOG[6615]["pin_names"] = ["gate", "drain", "source"]
_CATALOG[6700]["pin_names"] = ["input1", "input2", "output1", "output2"]
_CATALOG[6700]["stage_link"] = (1, 3)
_CATALOG[7000]["stage_link"] = (3, 1)
_CATALOG[6615]["stage_link"] = (1, 2)
_CATALOG[6300]["stage_link"] = (1, 3)
_CATALOG[1003]["notes"] = "Directional conductance: native AC probe confirms output current S*V(input,0), not a passive resistor."
_CATALOG[1003]["stage_link"] = (1, 2)
for _tid in (1003, 6003, 6100):
    _CATALOG[_tid]["native_test_scope"] = "Independent native AC scalar response probe; not an exhaustive nonlinear/transient test"


class CatalogError(ValueError):
    """A structured parameter or requested native geometry is invalid."""


def normalize_parameters(kind_or_id, parameters=None):
    """Merge numeric templates with typed, bounded native parameter overrides.

    No script, file-reference or arbitrary expression fields are accepted. U/I
    source waveforms and X project references use their dedicated adapters.
    """
    from .schematic import parse_value
    entry = get_element(kind_or_id)
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict) or set(parameters)-set(entry["defaults"]):
        raise CatalogError(f"{entry['kind']}: unsupported native parameter keys")
    result = {**entry["defaults"], **copy.deepcopy(parameters)}
    for key, schema in entry["parameter_schema"].items():
        value, category = result[key], schema["type"]
        if category == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise CatalogError(f"{key} must be an integer")
            if ("enum" in schema and value not in schema["enum"] or
                    "minimum" in schema and value < schema["minimum"] or
                    "maximum" in schema and value > schema["maximum"]):
                raise CatalogError(f"{key} is outside the supported native range")
        elif category == "number":
            result[key] = parse_value(value)
        elif category == "curve":
            if not isinstance(value, dict) or set(value) != {"x", "y"}:
                raise CatalogError(f"{key} must be exactly an x/y point table")
            x, y = value["x"], value["y"]
            if (not isinstance(x, list) or not isinstance(y, list) or len(x) != len(y)
                    or not schema["min_points"] <= len(x) <= schema["max_points"]):
                raise CatalogError(f"{key} needs matching bounded x/y arrays")
            x, y = [parse_value(v) for v in x], [parse_value(v) for v in y]
            if any(a >= b for a, b in zip(x, x[1:])):
                raise CatalogError(f"{key}.x must strictly increase")
            result[key] = {"x": x, "y": y}
        elif category in {"number_array", "integer_array"}:
            count = result[schema["length_parameter"]]
            if key not in parameters:
                value = [1.0 if category == "number_array" else 0]*count
            if not isinstance(value, list) or len(value) != count:
                raise CatalogError(f"{key} must contain exactly {count} values")
            if category == "number_array":
                result[key] = [parse_value(v) for v in value]
            else:
                if any(isinstance(v, bool) or not isinstance(v, int) or v not in schema["enum"] for v in value):
                    raise CatalogError(f"{key} must contain native 0/1 inversion flags")
                result[key] = list(value)
    for key in ("R", "C", "L", "Ron", "n", "n1", "n2", "Ri", "Rc", "Re", "Rb", "Len"):
        if key in result and result[key] <= 0:
            raise CatalogError(f"{key} must be positive")
    if "Ron" in result and result.get("Roff", result["Ron"]) < result["Ron"]:
        raise CatalogError("Roff must be at least Ron")
    if "F" in result and result["F"] <= 0:
        raise CatalogError("F must be positive")
    if "K" in result and not 0 <= result["K"] <= 100:
        raise CatalogError("K must be a duty percentage from 0 through 100")
    if "Delay" in result and result["Delay"] < 0:
        raise CatalogError("Delay must be nonnegative")
    if "alpha" in result and not 0 <= result["alpha"] <= 1:
        raise CatalogError("Native NPN alpha must be from 0 through 1")
    if "Uhigh" in result and result["Uhigh"] <= result["Ulow"]:
        raise CatalogError("Uhigh must exceed Ulow")
    if "Ul2h" in result and result["Ul2h"] < result["Uh2l"]:
        raise CatalogError("Rising threshold Ul2h must be at least falling threshold Uh2l")
    if "UInMax" in result and result["UInMax"] <= result["UInMin"]:
        raise CatalogError("UInMax must exceed UInMin")
    if "UOutMax" in result and result["UOutMax"] <= result["UOutMin"]:
        raise CatalogError("UOutMax must exceed UOutMin")
    if "Uoff" in result and result["Uoff"] > result["Uon"]:
        raise CatalogError("Uoff must not exceed Uon")
    if entry["kind"] == "LINE" and (result["n"] < 1 or result["n"] > 1000 or
            any(result[key] < 0 for key in ("L0", "R0", "C0", "G0"))):
        raise CatalogError("LINE needs nonnegative distributed parameters and n from 1 through 1000")
    return result


def get_geometry(kind_or_id, parameters=None):
    """Return unrotated native physical pins, including parameter-dependent pins.

    BALMOD's internal fourth node is deliberately not a physical wire endpoint.
    X box sizing remains in native_geometry with the declared side pin names.
    """
    entry = get_element(kind_or_id)
    if parameters is not None and not isinstance(parameters, dict):
        raise CatalogError("Native geometry parameters must be a mapping")
    params = {**entry["defaults"], **(parameters or {})}
    tid = entry["typeid"]
    # Inspecting an existing circuit must not evaluate its electrical parameter
    # expressions. Only N/HasRS alter these physical pin coordinates.
    if tid in (6911, 6912, 6913, 7000):
        n, limit = params["N"], 5 if tid == 7000 else 8
        if isinstance(n, bool) or not isinstance(n, int) or not (1 if tid == 7000 else 2) <= n <= limit:
            raise CatalogError("N is outside the native physical pin capacity")
    if tid in (6901, 6902) and (isinstance(params["HasRS"], bool) or not isinstance(params["HasRS"], int) or params["HasRS"] not in (0, 1)):
        raise CatalogError("HasRS must be native integer 0 or 1")
    shape = {key: copy.deepcopy(entry[key]) for key in ("base_pin_positions", "base_pin_directions", "body_bounds", "pin_names")}
    if tid in (6911, 6912, 6913):
        count = params["N"]
        pitch = 16 if count == 2 else 8
        ys = [-(count-1)*pitch//2+index*pitch for index in range(count)]
        shape = {**_geometry([(-32, y) for y in ys]+[(32, 0)], [(-1, 0)]*count+[(1, 0)], (40, max(32, 8*count+8))),
                 "pin_names": [f"input{pin}" for pin in range(1, count+1)]+["output"]}
    elif tid == 7000:
        count = params["N"]
        height = max(40, 16*count)
        shape = {**_geometry([(36, 0), (0, height//2+8)]+[(-36, -(count-1)*8+index*16) for index in range(count)],
                            [(1, 0), (0, 1)]+[(-1, 0)]*count, (56, height)),
                 "pin_names": ["output", "common"]+[f"input{pin}" for pin in range(1, count+1)]}
    elif tid in (6901, 6902) and params["HasRS"]:
        count = len(shape["base_pin_positions"])
        shape["base_pin_positions"].update({count+1: (0, -36), count+2: (0, 36)})
        shape["base_pin_directions"].update({count+1: (0, -1), count+2: (0, 1)})
        shape["pin_names"] += ["async_native_pin1", "async_native_pin2"]
    if shape["base_pin_positions"] is None:
        raise CatalogError(f"{entry['kind']}: geometry uses a separate adapter or is not a physical insertable element")
    return shape


def entries(*, include_service=False, include_legacy=False):
    """Return independent records; evidence is not a claim of full tool support."""
    result = [copy.deepcopy(entry) for tid, entry in sorted(_CATALOG.items()) if include_service or tid not in _SERVICES]
    if include_legacy:
        for tid, canonical in sorted(_LEGACY.items()):
            entry = get_element(tid)
            entry["kind"] = f"LEGACY_{tid}"
            result.append(entry)
    return sorted(result, key=lambda entry: entry["typeid"])


def get_element(kind_or_id):
    """Resolve a kind/alias or exact factory ID, returning a defensive copy."""
    if isinstance(kind_or_id, bool):
        raise KeyError("A boolean is not a native element ID")
    if isinstance(kind_or_id, int):
        if kind_or_id in _LEGACY:
            result = get_element(_LEGACY[kind_or_id])
            result.update({"typeid": kind_or_id, "type_id": kind_or_id, "legacy_alias_of": _LEGACY[kind_or_id]})
            result.update(native_tested=False,native_validation={
                "create_preview_export_transient_smoke":False,"independent_quantitative_cases":False,
                "device_model_calibrated":False},native_test_scope="Native factory alias; quantitative acceptance belongs to the canonical class, not an independently generated legacy record")
            return result
        return copy.deepcopy(_CATALOG[kind_or_id])
    if isinstance(kind_or_id, str):
        name = kind_or_id.upper()
        for entry in _CATALOG.values():
            if name == entry["kind"] or name in entry["aliases"]:
                return copy.deepcopy(entry)
    raise KeyError(f"Unknown native FASTMEAN element: {kind_or_id!r}")


def inventory_summary():
    """Report the bounded scope actually observed in this executable factory."""
    return {"native_version": "6.1", "native_executable_sha256": "a001582ada87cdf013605f43b019957ae23204ef4bfcc33be02a0681b186ee25",
            "factory_type_ids": sorted(_FACTORY_IDS),
            "factory_count": len(_FACTORY_IDS), "canonical_count": len(_CATALOG),
            "electrical_count": len(_CATALOG)-len(_SERVICES), "insertable_electrical_count": len(_CATALOG)-len(_SERVICES)-2,
            "internal_type_ids": [2011, 3011], "legacy_aliases": dict(_LEGACY),
            "service_type_ids": sorted(_SERVICES), "native_tested_count": len(_TESTED),
            "quantitatively_verified_count": len(_QUANTITATIVE),
            "unsupported_contexts": ["External DLL co-simulation and DIGITAL_IN/OUT bindings", "GUI editor interaction and arbitrary model/plugin import"],
            "geometry_pending": [entry["kind"] for entry in entries() if entry["geometry_status"] == "pending"]}
