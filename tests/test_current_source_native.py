"""Opt-in native current-source direction and parameter binding via real MCP."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from test_current_source import current_spec


APP = Path(os.environ.get("FASTMEAN_APP_DIR", ""))
if not (APP / "Fastmean.exe").is_file():
    APP = Path(os.environ.get("LOCALAPPDATA", "")) / "FASTMEAN 6.1"
ENABLED = (os.name == "nt" and os.environ.get("FASTMEAN_MCP_NATIVE_TEST") == "1"
           and (APP / "Fastmean.exe").is_file())


@unittest.skipUnless(ENABLED, "Requires Windows FASTMEAN and FASTMEAN_MCP_NATIVE_TEST=1")
class NativeCurrentSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_direction_parameter_and_measurement_through_stdio(self):
        with tempfile.TemporaryDirectory(prefix="fm-current-native-") as directory:
            parameters = StdioServerParameters(command=sys.executable,
                args=["-X", "utf8", "-m", "fastmean_mcp"],
                env=dict(os.environ, FASTMEAN_APP_DIR=str(APP), FASTMEAN_OUTPUT_DIR=directory))
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()

                    async def call(name, arguments):
                        result = await client.call_tool(name, arguments, read_timeout_seconds=30.0)
                        self.assertFalse(result.is_error, str(result.content)[:1800])
                        return result.structured_content

                    for reverse in (False, True):
                        with self.subTest(reverse=reverse):
                            spec = current_spec()
                            if reverse:
                                spec["components"][0]["nodes"].reverse()
                            created = await call("fastmean_create_circuit", {"spec": spec})
                            source = Path(created["path"])
                            original = source.read_bytes()
                            annotated = await call("fastmean_annotate_circuit", {
                                "path": str(source), "parameters": {"DriveCurrent": "2m"},
                                "bindings": {"I1": "DriveCurrent"}, "td_signals": ["U(out)"]})
                            run = await call("fastmean_transient", {
                                "path": annotated["path"], "signals": ["U(out)"],
                                "stop": .001, "step": 1e-5, "timeout": 10})
                            # Exclude the native solver's initial t=0 state.
                            # The resistor-only circuit is constant afterwards.
                            chart = await call("fastmean_plot", {"run_id": run["run_id"],
                                "measurement_window": [.0001, .001],
                                "panels": [{"signal": "U(out)", "metrics": ["mean", "rms"]}]})
                            metrics = chart["measurements"]["signals"][0]["metrics"]
                            self.assertAlmostEqual(metrics["mean"], -2 if reverse else 2, places=7)
                            self.assertAlmostEqual(metrics["rms"], 2, places=7)
                            self.assertEqual(source.read_bytes(), original)
