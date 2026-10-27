"""Build and calculate the flyback example through the real MCP stdio protocol.

Every output is a fresh registered job under --output-dir. The source checkout,
native installation, and existing calculations are preserved.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def rebuild(args):
    environment = dict(os.environ, FASTMEAN_OUTPUT_DIR=str(Path(args.output_dir).resolve()))
    if args.app_dir:
        environment["FASTMEAN_APP_DIR"] = str(Path(args.app_dir).resolve())
    parameters = StdioServerParameters(command=sys.executable,
        args=["-X", "utf8", "-m", "fastmean_mcp"], env=environment)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, arguments):
                response = await client.call_tool(name, arguments, read_timeout_seconds=90.0)
                if response.is_error:
                    raise RuntimeError(f"{name}: " + "\n".join(
                        item.text for item in response.content if item.type == "text"))
                result = response.structured_content
                print(json.dumps({"tool": name, "run_id": result.get("run_id"),
                    "path": result.get("path"), "png": result.get("png_path", result.get("plot_path")),
                    "images": sum(item.type == "image" for item in response.content)}), flush=True)
                return result

            status = await call("fastmean_status", {})
            if not status["installed"]:
                raise RuntimeError(status["installation_error"])
            spec = await call("fastmean_example", {"kind": "flyback"})
            created = await call("fastmean_create_circuit", {"spec": spec, "name": "flyback"})
            signals = ["U(out)", "U(drain)", "I(LM)", "I(DOUT)", "U(gate)"]
            annotated = await call("fastmean_annotate_circuit", {
                "path": created["path"], "td_signals": signals, "fd_signals": [],
                "descriptions": [
                    "Flyback: native TR transformer, magnetizing LM and voltage-controlled SW.",
                    "Open-loop educational model; no saturation, leakage or transistor parasitics."]})
            preview = await call("fastmean_preview", {"path": created["path"], "include_text": False})
            netlist = await call("fastmean_export_netlist", {"path": annotated["path"], "timeout": 20})
            native = await call("fastmean_transient", {"path": annotated["path"],
                "signals": signals, "stop": .01, "step": 1e-7, "eps": 1e-5, "timeout": 60})
            panels = [
                {"signal": "U(out)", "label": "Output voltage", "unit": "V", "metrics": ["mean", "peak_to_peak"]},
                {"signal": "U(drain)", "label": "Switch voltage", "unit": "V", "metrics": ["max"]},
                {"signal": "I(LM)", "label": "Magnetizing current", "unit": "A", "metrics": ["min", "max"]},
                {"signal": "I(DOUT)", "label": "Rectifier current", "unit": "A", "metrics": ["mean"]},
                {"signal": "U(gate)", "label": "Gate drive", "unit": "V", "metrics": []}]
            startup = await call("fastmean_plot", {"run_id": native["run_id"],
                "panels": [panels[0], panels[2]], "measurement_window": [.009, .01],
                "title": "Flyback startup", "x_unit": "ms"})
            switching = await call("fastmean_plot", {"run_id": native["run_id"],
                "panels": panels, "display_window": [.00994, .01],
                "measurement_window": [.009, .01], "title": "Flyback switching cycles", "x_unit": "us"})
            receipt = Path(native["working_dir"]) / "example-workflow.json"
            receipt.write_text(json.dumps({"server_version": status["server_version"],
                "spec": spec, "created": created, "annotated": annotated, "preview": preview,
                "netlist": netlist, "native": native, "startup": startup, "switching": switching},
                ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"receipt": str(receipt), "measurements": switching["measurements"]},
                             ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", help="Separately installed FASTMEAN directory")
    parser.add_argument("--output-dir", required=True, help="Writable ASCII directory for fresh MCP jobs")
    asyncio.run(rebuild(parser.parse_args()))
