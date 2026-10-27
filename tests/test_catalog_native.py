"""Opt-in real-SDK/native regressions for expanded elements and CIRSYM aliases."""
import ast
import csv
import hashlib
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from fastmean_mcp.schematic import parse_value

APP = Path(os.environ.get("FASTMEAN_APP_DIR", ""))
if not (APP / "Fastmean.exe").is_file():
    APP = Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1"
ENABLED = (os.name == "nt" and os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1"
           and (APP / "Fastmean.exe").is_file())


def data(result):
    with Path(result["csv_path"]).open(encoding="utf-8-sig", newline="") as stream:
        return [list(map(float, row)) for row in list(csv.reader(stream))[1:]]


def formula_value(expression, variables):
    """Evaluate only the arithmetic returned by CIRSYM, never Python source."""
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in {int, float, complex}:
            return node.value
        if isinstance(node, ast.Name):
            return variables[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / right
            if isinstance(node.op, ast.Pow): return left ** right
        raise AssertionError(f"Unexpected symbolic arithmetic: {ast.dump(node)}")
    return visit(ast.parse(expression.replace("^", "**"), mode="eval"))


@unittest.skipUnless(ENABLED, "Requires Windows FASTMEAN and FASTMEAN_MCP_NATIVE_TEST=1")
class CatalogNativeTests(unittest.IsolatedAsyncioTestCase):
    async def session(self, action):
        with tempfile.TemporaryDirectory(prefix="fm-catalog-native-") as directory:
            params = StdioServerParameters(command=sys.executable, args=["-X", "utf8", "-m", "fastmean_mcp"],
                env=dict(os.environ, FASTMEAN_APP_DIR=str(APP), FASTMEAN_OUTPUT_DIR=directory))
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()
                    async def call(tool, **arguments):
                        response = await client.call_tool(tool, arguments, read_timeout_seconds=90)
                        self.assertFalse(response.is_error, str(response.content)[:2500])
                        return response.structured_content
                    await call("fastmean_status")
                    await action(call)

    async def assert_symbolic_matches(self, call, path, source_name, amplitude, expected):
        symbolic = await call("fastmean_symbolic", path=str(path), output="OUT", input=None,
                              analysis="transfer", input_source=source_name)
        self.assertTrue(symbolic["ok"], str(symbolic)[:2000])
        function = symbolic["symbolic_function"]
        variables = dict(function.get("parameters", {}))
        variables.update({key: parse_value(value) for key, value in symbolic.get("parameters", {}).items()})
        ac = await call("fastmean_ac", path=str(path), signals=["RE(U(OUT))", "IM(U(OUT))"],
                        fmin=10, fmax=10000, points=4)
        for frequency, real, imag in data(ac):
            native = complex(real, imag) / amplitude
            value = formula_value(function["expression"], {**variables, "p": 2j * math.pi * frequency})
            self.assertAlmostEqual(native, expected, delta=1e-9)
            self.assertAlmostEqual(value, native, delta=1e-9)
        return symbolic

    async def test_long_qualified_component_names_survive_nested_symbolic_expansion(self):
        async def action(call):
            # These names used to collapse to the same long CIRSYM identifier.
            cell = {"pins": {"Left": ["A"], "Right": ["B"]}, "circuit": {
                "components": [
                    {"kind": "R", "name": "R_RL1", "nodes": ["a", "middle"], "value": 2000},
                    {"kind": "R", "name": "R_RL2", "nodes": ["middle", "b"], "value": 2000}],
                "ports": {"A": "a", "B": "b"}}}
            outer = {"pins": {"Left": ["A"], "Right": ["B"]}, "circuit": {
                "components": [{"kind": "X", "name": "LONGINNER", "model": "CELL",
                                "connections": {"A": "a", "B": "b"}}], "ports": {"A": "a", "B": "b"}}}
            spec = {"models": {"CELL": cell, "OUTER": outer}, "circuit": {"components": [
                {"kind": "U", "name": "VIN", "nodes": ["input", "0"], "value": 1,
                 "waveform": {"kind": "sine", "frequency": 1000}},
                {"kind": "X", "name": "LONGINSTANCE", "model": "OUTER", "connections": {"A": "input", "B": "output"}},
                {"kind": "R", "name": "R_RL3", "nodes": ["output", "0"], "value": 4000}],
                "ports": {"IN": "input", "OUT": "output"}}}
            created = await call("fastmean_create_project", name="nested_aliases", spec=spec)
            path = Path(created["path"])
            before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.parent.rglob("*.scm")}
            symbolic = await self.assert_symbolic_matches(call, path, "VIN", 1, .5)
            aliases = symbolic["conversion"]["native_aliases"]
            self.assertEqual(len(set(aliases.values())), len(aliases))
            self.assertTrue(any("LONGINNER.R_RL1" in part["name"] for part in symbolic["conversion"]["components"]))
            self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})
        await self.session(action)

    async def test_large_finite_opamp_gain_matches_native_ac(self):
        async def action(call):
            gain=1e15
            made=await call("fastmean_create_circuit",name="finite_opamp",spec={"components":[
                {"kind":"U","name":"VIN","nodes":["input","0"],"value":1,
                 "waveform":{"kind":"sine","frequency":1000}},
                {"kind":"OPAMP","name":"AMP","nodes":["input","0","output"],"parameters":{"k":gain}},
                {"kind":"R","name":"RL","nodes":["output","0"],"value":1000}],
                "ports":{"IN":"input","OUT":"output"}})
            symbolic=await call("fastmean_symbolic",path=made["path"],output="OUT",input=None,
                                analysis="transfer",input_source="VIN")
            self.assertTrue(symbolic["ok"])
            function=symbolic["symbolic_function"]
            variables={**function["parameters"],**{k:parse_value(v) for k,v in symbolic["parameters"].items()}}
            ac=await call("fastmean_ac",path=made["path"],signals=["RE(U(OUT))","IM(U(OUT))"],
                          fmin=1000,fmax=2000,points=2)
            for frequency,real,imag in data(ac):
                native=complex(real,imag)
                actual=formula_value(function["expression"],{**variables,"p":2j*math.pi*frequency})
                self.assertAlmostEqual(native/gain,1,delta=1e-12)
                self.assertAlmostEqual(actual/native,1,delta=1e-12)
        await self.session(action)

    async def test_cccs_and_ccvs_symbolic_polarity_matches_native_current_drive(self):
        async def action(call):
            for kind, field, gain, ratio in (("F", "h", 2, 2000), ("H", "r", 1000, 1000)):
                for reversed_output in (False, True):
                    with self.subTest(kind=kind, reversed_output=reversed_output):
                        output_pins = ["0", "output"] if reversed_output else ["output", "0"]
                        spec = {"components": [
                            {"kind": "I", "name": "IBIAS", "nodes": ["0", "control"], "value": .001,
                             "waveform": {"kind": "sine", "frequency": 1000}},
                            {"kind": kind, "name": "DUT", "nodes": ["control", "0", *output_pins],
                             "parameters": {field: gain}},
                            {"kind": "R", "name": "RL", "nodes": ["output", "0"], "value": 1000}],
                            "ports": {"IN": "control", "OUT": "output"}}
                        created = await call("fastmean_create_circuit", name=f"{kind}_polarity", spec=spec)
                        path = Path(created["path"])
                        before = path.read_bytes()
                        await self.assert_symbolic_matches(call, path, "IBIAS", .001, -ratio if reversed_output else ratio)
                        self.assertEqual(path.read_bytes(), before)
        await self.session(action)

    async def test_transformer_scalar_parameter_bindings_are_native_expressions(self):
        async def action(call):
            spec = {"components": [
                {"kind": "U", "name": "VIN", "nodes": ["input", "0"], "value": 1,
                 "waveform": {"kind": "sine", "frequency": 1000}},
                {"kind": "TR3", "name": "T1", "nodes": ["input", "0", "a", "0", "b", "0"],
                 "parameters": {"n1": 2, "n2": 3}},
                {"kind": "R", "name": "RA", "nodes": ["a", "0"], "value": 1000},
                {"kind": "R", "name": "RB", "nodes": ["b", "0"], "value": 1000}],
                "ports": {"IN": "input", "OUT": "a", "AUX": "b"}}
            made = await call("fastmean_create_circuit", name="transformer_bindings", spec=spec)
            bound = await call("fastmean_annotate_circuit", path=made["path"],
                parameters={"RatioA": 2, "RatioB": 3, "DriveFreq": 1000},
                bindings={"T1": {"n1": "RatioA", "n2": "RatioB"}, "VIN": {"AC.F": "DriveFreq"}})
            bound_path = Path(bound["path"])
            before = bound_path.read_bytes()
            changed = await call("fastmean_edit_parameters", path=str(bound_path), updates={"RatioA": 4, "DriveFreq": 2000})
            for source, ratio in ((bound["path"], .5), (changed["path"], .25)):
                ac = await call("fastmean_ac", path=source, signals=["RE(U(OUT)/U(IN))", "RE(U(AUX)/U(IN))"],
                                fmin=10, fmax=10000, points=4)
                for row in data(ac):
                    self.assertAlmostEqual(row[1], ratio, delta=1e-12)
                    self.assertAlmostEqual(row[2], 1 / 3, delta=1e-12)
            self.assertEqual(bound_path.read_bytes(), before)
        await self.session(action)

    async def test_optional_async_flipflop_terminals_are_connected_in_native_model(self):
        async def action(call):
            for kind, input_count in (("DFF", 2), ("JK", 3)):
                with self.subTest(kind=kind):
                    inputs = [f"in{i}" for i in range(input_count)]
                    nodes = inputs + ["q", "nq", "reset", "set"]
                    spec = {"components": [{"kind": kind, "name": "DUT", "nodes": nodes, "parameters": {"HasRS": 1}}]
                        + [{"kind": "U", "name": f"DRIVE{i}", "nodes": [node, "0"], "value": 0}
                           for i, node in enumerate(inputs + ["reset", "set"])]
                        + [{"kind": "R", "name": "RQ", "nodes": ["q", "0"], "value": 1000},
                           {"kind": "R", "name": "RNQ", "nodes": ["nq", "0"], "value": 1000}],
                        "ports": {"OUT": "q", "NEGATED": "nq"}}
                    made = await call("fastmean_create_circuit", name=f"{kind}_async", spec=spec)
                    td = await call("fastmean_transient", path=made["path"], signals=["U(OUT)", "U(NEGATED)"],
                                    stop=1e-5, step=1e-6)
                    rows = data(td)
                    self.assertGreaterEqual(len(rows), 11)
                    self.assertTrue(all(math.isfinite(value) for row in rows for value in row))
                    self.assertTrue(all(abs(row[1] + row[2] - 5) < 1e-9 for row in rows))
        await self.session(action)
