"""Typed stdio tools using FASTMEAN's documented scripts and CIRSYM worker."""
from __future__ import annotations

import base64
import asyncio
import functools
import hashlib
from importlib.resources import files
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from typing import Annotated, Any, Literal
from uuid import uuid4

import anyio
from pydantic import Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, ResourceError
from mcp.types import CallToolResult, ImageContent, ResourceLink, TextContent, ToolAnnotations

from . import __version__
from .schematic import create_circuit, edit_component_values, example_circuit, read_scheme
from .symbolic import cirsym_from_fastmean_netlist, run_symbolic

PROJECT = Path(__file__).resolve().parent.parent
INSTRUCTIONS = """Use the installed FASTMEAN native engines for circuit analysis. Start with status and example. Create circuits with adjacent components and real orthogonal wires; ports are external interfaces only. Use relayout for old port-stub circuits; preview returns a schematic PNG/SVG for visual inspection. AC/transient PNGs render native numerical data. Symbolic CIRSYM supports linear zero-state R/C/L and one voltage source, not arbitrary CAS. Use exact ports from inspect. Results persist with run_id, paged data and MCP artifact resources. Sources are never overwritten; each operation gets a private folder. Long native requests support cancellation of owned processes only. No Windows locale changes. Read fastmean://guide."""

mcp = MCPServer(name="fastmean", title="FASTMEAN circuit analysis", version=__version__,
                instructions=INSTRUCTIONS, log_level="WARNING")
READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
ACTIVE_LOCK = threading.Lock()
NATIVE_LOCK = asyncio.Lock()
ACTIVE: dict[str, dict] = {}
Signals = Annotated[list[str], Field(min_length=1, max_length=30)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


def tool_errors(function):
    """Expose expected domain errors; SDK 2.x otherwise hides their messages."""
    def explain(error):
        code = "not_found" if isinstance(error, FileNotFoundError) else "permission_denied" if isinstance(error, PermissionError) else "invalid_request"
        return ToolError(json.dumps({"ok": False, "error": {"code": code, "message": str(error)}}, ensure_ascii=False))
    if inspect.iscoroutinefunction(function):
        @functools.wraps(function)
        async def asynchronous(*args, **kwargs):
            try:
                return await function(*args, **kwargs)
            except (ValueError, OSError) as error:
                raise explain(error) from error
        return asynchronous
    @functools.wraps(function)
    def synchronous(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, OSError) as error:
            raise explain(error) from error
    return synchronous


def store():
    from .artifacts import ArtifactStore
    return ArtifactStore(output_dir())


async def native_operation(name, path, operation):
    """Keep SDK cancellation responsive while a native worker runs in a thread."""
    async with NATIVE_LOCK:
        instance = engine()
        operation_id = uuid4().hex
        finished = threading.Event()
        with ACTIVE_LOCK:
            ACTIVE[operation_id] = {"operation_id": operation_id, "name": name,
                                    "source_path": str(path), "started_at": time.time(), "engine": instance}
        def execute():
            try:
                return operation(instance)
            finally:
                finished.set()
        try:
            result = await anyio.to_thread.run_sync(execute, abandon_on_cancel=True)
            result["operation_id"] = operation_id
            return result
        except anyio.get_cancelled_exc_class():
            instance.cancel()
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(lambda: finished.wait(6))
            raise
        finally:
            with ACTIVE_LOCK:
                ACTIVE.pop(operation_id, None)


def app_dir() -> Path:
    explicit = os.environ.get("FASTMEAN_APP_DIR")
    if explicit:
        result = Path(explicit).expanduser().resolve()
        if not (result / "Fastmean.exe").is_file():
            raise FileNotFoundError(f"Fastmean.exe not found under FASTMEAN_APP_DIR: {result}")
        return result
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    for name in ("FASTMEAN 6.1", "FASTMEAN 6.0"):
        if (local / name / "Fastmean.exe").is_file():
            return (local / name).resolve()
    raise FileNotFoundError("FASTMEAN not found. Set FASTMEAN_APP_DIR to its installation folder.")


def output_dir() -> Path:
    result = Path(os.environ.get("FASTMEAN_OUTPUT_DIR", str(Path.home() / "Documents" / "Codex" / "FASTMEAN-runs"))).expanduser().resolve()
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    installations = [local / "FASTMEAN 6.1", local / "FASTMEAN 6.0"]
    if os.environ.get("FASTMEAN_APP_DIR"):
        installations.append(Path(os.environ["FASTMEAN_APP_DIR"]).expanduser())
    for installation in installations:
        installation = installation.resolve()
        if result == installation or installation in result.parents:
            raise ValueError("FASTMEAN_OUTPUT_DIR must be outside the installation directory.")
    return result


def new_job(prefix: str) -> Path:
    destination = output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix + "-", dir=destination))


