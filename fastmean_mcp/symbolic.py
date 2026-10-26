"""Run the installed FASTMEAN CIRSYM worker in an isolated working directory.

This module returns the native worker's expressions without replacing them with
another algebra engine.  ``cirsymw.exe -s human.sym`` reads ``cir`` and writes
``out`` relative to its current directory.  The executable remains at its
installed location; only its settings and the caller's netlist are copied.
"""

from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from typing import Any


ENGINE_NAME = "FASTMEAN CIRSYM (cirsymw.exe)"
MAX_NETLIST_BYTES = 1_000_000
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(data: bytes | str | None) -> str:
    if isinstance(data, str):
        return data
    return (data or b"").decode("cp1251", errors="replace")


def parse_native_output(text: str) -> dict[str, Any]:
    """Extract assignments from CIRSYM output; do not simplify expressions.

    The full unmodified text is returned separately by :func:`run_symbolic`.
    Whitespace is removed from the machine-readable ``expression`` field only.
    Numeric component assignments remain strings to preserve native precision.
    """
    output_names = set(re.findall(r"^\s*%\s*Output:\s*([A-Za-z_]\w*)", text, re.M))
    body = re.sub(r"%[^\r\n]*", "", text)
    parameters: dict[str, str] = {}
    equations: list[dict[str, str]] = []
    for match in re.finditer(r"^\s*([A-Za-z_]\w*)\s*=\s*(.*?);", body, re.M | re.S):
        name, native_expression = match.groups()
        expression = re.sub(r"\s+", "", native_expression)
        if not expression:
            continue
        if name not in output_names and _NUMBER.fullmatch(expression):
            parameters[name] = expression
        else:
            equations.append({"name": name, "expression": expression})
    return {"parameters": parameters, "equations": equations}


def _constant_fraction(node: ast.AST, expression: str) -> Fraction | None:
    """Recognize exact constant zeros for validation, without evaluating names.

    Fractions avoid classifying a tiny nonzero native long-double coefficient as
    zero through Python float underflow.  Unknown symbols remain unknown.
    """
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        literal = ast.get_source_segment(expression, node)
        if literal is None or len(literal) > 100:
            return None
        exponent = re.search(r"[eE]([+-]?\d+)$", literal)
        if exponent and abs(int(exponent[1])) > 10000:
            return None
        try:
            return Fraction(literal)
        except (ValueError, ZeroDivisionError):
            return None
    if isinstance(node, ast.UnaryOp):
        value = _constant_fraction(node.operand, expression)
        if value is not None and isinstance(node.op, (ast.UAdd, ast.USub)):
            return value if isinstance(node.op, ast.UAdd) else -value
        return None
    if not isinstance(node, ast.BinOp):
        return None
    left = _constant_fraction(node.left, expression)
    right = _constant_fraction(node.right, expression)
    if isinstance(node.op, ast.Mult) and (left == 0 or right == 0):
        return Fraction(0)
    if left is None or right is None:
        return None
    if isinstance(node.op, ast.Add):
        return left + right
    if isinstance(node.op, ast.Sub):
        return left - right
    if isinstance(node.op, ast.Mult):
        return left * right
    if isinstance(node.op, ast.Div) and right != 0:
        return left / right
    if isinstance(node.op, ast.Pow) and right.denominator == 1 and abs(right) <= 64:
        if left == 0 and right < 0:
            return None
        return left ** int(right)
    return None


def _has_zero_denominator(expression: str) -> bool:
    try:
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                if _constant_fraction(node.right, expression) == 0:
                    return True
    except (SyntaxError, RecursionError, ValueError):
        # Native text is retained even when its syntax cannot be inspected by
        # Python's parser.  No expression or identifier is ever executed.
        return False
    return False


def _require_grounded_graph(edges: list[tuple[int, int]]) -> None:
    adjacency: dict[int, set[int]] = {0: set()}
    for a, b in edges:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    reached, todo = {0}, [0]
    while todo:
        for neighbor in adjacency[todo.pop()] - reached:
            reached.add(neighbor)
            todo.append(neighbor)
    if reached != set(adjacency):
        raise ValueError("native symbolic circuit contains a floating island or has no connection to ground")


