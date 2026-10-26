"""Rebuild, annotate, calculate and chart the example through genuine MCP stdio.

Run with the Python environment containing fastmean-mcp-local. No desktop
control or direct calls into the schematic/solver/plot implementation are used.
All outputs are new jobs under --output-dir; repository files stay unchanged.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


HERE = Path(__file__).resolve().parent


async def rebuild(args):
    output = Path(args.output_dir).expanduser().resolve()
    env = dict(os.environ, FASTMEAN_OUTPUT_DIR=str(output))
    if args.app_dir:
        env["FASTMEAN_APP_DIR"] = str(Path(args.app_dir).expanduser().resolve())
    parameters = StdioServerParameters(command=sys.executable,
        args=["-X", "utf8", "-m", "fastmean_mcp"], env=env)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, arguments):
                response = await client.call_tool(name, arguments, read_timeout_seconds=90.0)
                if response.is_error:
                    messages = [item.text for item in response.content if item.type == "text"]
                    raise RuntimeError(f"{name}: {messages}")
                data = response.structured_content
                print(json.dumps({"tool": name, "run_id": data.get("run_id"),
                    "path": data.get("path"), "png": data.get("png_path", data.get("plot_path")),
                    "images": sum(item.type == "image" for item in response.content)}), flush=True)
                return data

            status = await call("fastmean_status", {})
            if not status["installed"]:
                raise RuntimeError(status["installation_error"])
            spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
            project = await call("fastmean_create_project", {"spec": spec, "name": "four_bjt_amplifier"})
            annotation = json.loads((HERE / "annotation.request.json").read_text(encoding="utf-8"))
            annotation["path"] = project["path"]
            annotated = await call("fastmean_annotate_circuit", annotation)
            main_preview = await call("fastmean_preview", {"path": annotated["path"]})
            model_previews = []
            for model_path in annotated["dependency_paths"]:
                model_previews.append(await call("fastmean_preview", {"path": model_path}))
            netlist = await call("fastmean_export_netlist", {"path": annotated["path"], "timeout": 20})
            native = await call("fastmean_transient", {"path": annotated["path"],
                "signals": ["U(IN)", "U(OUT)", "I(RL)", "I(VIN)", "U(OUT)*I(RL)"],
                "stop": .3, "step": 1e-5, "eps": 1e-5, "timeout": 60})
            chart = await call("fastmean_plot", {"run_id": native["run_id"],
                "display_window": [.297, .3], "measurement_window": [.29, .3],
                "x_unit": "ms", "title": "Four-BJT amplifier",
                "subtitle": "Native FASTMEAN transient · nominal PWL model",
                "panels": [
                    {"signal": "U(IN)", "label": "Input voltage", "unit": "V", "metrics": ["rms"]},
                    {"signal": "U(OUT)", "label": "Output voltage", "unit": "V", "metrics": ["rms"]},
                    {"signal": "I(RL)", "label": "Load current", "unit": "A", "metrics": ["rms"]},
                    {"signal": "I(VIN)", "label": "Input current", "unit": "mA", "scale": 1000,
                     "metrics": ["rms", "peak"]},
                    {"signal": "U(OUT)*I(RL)", "label": "Load power", "unit": "W",
                     "metrics": ["mean"], "guides": ["mean"]}]})
            result = {"project": project, "annotated": annotated, "preview": main_preview,
                      "models": model_previews, "netlist": netlist, "native": native, "chart": chart}
            receipt = Path(chart["working_dir"]) / "example-workflow.json"
            receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"receipt": str(receipt), "measurements": chart["measurements"]},
                             ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", help="Separately installed FASTMEAN folder; default: server discovery")
    parser.add_argument("--output-dir", required=True, help="Writable ASCII path for new MCP jobs")
    parser.add_argument("--spec", default=str(HERE / "project.input.json"),
                        help="Compatible project JSON; nominal root annotations still apply")
    asyncio.run(rebuild(parser.parse_args()))
