"""Run the documented FASTMEAN script CLI in private, auditable job folders.

All numerical samples come from the installed FASTMEAN executable. CSV files
and Matplotlib figures are renderings of those samples, not replacements for
the native solver or screenshots of the FASTMEAN GUI.
"""
from __future__ import annotations

import copy
import csv
import atexit
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any
from uuid import uuid4

from .schematic import SchemeError, _load, _summarize, _write_document, parse_value, read_scheme

MAX_AC_POINTS = 10000
MAX_TRANSIENT_STEPS = 1000000
MAX_TABLE_BYTES = 256 * 1024 * 1024
MAX_SIGNALS = 30
MAX_MODEL_FILES = 100
MAX_PROJECT_BYTES = 64 * 1024 * 1024
_RENDER_LOCK = threading.Lock()
_OWNED_LOCK = threading.Lock()
_OWNED_PROCESSES: set[subprocess.Popen] = set()
_UNSAFE_DIRECTIVE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])\.(?:write|include|read|save(?:_as|_netlist)?|open|cd|exit|exec|run|system)\b")
_FORBIDDEN_WORDS = frozenset({"write", "include", "read", "save", "save_as", "save_netlist",
                              "open", "cd", "exit", "exec", "run", "system", "sim", "ac", "define", "set"})
