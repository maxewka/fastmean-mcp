"""Assigned 1-kHz nominal values for TI SLOA049D Figure B-2's topology.

Reference: https://www.ti.com/lit/an/sloa049d/sloa049d.pdf, section B.2.
The published topology contains 18 parts. VIN and RL are two test fixtures.
These component values and the ideal finite-gain op-amps are our test choices,
not TI's commercial-amplifier model or a redistributed reference image.
"""
import json
import math


SOURCE_URL = "https://www.ti.com/lit/an/sloa049d/sloa049d.pdf"
STAGES = ((1.6060, .5103), (1.6913, .6112), (1.9071, 1.0234))
CORNER_HZ = 1000.0
RESISTANCE = 10000.0
OPAMP_GAIN = 1e8
AC_SIGNALS = ["db(U(S1)/U(IN))", "db(U(S2)/U(IN))", "db(U(OUT)/U(IN))", "phs(U(OUT)/U(IN))"]
TD_SIGNALS = ["U(IN)", "U(S1)", "U(S2)", "U(OUT)"]


def stage_values(fsf, quality, fc=CORNER_HZ, resistance=RESISTANCE):
    c1 = 1 / (2*math.pi*resistance*fsf*fc*3*quality)
    return c1, (3*quality)**2*c1


def make_spec():
    parts = [{"kind": "U", "name": "VIN", "nodes": ["input", "0"], "value": 1,
              "waveform": {"kind": "sine", "frequency": CORNER_HZ, "phase": -90}}]
    previous = "input"
    bindings = {"VIN": "VPEAK", "RL": "RLOAD"}
    parameters = {"VPEAK": 1, "RBASE": RESISTANCE, "RLOAD": 10000}
    for index, (fsf, quality) in enumerate(STAGES):
        letter = "ABC"[index]
        a, b, output = f"a{index+1}", f"b{index+1}", f"o{index+1}"
        c1, c2 = stage_values(fsf, quality)
        parts.extend([
            {"kind": "R", "name": f"R1{letter}", "nodes": [previous, a], "value": RESISTANCE},
            {"kind": "R", "name": f"R3{letter}", "nodes": [a, b], "value": RESISTANCE},
            {"kind": "OPAMP", "name": f"OA{index+1}", "nodes": ["0", b, output], "parameters": {"k": OPAMP_GAIN}},
            {"kind": "R", "name": f"R2{letter}", "nodes": [a, output], "value": RESISTANCE},
            {"kind": "C", "name": f"C1{letter}", "nodes": [b, output], "value": c1},
            {"kind": "C", "name": f"C2{letter}", "nodes": [a, "0"], "value": c2},
        ])
        for number in (1, 2, 3):
            bindings[f"R{number}{letter}"] = "RBASE"
        for number, value in ((1, c1), (2, c2)):
            parameter = f"CAP{number}{letter}"
            parameters[parameter] = value
            bindings[f"C{number}{letter}"] = parameter
        previous = output
    parts.append({"kind": "R", "name": "RL", "nodes": [previous, "0"], "value": parameters["RLOAD"]})
    ports = {"IN": "input", "S1": "o1", "S2": "o2", "OUT": "o3"}
    spec = {"title": "Sixth-order Bessel MFB low-pass; TI SLOA049D Figure B-2 topology",
        "description": "18 reference topology parts + VIN/RL test fixtures; assigned 1-kHz values; ideal native op-amps.",
        "components": parts, "ports": ports,
        "analysis": {"input": "IN", "output": "OUT", "frequency": {"start": 10, "stop": 100000, "points": 301},
                     "transient": {"stop": .01, "step": 2e-6}}}
    return spec, {"parameters": parameters, "bindings": bindings,
        "td_signals": TD_SIGNALS, "fd_signals": AC_SIGNALS,
        "descriptions": [
            "Bessel MFB: 3 cascaded second-order stages; corner about 1 kHz.\nTI SLOA049D Fig.B-2 topology: 18 parts + VIN and RL test fixtures.",
            "U(IN), U(S1), U(S2), U(OUT): input and stage-output waveforms [V].\ndb(U(OUT)/U(IN)): overall gain [dB]; phs(...): phase [degrees].",
            "db(U(S1)/U(IN)), db(U(S2)/U(IN)): accumulated stage gains [dB].\nRBASE changes all nine filter resistors; CAP1A through CAP2C set pole pairs.",
            "Assigned values: RBASE=10 kohm, VIN=1 V peak at 1 kHz, RLOAD=10 kohm.\nOA1 through OA3: native ideal gain 1e8; no rails, clipping, GBW or current limit."]}


if __name__ == "__main__":
    print(json.dumps(make_spec()[0], indent=2))
