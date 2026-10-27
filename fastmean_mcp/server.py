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
INSTRUCTIONS = """Use FASTMEAN's installed native engines through file-based MCP, without desktop automation.
Start with status and catalog: all 44 insertable native 6.1 electrical classes are available, including TR/TR3,
switches, MOSFET/NPN, nonlinear curves, logic, modulators, lines, op-amps and subcircuits. Catalog gives exact
native pin order, schemas and separate verification evidence. Use components with adjacent physical wires;
PORTs are external interfaces. create_project builds portable models. relayout retains parameters/formulas.
Sources support DC/sine/pulse/triangle/PWL; public delay is seconds, delay_periods gives native periodic units.
annotate_circuit saves .parameter, scalar field bindings, explanations and TD/FD formulas. edit_properties
edits all known native numeric parameters/tables, saved analysis settings, style and .define functions;
changing pin count requires a newly connected circuit. edit_parameters preserves existing shared bindings.
AC/transient/DC and sweeps use native calculations; definitions and qualified overrides are typed maths.
evaluate performs native final statistics or native FFT; harmonics uses native tre/tim/tmag/tph.
spectrum explicitly uses NumPy on native TD samples. plot renders registered data with original provenance,
units/windows and TD time-weighted metrics. CIRSYM supplies linear zero-state U/I/H/Z/Y formulas, including
controlled sources, transformers, gyrators, summators, op-amps and natively expanded models. It is not a CAS
for arbitrary nonlinear equations. Original SCMs are preserved; jobs, CSVs, images and metadata are registered.
Use inspect's complete paged sections/detail_path and expected_source_sha256 for large immutable reads.
External DLL co-simulation contacts are not ordinary ports and cannot be executed by this adapter.
Cancel only owned jobs. Open a GUI only on an explicit request; no Windows locale/security changes.
Read fastmean://guide and report any unsupported native context truthfully."""

INSTRUCTIONS += " Native TR transformers and SW voltage-controlled switches are available in create_circuit/create_project. Start switching converters with example(kind='flyback'); an ideal TR needs a separate magnetizing inductance for flyback energy storage. Read the guide for native terminal polarity. Transient switching events may contain repeated timestamps: preserve both sides in native order; plot supports these events."

mcp = MCPServer(name="fastmean", title="FASTMEAN circuit analysis", version=__version__,
                instructions=INSTRUCTIONS, log_level="WARNING")
READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
ACTIVE_LOCK = threading.Lock()
NATIVE_LOCK = asyncio.Lock()
ACTIVE: dict[str, dict] = {}
Signals = Annotated[list[str], Field(min_length=1, max_length=30)]
SavedSignals = Annotated[list[str], Field(min_length=0, max_length=30)]
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


async def native_operation(name, path, operation, timeout=None):
    """Keep SDK cancellation responsive while a native worker runs in a thread."""
    async with NATIVE_LOCK:
        instance = engine() if timeout is None else engine(timeout=timeout)
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


