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


# Kept as public imports for existing clients of this module.
from .symbolic_conversion import (  # noqa: E402
    cirsym_from_fastmean_netlist, derive_symbolic_function, netlist_from_spec, symbolic_capabilities,
)