def source_path(path: str) -> Path:
    result = Path(path).expanduser().resolve(strict=True)
    if result.suffix.lower() != ".scm" or not result.is_file():
        raise ValueError("Select an existing .scm file.")
    return result


def engine():
    from .engine import Engine
    return Engine(app_dir(), output_dir())


def guide_text() -> str:
    return files("fastmean_mcp").joinpath("data", "fastmean-capabilities.txt").read_text(encoding="utf-8-sig")


def _saved_signals(path: Path, section: str) -> list[str]:
    summary = read_scheme(path)
    expressions = summary["analysis"].get(section, {}).get("Expressions", [])
    expected_x = "f" if section == "FD" else "t"
    values = []
    for item in expressions:
        if not isinstance(item, dict):
            continue
        plot = item.get("plot")
        if isinstance(plot, bool) or not isinstance(plot, (int, float)) or plot <= 0:
            continue
        if str(item.get("x", expected_x)).strip() != expected_x:
            raise ValueError("An active saved trace uses a custom x axis. Pass explicit signals for both axes; batch charts use frequency or time.")
        if isinstance(item.get("y"), str) and item["y"].strip():
            values.append(item["y"])
    values = list(dict.fromkeys(values))
    if not values or len(values) > 30:
        raise ValueError("Select 1–30 explicit signals, or enable saved traces with frequency/time x axes.")
    return values


def _filename(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name):
        raise ValueError("name must be 1–80 ASCII letters, digits, underscore or hyphen, without paths.")
    return name + ".scm"