def _voltage_value(component: dict[str, Any]) -> float:
    """Use the active DC/sine amplitude rather than an inactive DC default."""
    value = _parse_value(component.get("value"))
    waveform = component.get("waveform")
    if waveform is None:
        return value
    if not isinstance(waveform, dict):
        raise ValueError("source waveform must be a mapping")
    kind = str(waveform.get("kind", "dc")).lower()
    fields = {"dc": {"amplitude", "delay", "rise_time"},
              "sine": {"amplitude", "frequency", "phase", "delay"}}
    if kind not in fields:
        raise ValueError("native symbolic spec conversion supports DC or sine voltage sources; a waveform Laplace transform is not synthesized")
    unknown = set(waveform) - fields[kind] - {"kind"}
    if unknown:
        raise ValueError(f"unsupported {kind} source waveform fields: {sorted(unknown)}")
    for key, raw in waveform.items():
        if key == "kind":
            continue
        numeric = _parse_value(raw)
        if key in {"frequency", "rise_time"} and numeric <= 0:
            raise ValueError(f"source {key} must be positive")
        if key == "delay" and numeric < 0:
            raise ValueError("source delay cannot be negative")
    return _parse_value(waveform["amplitude"]) if "amplitude" in waveform else value


def _failure(result: dict[str, Any], kind: str, message: str, **extra: Any) -> dict[str, Any]:
    result["ok"] = False
    result["error"] = {"kind": kind, "message": message, **extra}
    return result


def _kill_owned_worker(process: subprocess.Popen) -> None:
    """Terminate only the process represented by this private Popen object."""
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            if process.poll() is None:
                raise


def _run_cancellable(command: list[str], workspace: Path, timeout: float,
                     cancelled: threading.Event) -> tuple[subprocess.CompletedProcess, bool, int]:
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, cwd=workspace, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          creationflags=subprocess.CREATE_NO_WINDOW, shell=False) as process:
        while True:
            if cancelled.is_set():
                _kill_owned_worker(process)
                stdout, stderr = process.communicate()
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr), True, process.pid
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill_owned_worker(process)
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
            try:
                stdout, stderr = process.communicate(timeout=min(0.1, remaining))
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr), cancelled.is_set(), process.pid
            except subprocess.TimeoutExpired:
                continue


