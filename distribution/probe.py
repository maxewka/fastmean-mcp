"""Read-only dependency/config checks and a real FASTMEAN MCP stdio handshake."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib


REQUIRED_TOOLS = {"fastmean_status", "fastmean_example", "fastmean_create_circuit",
                  "fastmean_create_project",
                  "fastmean_annotate_circuit",
                  "fastmean_export_netlist",
                  "fastmean_ac", "fastmean_transient", "fastmean_symbolic", "fastmean_inspect"}


async def protocol(python: Path, app_dir: Path, output_dir: Path) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    environment = dict(os.environ, FASTMEAN_APP_DIR=str(app_dir),
                       FASTMEAN_OUTPUT_DIR=str(output_dir), PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    parameters = StdioServerParameters(command=str(python),
        args=["-X", "utf8", "-m", "fastmean_mcp"], env=environment,
        cwd=str(python.parent))
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
        try:
            async with asyncio.timeout(30):
                async with stdio_client(parameters, errlog=errors) as (reader, writer):
                    async with ClientSession(reader, writer, read_timeout_seconds=20) as client:
                        initialized = await client.initialize()
                        tools = await client.list_tools()
                        names = sorted(tool.name for tool in tools.tools)
                        missing = REQUIRED_TOOLS - set(names)
                        if missing:
                            raise ValueError("Missing expected tools: " + ", ".join(sorted(missing)))
                        status = await client.call_tool("fastmean_status", {})
                        if status.is_error:
                            raise ValueError("fastmean_status returned a protocol tool error.")
                        return {"initialized": True, "protocol_version": initialized.protocol_version,
                                "server_name": initialized.server_info.name,
                                "tool_count": len(names), "tools": names, "status_call_ok": True}
        except BaseException:
            errors.seek(0)
            diagnostic = errors.read()[-4000:]
            if diagnostic:
                print("MCP diagnostic stderr:\n" + diagnostic, file=sys.stderr)
            raise


def inspect(python: Path, app_dir: Path, output_dir: Path, config_home: Path,
            skip_protocol: bool = False) -> dict:
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12+ is required.")
    executable = app_dir / "Fastmean.exe"
    if not executable.is_file():
        raise ValueError("FASTMEAN executable is missing: " + str(executable))
    if output_dir.resolve().is_relative_to(app_dir.resolve()):
        raise ValueError("Result folder must be outside the FASTMEAN installation.")
    if not str(output_dir).isascii():
        raise ValueError("Native batch output folder must have an ASCII path.")
    packages = {name: version(name) for name in ("fastmean-mcp-local", "mcp", "PyYAML", "matplotlib")}
    import fastmean_mcp.server  # noqa: F401 - detect actual import/API mismatches
    config = config_home / "config.toml"
    data = tomllib.loads(config.read_text(encoding="utf-8-sig"))
    entry = data.get("mcp_servers", {}).get("fastmean", {})
    if Path(entry.get("command", "")).resolve() != python.resolve():
        raise ValueError("The fastmean Codex command does not point to this installed venv.")
    if entry.get("args") != ["-X", "utf8", "-m", "fastmean_mcp"]:
        raise ValueError("Unexpected fastmean MCP command arguments.")
    environment = entry.get("env", {})
    if Path(environment.get("FASTMEAN_APP_DIR", "")).resolve() != app_dir.resolve():
        raise ValueError("Codex FASTMEAN_APP_DIR does not match the installation receipt.")
    if Path(environment.get("FASTMEAN_OUTPUT_DIR", "")).resolve() != output_dir.resolve():
        raise ValueError("Codex FASTMEAN_OUTPUT_DIR does not match the installation receipt.")
    result = {"ok": True, "python": str(python), "python_version": sys.version.split()[0],
              "packages": packages, "fastmean_executable": str(executable),
              "fastmean_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "output_dir": str(output_dir), "codex_config": str(config),
              "codex_entry_enabled": entry.get("enabled", True),
              "codex_enabled_tools": entry.get("enabled_tools"),
              "windows_settings_changed": False, "native_analysis_started": False,
              "mcp_protocol": {"skipped": True}}
    if not skip_protocol:
        result["mcp_protocol"] = asyncio.run(protocol(python, app_dir, output_dir))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--app-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config-home", type=Path, required=True)
    parser.add_argument("--skip-protocol", action="store_true")
    args = parser.parse_args()
    try:
        result = inspect(args.python, args.app_dir, args.output_dir, args.config_home, args.skip_protocol)
    except Exception as error:
        parser.exit(1, f"FASTMEAN MCP doctor failed: {error}\nRerun install.ps1 after checking the FASTMEAN path, Python runtime, and pinned dependencies.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