def engine(timeout=60):
    from .engine import Engine
    return Engine(app_dir(), output_dir(), timeout=timeout)


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
    # Inline images have the same publication boundary and integrity checks as
    # resource reads. Persisted absolute path hints can be stale or modified;
    # they must never select a file from another job or bypass its digest.
    for artifact in result.get("artifacts", []):
        if (artifact.get("mime_type") == "image/png"
                and type(artifact.get("size")) is int and artifact["size"] < 4_000_000):
            data = store().read_artifact(result["run_id"], artifact["name"])
            contents.append(ImageContent(type="image", data=base64.b64encode(data).decode("ascii"), mime_type="image/png"))
            break
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
    from .element_catalog import inventory_summary
    from .symbolic_conversion import symbolic_capabilities
    return {"ok": True, "server_version": __version__, "installed": exe is not None,
            "installation": str(installation) if installation else None,
            "installation_error": installation_error,
            "executable": str(exe) if exe else None,
            "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest() if exe else None,
            "symbolic_available": bool(installation and all(
                (installation / "symbolic" / name).is_file() for name in ("cirsymw.exe", "human.sym"))),
            "output_directory": str(output_dir()), "windows_locale_modified": False, "active_operations": active,
            "native_operations": ["AC frequency response", "transient analysis", "DC operating point", "parameter sweeps",
                "native FFT", "native harmonic extraction", "native final statistics", "netlist export", "CIRSYM U/I/H/Z/Y"],
            "derived_operations": ["NumPy rFFT/PSD of native transient samples", "Matplotlib charts", "SCM engineering previews"],
            "authoring": "44 native 6.1 insertable electrical classes; call fastmean_catalog for pins, defaults and verification scope",
            "element_catalog": inventory_summary(), "symbolic_capabilities": symbolic_capabilities(),
            "source_waveforms": {"modes":["dc","sine","pulse","triangle","pwl"],
                "delay":"Public delay is seconds; native AC/PULSE/TRIANG Delay uses periods; delay_periods is explicit",
                "pwl":"ScaleT, scale, offset, delay, periodic, periods and numeric point tables; nonperiodic native PWL extrapolates"},
            "opamp": {"kind": "OPAMP", "native_type": 6400,
                      "nodes": ["noninverting", "inverting", "output"], "parameters": ["k"],
                      "model": "Uout=k*(Uplus-Uminus), referenced to global ground; no rails, saturation, bandwidth or current limit"},
            "power_electronics": {
                "transformer": {"kind": "TR", "native_type": 6101, "parameters": ["n"],
                    "energy_storage": "Ideal transformer; add a separate L across its primary for flyback magnetizing inductance"},
                "voltage_controlled_switch": {"kind": "SW", "native_type": 6600,
                    "parameters": ["Uon", "Uoff", "Ron", "Roff"]},
                "example": "fastmean_example(kind='flyback')",
                "transient_events": "Equal timestamps retain both native event states; zero-duration jumps add no time integral"},
            "hierarchy": {"native_type": 7100, "max_model_definitions": 99, "max_pins_per_model": 32,
                          "parameter_overrides_supported": False,
                          "editing": "Modify saved project.spec.json and create a new project; originals remain unchanged"},
            "annotations": "Root numeric .parameter constants, supported scalar native-field bindings, explanatory TEXT and saved TD/FD signal expressions in a new copy",
            "parameter_editing": "fastmean_edit_parameters updates existing finite numeric root constants, preserving bindings and descriptions; no native expression evaluation",
            "inspection": "Critical metadata plus complete byte-bounded pages; section/detail_path and expected_source_sha256 support stable reads of large fields",
            "transient_preflight": "Active local U/C loops plus cross-instance loops with verified native PORT geometry; child underscore test components excluded; partial coverage reported in manifest",
            "plot_origin": "Matplotlib from registered data; native FASTMEAN and separately derived NumPy spectra retain distinct provenance",
            "saved_data_charts": {"tool": "fastmean_plot", "max_panels": 12,
                "input": "registered AC/transient/native_fft/spectrum run_id; exact columns and authenticated source artifacts",
                "outputs": ["MCP ImageContent", "PNG", "SVG", "chart spec", "measurements", "provenance"],
                "measurements": "transient time-weighted RMS/mean, peak/min/max/peak_to_peak; exact interpolated window endpoints",
                "simulation_started": False},
            "layout": "Compact spacing; exact native pin axes and orthogonal wires; four-unit explicit coordinates; bottom rail or local ground symbols; external ports only",
            "limits_numeric": {"max_ac_points": 10000, "max_transient_steps": 1000000, "max_signals": 30, "native_timeout_seconds": 60},
            "limits": ["No arbitrary CAS equation solver", "Symbolic adapter requires linear zero-state circuits",
                       "Native instance parameter overrides and arbitrary BJT/SPICE model import are unsupported",
                       "External DLL co-simulation bindings and DIGITAL_IN/OUT execution are unsupported",
                       "Legacy binary SCM files are not parsed", "DEMO installation may limit circuit size"]}


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_example(kind: str = "rc_lowpass") -> dict[str, Any]:
    """Get an editable JSON spec: rc_lowpass, rlc_lowpass, voltage_divider, flyback.

    components have kind, name, nodes [positive,negative] for U/V, and SI value.
    Voltage waveform: {kind:dc|sine|pulse, frequency, amplitude, phase, delay,
    high, low, duty_percent, rise_time}; only fields applicable to its kind.
    flyback uses a native TR transformer, separate magnetizing L, native SW
    voltage-controlled switch, pulse drive and diode rectifier. Use transient.
    """
    return example_circuit(kind)


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_create_circuit(spec: dict, name: str = "circuit") -> dict[str, Any]:
    """Create a native .scm in a fresh folder from a node-based JSON circuit spec.

    Start from fastmean_example. R/C/L values must be positive. Ground is 0.
    Components connect through physical wires and junctions; ports are external
    I/O only. Optional spec.layout.placements maps names to {x,y,rotation}; x/y
    are multiples of 4 and rotation is 0=left/right,1=up/down,2/3=reversed.
    spec.layout.density is compact (default) or standard. Explicit coordinates
    stay unchanged; density controls automatic spacing only. ground_style is
    rail (default) or local. U nodes are [+,-]; I nodes are [from,to].
    A single-terminal node gets one short wire and native CON endpoint, without
    an added electrical load or external PORT.
    All names used in analysis must be ASCII. Does not open a window.
    Fixed native primitives: D nodes=[anode,cathode], parameters={Ron,Roff,Uon}; G/VCCS,
    E/VCVS and F/CCCS use four native-ordered nodes and a numeric value.
    TR/TRANSFORMER nodes=[p1,p2,s1,s2], dotted pins1/3, n=Np/Ns>0;
    value=n or parameters={n}. SW/VCSWITCH nodes=[control+,control-,switch1,switch2],
    parameters={Ron,Roff,Uon,Uoff}, 0<Ron<=Roff, Uoff<=Uon; native hysteresis.
    See example(kind='flyback') and the guide for polarity and magnetic storage.
    spec.analysis.transient accepts stop, step and eps (0<eps<=0.1), saved in SCM.
    Use fastmean_create_project for X subcircuits and portable model files.
    All44 insertable classes are supported: call fastmean_catalog(detail=true)
    for nonlinear R/C/L, H, GYR, TR3, TUBE, NMOS_SMALL, NPN, OPAMP_SAT, PWM,
    PAM1/PAM2, BALMOD, THYRISTOR, MOSFET, LINE, BRIDGE, RS/DFF/JK/RSCLK,
    NOT/AND/OR/XOR/LATCH/COMP and SUM. Supply parameters by native key; omitted
    values use explicit adapter templates. Sources also support triangle/PWL.
    """
    filename = _filename(name)
    job = new_job("create")
    return store().publish(create_circuit(spec, job / filename))


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_create_project(spec: dict, name: str = "project") -> dict[str, Any]:
    """Create a portable native root circuit and fixed numeric subcircuit files.

    spec={name?,models:{MODEL:{pins:{Left:[B],Top:[C],Right:[],Bottom:[E]},
    circuit:{components:[...],ports:{B:b,C:c,E:e}}}},circuit:rootCircuit}.
    X components use {kind:X,name:Q1,model:MODEL,connections:{B:base,C:col,E:0}}.
    Side lists determine native terminal numbering Left,Top,Right,Bottom.
    A definition may float; ports must match declared pins exactly. All models
    must exist and be acyclic; instance parameters and .parameter headers are
    unsupported. Other components use the create_circuit schema. Each circuit
    supports compact/standard density and explicit coordinates independently.
    Return main.scm, models/*.scm, original JSON specs, hashes and a manifest.
    To edit definitions, modify the saved project.spec.json and call this tool
    again: every call creates a new project and preserves the previous files.
    Does not launch FASTMEAN, calculations, GUI or desktop automation.
    """
    from .hierarchy import create_project
    directory_name = _filename(name)[:-4]
    job = new_job("project")
    result = create_project(spec, job / directory_name)
    result.update({"working_dir": str(job), "analysis": "create_project", "ok": True,
                   "origin": "Native SCM project authored by MCP; no analysis performed"})
    return store().publish(result)


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_inspect(path: str, include_objects: bool = False,
        section: Literal["summary", "components", "nodes", "objects", "texts", "ports",
                         "parameters", "analysis", "wires", "warnings", "parameter_issues"] = "summary",
        offset: Annotated[int, Field(ge=0, le=16777216, strict=True)] = 0,
        limit: Annotated[int, Field(ge=1, le=1000, strict=True)] = 100,
        detail_path: Annotated[list[str | Annotated[int, Field(strict=True)]], Field(max_length=24)] | None = None,
        expected_source_sha256: str | None = None) -> dict[str, Any]:
    """Read SCM metadata, root parameters, ports and formulas without losing fields.

    Default summary has compact components and independently budgeted pages;
    include_objects adds a raw-object page. section selects complete native data
    with offset/limit pagination. data is a list, mapping or text, as page.kind
    reports. Use detail_path for nested large fields, e.g. objects [5,"Params"]
    or analysis ["TD","Expressions"]. Text selections paginate characters.
    Reuse source_sha256 as expected_source_sha256 on later pages to reject edits
    between reads. Reads create no jobs and start no calculations or windows.
    """
    from .inspection import inspect_circuit
    return inspect_circuit(source_path(path), include_objects, section=section,
        offset=offset, limit=limit, detail_path=detail_path, expected_source_sha256=expected_source_sha256)


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_edit_parameters(path: str, updates: dict, expected_source_sha256: str | None = None) -> dict[str, Any]:
    """Update existing numeric root .parameter/.param constants in a new copy.

    updates maps exact case-sensitive parameter names to finite numbers/SI values.
    Only literal spans change; descriptions, component bindings, graph formulas
    and portable model files are preserved. Expressions, ambiguous declarations
    and overriding define/global/set names are rejected. Use inspect's
    root_parameters before editing. This does not run a calculation or a GUI.
    Pass the inspection's source_sha256 as expected_source_sha256 to reject
    source changes made between inspection and this request.
    """
    from .parameters import edit_parameters
    job = new_job("parameters")
    result = edit_parameters(source_path(path), updates, job / "circuit.scm",
                             expected_source_sha256=expected_source_sha256)
    result.update({"working_dir": str(job), "analysis": "edit_parameters", "ok": True,
        "dependency_artifacts": [{"path": value} for value in result.get("dependency_paths", [])],
        "origin": "Root native parameter literals edited by MCP; no analysis performed"})
    return store().publish(result)


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_annotate_circuit(path: str, parameters: dict | None = None, bindings: dict | None = None,
                              descriptions: list[str] | None = None, td_signals: SavedSignals | None = None,
                              fd_signals: SavedSignals | None = None) -> dict[str, Any]:
    """Add numeric constants, text explanations and saved native formulas to a copy.

    parameters maps ASCII identifiers to finite numbers/SI literals. bindings
    maps root component names to an expression for convenience value fields,
    or to native scalar fields, e.g. {"TR1":{"n":"Ratio"},"VIN":{"PULSE.F":"Freq"}}.
    Native child-instance parameter declarations are unsupported. descriptions adds plain
    explanatory native TEXT objects. [] clears saved traces; None preserves them.
    td_signals/fd_signals replace saved active
    expressions, for example U(OUT), I(RL), db(U(OUT)/U(IN)), phs(U(OUT)/U(IN)).
    Root TD/FD settings are retained, requested expressions are preloaded, and
    SCM model dependencies are privately packaged. Sources remain unchanged.
    Does not launch calculations, a window or desktop automation.
    """
    from .annotations import annotate_circuit
    source = source_path(path)
    job = new_job("annotate")
    result = annotate_circuit(source, job / "circuit.scm", parameters=parameters, bindings=bindings,
                              descriptions=descriptions, td_signals=td_signals, fd_signals=fd_signals)
    dependencies = []
    for value in result.get("dependency_paths", []):
        private = Path(value).resolve(strict=True)
        if not private.is_relative_to(job.resolve()) or private.suffix.lower() != ".scm":
            raise ValueError("An annotation dependency escaped its private SCM job.")
        dependencies.append({"path": str(private)})
    result.update({"working_dir": str(job), "analysis": "annotate", "dependency_artifacts": dependencies,
                   "ok": True, "origin": "Native SCM annotations authored by MCP; no analysis performed"})
    return store().publish(result)


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_edit_values(path: str, updates: dict) -> dict[str, Any]:
    """Create an edited copy, retaining topology and unknown native objects.

    updates maps component names to SI values, or to {value:...,waveform:...}.
    This supports R/C/L/U/I value edits and never overwrites the selected source.
    A literal edit replaces any parameter binding on that component. To keep
    shared .parameter bindings, use fastmean_edit_parameters instead.
    Explicit waveform fields update the selected mode, retaining omitted fields
    and other modes; waveform amplitude/high overrides value when supplied.
    """
    source = source_path(path)
    job = new_job("edit")
    result = edit_component_values(source, updates, job / "edited.scm")
    dependencies = []
    for value in result.get("dependency_paths", []):
        private = Path(value).resolve(strict=True)
        if not private.is_relative_to(job.resolve()) or private.suffix.lower() != ".scm":
            raise ValueError("An edited dependency escaped its private SCM job.")
        dependencies.append({"path": str(private)})
    result.update({"working_dir": str(job), "analysis": "edit", "dependency_artifacts": dependencies,
                   "ok": True, "origin": "Native SCM values edited by MCP; no analysis performed"})
    return store().publish(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_export_netlist(path: str,
        timeout: Annotated[float, Field(ge=1, le=60, allow_inf_nan=False)] = 60) -> CallToolResult:
    """Export the installed FASTMEAN engine's native expanded circuit netlist.

    Opens a sanitized recursive working copy in a private batch process, runs
    save_netlist and exits. Returns bounded text, full netlist and provenance
    artifacts. Does not launch a GUI or request AC/transient simulation.
    timeout limits only this owned worker to 1–60 seconds; cancellation uses
    the same owned-process mechanism as other native operations.
    """
    source = source_path(path)
    result = await native_operation("netlist", source, lambda native: native.export_netlist(source), timeout=timeout)
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_ac(path: str, signals: Signals | None = None, fmin: Positive = 1,
                fmax: Positive = 1e6, points: Annotated[int, Field(ge=2, le=10000)] = 101,
                scale: Literal["log", "linear"] = "log", definitions: list[dict] | None = None,
                overrides: dict | None = None) -> CallToolResult:
    """Run native AC analysis. Return CSV, native text, manifest and a PNG chart.

    Example signals: db(U(out)/U(in)), phs(U(out)/U(in)), mag(U(out)), I(R1).
    Use exact circuit port/component names. PNG is rendered from native data.
    A working copy disables graph windows and sweeps; original SCM is untouched.
    """
    source = source_path(path)
    if signals is None:
        signals = _saved_signals(source, "FD")
    result = await native_operation("ac", source, lambda native: native.run_ac(source, signals, fmin, fmax, points,
        scale=scale, definitions=definitions, overrides=overrides))
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_transient(path: str, signals: Signals | None = None, stop: Positive = .01,
                       step: Positive = 1e-5, eps: Annotated[float, Field(gt=0, le=.1, allow_inf_nan=False)] = 1e-5,
                       timeout: Annotated[float, Field(ge=1, le=60, allow_inf_nan=False)] = 60,
                       definitions: list[dict] | None = None, overrides: dict | None = None,
                       sample_after: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0,
                       initial_conditions: str | dict = "scheme", state2scheme: bool = False) -> CallToolResult:
    """Run native time-domain analysis; return native samples, CSV and PNG.

    Examples: U(out), U(in), I(R1). Seconds and SI values are numeric. Starts at
    time zero with the schematic's component IC values; no saved-state files.
    timeout limits this owned worker to 1–60 seconds (default 60).
    """
    source = source_path(path)
    if signals is None:
        signals = _saved_signals(source, "TD")
    result = await native_operation("transient", source, lambda native: native.run_transient(source, signals, stop, step, eps,
        definitions=definitions, overrides=overrides, sample_after=sample_after,
        initial_conditions=initial_conditions, state2scheme=state2scheme), timeout=timeout)
    return _with_image(result)


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_catalog(query: str = "", detail: bool = False, include_service: bool = False) -> dict[str, Any]:
    """Discover native FASTMEAN element kinds, aliases, pins and parameter schemas.

    Start here before creating an unfamiliar component. detail=true includes
    native defaults, bounds and validation schemas. Numerical test evidence is
    reported separately from the observed native factory and pin geometry.
    """
    from .element_catalog import entries, get_element, inventory_summary
    all_entries = entries(include_service=include_service)
    if query:
        try:
            matched = [get_element(int(query) if query.isdigit() else query)]
        except KeyError:
            needle = query.casefold()
            matched = [entry for entry in all_entries if needle in str(entry).casefold()]
    else:
        matched = all_entries
    if not detail:
        fields = ("kind", "typeid", "aliases", "pin_names", "pin_count", "internal", "service",
                  "geometry_status", "native_tested", "native_validation", "notes")
        matched = [{**{key:entry[key] for key in fields if key in entry},
                    "parameter_names": list(entry["defaults"])} for entry in matched]
    return {"ok": True, "inventory": inventory_summary(), "count": len(matched), "elements": matched}


@mcp.tool(annotations=WRITE, structured_output=True)
@tool_errors
def fastmean_edit_properties(path: str, updates: dict | None = None, analysis: dict | None = None,
                            definitions: list[dict] | None = None) -> dict[str, Any]:
    """Edit native component parameters, tables and saved settings in a new project.

    updates={"TR1":{"n":2},"SW1":{"Ron":0.01}}; nested parameter patches retain
    omitted fields. analysis selects saved TD/FD/AOD/SOD/DCOP fields, including
    graph expressions and sweep settings. definitions saves native .define
    variables/functions as TEXT. No source files are overwritten or run here.
    File/model interfaces use create_project, not arbitrary parameter paths.
    """
    from .properties import edit_properties
    source = source_path(path)
    job = new_job("properties")
    result = edit_properties(source, job/"circuit.scm", updates, analysis, definitions)
    result.update(ok=True, analysis="properties", working_dir=str(job),
                  origin="Native SCM properties edited by MCP; no analysis performed")
    result["dependency_artifacts"] = [{"path":value} for value in result.get("dependency_paths",[])]
    return store().publish(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_dc(path: str, signals: Signals | None = None, source_values: dict | None = None,
                      definitions: list[dict] | None = None, overrides: dict | None = None,
                      timeout: Annotated[float, Field(ge=1,le=60,allow_inf_nan=False)] = 60) -> CallToolResult:
    """Calculate the native DC operating point in a private copy.

    Uses native DC initialization and a zero-duration native export. DC source
    ramps/delays are removed only in the private DC copy and recorded. Supply
    source_values to replace non-DC source waveforms for this calculation.
    """
    source=source_path(path)
    result=await native_operation("dc",source,lambda native:native.run_dc(source,signals,
        definitions=definitions,overrides=overrides,source_values=source_values),timeout=timeout)
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_sweep(path: str, target: str, values: list,
        analysis: Literal["ac","transient","dc"] = "ac", settings: dict | None = None,
        signals: Signals | None = None, definitions: list[dict] | None = None,
        overrides: dict | None = None,
        timeout: Annotated[float,Field(ge=1,le=60,allow_inf_nan=False)] = 60) -> CallToolResult:
    """Sweep one native variable or component.parameter over 1–32 values.

    Each point is a separate owned native calculation. settings carries the
    corresponding AC/transient/DC options; native samples and provenance are
    retained for every point. The original schematic is preserved.
    """
    source=source_path(path)
    if signals is None and analysis in {"ac","transient"}:
        signals=_saved_signals(source,"FD" if analysis=="ac" else "TD")
    result=await native_operation("sweep",source,lambda native:native.run_parameter_sweep(
        source,target,values,analysis,settings,signals,definitions=definitions,overrides=overrides),timeout=timeout)
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_spectrum(path: str, signal: str, window: list[float] | None = None,
        stop: Positive = .01, step: Positive = 1e-6, eps: Positive = 1e-5,
        points: Annotated[int,Field(ge=16,le=262144)] = 4096,
        window_function: Literal["hann","rectangular","hamming","blackman","bartlett"] = "hann",
        definitions: list[dict] | None = None, overrides: dict | None = None,
        timeout: Annotated[float,Field(ge=1,le=60,allow_inf_nan=False)] = 60) -> CallToolResult:
    """Return spectrum amplitude/phase/PSD of real FASTMEAN transient samples.

    FASTMEAN calculates time samples. NumPy interpolates onto a uniform grid and
    performs rFFT; the PNG is Matplotlib, not a native FFT-window screenshot.
    Native source CSV, selected window and transform normalization are retained.
    """
    source=source_path(path)
    result=await native_operation("spectrum",source,lambda native:native.run_spectrum(
        source,signal,window,stop,step,eps,points,window_function,
        definitions=definitions,overrides=overrides),timeout=timeout)
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_evaluate(path: str, signals: Signals, stop: Positive = .01,
        step: Positive = 1e-6, eps: Positive = 1e-5, fft: dict | None = None,
        definitions: list[dict] | None = None, overrides: dict | None = None,
        timeout: Annotated[float,Field(ge=1,le=60,allow_inf_nan=False)] = 60) -> CallToolResult:
    """Evaluate native post-analysis functions or the native FASTMEAN FFT.

    signals may use last/AVG/RMS or native harmonic functions. FFT mode uses
    explicit fft settings and FFT expressions; a separate native time writer
    proves the simulated interval. Returns the actual native summary/FFT table,
    not a fabricated transient time axis. No arbitrary script is accepted.
    """
    from .analysis import run_summary
    source=source_path(path)
    result=await native_operation("evaluate",source,lambda native:run_summary(native,source,
        signals,stop,step,eps,definitions=definitions,overrides=overrides,fft=fft),timeout=timeout)
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_harmonics(path: str, signal: str, frequencies: list[float], window: list[float],
        stop: Positive = .01, step: Positive = 1e-6, eps: Positive = 1e-5,
        definitions: list[dict] | None = None, overrides: dict | None = None,
        timeout: Annotated[float,Field(ge=1,le=60,allow_inf_nan=False)] = 60) -> CallToolResult:
    """Extract up to seven harmonics using native tre/tim/tmag/tph expressions.

    Frequencies are Hz; window=[start,end] seconds. FASTMEAN itself evaluates
    the harmonic expressions. This differs from the NumPy spectrum tool.
    """
    source=source_path(path)
    result=await native_operation("harmonics",source,lambda native:native.run_harmonics(
        source,signal,frequencies,window,stop,step,eps,
        definitions=definitions,overrides=overrides),timeout=timeout)
    return _with_image(result)


@mcp.tool(annotations=WRITE)
@tool_errors
async def fastmean_symbolic(path: str, output: str = "out", input: str | None = "in",
        analysis: Literal["voltage","current","transfer","impedance","admittance"] = "voltage",
        output_reference: str = "0", output_element: str | None = None,
        input_source: str | None = None) -> CallToolResult:
    """Get native CIRSYM U/I/H/Z/Y formulas for supported linear zero-state circuits.

    Native FASTMEAN exports connectivity before conversion to CIRSYM. Optional
    input must be driven by a unique grounded independent voltage source; the
    transfer function is derived by dividing the native output by its amplitude.
    Set input=null for an output equation only. Not an arbitrary equation solver.
    """
    source = source_path(path)
    from .symbolic_conversion import component_kinds_from_export,derive_symbolic_function
    installation = app_dir()
    for name in ("cirsymw.exe", "human.sym"):
        required = installation / "symbolic" / name
        if not required.is_file():
            raise FileNotFoundError(f"Native symbolic analysis requires the installed file: {required}")
    def solve(native):
        exported = native.export_netlist(source)
        kinds = component_kinds_from_export(exported)
        converted = cirsym_from_fastmean_netlist(exported["text"], output=output, input=input, component_kinds=kinds,
            analysis=analysis,output_reference=output_reference,output_element=output_element,input_source=input_source)
        result = run_symbolic(installation, converted["netlist"], output_dir(), cancel_event=native.cancel_event)
        # If the optional worker disappears after the preflight, retain its
        # real failure in the already-created export job instead of failing
        # publication with an unrelated missing-working-directory error.
        if not result.get("cwd"):
            result["working_dir"] = exported["working_dir"]
        result["native_netlist_export"] = exported
        result["conversion"] = {k: v for k, v in converted.items() if k != "netlist"}
        derived = derive_symbolic_function(result,converted)
        if derived:
            result["symbolic_function"] = derived
            if converted.get("input_parameter"):
                result["transfer_function"] = derived
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

    Recursively packages SCM model dependencies and records source/copy hashes.
    Starts a separate application process; leaves existing windows alone. The
    circuit window stays open for the user, and is not controlled automatically.
    This command does not apply locale emulation; old Russian UI text may appear
    garbled on Windows configured for another legacy code page.
    """
    source = source_path(path)
    # The existing project preparer validates every model before any GUI launch;
    # it performs no calculation and keeps file directives disabled in copies.
    instance = engine()
    job, manifest = instance._job(source, "open")
    copied = Path(manifest["private_schematic"])
    exe = instance.executable
    command = [str(exe), "-o", str(copied)]
    try:
        process = subprocess.Popen(command, cwd=str(job), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as error:
        manifest.update({"status": "failed", "error": str(error), "command": command})
        instance._manifest(job, manifest)
        raise
    manifest.update({"status": "opened", "pid": process.pid, "command": command,
                     "analysis_requested": False, "gui_owned_by_user": True})
    instance._manifest(job, manifest)
    return store().publish({"ok": True, "analysis": "open", "working_dir": str(job),
            "path": str(copied), "source": str(source), "source_path": str(source),
            "source_sha256": manifest["source_sha256"], "source_models": manifest["source_models"],
            "models": [{"path": item["private_path"], "sha256": item["private_sha256"]}
                       for item in manifest["source_models"]],
            "manifest_path": str(job / "manifest.json"), "engine": manifest["engine"], "pid": process.pid,
            "russian_launcher": False, "message": "Started native FASTMEAN with a recursively packaged working copy. No locale emulation is applied."})


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
def fastmean_relayout(path: str, placements: dict | None = None,
                      density: Literal["compact", "standard"] = "compact") -> dict[str, Any]:
    """Rebuild a supported circuit as adjacent components with physical wires.

    Converts old per-pin PORT layouts into a connected orthogonal drawing.
    Preserves values, waveforms and native analysis in a new SCM. Supports
    catalog primitives and portable subcircuits. Optional
    placements: {R1:{x:960,y:1000,rotation:0}}. Numeric node-voltage references
    require stable named ports before changing geometry.
    density selects compact (default) or the previous standard spacing.
    """
    from .relayout import relayout_circuit
    job = new_job("layout")
    result = relayout_circuit(source_path(path), job / "circuit.scm",placements=placements,density=density)
    result.update(working_dir=str(job),ok=True,analysis="relayout")
    result["dependency_artifacts"] = [{"path":value} for value in result.get("dependency_paths",[])]
    return store().publish(result)


@mcp.tool(annotations=WRITE)
@tool_errors
def fastmean_preview(path: str, include_text: bool = True) -> CallToolResult:
    """Render a wire-connected SCM to readable PNG and SVG for visual review.

    This is an MCP rendering of native objects, not a FASTMEAN screenshot.
    Proven native L/midpoint bends are reconstructed exactly. Unsupported
    symbols/detours are rejected. No application window is opened.
    include_text=False omits TEXT notes from this image and its bounds only;
    all source annotations and parameter bindings remain unchanged.
    """
    from .preview import render_schematic
    source = source_path(path)
    result = render_schematic(source, output_dir(), include_text=include_text)
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


@mcp.tool(annotations=WRITE)
@tool_errors
def fastmean_plot(run_id: str,
                  panels: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=12)] | None = None,
                  display_window: list[Any] | None = None,
                  measurement_window: list[Any] | None = None,
                  title: Annotated[str, Field(min_length=1, max_length=160, strict=True)] | None = None,
                  subtitle: Annotated[str, Field(min_length=1, max_length=240, strict=True)] | None = None,
                  x_unit: Literal["s", "ms", "us", "Hz", "kHz", "MHz"] | None = None) -> CallToolResult:
    """Plot registered AC, transient, native FFT or NumPy spectrum data through MCP.

    panels selects 1–12 exact exported columns. A panel is {signal, label?,
    unit?, scale?:1, metrics?:[rms], guides?:[], color?:'#2563eb'}. Metrics are
    rms/mean/peak/min/max/peak_to_peak; guides are mean/rms and include that
    measurement. Frequency panels have metrics=[]; time-weighted metrics require TD.
    unit is a caller-supplied display label; display_value=native_value*scale
    with finite positive scale. No new formulas are evaluated. For native power,
    export e.g. U(OUT)*I(RL) during transient and select that exact column here.
    Windows are [start,stop] in original seconds/Hz, independently of x_unit.
    Interpolate exact endpoints, retain adaptive timestamps and both states of
    equal-time switching events in native order, and reject
    extrapolation. RMS uses trapezoids of squared samples. Metrics use the full
    measurement window before graphical decimation. Original run stays intact;
    a new run returns ImageContent, PNG/SVG/spec/measurements/manifest resources.
    """
    from .plotting import prepare_plot, render_plot
    plan = prepare_plot(store(), run_id, panels=panels, display_window=display_window,
                        measurement_window=measurement_window, title=title,
                        subtitle=subtitle, x_unit=x_unit)
    return _with_image(render_plot(plan, new_job("plot")))


@mcp.tool(annotations=READ, structured_output=True)
@tool_errors
def fastmean_read_data(run_id: str, offset: Annotated[int, Field(ge=0, le=1000000)] = 0,
                       limit: Annotated[int, Field(ge=1, le=500)] = 200) -> dict[str, Any]:
    """Read a page of registered calculation samples with their recorded provenance."""
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