_TOKEN = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:[A-Za-z]+)?|[A-Za-z_][A-Za-z0-9_]*|[()+\-*/^,.]")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EngineError(ValueError):
    """Native solver failure or invalid request; job artifacts remain available."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _stop_owned(process: subprocess.Popen) -> None:
    """Stop only the process represented by this exact Popen handle."""
    try:
        if process.poll() is None:
            process.kill()
    except OSError:
        pass  # It may have exited between poll and TerminateProcess.


def _cleanup_at_exit() -> None:
    with _OWNED_LOCK:
        processes = list(_OWNED_PROCESSES)
    for process in processes:
        _stop_owned(process)


atexit.register(_cleanup_at_exit)


def _sanitize_document(document: dict) -> None:
    for mapping in _walk(document):
        if mapping.get("Type") == 900:
            text = (mapping.get("Params") or {}).get("Text", "")
            if not isinstance(text, str):
                raise EngineError("A schematic Text object has non-text contents.")
            match = _UNSAFE_DIRECTIVE.search(text)
            if match:
                raise EngineError(f"Embedded schematic directive {match.group()} is not permitted in a private batch run.")
    body = document["scm"]
    body.setdefault("AOD", {}).update({"DrawGraph": 0, "ShowTransStat": 0})
    td = body.setdefault("TD", {})
    td["IC"] = 0
    state = td.setdefault("SVD", {})
    state.update({"IC": 0, "SVWriteFlag": 0, "SV2SchemeFlag": 0, "SVPredictFlag": 0,
                  "ICReadFileName": "disabled-input.sv", "SVWriteFileName": "disabled-output.sv"})
    for name in ("TD", "FD"):
        section = body.setdefault(name, {})
        section["ParamSweep"] = 0
        section["FFT"] = 0
        for sweep in section.get("PSD") or []:
            if isinstance(sweep, dict):
                sweep["On"] = 0


def _normalize_numeric_literals(document: dict) -> list[dict]:
    """Normalize Unicode SI literals only in known electrical number fields.

    The original ANSI native CLI can show a hidden error dialog for Russian SI
    suffixes. Full numeric literals have an unambiguous SI equivalent; symbolic
    expressions, names, unknown model parameters and all source files remain
    untouched. Every changed scalar is recorded for provenance.
    """
    changes = []

    def scalar(container: dict | list, key: str | int, field: str, obj: dict):
        value = container[key]
        if not isinstance(value, str) or value.isascii():
            return
        try:
            number = parse_value(value)
        except SchemeError:
            return
        container[key] = number
        changes.append({"component": obj.get("Name"), "type": obj["Type"],
                        "field": field, "original": value, "si_value": number})

    numeric_fields = {1000: ("R",), 1001: ("C", "IC"), 1002: ("L", "IC"),
                      6101: ("n",), 6600: ("Uon", "Uoff", "Ron", "Roff")}
    waveform = {
        "DC": ("U0", "I0", "Delay", "TFR"),
        "AC": ("U0", "I0", "F", "PHI0", "FD", "NP", "Delay"),
        "PULSE": ("F", "K", "UMAX", "UMIN", "IMAX", "IMIN", "TFR", "Delay"),
        "TRIANG": ("F", "K", "UMAX", "UMIN", "IMAX", "IMIN", "Delay"),
        "USER": ("ScaleT", "ScaleU", "ScaleI", "OffsetU", "OffsetI", "Delay", "PER", "NP")}
    for obj in document["scm"]["Scheme"].get("Objects") or []:
        params = obj.get("Params") or {}
        for key in numeric_fields.get(obj.get("Type"), ()):
            if key in params:
                scalar(params, key, key, obj)
        if obj.get("Type") in (2010, 3010):
            for section, keys in waveform.items():
                part = params.get(section) or {}
                if not isinstance(part, dict):
                    continue
                for key in keys:
                    if key in part:
                        scalar(part, key, section + "." + key, obj)
                if section == "USER":
                    for quantity in ("U", "I"):
                        data = part.get(quantity) or {}
                        if not isinstance(data, dict):
                            continue
                        for axis in ("x", "y"):
                            values = data.get(axis)
                            if isinstance(values, list):
                                for index in range(len(values)):
                                    scalar(values, index, f"USER.{quantity}.{axis}[{index}]", obj)
    return changes


def _dependency_path(parent: Path, reference: Any) -> Path:
    if not isinstance(reference, str) or not reference.strip() or "\x00" in reference:
        raise EngineError("A subcircuit has an invalid FileName reference.")
    if reference.startswith(("\\\\", "//")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", reference):
        raise EngineError("Network/URL subcircuit dependencies are not supported in private native jobs.")
    candidate = Path(reference.replace("\\", os.sep))
    if not candidate.is_absolute():
        candidate = parent / candidate
    try:
        candidate = candidate.resolve(strict=True)
    except OSError as error:
        raise EngineError(f"Subcircuit model is missing: {candidate}") from error
    if str(candidate).startswith(("\\\\", "//")):
        raise EngineError("Network subcircuit dependencies are not supported.")
    if not candidate.is_file() or candidate.suffix.lower() != ".scm":
        raise EngineError(f"Subcircuit model must be an existing .scm file: {candidate}")
    return candidate


def _validate_active_dependencies(root: Path, graph: dict[Path, list[tuple[str, Path]]],
                                  check_cancelled=lambda: None) -> None:
    """A file graph may cycle when a child-only test instance breaks expansion.

    Only the initial context includes underscore-prefixed test elements. The
    same file instantiated below itself is a child context, not another root.
    """
    complete, active = set(), []

    def visit(path, root_context=False):
        check_cancelled()
        context = (path, root_context)
        if context in active:
            cycle = active[active.index(context):] + [context]
            raise EngineError("Recursive active subcircuit dependency cycle: " +
                              " -> ".join(str(item[0]) for item in cycle))
        if context in complete:
            return
        active.append(context)
        for name, child in graph[path]:
            if root_context or not name.startswith("_"):
                visit(child)
        active.pop()
        complete.add(context)

    visit(root, True)


def _prepare_project(source: str | Path, destination: str | Path,
                     cancelled: threading.Event | None = None) -> tuple[Path, list[dict]]:
    original = Path(source).expanduser().resolve(strict=True)
    target = Path(destination).expanduser().absolute()
    if original == target.resolve(strict=False):
        raise EngineError("The batch copy must have a different path from the original schematic.")
    if target.exists() or target.is_symlink():
        raise EngineError(f"Private schematic destination already exists: {target}")
    records: dict[Path, dict] = {}
    total_bytes = 0
    asset_root = target.parent / (target.stem + "_assets_" + uuid4().hex[:8])

    def visit(path: Path) -> None:
        nonlocal total_bytes
        if cancelled is not None and cancelled.is_set():
            raise EngineError("FASTMEAN request was cancelled during project preparation.")
        if path in records:
            return
        if len(records) >= MAX_MODEL_FILES:
            raise EngineError(f"Project exceeds {MAX_MODEL_FILES} SCM model files.")
        total_bytes += path.stat().st_size
        if total_bytes > MAX_PROJECT_BYTES:
            raise EngineError("Project SCM dependencies exceed the 64 MiB limit.")
        before = _sha256(path)
        _, document, encoding = _load(path)
        if _sha256(path) != before:
            raise EngineError(f"Schematic changed while being read: {path}")
        _summarize(document, path, encoding)
        _sanitize_document(document)
        normalizations = _normalize_numeric_literals(document)
        private = target if path == original else asset_root / f"model_{len(records):03d}.scm"
        records[path] = {"document": document, "private_path": private, "source_sha256": before,
                         "numeric_normalizations": normalizations, "dependencies": []}
        for obj in document["scm"]["Scheme"].get("Objects") or []:
            params = obj.get("Params") or {}
            for mapping in _walk(params):
                for key, value in mapping.items():
                    if isinstance(value, str) and value and re.search(r"(?i)(?:file(?:name|path)?|path)$", str(key)):
                        if obj.get("Type") != 7100 or mapping is not params or key != "FileName":
                            raise EngineError(f"Unvalidated external model/data field {obj.get('Name')}.{key}; cannot safely relocate this project.")
            if obj.get("Type") == 7100:
                dependency = _dependency_path(path.parent, params.get("FileName"))
                records[path]["dependencies"].append((str(obj.get("Name", "")), dependency))
                visit(dependency)
                # Absolute private ASCII paths remove dependence on FASTMEAN's
                # ambiguous current-directory changes when loading nested models.
                params["FileName"] = str(records[dependency]["private_path"])

    visit(original)
    _validate_active_dependencies(original, {path: record["dependencies"] for path, record in records.items()},
                                  lambda: _check_cancelled(cancelled))
    # All dependency validation finishes before any native-readable file is made.
    if len(records) > 1:
        asset_root.mkdir(exist_ok=False)
    provenance = []
    try:
        for path, record in records.items():
            private = _write_document(record["document"], record["private_path"], overwrite=False)
            if _sha256(path) != record["source_sha256"]:
                raise EngineError(f"Source model changed during preparation: {path}")
            provenance.append({"source_path": str(path), "source_sha256": record["source_sha256"],
                               "private_path": str(private), "private_sha256": _sha256(private),
                               "numeric_normalizations": record["numeric_normalizations"]})
    except (SchemeError, OSError) as error:
        raise EngineError(f"Could not prepare private schematic copy: {error}") from error
    return target.resolve(), provenance


def prepare_copy(source: str | Path, destination: str | Path) -> Path:
    """Create an isolated SCM and recursively package its native SCM models.

    All original files remain unchanged. Repeated and relative Type-7100 models
    are copied, validated and sanitized; references point to the private models.
    Network, actively recursive, missing or unvalidated external-data references
    fail before native execution. Test-only file cycles are packaged intact.
    Known numeric Unicode SI literals become equivalent SI
    numbers; component IC values and native .define mathematics are preserved.
    """
    return _prepare_project(source, destination)[0]


class _ExpressionParser:
    def __init__(self, tokens: list[str]):
        self.tokens, self.at = tokens, 0

    def take(self, token: str) -> bool:
        if self.at < len(self.tokens) and self.tokens[self.at] == token:
            self.at += 1
            return True
        return False

    def expression(self):
        self.product()
        while self.at < len(self.tokens) and self.tokens[self.at] in {"+", "-"}:
            self.at += 1
            self.product()

    def product(self):
        self.power()
        while self.at < len(self.tokens) and self.tokens[self.at] in {"*", "/"}:
            self.at += 1
            self.power()

    def power(self):
        self.atom()
        if self.take("^"):
            self.power()

    def atom(self):
        if self.take("+") or self.take("-"):
            self.atom()
            return
        if self.take("("):
            self.expression()
            if not self.take(")"):
                raise EngineError("Unbalanced signal-expression parentheses.")
            return
        if self.at >= len(self.tokens):
            raise EngineError("Signal expression ends unexpectedly.")
        token = self.tokens[self.at]
        self.at += 1
        if _IDENTIFIER.fullmatch(token):
            if token.casefold() in _FORBIDDEN_WORDS:
                raise EngineError(f"Command keyword {token!r} is not permitted in a signal expression.")
            if self.take("."):
                if self.at >= len(self.tokens) or not _IDENTIFIER.fullmatch(self.tokens[self.at]):
                    raise EngineError("Invalid element.parameter reference.")
                self.at += 1
            if self.take("("):
                if self.take(")"):
                    raise EngineError("Signal functions require an argument.")
                self.expression()
                while self.take(","):
                    self.expression()
                if not self.take(")"):
                    raise EngineError("Unbalanced signal-function parentheses.")
        else:
            try:
                parse_value(token)
            except (SchemeError, ValueError) as error:
                raise EngineError(f"Invalid signal-expression token {token!r}.") from error


def validate_signal(expression: Any) -> str:
    """Validate a single mathematical expression, not a native script fragment."""
    if not isinstance(expression, str) or not expression or len(expression) > 512:
        raise EngineError("Each signal must be a nonempty expression of at most 512 characters.")
    if not expression.isascii() or any(c in expression for c in '\r\n;\"\'%\\:=[]{}<>!&|'):
        raise EngineError("Signals require ASCII mathematics; quotes, comments and script separators are forbidden.")
    if re.search(r"[A-Za-z0-9_.][ \t]+[A-Za-z0-9_.]", expression):
        raise EngineError("Whitespace cannot concatenate separate identifiers or numbers in a signal.")
    canonical = re.sub(r"[ \t]", "", expression)
    tokens = _TOKEN.findall(canonical)
    if not tokens or "".join(tokens) != canonical:
        raise EngineError("Unsupported character in signal expression.")
    parser = _ExpressionParser(tokens)
    try:
        parser.expression()
    except RecursionError as error:
        raise EngineError("Signal expression is too deeply nested.") from error
    if parser.at != len(tokens):
        raise EngineError("A signal must be one complete mathematical expression.")
    return canonical


def _signals(signals: Any, source: Path, axis: str) -> list[str]:
    if signals is None:
        summary = read_scheme(source)
        ports = summary["ports"]
        output = "out" if "out" in ports else "OUT" if "OUT" in ports else next(iter(ports), None)
        if output is None or not _IDENTIFIER.fullmatch(output):
            raise EngineError("No ASCII output port was found; specify explicit signal expressions.")
        signals = [f"U({output})"]
    if not isinstance(signals, (list, tuple)) or not 1 <= len(signals) <= MAX_SIGNALS:
        raise EngineError(f"signals must contain 1 to {MAX_SIGNALS} mathematical expressions.")
    expressions = [validate_signal(value) for value in signals]
    if len(set(expressions)) != len(expressions):
        raise EngineError("signals must contain distinct expressions; duplicate CSV columns are ambiguous.")
    if axis in expressions:
        raise EngineError(f"Signal {axis!r} duplicates the independent axis column; it is already included in the result.")
    return expressions


def _check_cancelled(cancelled: threading.Event | None) -> None:
    if cancelled is not None and cancelled.is_set():
        raise EngineError("FASTMEAN request cancelled.")


def _validate_requested_axis(rows: list[list[float]], analysis: str, request: dict) -> dict:
    """Reject truncated or stale native output before publishing it as a result.

    The native exporter writes adaptive TD samples, so only coverage is fixed
    there. AC requests specify an entire uniform linear/logarithmic grid. A
    successful process exit and increasing rows alone prove neither contract.
    Relative tolerance accommodates the exporter's decimal rounding at any SI
    scale; a fixed absolute tolerance would accept missing tiny time intervals.
    """
    start = request["fmin"] if analysis == "ac" else 0.0
    end = request["fmax"] if analysis == "ac" else request["stop"]
    if not math.isclose(rows[0][0], start, rel_tol=1e-9, abs_tol=0.0):
        raise EngineError(f"Native {analysis} axis starts at {rows[0][0]:.17g}; requested {start:.17g}.")
    if not math.isclose(rows[-1][0], end, rel_tol=1e-9, abs_tol=0.0):
        raise EngineError(f"Native {analysis} axis ends at {rows[-1][0]:.17g}; requested {end:.17g}. The calculation is incomplete or inconsistent.")
    if analysis == "ac":
        points = request["points"]
        if len(rows) != points:
            raise EngineError(f"Native AC row count {len(rows)} does not match requested {points}.")
        for index, row in enumerate(rows[1:-1], 1):
            fraction = index / (points - 1)
            if request["scale"] == "log":
                # Interpolate logarithms rather than end/start, which can
                # overflow even when both requested endpoints are finite.
                expected = math.exp(math.log(start) * (1 - fraction) + math.log(end) * fraction)
            else:
                expected = start * (1 - fraction) + end * fraction
            if not math.isclose(row[0], expected, rel_tol=1e-9, abs_tol=0.0):
                raise EngineError(f"Native AC frequency at row {index + 1} does not match the requested {request['scale']} grid.")
    return {"requested_start": start, "requested_end": end,
            "observed_start": rows[0][0], "observed_end": rows[-1][0],
            "coverage_verified": True,
            "sampling_verified": request["scale"] if analysis == "ac" else "adaptive",
            "ordering": "strictly_increasing" if analysis == "ac" else "nondecreasing",
            "repeated_timestamp_rows": sum(rows[i][0] == rows[i - 1][0] for i in range(1, len(rows))),
            "native_row_order_preserved": True,
            "simultaneous_samples": "retained in native order; zero-duration intervals contribute no integral"}


def parse_native_table(path: str | Path, columns: int, max_rows: int = MAX_TRANSIENT_STEPS + 1,
                       cancelled: threading.Event | None = None) -> list[list[float]]:
    """Read native whitespace-separated numbers, including its CRCRLF lines."""
    source = Path(path)
    _check_cancelled(cancelled)
    if not source.is_file() or source.stat().st_size == 0:
        raise EngineError("FASTMEAN did not produce a numerical data table.")
    if source.stat().st_size > MAX_TABLE_BYTES:
        raise EngineError("Native data table exceeds the 256 MiB limit.")
    try:
        text = source.read_bytes().decode("ascii")
    except UnicodeError as error:
        raise EngineError("Native numerical table contains non-ASCII data.") from error
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if number % 1024 == 0:
            _check_cancelled(cancelled)
        if not line.strip():
            continue
        values = line.split()
        if len(values) != columns:
            raise EngineError(f"Native table line {number} has {len(values)} columns; expected {columns}.")
        try:
            row = [float(value.replace("D", "E").replace("d", "e")) for value in values]
        except ValueError as error:
            raise EngineError(f"Native table line {number} is not numeric.") from error
        if not all(math.isfinite(value) for value in row):
            raise EngineError(f"Native table line {number} contains non-finite values.")
        rows.append(row)
        if len(rows) > max_rows:
            raise EngineError("Native table exceeds the requested row limit.")
    if not rows:
        raise EngineError("Native table contains no numerical samples.")
    _check_cancelled(cancelled)
    return rows


def _csv_file(path: Path, columns: list[str], rows: list[list[float]],
              cancelled: threading.Event | None = None) -> None:
    with path.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for start in range(0, len(rows), 1024):
            _check_cancelled(cancelled)
            writer.writerows(rows[start:start + 1024])


def _plot_file(path: Path, columns: list[str], rows: list[list[float]], analysis: str,
               sampling: str = "log", cancelled: threading.Event | None = None) -> None:
    # Figure/Agg avoids pyplot's current-figure state and never opens a GUI.
    with _RENDER_LOCK:
        _check_cancelled(cancelled)
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        count = len(columns) - 1
        figure = Figure(figsize=(9, max(3.2, min(12, count * 2.6))), dpi=140, constrained_layout=True)
        FigureCanvasAgg(figure)
        axes = figure.subplots(count, 1, squeeze=False)[:, 0]
        x = [row[0] for row in rows]
        # Preserve all samples in CSV; cap graphical vertices for huge runs.
        stride = max(1, len(rows) // 50000)
        selected = set(range(0, len(rows), stride))
        selected.add(len(rows) - 1)
        # Keep both sides of native switching events even in the overview PNG.
        # Collapsing equal timestamps or subsampling only one side invents a
        # finite-duration ramp and can hide a switching spike.
        for i in range(1, len(rows)):
            if x[i] == x[i - 1]:
                selected.update((i - 1, i))
        selected = sorted(selected)
        for index, axis in enumerate(axes, 1):
            _check_cancelled(cancelled)
            axis.plot([x[i] for i in selected], [rows[i][index] for i in selected], linewidth=1.2)
            if analysis == "ac" and sampling == "log":
                axis.set_xscale("log")
            axis.set_ylabel(columns[index], fontsize=9)
            axis.grid(True, which="both", alpha=.25)
        axes[-1].set_xlabel("Frequency (Hz)" if analysis == "ac" else "Time (s)")
        figure.suptitle("FASTMEAN native data — rendered by MCP", fontsize=12)
        figure.savefig(path, format="png")
        _check_cancelled(cancelled)


class Engine:
    def __init__(self, app_dir: str | Path, output_dir: str | Path, timeout: float = 60):
        self.app_dir = Path(app_dir).expanduser().resolve(strict=True)
        self.executable = self.app_dir / "Fastmean.exe"
        if not self.executable.is_file():
            raise EngineError(f"Installed FASTMEAN executable was not found: {self.executable}")
        self.output_dir = Path(output_dir).expanduser().resolve(strict=False)
        if self.output_dir.is_relative_to(self.app_dir):
            raise EngineError("Native job output directory must be outside the installed application directory.")
        if not str(self.output_dir).isascii():
            raise EngineError("Native batch job directory must have an ASCII path; source SCM filenames may be Unicode.")
        self.timeout = float(timeout)
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 60:
            raise EngineError("Native timeout must be greater than zero and at most 60 seconds.")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._requests: set[threading.Event] = set()
        self._active_processes: set[subprocess.Popen] = set()
        self._cancel_event = threading.Event()

    @property
    def cancel_event(self) -> threading.Event:
        """Shared cancellation notification for separately owned native workers.

        Cancellation is latched for the lifetime of this instance so that an
        early cancellation cannot be lost before a worker thread starts.
        Create a new Engine after cancelling; ordinary completed calls may
        reuse the same instance.
        """
        return self._cancel_event

    def cancel(self) -> None:
        """Cancel this Engine's active/pending calls and stop only owned PIDs.

        The running thread observes its request event, reaps its own process
        and records a cancelled job. Later calls on this instance also remain
        cancelled, including calls whose worker thread has not started yet.
        """
        with self._state_lock:
            self._cancel_event.set()
            for event in self._requests:
                event.set()
            processes = list(self._active_processes)
        for process in processes:
            _stop_owned(process)

    def _begin_request(self) -> threading.Event:
        event = threading.Event()
        with self._state_lock:
            if self._cancel_event.is_set():
                event.set()
            self._requests.add(event)
        return event

    def _end_request(self, event: threading.Event) -> None:
        with self._state_lock:
            self._requests.discard(event)

    def _job(self, source: str | Path, analysis: str,
             cancelled: threading.Event | None = None) -> tuple[Path, dict]:
        original = Path(source).expanduser().resolve(strict=True)
        source_hash = _sha256(original)
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + uuid4().hex[:12] + "_" + analysis
        job = self.output_dir / name
        job.mkdir(exist_ok=False)
        manifest = {"analysis": analysis, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "preparing", "source_path": str(original), "source_sha256": source_hash,
                    "working_dir": str(job), "engine": {"name": "FASTMEAN native CLI",
                    "executable": str(self.executable), "sha256": _sha256(self.executable)},
                    "plot_provenance": "FASTMEAN data rendered by MCP; not a native GUI screenshot"}
        self._manifest(job, manifest)
        try:
            copied, assets = _prepare_project(original, job / "circuit.scm", cancelled)
            if _sha256(original) != source_hash:
                raise EngineError("Source schematic changed while its private copy was being prepared.")
            manifest.update({"private_schematic": str(copied), "private_schematic_sha256": _sha256(copied),
                             "source_models": assets, "status": "prepared",
                             "preparation_policy": {"component_initial_conditions": "preserved",
                             "state_vector_file_io": False, "parameter_sweeps": False,
                             "saved_fft": False, "graph_windows": False,
                             "known_unicode_si_literals": "equivalent numeric SI values; listed per source model",
                             "subcircuit_models": "sanitized private copies"}})
            if analysis == "transient":
                from .topology import TopologyError, check_transient_project
                manifest["transient_preflight"] = {
                    "checked_models": [], "status": "checking"}
                origins = {Path(asset["private_path"]).resolve(): asset["source_path"] for asset in assets}
                failure = None
                try:
                    report = check_transient_project(copied, assets, lambda: _check_cancelled(cancelled))
                except TopologyError as error:
                    failure, report = error, error.report
                report["checked_models"] = [origins[Path(path)] for path in report["checked_models"]]
                for ignored in report["ignored_test_components"]:
                    ignored["model_path"] = origins[Path(ignored["model_path"])]
                manifest["transient_preflight"] = report
                if failure:
                    model = origins[failure.model_path]
                    report.update({"status": "rejected", "model_path": model, "loop": failure.loop})
                    raise EngineError("Native transient preflight found a closed loop of ideal voltage sources and capacitors "
                        f"({', '.join(failure.loop)}). Source model: {model}. "
                        "FASTMEAN does not support this transient topology; model finite source/internal or series resistance "
                        "explicitly if physically appropriate. The source circuit was not modified. "
                        f"This preflight applies only to transient analysis. Artifacts: {job}")
            self._manifest(job, manifest)
        except Exception as error:
            manifest.update({"status": "cancelled" if cancelled is not None and cancelled.is_set() else "failed", "error": str(error)})
            self._manifest(job, manifest)
            raise
        return job, manifest

    @staticmethod
    def _manifest(job: Path, manifest: dict) -> None:
        (job / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _configure_job(self, job: Path, manifest: dict, request: dict) -> None:
        private = job / "circuit.scm"
        _, document, _ = _load(private)
        body = document["scm"]
        if manifest["analysis"] == "ac":
            section = body["FD"]
            section.update({"StartFreq": request["fmin"], "EndFreq": request["fmax"],
                            "NumPts": request["points"], "ScaleX": 2 if request["scale"] == "log" else 1})
            axis = "f"
        else:
            section = body["TD"]
            section["IPNum"] = 1
            section["IP"] = [{"StartTime": 0, "EndTime": request["stop"], "TimeStep": request["step"],
                              "NumPts": int(math.ceil(request["stop"] / request["step"])),
                              "PtsStepFl": 2, "EPS": request["eps"], "GraphType": 1}]
            axis = "t"
        section["ExprRowOffset"] = 0
        section["Expressions"] = [{"plot": i + 1, "x": axis, "y": signal}
                                  for i, signal in enumerate(request["signals"])]
        _write_document(document, private, overwrite=True)
        manifest["private_schematic_sha256"] = _sha256(private)
        manifest["source_models"][0]["private_sha256"] = manifest["private_schematic_sha256"]
        manifest["request"] = request
        self._manifest(job, manifest)

    def _execute(self, job: Path, manifest: dict, script: str,
                  cancelled: threading.Event | None = None) -> None:
        cancelled = cancelled or threading.Event()
        if cancelled.is_set():
            manifest.update({"status": "cancelled", "error": "Request cancelled before native execution."})
            self._manifest(job, manifest)
            raise EngineError(f"FASTMEAN request cancelled. Artifacts: {job}")
        if not script.isascii():
            raise EngineError("Generated native script is not ASCII.")
        script_path = job / "run.txt"
        script_path.write_bytes(script.replace("\n", "\r\n").encode("ascii"))
        command = [str(self.executable), "-s", str(script_path)]
        manifest.update({"status": "running", "script_path": str(script_path), "script": script,
                         "script_sha256": _sha256(script_path), "command": command})
        self._manifest(job, manifest)
        startup = None
        options: dict[str, Any] = {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        started = time.monotonic()
        process = None
        try:
            with self._lock:
                if cancelled.is_set():
                    raise EngineError("FASTMEAN request cancelled while waiting for its native execution slot.")
                process = subprocess.Popen(command, cwd=job, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, startupinfo=startup, **options)
                with self._state_lock:
                    self._active_processes.add(process)
                with _OWNED_LOCK:
                    _OWNED_PROCESSES.add(process)
                manifest["owned_pid"] = process.pid
                self._manifest(job, manifest)
                deadline = time.monotonic() + self.timeout
                while True:
                    if cancelled.is_set():
                        _stop_owned(process)
                        process.communicate(timeout=5)
                        manifest.update({"status": "cancelled", "error": "Request cancelled.", "returncode": process.returncode})
                        self._manifest(job, manifest)
                        raise EngineError(f"FASTMEAN request cancelled; owned PID {process.pid} stopped. Artifacts: {job}")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        _stop_owned(process)
                        process.communicate(timeout=5)
                        manifest.update({"status": "timed_out", "error": f"Native process exceeded {self.timeout:g} seconds.",
                                         "returncode": process.returncode})
                        self._manifest(job, manifest)
                        raise EngineError(f"FASTMEAN timed out; only owned PID {process.pid} was stopped. Artifacts: {job}")
                    try:
                        stdout, stderr = process.communicate(timeout=min(.25, remaining))
                        if cancelled.is_set():
                            raise EngineError("FASTMEAN request cancelled after native process exit.")
                        break
                    except subprocess.TimeoutExpired:
                        continue
            manifest.update({"returncode": process.returncode, "elapsed_seconds": time.monotonic() - started,
                             "stdout": stdout.decode("utf-8", errors="replace")[:8192],
                             "stderr": stderr.decode("utf-8", errors="replace")[:8192]})
            if process.returncode != 0:
                raise EngineError(f"FASTMEAN returned {process.returncode}; inspect job artifacts: {job}")
        except BaseException as error:
            if manifest.get("status") not in {"timed_out", "cancelled"}:
                interrupted = cancelled.is_set() or not isinstance(error, Exception)
                manifest.update({"status": "cancelled" if interrupted else "failed", "error": str(error)})
                self._manifest(job, manifest)
            if not isinstance(error, Exception):
                raise
            if isinstance(error, EngineError):
                raise
            raise EngineError(f"Could not run native FASTMEAN: {error}. Artifacts: {job}") from error
        finally:
            if process is not None:
                _stop_owned(process)
                try:
                    process.communicate(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                with self._state_lock:
                    self._active_processes.discard(process)
                with _OWNED_LOCK:
                    _OWNED_PROCESSES.discard(process)

    def _result(self, job: Path, manifest: dict) -> dict:
        return {"engine": copy.deepcopy(manifest["engine"]), "working_dir": str(job),
                "source_path": manifest["source_path"], "source_sha256": manifest["source_sha256"],
                "script_path": str(job / "run.txt"), "manifest_path": str(job / "manifest.json"),
                "source_models": copy.deepcopy(manifest.get("source_models", [])),
                "preparation_policy": copy.deepcopy(manifest.get("preparation_policy", {}))}

    def _complete_data(self, job: Path, manifest: dict, signals: list[str], axis: str,
                       max_rows: int, expected_rows: int | None = None,
                       cancelled: threading.Event | None = None) -> dict:
        try:
            native = job / "native_data.txt"
            rows = parse_native_table(native, len(signals) + 1, max_rows, cancelled)
            if expected_rows is not None and len(rows) != expected_rows:
                raise EngineError(f"Native AC row count {len(rows)} does not match requested {expected_rows}.")
            if any(rows[i][0] < rows[i-1][0] for i in range(1, len(rows))):
                raise EngineError("Native table axis decreases; native sample order must be preserved.")
            if axis == "f" and any(rows[i][0] == rows[i-1][0] for i in range(1, len(rows))):
                raise EngineError("Native AC table axis is not strictly increasing.")
            if axis == "f" and rows[0][0] <= 0:
                raise EngineError("Native AC data has a non-positive frequency.")
            if axis == "t" and rows[0][0] < 0:
                raise EngineError("Native transient data has a negative time.")
            axis_validation = _validate_requested_axis(rows, manifest["analysis"], manifest["request"])
            columns = [axis, *signals]
            csv_path, plot_path = job / "data.csv", job / "plot.png"
            _csv_file(csv_path, columns, rows, cancelled)
            _plot_file(plot_path, columns, rows, manifest["analysis"],
                       manifest["request"].get("scale", "linear"), cancelled)
            manifest.update({"status": "completed", "row_count": len(rows), "columns": columns,
                             "axis_validation": axis_validation,
                             "native_data_sha256": _sha256(native), "csv_sha256": _sha256(csv_path),
                             "plot_sha256": _sha256(plot_path)})
            self._manifest(job, manifest)
            return {**self._result(job, manifest), "analysis": manifest["analysis"], "data_path": str(native),
                    "csv_path": str(csv_path), "plot_path": str(plot_path), "columns": columns,
                    "row_count": len(rows), "rows": rows,
                    "axis_validation": axis_validation,
                    "plot_provenance": manifest["plot_provenance"]}
        except BaseException as error:
            manifest.update({"status": "cancelled" if (cancelled is not None and cancelled.is_set())
                             or not isinstance(error, Exception) else "failed", "error": str(error)})
            self._manifest(job, manifest)
            if not isinstance(error, Exception):
                raise
            if isinstance(error, EngineError):
                raise EngineError(f"{error} Artifacts: {job}") from error
            raise EngineError(f"Could not validate/render native data: {error}. Artifacts: {job}") from error

    def run_ac(self, path: str | Path, signals: list[str] | None = None,
               fmin: Any = 1, fmax: Any = 1e6, points: int = 101, scale: str = "log") -> dict:
        start, end = parse_value(fmin), parse_value(fmax)
        if start <= 0 or end <= start:
            raise EngineError("AC sweep requires 0 < fmin < fmax.")
        if isinstance(points, bool) or not isinstance(points, int) or not 2 <= points <= MAX_AC_POINTS:
            raise EngineError(f"AC points must be an integer from 2 to {MAX_AC_POINTS}.")
        if scale not in {"log", "linear"}:
            raise EngineError("AC scale must be 'log' or 'linear'.")
        source = Path(path).expanduser().resolve(strict=True)
        expressions = _signals(signals, source, "f")
        cancelled = self._begin_request()
        try:
            job, manifest = self._job(source, "ac", cancelled)
            self._configure_job(job, manifest, {"signals": expressions, "fmin": start, "fmax": end,
                                                "points": points, "scale": scale})
            self._execute(job, manifest, 'open "circuit.scm";\nwrite "native_data.txt" f ' + " ".join(expressions)
                          + f';\nac fmin={start:.17g} fmax={end:.17g} numpts={points};\nexit;\n', cancelled)
            if cancelled.is_set():
                raise EngineError(f"FASTMEAN request cancelled. Artifacts: {job}")
            result = self._complete_data(job, manifest, expressions, "f", MAX_AC_POINTS, points, cancelled)
            result["sampling"] = scale
            return result
        finally:
            self._end_request(cancelled)

    def run_transient(self, path: str | Path, signals: list[str] | None = None,
                      stop: Any = .005, step: Any = 1e-6, eps: Any = 1e-5) -> dict:
        end, dt, accuracy = parse_value(stop), parse_value(step), parse_value(eps)
        if end <= 0 or dt <= 0 or dt > end:
            raise EngineError("Transient analysis requires 0 < step <= stop.")
        if end / dt > MAX_TRANSIENT_STEPS + 1e-6:
            raise EngineError(f"Transient stop/step exceeds {MAX_TRANSIENT_STEPS} steps.")
        if not 0 < accuracy <= .1:
            raise EngineError("Transient eps must satisfy 0 < eps <= 0.1.")
        source = Path(path).expanduser().resolve(strict=True)
        expressions = _signals(signals, source, "t")
        cancelled = self._begin_request()
        try:
            job, manifest = self._job(source, "transient", cancelled)
            self._configure_job(job, manifest, {"signals": expressions, "stop": end, "step": dt, "eps": accuracy})
            self._execute(job, manifest, 'open "circuit.scm";\nwrite "native_data.txt" t ' + " ".join(expressions)
                          + f';\nsim tmax={end:.17g} step={dt:.17g} eps={accuracy:.17g} sv2scheme=no;\nexit;\n', cancelled)
            if cancelled.is_set():
                raise EngineError(f"FASTMEAN request cancelled. Artifacts: {job}")
            return self._complete_data(job, manifest, expressions, "t", MAX_TRANSIENT_STEPS + 1,
                                       cancelled=cancelled)
        finally:
            self._end_request(cancelled)

    def export_netlist(self, path: str | Path) -> dict:
        cancelled = self._begin_request()
        try:
            job, manifest = self._job(path, "netlist", cancelled)
            self._execute(job, manifest, 'open "circuit.scm";\nsave_netlist "netlist.txt";\nexit;\n', cancelled)
            return self._complete_netlist(job, manifest, cancelled)
        finally:
            self._end_request(cancelled)

    def _complete_netlist(self, job: Path, manifest: dict,
                          cancelled: threading.Event | None = None) -> dict:
        netlist = job / "netlist.txt"
        try:
            _check_cancelled(cancelled)
            if not netlist.is_file() or not netlist.stat().st_size:
                raise EngineError("Native FASTMEAN did not produce a netlist.")
            raw = netlist.read_bytes()
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeError:
                text = raw.decode("cp1251", errors="strict")
            _check_cancelled(cancelled)
            manifest.update({"status": "completed", "netlist_sha256": _sha256(netlist)})
            self._manifest(job, manifest)
            return {**self._result(job, manifest), "path": str(netlist), "text": text}
        except BaseException as error:
            manifest.update({"status": "cancelled" if (cancelled is not None and cancelled.is_set())
                             or not isinstance(error, Exception) else "failed", "error": str(error)})
            self._manifest(job, manifest)
            if not isinstance(error, Exception):
                raise
            if isinstance(error, EngineError):
                raise
            raise EngineError(f"Could not read native netlist: {error}. Artifacts: {job}") from error