def _with_image(result: dict, publish: bool = True) -> CallToolResult:
    # The complete numeric table lives in CSV. Keep tool responses bounded.
    result = store().publish(result) if publish else dict(result)
    if isinstance(result.get("rows"), list):
        result["preview_rows"] = result.pop("rows")[:8]
    contents: list[Any] = [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    for artifact in result.get("artifacts", [])[:12]:
        contents.append(ResourceLink(name=artifact["name"], uri=artifact["uri"], mime_type=artifact.get("mime_type"), size=artifact.get("size")))
    # Engine paths are generated internally; do not expose an arbitrary-file reader.
    candidates = [v for k, v in result.items() if isinstance(v, str) and
                  ("plot" in k or "png" in k) and v.lower().endswith(".png")]
    for value in candidates[:1]:
        path = Path(value).resolve()
        if output_dir() in path.parents and path.is_file() and path.stat().st_size < 4_000_000:
            contents.append(ImageContent(type="image", data=base64.b64encode(path.read_bytes()).decode("ascii"), mime_type="image/png"))
    return CallToolResult(content=contents, structured_content=result, is_error=result.get("ok") is False)


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_status() -> dict[str, Any]:
    """Check installation, native engines, output location and supported operations."""
    installation, exe, installation_error = None, None, None
    try:
        installation = app_dir()
        exe = installation / "Fastmean.exe"
    except FileNotFoundError as error:
        installation_error = str(error)
    with ACTIVE_LOCK:
        active = [{k:v for k,v in item.items() if k != "engine"} for item in ACTIVE.values()]
    return {"ok": True, "server_version": __version__, "installed": exe is not None,
            "installation": str(installation) if installation else None,
            "installation_error": installation_error,
            "executable": str(exe) if exe else None,
            "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest() if exe else None,
            "symbolic_available": bool(installation and (installation / "symbolic" / "cirsymw.exe").is_file()),
            "output_directory": str(output_dir()), "windows_locale_modified": False, "active_operations": active,
            "native_operations": ["AC frequency response", "transient analysis", "netlist export", "CIRSYM symbolic linear analysis"],
            "authoring": "R, C, L and independent U/V sources; DC, sine and pulse waveforms",
            "plot_origin": "Matplotlib PNG rendered from the native FASTMEAN numeric export",
            "layout": "Real orthogonal wires, native junctions, adjacent components, bottom ground rail; external ports only",
            "limits_numeric": {"max_ac_points": 10000, "max_transient_steps": 1000000, "max_signals": 30, "native_timeout_seconds": 60},
            "limits": ["No arbitrary CAS equation solver", "Symbolic adapter requires linear zero-state circuits",
                       "Legacy binary SCM files are not parsed", "DEMO installation may limit circuit size"]}


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_example(kind: str = "rc_lowpass") -> dict[str, Any]:
    """Get an editable circuit JSON spec: rc_lowpass, rlc_lowpass or voltage_divider.

    components have kind, name, nodes [positive,negative] for U/V, and SI value.
    Voltage waveform: {kind:dc|sine|pulse, frequency, amplitude, phase, delay,
    high, low, duty_percent, rise_time}; only fields applicable to its kind.
    """
    return example_circuit(kind)


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_create_circuit(spec: dict, name: str = "circuit") -> dict[str, Any]:
    """Create a native .scm in a fresh folder from a node-based JSON circuit spec.

    Start from fastmean_example. R/C/L values must be positive. Ground is 0.
    Components connect through physical wires and junctions; ports are external
    I/O only. Optional spec.layout.placements maps names to {x,y,rotation}; x/y
    are multiples of 20 and rotation is 0=left/right,1=up/down,2/3=reversed.
    All names used in analysis must be ASCII. Does not open a window.
    """
    filename = _filename(name)
    job = new_job("create")
    return store().publish(create_circuit(spec, job / filename))


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_inspect(path: str, include_objects: bool = False) -> dict[str, Any]:
    """Read a text SCM: components, values, native nodes, named ports and settings."""
    result = read_scheme(source_path(path))
    if not include_objects:
        result.pop("objects", None)
    from .artifacts import bounded_result
    return bounded_result(result)


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_edit_values(path: str, updates: dict) -> dict[str, Any]:
    """Create an edited copy, retaining topology and unknown native objects.

    updates maps component names to SI values, or to {value:...,waveform:...}.
    This supports R/C/L/U value edits and never overwrites the selected source.
    """
    source = source_path(path)
    job = new_job("edit")
    return store().publish(edit_component_values(source, updates, job / "edited.scm"))


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_ac(path: str, signals: Signals | None = None, fmin: Positive = 1,
                fmax: Positive = 1e6, points: Annotated[int, Field(ge=2, le=10000)] = 101,
                scale: Literal["log", "linear"] = "log") -> CallToolResult:
    """Run native AC analysis. Return CSV, native text, manifest and a PNG chart.

    Example signals: db(U(out)/U(in)), phs(U(out)/U(in)), mag(U(out)), I(R1).
    Use exact circuit port/component names. PNG is rendered from native data.
    A working copy disables graph windows and sweeps; original SCM is untouched.
    """
    source = source_path(path)
    if signals is None:
        signals = _saved_signals(source, "FD")
    result = await native_operation("ac", source, lambda native: native.run_ac(source, signals, fmin, fmax, points, scale=scale))
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_transient(path: str, signals: Signals | None = None, stop: Positive = .01,
                       step: Positive = 1e-5, eps: Annotated[float, Field(gt=0, le=.1, allow_inf_nan=False)] = 1e-5) -> CallToolResult:
    """Run native time-domain analysis; return native samples, CSV and PNG.

    Examples: U(out), U(in), I(R1). Seconds and SI values are numeric. Starts at
    time zero with the schematic's component IC values; no saved-state files.
    """
    source = source_path(path)
    if signals is None:
        signals = _saved_signals(source, "TD")
    result = await native_operation("transient", source, lambda native: native.run_transient(source, signals, stop, step, eps))
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_symbolic(path: str, output: str = "out", input: str | None = "in") -> CallToolResult:
    """Get a real CIRSYM output equation for a linear zero-state R/C/L/U circuit.

    Native FASTMEAN exports connectivity before conversion to CIRSYM. Optional
    input must be driven by a unique grounded independent voltage source; the
    transfer function is derived by dividing the native output by its amplitude.
    Set input=null for an output equation only. Not an arbitrary equation solver.
    """
    source = source_path(path)
    summary = read_scheme(source)
    kinds = {c["name"]: c["kind"] for c in summary["components"]}
    if summary["unsupported_type_ids"]:
        raise ValueError(f"Unsupported symbolic element types: {summary['unsupported_type_ids']}")
    def solve(native):
        exported = native.export_netlist(source)
        converted = cirsym_from_fastmean_netlist(exported["text"], output=output, input=input, component_kinds=kinds)
        result = run_symbolic(app_dir(), converted["netlist"], output_dir(), cancel_event=native.cancel_event)
        result["native_netlist_export"] = exported
        result["conversion"] = {k: v for k, v in converted.items() if k != "netlist"}
        parameter = converted.get("input_parameter")
        output_eq = next((eq for eq in result.get("equations", []) if eq["name"] == converted.get("output_equation")), None)
        if result.get("ok") and parameter and output_eq:
            result["transfer_function"] = {"name": "H(p)", "expression": f"({output_eq['expression']})/({parameter})",
                "origin": "Native CIRSYM output equation divided by input source amplitude", "input_parameter": parameter}
        return result
    result = await native_operation("symbolic", source, solve)
    return _with_image(result)


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_list_examples(query: str = "") -> dict[str, Any]:
    """Find installed example SCM files by substring; use returned paths in analysis."""
    query = query.casefold().strip()
    files = [p for p in app_dir().rglob("*.scm") if query in str(p.relative_to(app_dir())).casefold()]
    return {"examples": [{"name": str(p.relative_to(app_dir())), "path": str(p)} for p in sorted(files)[:200]],
            "count": len(files), "truncated": len(files) > 200}


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_open(path: str) -> dict[str, Any]:
    """Open a working copy through the installed FASTMEAN executable's documented CLI.

    Starts a separate application process; leaves existing windows alone. The
    circuit window stays open for the user, and is not controlled automatically.
    This command does not apply locale emulation; old Russian UI text may appear
    garbled on Windows configured for another legacy code page.
    """
    source = source_path(path)
    # Validate the SCM before opening; the native engine applies any directives.
    from .engine import prepare_copy
    job = new_job("open")
    copied = prepare_copy(source, job / "circuit.scm")
    installation = app_dir()
    exe = installation / "Fastmean.exe"
    command = [str(exe), "-o", str(copied)]
    process = subprocess.Popen(command, cwd=str(job), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "path": str(copied), "source": str(source), "pid": process.pid,
            "russian_launcher": False, "message": "Started native FASTMEAN with a working copy. No locale emulation is applied."}


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_search_manual(query: str) -> dict[str, Any]:
    """Search the verified native automation reference; query is literal text."""
    if not query.strip() or len(query) > 160:
        raise ValueError("Enter a nonempty search phrase of at most 160 characters.")
    text = guide_text()
    lines = text.splitlines()
    hits = [i for i, line in enumerate(lines) if query.casefold() in line.casefold()]
    return {"query": query, "matches": [{"line": i + 1, "text": "\n".join(lines[max(0, i - 2):i + 5])} for i in hits[:12]],
            "reference": "fastmean://guide"}


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_relayout(path: str, placements: dict | None = None) -> dict[str, Any]:
    """Rebuild a supported circuit as adjacent components with physical wires.

    Converts old per-pin PORT layouts into a connected orthogonal drawing.
    Preserves values, waveforms and native analysis in a new SCM. Supports
    R/C/L/U circuits. Optional placements: {R1:{x:960,y:1000,rotation:0}}.
    """
    from .relayout import relayout_circuit
    job = new_job("layout")
    return store().publish(relayout_circuit(source_path(path), job / "circuit.scm", placements=placements))


@mcp.tool(annotations=WRITE)
@tool_errors
def fastmean_preview(path: str) -> CallToolResult:
    """Render a wire-connected SCM to readable PNG and SVG for visual review.

    This is an MCP rendering of native objects, not a FASTMEAN screenshot.
    Unknown symbols or implicit bends are rejected; use fastmean_open for them.
    """
    from .preview import render_schematic
    source = source_path(path)
    result = render_schematic(source, output_dir())
    result["working_dir"] = str(Path(result["png_path"]).parent)
    result["source_path"] = str(source)
    result["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    return _with_image(result)


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_list_runs(limit: Annotated[int, Field(ge=1, le=100)] = 20) -> dict[str, Any]:
    """Find persisted calculations, created diagrams and preview runs after restart."""
    return store().list_runs(limit=limit)


@mcp.tool(annotations=READ)
@tool_errors
def fastmean_get_result(run_id: str) -> CallToolResult:
    """Reopen a persisted result with images and registered artifact resources."""
    # Reading must not republish/update a result, so use the response renderer
    # separately from the publisher.
    return _with_image(store().get_run(run_id), publish=False)


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_read_data(run_id: str, offset: Annotated[int, Field(ge=0, le=1000000)] = 0,
                       limit: Annotated[int, Field(ge=1, le=500)] = 200) -> dict[str, Any]:
    """Read a page of native calculation samples from a registered run's CSV."""
    return store().read_data(run_id, offset=offset, limit=limit)


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_cancel(operation_id: str) -> dict[str, Any]:
    """Cancel one active native operation listed by status; never other processes."""
    with ACTIVE_LOCK:
        active = ACTIVE.get(operation_id)
        if active is None:
            raise ValueError("No such active operation; call fastmean_status for active_operations.")
        active["engine"].cancel()
    return {"ok": True, "operation_id": operation_id, "cancellation_requested": True}


@mcp.resource("fastmean://guide", description="Verified native FASTMEAN automation, circuit spec and limits")
def guide() -> str:
    return guide_text()


@mcp.resource("fastmean://runs/{run_id}", mime_type="application/json", description="Persisted FASTMEAN result and artifact catalog")
def run_resource(run_id: str) -> str:
    try:
        return json.dumps(store().get_run(run_id), ensure_ascii=False)
    except (ValueError, OSError) as error:
        raise ResourceError(str(error)) from error


@mcp.resource("fastmean://artifacts/{run_id}/{name}", mime_type="application/octet-stream", description="Registered native data, diagram, graph or provenance file")
def artifact_resource(run_id: str, name: str) -> bytes:
    try:
        return store().read_artifact(run_id, name)
    except (ValueError, OSError) as error:
        raise ResourceError(str(error)) from error


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