def run_symbolic(
    app_dir: Path,
    netlist: str,
    output_dir: Path,
    timeout: float = 30,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Execute FASTMEAN's installed native symbolic worker.

    ``app_dir`` is the FASTMEAN installation directory (or its ``symbolic``
    subdirectory).  A new directory under ``output_dir`` retains the exact
    input, copied settings, stdout, stderr and native output for reproducibility.
    No file in the installation is written and Windows settings are untouched.

    Validation errors raise ``ValueError``.  Missing engine, policy blocks,
    timeouts, cancellation, invalid native input and missing native output are explicit
    ``ok=False`` results.  An existing output file can never be reused.
    """
    if not isinstance(netlist, str) or not netlist.strip():
        raise ValueError("netlist must be a nonempty native CIRSYM netlist string")
    if "\x00" in netlist:
        raise ValueError("netlist must not contain NUL characters")
    try:
        netlist_bytes = netlist.encode("cp1251")
    except UnicodeEncodeError as error:
        raise ValueError("native CIRSYM netlists must be representable in Windows-1251") from error
    if len(netlist_bytes) > MAX_NETLIST_BYTES:
        raise ValueError(f"netlist exceeds {MAX_NETLIST_BYTES} bytes")
    if not re.search(r"^\s*\.END\s*(?:[;*].*)?$", netlist, re.M | re.I):
        raise ValueError("native CIRSYM netlist must contain a .END line")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0 or timeout > 600:
        raise ValueError("timeout must be a finite number in (0, 600] seconds")

    installation = Path(app_dir).expanduser().resolve()
    engine_dir = installation / "symbolic" if (installation / "symbolic").is_dir() else installation
    executable = engine_dir / "cirsymw.exe"
    settings = engine_dir / "human.sym"
    destination = Path(output_dir).expanduser().resolve()
    # Also reject the application parent when app_dir names its symbolic folder.
    protected_installation = installation.parent if installation.name.lower() == "symbolic" else installation
    if destination == protected_installation or protected_installation in destination.parents:
        raise ValueError("output_dir must be outside the FASTMEAN installation")

    result: dict[str, Any] = {
        "ok": False,
        "engine": ENGINE_NAME,
        "engine_path": str(executable),
        "command": [],
        "cwd": None,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "raw_output": "",
        "native_output_path": None,
        "parameters": {},
        "equations": [],
    }
    if not executable.is_file() or not settings.is_file():
        return _failure(result, "engine_missing", "cirsymw.exe and human.sym were not found in the FASTMEAN symbolic directory")
    if os.name != "nt":
        return _failure(result, "unsupported_platform", "The native FASTMEAN worker requires Windows")

    executable_bytes = executable.read_bytes()
    settings_bytes = settings.read_bytes()
    result["engine_sha256"] = _sha256(executable_bytes)
    result["settings_sha256"] = _sha256(settings_bytes)
    result["input_sha256"] = _sha256(netlist_bytes)
    destination.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="native-symbolic-", dir=destination))
    (workspace / "cir").write_bytes(netlist_bytes)
    (workspace / "human.sym").write_bytes(settings_bytes)
    command = [str(executable), "-s", "human.sym"]
    result.update({"command": command, "cwd": str(workspace), "input_path": str(workspace / "cir")})

    start = time.monotonic()
    failure: tuple[str, str, dict[str, Any]] | None = None
    try:
        if cancel_event is not None and cancel_event.is_set():
            failure = ("cancelled", "Native CIRSYM request was cancelled before process creation", {})
        else:
            if cancel_event is None:
                completed = subprocess.run(
                    command,
                    cwd=workspace,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    shell=False,
                    check=False,
                )
            else:
                completed, was_cancelled, pid = _run_cancellable(command, workspace, timeout, cancel_event)
                result["pid"] = pid
                if was_cancelled:
                    failure = ("cancelled", "Native CIRSYM request was cancelled; only its owned process was terminated", {})
            result.update({"exit_code": completed.returncode, "stdout": _decode(completed.stdout), "stderr": _decode(completed.stderr)})
    except subprocess.TimeoutExpired as error:
        result.update({"stdout": _decode(error.stdout), "stderr": _decode(error.stderr)})
        failure = ("timeout", f"Native CIRSYM exceeded {timeout:g} seconds and was terminated", {})
    except OSError as error:
        number = getattr(error, "winerror", None)
        kind = "blocked_by_application_control" if number in {4551, 577, 1260} else "launch_failed"
        failure = (kind, str(error), {"winerror": number} if number is not None else {})
    result["elapsed_seconds"] = round(time.monotonic() - start, 6)
    (workspace / "stdout.txt").write_text(result["stdout"], encoding="utf-8")
    (workspace / "stderr.txt").write_text(result["stderr"], encoding="utf-8")

    native_output = workspace / "out"
    if native_output.is_file():
        raw = native_output.read_bytes()
        result.update({"raw_output": _decode(raw), "native_output_path": str(native_output), "output_sha256": _sha256(raw)})
        result.update(parse_native_output(result["raw_output"]))
    if failure:
        return _failure(result, failure[0], failure[1], **failure[2])
    if result["exit_code"] != 0:
        return _failure(result, "native_error", f"Native CIRSYM exited with code {result['exit_code']}")
    native_diagnostics = result["stdout"] + "\n" + result["stderr"] + "\n" + result["raw_output"]
    if re.search(r"(?:^|\n)\s*%?\s*Cannot (?:open|execute)\b", native_diagnostics, re.I):
        return _failure(result, "invalid_native_input", "Native CIRSYM reported that it could not read or analyze the netlist; inspect its retained output")
    if not result["equations"]:
        return _failure(result, "native_output_missing", "Native CIRSYM returned no parseable equation; inspect its retained output")
    singular = [equation["name"] for equation in result["equations"]
                if _has_zero_denominator(equation["expression"])]
    if singular:
        return _failure(result, "native_singular_circuit", "Native CIRSYM returned an identically zero denominator; the circuit is singular or floating", equations=singular)
    result["ok"] = True
    return result


def _parse_value(value: Any) -> float:
    # These public helpers are shared with the schematic builder when available.
    from .schematic import parse_value
    return parse_value(value)


def _node(value: Any) -> str:
    from .schematic import normalize_node
    return normalize_node(value)


def netlist_from_spec(
    spec: dict[str, Any],
    output_node: str = "out",
    input_node: str | None = None,
) -> dict[str, Any]:
    """Generate a small native CIRSYM netlist from the shared schematic spec.

    Supports positive R/C/L and independent voltage sources U (alias V).
    Public source nodes are [positive, negative]; native CIRSYM E entries use
    [negative, positive], as observed in FASTMEAN's own RC netlist export.
    Output is a voltage to ground.  Exactly one independent voltage source is
    supported, preserving CIRSYM's single-input/single-output polynomial mode.
    Optional input_node must be that source's positive node with its negative
    node grounded.  Its native E parameter is returned so a caller can derive
    H=U_symbolic_output/E without asking CIRSYM for a second output probe.
    """
    if not isinstance(spec, dict) or not isinstance(spec.get("components"), list) or not spec["components"]:
        raise ValueError("spec.components must be a nonempty list")
    node_map: dict[str, int] = {"0": 0}
    names: set[str] = set()
    lines = ["--- Generated for the native FASTMEAN CIRSYM worker ---", ""]
    generated_components: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    graph_edges: list[tuple[int, int]] = []

    def node_number(value: Any) -> int:
        name = _node(value)
        if name not in node_map:
            node_map[name] = len(node_map)
        return node_map[name]

    prefixes = {"R": "R_", "C": "c_", "L": "L_", "U": "E_"}
    for component in spec["components"]:
        if not isinstance(component, dict):
            raise ValueError("each component must be an object")
        if "kind" in component and "type" in component:
            kinds = {"U" if str(component[key]).upper() == "V" else str(component[key]).upper()
                     for key in ("kind", "type")}
            if len(kinds) != 1:
                raise ValueError("component kind and type disagree")
        kind = str(component.get("kind", component.get("type", ""))).upper()
        if kind == "V":
            kind = "U"
        if kind not in prefixes:
            raise ValueError(f"native netlist generation does not support component kind {kind!r}; supported kinds: R, C, L, U/V")
        name = component.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("native component names must be ASCII letters/digits/underscores and start with a letter or underscore")
        if name.casefold() in names:
            raise ValueError(f"duplicate component name: {name}")
        names.add(name.casefold())
        nodes = component.get("nodes")
        if not isinstance(nodes, (tuple, list)) or len(nodes) != 2:
            raise ValueError(f"component {name} must have exactly two nodes")
        a, b = node_number(nodes[0]), node_number(nodes[1])
        if a == b:
            raise ValueError(f"component {name} connects a node to itself")
        graph_edges.append((a, b))
        value = _voltage_value(component) if kind == "U" else _parse_value(component.get("value"))
        if kind != "U" and value <= 0:
            raise ValueError(f"{kind} component {name} must have a positive value")
        if kind in {"C", "L"} and _parse_value(component.get("initial_condition", 0)) != 0:
            raise ValueError(f"{kind} component {name} has nonzero initial conditions; zero-state symbolic analysis would discard them")
        if kind != "U" and "waveform" in component:
            raise ValueError(f"{kind} component {name} cannot have a source waveform")
        if kind == "U":
            a, b = b, a
        native_name = prefixes[kind] + name
        lines.append(f"{native_name} {a} {b} {value:.17g}")
        generated_components.append({"name": name, "native_name": native_name, "kind": kind, "value": value})
        if kind == "U":
            sources.append({"native_name": native_name, "negative_node": a, "positive_node": b, "value": value})
    _require_grounded_graph(graph_edges)
    if len(sources) != 1:
        raise ValueError("native symbolic conversion currently requires exactly one independent voltage source to preserve CIRSYM's polynomial p representation")
    normalized_output = _node(output_node)
    if normalized_output not in node_map or normalized_output == "0":
        raise ValueError(f"output node {output_node!r} must be an existing nonground circuit node")
    lines.extend(["", f"U_symbolic_output {node_map[normalized_output]} 0"])
    input_parameter = None
    if input_node is not None:
        normalized_input = _node(input_node)
        if normalized_input not in node_map or normalized_input == "0":
            raise ValueError(f"input node {input_node!r} must be an existing nonground circuit node")
        source = sources[0]
        if source["positive_node"] != node_map[normalized_input] or source["negative_node"] != 0:
            raise ValueError("transfer-function input must be the positive node of the single independent voltage source, whose negative terminal must be grounded")
        if source["value"] == 0:
            raise ValueError("a transfer-function input amplitude must be nonzero; use input_node=None for the native output equation only")
        input_parameter = source["native_name"]
    lines.extend(["", ".END", ""])
    return {"netlist": "\r\n".join(lines), "node_map": node_map, "components": generated_components,
            "output_equation": "U_symbolic_output", "input_parameter": input_parameter,
            "transfer_relation": "U_symbolic_output/" + input_parameter if input_parameter else None,
            "analysis_mode": "native single-input single-output polynomial"}


def cirsym_from_fastmean_netlist(
    text: str,
    output: str = "OUT",
    input: str | None = "IN",
    component_kinds: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convert native ``save_netlist`` output to the CIRSYM worker dialect.

    FASTMEAN's main executable supplies the actual circuit connectivity and
    values.  This adapter supports R/C/L and independent voltage sources only;
    nonlinear, controlled and unsupported elements cause a clear rejection.
    C/L initial conditions must be zero.  With ``component_kinds`` supplied,
    every element must appear in that map, so renamed elements cannot be
    misclassified by their instance-name prefix.  Without it, only canonical
    names R1/C1/L1/U1 (letter followed by digits) can be inferred.

    ``output`` and ``input`` name a native named port or integer node.  The
    input must be the positive terminal of the single independent voltage
    source, with its negative terminal grounded.  That native E parameter is
    returned for H=U_symbolic_output/E.  Only ONE output probe is emitted: the
    native worker changes algorithms for multiple probes and its expressions
    then omit the explicit p variable with the bundled settings.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("native FASTMEAN netlist text must be nonempty")
    if component_kinds is not None and not isinstance(component_kinds, dict):
        raise ValueError("component_kinds must map native instance names to component kinds")
    kinds = {str(name): str(kind).upper() for name, kind in (component_kinds or {}).items()}
    ports: dict[str, int] = {}
    seen_names: set[str] = set()
    node_numbers: set[int] = {0}
    components: list[dict[str, Any]] = []
    lines = ["--- Converted from FASTMEAN native save_netlist ---", ""]
    used_native_names: set[str] = set()
    prefixes = {"R": "R_", "C": "c_", "L": "L_", "U": "E_"}

    def parse_node(token: str, line_number: int) -> int:
        if not re.fullmatch(r"\d+", token):
            raise ValueError(f"invalid native node {token!r} on line {line_number}")
        number = int(token)
        if number > 2_147_483_647:
            raise ValueError(f"native node is too large on line {line_number}")
        return number

    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("*", "%")):
            continue
        fields = stripped.split()
        name = fields[0]
        if name.startswith("."):
            raise ValueError(f"native netlist directive {name!r} is unsupported for symbolic conversion (line {line_number})")
        if len(fields) == 2:
            if name in kinds or re.fullmatch(r"[RCLU]\d+", name, re.I):
                raise ValueError(f"native component {name!r} is missing terminals/value on line {line_number}")
            number = parse_node(fields[1], line_number)
            if name in ports and ports[name] != number:
                raise ValueError(f"native port {name!r} maps to inconsistent nodes")
            ports[name] = number
            # A label alone is not an electrical connection. Probes must refer
            # to nodes actually used by supported components, never a dangling
            # named port that would create a nonexistent CIRSYM output node.
            continue
        if len(fields) < 4:
            raise ValueError(f"unsupported native netlist row on line {line_number}: {stripped}")
        if name.casefold() in seen_names:
            raise ValueError(f"duplicate native element name {name!r}")
        seen_names.add(name.casefold())
        if component_kinds is not None:
            if name not in kinds:
                raise ValueError(f"native element {name!r} has no explicit component kind")
            kind = kinds[name]
        else:
            inferred = re.fullmatch(r"([RCLU])\d+", name, re.I)
            if inferred is None:
                raise ValueError(f"cannot infer the kind of renamed element {name!r}; supply component_kinds")
            kind = inferred[1].upper()
        if kind == "V":
            kind = "U"
        if kind not in prefixes:
            raise ValueError(f"native symbolic conversion does not support {kind!r} element {name!r}; supported kinds: R, C, L, U/V")
        a, b = parse_node(fields[1], line_number), parse_node(fields[2], line_number)
        if a == b:
            raise ValueError(f"native element {name!r} connects a node to itself")
        node_numbers.update((a, b))
        if kind == "U":
            if len(fields) < 5 or fields[3].upper() not in {"DC", "AC"}:
                raise ValueError(f"native voltage source {name!r} must use DC or AC; waveform sources require an explicit native CIRSYM netlist")
            value = _parse_value(fields[4])
        else:
            value = _parse_value(fields[3])
            if value <= 0:
                raise ValueError(f"native {kind} element {name!r} must have a positive value")
            if kind == "R" and len(fields) != 4:
                raise ValueError(f"unsupported extra parameters for native resistor {name!r}")
            if kind in {"C", "L"}:
                if len(fields) not in {4, 5}:
                    raise ValueError(f"unsupported extra parameters for native {kind} element {name!r}")
                if len(fields) == 5 and _parse_value(fields[4]) != 0:
                    raise ValueError(f"native {kind} element {name!r} has nonzero initial conditions; zero-state transfer analysis would discard them")
        safe_name = name if _NAME.fullmatch(name) else "component_" + str(len(components) + 1)
        native_name = prefixes[kind] + safe_name
        if native_name.casefold() in used_native_names:
            native_name += "_" + str(len(components) + 1)
        used_native_names.add(native_name.casefold())
        # save_netlist already emits U-source terminals in native [negative,
        # positive] order.  Unlike netlist_from_spec, do not reverse them here.
        lines.append(f"{native_name} {a} {b} {value:.17g}")
        components.append({"name": name, "native_name": native_name, "kind": kind, "nodes": [a, b], "value": value})
    if not components:
        raise ValueError("native FASTMEAN netlist contains no supported circuit elements")
    _require_grounded_graph([tuple(component["nodes"]) for component in components])

    def probe(value: str, role: str) -> int:
        token = str(value)
        if token in ports:
            number = ports[token]
        elif re.fullmatch(r"\d+", token):
            number = int(token)
        else:
            raise ValueError(f"{role} {value!r} is not a native port or integer node")
        if number == 0 or number not in node_numbers:
            raise ValueError(f"{role} {value!r} must refer to an existing nonground circuit node")
        return number

    output_number = probe(output, "output")
    sources = [component for component in components if component["kind"] == "U"]
    if len(sources) != 1:
        raise ValueError("native symbolic conversion currently requires exactly one independent voltage source to preserve CIRSYM's polynomial p representation")
    lines.extend(["", f"U_symbolic_output {output_number} 0"])
    input_parameter = None
    if input is not None:
        input_number = probe(input, "input")
        source = sources[0]
        if source["nodes"] != [0, input_number]:
            raise ValueError("transfer-function input must be the positive node of the single independent voltage source, whose negative terminal must be grounded")
        if source["value"] == 0:
            raise ValueError("a transfer-function input amplitude must be nonzero; use input=None for the native output equation only")
        input_parameter = source["native_name"]
    lines.extend(["", ".END", ""])
    return {"netlist": "\r\n".join(lines), "ports": ports, "components": components,
            "output_equation": "U_symbolic_output", "input_parameter": input_parameter,
            "transfer_relation": "U_symbolic_output/" + input_parameter if input_parameter else None,
            "conversion": "native FASTMEAN save_netlist to CIRSYM; linear zero-state circuit",
            "analysis_mode": "native single-input single-output polynomial"}
