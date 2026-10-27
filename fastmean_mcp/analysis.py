"""Typed native analysis commands and explicit postprocessing of native data.

No caller can supply a script or an output filename. Native jobs retain the
source/provenance protections of Engine; only mathematical definitions and
qualified electrical parameter names enter the generated command stream.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import re
import shutil

from .engine import (EngineError, MAX_MODEL_FILES, MAX_PROJECT_BYTES,
                     MAX_SIGNALS, MAX_TRANSIENT_STEPS, _FORBIDDEN_WORDS,
                     _RENDER_LOCK, _check_cancelled, _csv_file, _sha256, _signals,
                     parse_native_table, validate_signal)
from .schematic import SchemeError, _load, _write_document, parse_value

MAX_DEFINITIONS = 64
MAX_OVERRIDES = 64
MAX_SWEEP_VALUES = 32
MAX_SPECTRUM_POINTS = 262144
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_TARGET = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,15}$")
_AXES = frozenset({"t", "f", "pi", "e", "i", "j"})


def number(value, label):
    try:
        return parse_value(value)
    except (SchemeError, ValueError, TypeError) as error:
        raise EngineError(f"{label} must be a finite number or SI literal.") from error


def parameter_target(value):
    if (not isinstance(value, str) or len(value) > 512 or not _TARGET.fullmatch(value)
            or any(part.casefold() in _FORBIDDEN_WORDS for part in value.split("."))):
        raise EngineError("An override target must be an ASCII variable or qualified component.parameter name.")
    return value


def math_expression(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{number(value, 'Expression'):.17g}"
    if not isinstance(value, str):
        raise EngineError("An expression must be mathematical text or a finite number.")
    if not value.isascii():
        return f"{number(value, 'Expression'):.17g}"
    return validate_signal(value)


def command_prelude(definitions=None, overrides=None):
    """Return generated define/set commands and their validated audit record."""
    if definitions is None:
        definitions = []
    if not isinstance(definitions, list) or len(definitions) > MAX_DEFINITIONS:
        raise EngineError(f"definitions must be a list with at most {MAX_DEFINITIONS} entries.")
    cleaned, names, commands = [], set(), []
    for entry in definitions:
        if (not isinstance(entry, dict) or set(entry) - {"name", "arguments", "expression"}
                or not {"name", "expression"} <= set(entry)):
            raise EngineError("Each definition needs name, expression and optional arguments.")
        name = entry["name"]
        if (not isinstance(name, str) or not _NAME.fullmatch(name)
                or name.casefold() in _FORBIDDEN_WORDS | _AXES or name in names):
            raise EngineError("Definition names must be distinct ASCII identifiers, excluding commands and axis constants.")
        names.add(name)
        expression = math_expression(entry["expression"])
        item = {"name": name, "expression": expression}
        signature = name
        if "arguments" in entry:
            arguments = entry["arguments"]
            if (not isinstance(arguments, list) or len(arguments) > 16
                    or any(not isinstance(arg, str) or not _NAME.fullmatch(arg)
                           or arg.casefold() in _FORBIDDEN_WORDS for arg in arguments)
                    or len(set(arguments)) != len(arguments)):
                raise EngineError("Function arguments must be up to 16 distinct ASCII identifiers.")
            signature += "(" + ",".join(arguments) + ")"
            item["arguments"] = list(arguments)
        cleaned.append(item)
        commands.append(f"define {signature}={expression};\n")
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict) or len(overrides) > MAX_OVERRIDES:
        raise EngineError(f"overrides must map up to {MAX_OVERRIDES} electrical targets to expressions.")
    assignments = {parameter_target(target): math_expression(value) for target, value in overrides.items()}
    for target, expression in assignments.items():
        commands.append(f"set {target}={expression};\n")
    return "".join(commands), {"definitions": cleaned, "overrides": assignments}


def validate_initial_conditions(value):
    if isinstance(value, str) and value in {"scheme", "zero", "dc"}:
        return value
    if not isinstance(value, dict) or not value or len(value) > 200:
        raise EngineError("initial_conditions must be scheme, zero, dc, or a component-to-IC numeric mapping.")
    return {parameter_target(name): number(item, "Initial condition") for name, item in value.items()}


MAX_ANALYSIS_DEPTH = 64
MAX_EXPANDED_OBJECTS = 100000


def _private_model_path(current, reference, base):
    if not isinstance(reference, str) or not reference or "\x00" in reference:
        raise EngineError("A private subcircuit has an invalid model reference.")
    child = Path(reference)
    if not child.is_absolute():
        child = current.parent / child
    child = child.resolve(strict=False)
    if not child.is_relative_to(base):
        raise EngineError("An analysis model escaped its private project.")
    return child


def _document_byte_estimate(document, cancelled=None):
    """Count native YAML bytes without retaining another serialized document.

    This uses the same serializer and CRLF convention as _write_document.
    Its stream checks cancellation and stops at the project byte limit.
    """
    import yaml
    from .schematic import _IndentedDumper

    class Counter:
        size = 0

        def write(self, text):
            _check_cancelled(cancelled)
            self.size += len(text.encode("utf-8")) + text.count("\n")
            if self.size > MAX_PROJECT_BYTES:
                raise EngineError(f"Private analysis project exceeds {MAX_PROJECT_BYTES} bytes.")

    counter = Counter()
    yaml.dump(document, counter, Dumper=_IndentedDumper, allow_unicode=True,
              sort_keys=False, default_flow_style=False, width=120)
    return counter.size


def _check_clone_budget(private, child, clone, documents, manifest, cancelled=None):
    """Bound original and pending private models before deepcopy or file writes."""
    _check_cancelled(cancelled)
    assets = {Path(item["private_path"]).resolve(strict=False)
              for item in manifest["source_models"]}
    if len(assets) + 1 > MAX_MODEL_FILES:
        raise EngineError(f"Private analysis project exceeds {MAX_MODEL_FILES} SCM model files.")
    sizes = {}
    total = 0
    for path in assets:
        _check_cancelled(cancelled)
        if not path.is_relative_to(private.parent):
            raise EngineError("An analysis model escaped its private project.")
        if path in documents:
            size = _document_byte_estimate(documents[path], cancelled)
        else:
            size = path.stat().st_size
        sizes[path] = size
        total += size
        if total > MAX_PROJECT_BYTES:
            raise EngineError(f"Private analysis project exceeds {MAX_PROJECT_BYTES} bytes.")
    # Also reserve the new parent's longer FileName scalar, including possible
    # YAML quoting, before it is changed in memory. Conservatively reserve the
    # entire new path rather than subtracting the old reference's length.
    clone_size = sizes.get(child)
    if clone_size is None:
        clone_size = _document_byte_estimate(documents[child], cancelled)
    total += clone_size + len(str(clone).encode("utf-8")) + 16
    if total > MAX_PROJECT_BYTES:
        raise EngineError(f"Private analysis project exceeds {MAX_PROJECT_BYTES} bytes after instance cloning.")
    return clone_size


def _component(private, qualified, documents, manifest, *, cancelled=None):
    """Resolve only already-packaged SCM dependencies, never caller paths."""
    parts = parameter_target(qualified).split(".")
    if len(parts)-1 > MAX_ANALYSIS_DEPTH:
        raise EngineError(f"Analysis hierarchy exceeds {MAX_ANALYSIS_DEPTH} instance levels.")
    current = private
    for index, name in enumerate(parts):
        _check_cancelled(cancelled)
        if current not in documents:
            _, document, _ = _load(current)
            documents[current] = document
        objects = documents[current]["scm"]["Scheme"].get("Objects") or []
        matches = [obj for obj in objects if obj.get("Name") == name]
        if len(matches) != 1:
            raise EngineError(f"Initial-condition/source target {qualified!r} is not a unique component.")
        obj = matches[0]
        if index == len(parts)-1:
            return current, obj
        if obj.get("Type") != 7100:
            raise EngineError(f"{name!r} is not a subcircuit instance.")
        child = _private_model_path(current, obj["Params"]["FileName"], private.parent)
        clones = manifest.setdefault("instance_model_clones", [])
        if str(child) not in {entry["private_path"] for entry in clones}:
            # A model definition may serve many instances. Clone this branch
            # before changing an instance-specific IC or DC-source bias.
            if child not in documents:
                _, documents[child], _ = _load(child)
            folder = private.parent / "instance_models"
            clone = folder / f"instance_{len(clones):03d}.scm"
            estimated_bytes = _check_clone_budget(private, child, clone, documents, manifest, cancelled)
            _check_cancelled(cancelled)
            copied = copy.deepcopy(documents[child])
            _check_cancelled(cancelled)
            folder.mkdir(exist_ok=True)
            documents[clone] = copied
            origin = next(asset for asset in manifest["source_models"] if Path(asset["private_path"]) == child)
            record = {**origin, "private_path": str(clone), "instance_path": ".".join(parts[:index+1]),
                      "private_instance_clone": True, "private_byte_estimate": estimated_bytes}
            clones.append(record)
            manifest["source_models"].append(record)
            obj["Params"]["FileName"] = str(clone)
            child = clone
        current = child
    raise EngineError("Empty component path.")


def _active_components(private, documents, prefix="", *, cancelled=None):
    """Iterate active instances with bounded expansion and no Python recursion."""
    base = private.parent

    def frame(path, name, depth):
        _check_cancelled(cancelled)
        if depth > MAX_ANALYSIS_DEPTH:
            raise EngineError(f"Analysis hierarchy exceeds {MAX_ANALYSIS_DEPTH} instance levels.")
        if path not in documents:
            _, documents[path], _ = _load(path)
        objects = documents[path]["scm"]["Scheme"].get("Objects") or []
        return path, name, depth, iter(objects)

    stack = [frame(private, prefix, 0)]
    # Root-only test components may refer to the root definition once. Below
    # the root those underscore-prefixed objects are inactive, just as native.
    active = {(private, not bool(prefix))}
    expanded = 0
    while stack:
        _check_cancelled(cancelled)
        path, context, depth, objects = stack[-1]
        try:
            obj = next(objects)
        except StopIteration:
            stack.pop()
            active.remove((path, not bool(context)))
            continue
        name = str(obj.get("Name", ""))
        if context and name.startswith("_"):
            continue
        expanded += 1
        if expanded > MAX_EXPANDED_OBJECTS:
            raise EngineError(f"Analysis hierarchy exceeds {MAX_EXPANDED_OBJECTS} expanded objects.")
        qualified = context + name
        yield path, obj, qualified
        if obj.get("Type") == 7100:
            child = _private_model_path(path, obj["Params"]["FileName"], base)
            key = child, False
            if key in active:
                raise EngineError("Recursive active subcircuit dependency cycle during analysis expansion.")
            stack.append(frame(child, qualified+".", depth+1))
            active.add(key)


def _save_private_changes(engine, job, manifest, documents):
    for path, document in documents.items():
        _write_document(document, path, overwrite=path.exists())
    for item in manifest["source_models"]:
        item["private_sha256"] = _sha256(Path(item["private_path"]))
    manifest["private_schematic_sha256"] = _sha256(job / "circuit.scm")
    engine._manifest(job, manifest)


def configure_initial_conditions(engine, job, manifest, value):
    private = job / "circuit.scm"
    _, document, _ = _load(private)
    documents = {private: document}
    mode = {"scheme": 0, "zero": 1, "dc": 2}.get(value, 0) if isinstance(value, str) else 0
    document["scm"]["TD"]["IC"] = mode
    document["scm"]["TD"]["SVD"]["IC"] = mode
    if isinstance(value, dict):
        for name, initial in value.items():
            _, obj = _component(private, name, documents, manifest, cancelled=engine.cancel_event)
            params = obj.get("Params") or {}
            if "IC" not in params:
                raise EngineError(f"Component {name!r} has no supported native IC scalar.")
            params["IC"] = initial
    manifest["preparation_policy"]["requested_initial_conditions"] = value
    _save_private_changes(engine, job, manifest, documents)


def _failed(engine, job, manifest, error):
    status = manifest.get("status")
    if status not in {"timed_out", "cancelled"}:
        status = "cancelled" if engine.cancel_event.is_set() else "failed"
    manifest.update({"status": status, "error": str(error)})
    engine._manifest(job, manifest)


def run_dc(engine, path, signals=None, *, definitions=None, overrides=None, source_values=None):
    commands, directives = command_prelude(definitions, overrides)
    if any(target.rsplit(".", 1)[-1].casefold() in {"tfr", "delay"}
           for target in (overrides or {})):
        raise EngineError("DC overrides cannot reintroduce source ramps or delays; use source_values for DC bias.")
    if source_values is None:
        source_values = {}
    if not isinstance(source_values, dict) or len(source_values) > 200:
        raise EngineError("source_values must map component paths to numeric DC values.")
    source_values = {parameter_target(key): number(value, "DC source value") for key, value in source_values.items()}
    source = Path(path).expanduser().resolve(strict=True)
    expressions = _signals(signals, source, "t")
    cancelled = engine._begin_request()
    job = manifest = None
    try:
        job, manifest = engine._job(source, "dc", cancelled)
        engine._configure_job(job, manifest, {"signals": expressions, "stop": 0., "step": 1e-9,
            "eps": 1e-5, "source_values": source_values, **directives})
        configure_initial_conditions(engine, job, manifest, "dc")
        private = job / "circuit.scm"
        documents = {}
        for qualified, value in source_values.items():
            _, obj = _component(private, qualified, documents, manifest, cancelled=engine.cancel_event)
            if obj.get("Type") not in {2010, 3010}:
                raise EngineError(f"DC source target {qualified!r} must be an independent U/I source.")
            params = obj["Params"]
            quantity = "U0" if obj["Type"] == 2010 else "I0"
            params["ST"] = 1
            params.setdefault("DC", {})[quantity] = value
        changes = []
        for model, obj, qualified in _active_components(private, documents, cancelled=engine.cancel_event):
            if obj.get("Type") not in {2010, 3010}:
                continue
            params = obj.get("Params") or {}
            if params.get("ST") != 1:
                raise EngineError(f"DC requires an explicit source_values entry for non-DC source {qualified!r}.")
            dc = params.setdefault("DC", {})
            origin = next(asset["source_path"] for asset in manifest["source_models"] if Path(asset["private_path"]) == model)
            changes.append({"source_model": origin, "component": qualified,
                "original_delay": dc.get("Delay"), "original_rise_time": dc.get("TFR"),
                "private_delay": 0, "private_rise_time": 0})
            dc.update({"Delay": 0, "TFR": 0})
        manifest["dc_method"] = "Native DC operating-point initialization (SVD.IC=2), zero-duration sim; DC-source ramps disabled in private copy"
        manifest["dc_source_changes"] = changes
        _save_private_changes(engine, job, manifest, documents)
        engine._execute(job, manifest, 'open "circuit.scm";\n' + commands
            + 'write "native_data.txt" t ' + " ".join(expressions)
            + ';\nsim tmax=0 step=1n eps=10u sv2scheme=no;\nexit;\n', cancelled)
        rows = parse_native_table(job / "native_data.txt", len(expressions)+1, 1, cancelled)
        if len(rows) != 1 or rows[0][0] != 0:
            raise EngineError("Native DC initialization did not return exactly one zero-time row.")
        csv_path = job / "data.csv"
        _csv_file(csv_path, ["t", *expressions], rows, cancelled)
        manifest.update({"status": "completed", "row_count": 1, "columns": ["t", *expressions],
            "native_data_sha256": _sha256(job / "native_data.txt"), "csv_sha256": _sha256(csv_path)})
        engine._manifest(job, manifest)
        return {**engine._result(job, manifest), "analysis": "dc", "values": dict(zip(expressions, rows[0][1:])),
            "columns": ["t", *expressions], "rows": rows, "row_count": 1,
            "data_path": str(job / "native_data.txt"), "csv_path": str(csv_path),
            "dc_method": manifest["dc_method"], "dc_source_changes": changes}
    except BaseException as error:
        if job is not None:
            _failed(engine, job, manifest, error)
        raise
    finally:
        engine._end_request(cancelled)


def _window(value, stop):
    if value is None:
        return [0., stop]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise EngineError("window must contain [start_seconds, end_seconds].")
    start, end = [number(item, "Window endpoint") for item in value]
    if not 0 <= start < end <= stop:
        raise EngineError("window must satisfy 0 <= start < end <= stop.")
    return [start, end]


def _derived_manifest(engine, path, kind, request):
    job, manifest = engine._job(path, kind, engine.cancel_event)
    manifest["request"] = request
    engine._manifest(job, manifest)
    return job, manifest


def _derived_result(engine, job, manifest):
    result = engine._result(job, manifest)
    # Orchestration/postprocessing parents have native child jobs, rather than
    # their own executable script. Do not return a nonexistent run.txt path.
    result.pop("script_path", None)
    return result


def _retain_native_files(result, destination, prefix):
    retained = {}
    for field,suffix in (("manifest_path","manifest.json"),("script_path","run.txt"),("data_path","native.txt")):
        source = Path(result[field]) if field in result else None
        if source is not None and source.is_file():
            target = destination/f"{prefix}_{suffix}"
            shutil.copyfile(source,target)
            retained[field] = str(target)
    return retained


def run_parameter_sweep(engine, path, target, values, analysis="transient", settings=None,
                        signals=None, *, definitions=None, overrides=None):
    target = parameter_target(target)
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_SWEEP_VALUES:
        raise EngineError(f"values must contain 1..{MAX_SWEEP_VALUES} numeric sweep values.")
    values = [number(value, "Sweep value") for value in values]
    if len(set(values)) != len(values):
        raise EngineError("Sweep values must be distinct.")
    allowed = {"ac": {"fmin", "fmax", "points", "scale"},
        "transient": {"stop", "step", "eps", "sample_after", "initial_conditions", "state2scheme", "fft"},
        "dc": {"source_values"}}
    if analysis not in allowed:
        raise EngineError("Sweep analysis must be ac, transient or dc.")
    if settings is None:
        settings = {}
    if not isinstance(settings, dict) or set(settings)-allowed[analysis]:
        raise EngineError(f"Unsupported {analysis} sweep settings.")
    postprocess = (analysis == "transient" and signals is not None and
        any(isinstance(value,str) and re.search(r"(?i)\b(?:last|tre|tim|tmag|tph|FFT)\s*\(", value) for value in signals))
    if analysis == "transient" and "fft" in settings and not postprocess:
        raise EngineError("Sweep settings.fft requires explicit FFT(...) signals.")
    if postprocess and (settings.get("state2scheme",False) or number(settings.get("sample_after",0),"sample_after") != 0):
        raise EngineError("Native summary/FFT sweeps do not support state2scheme or write-after filtering; choose the averaging/FFT window explicitly.")
    command_prelude(definitions, overrides)
    if analysis == "transient":
        end, step = number(settings.get("stop", .005), "Stop"), number(settings.get("step", 1e-6), "Step")
        if step <= 0 or end/step*len(values) > MAX_TRANSIENT_STEPS:
            raise EngineError("Combined sweep exceeds the one-million requested-step budget.")
    job, manifest = _derived_manifest(engine, path, "sweep", {"target": target, "values": values,
        "analysis": analysis, "settings": settings})
    snapshot = job / "circuit.scm"
    results, summary = [], []
    try:
        folder = job / "curves"
        folder.mkdir()
        for index, value in enumerate(values):
            _check_cancelled(engine.cancel_event)
            assignments = {**(overrides or {}), target: value}
            call = {"ac": engine.run_ac, "transient": engine.run_transient, "dc": engine.run_dc}[analysis]
            if postprocess:
                summary_settings = {key:value for key,value in settings.items() if key not in {"sample_after","state2scheme"}}
                result = run_summary(engine,snapshot,signals,definitions=definitions,overrides=assignments,**summary_settings)
            else:
                result = call(snapshot, signals=signals, definitions=definitions, overrides=assignments, **settings)
            exported = folder / f"curve_{index:03d}.csv"
            shutil.copyfile(result["csv_path"], exported)
            entry = {"value": value, "csv_path": str(exported), "columns": result["columns"],
                "row_count": result["row_count"], "native_working_dir": result["working_dir"],
                "native_manifest_sha256": _sha256(Path(result["manifest_path"])),
                "source_snapshot_path": str(snapshot), "source_snapshot_sha256": _sha256(snapshot),
                "last_row": result["rows"][-1]}
            entry.update(_retain_native_files(result,folder,f"curve_{index:03d}"))
            if "plot_path" in result:
                plot = folder / f"curve_{index:03d}.png"
                shutil.copyfile(result["plot_path"], plot)
                entry["plot_path"] = str(plot)
            results.append(entry)
            summary.append([value, *result["rows"][-1][1:]])
            manifest["completed_curves"] = results
            engine._manifest(job, manifest)
        columns = [target, *result["columns"][1:]]
        csv_path = job / "sweep_summary.csv"
        _csv_file(csv_path, columns, summary, engine.cancel_event)
        manifest.update({"status": "completed", "row_count": len(summary), "columns": columns,
            "reduction": "Last native exported row of each independently calculated curve",
            "csv_sha256": _sha256(csv_path)})
        engine._manifest(job, manifest)
        return {**_derived_result(engine, job, manifest), "analysis": "sweep", "target": target,
            "values": values, "curves": results, "columns": columns, "rows": summary,
            "row_count": len(summary), "csv_path": str(csv_path), "reduction": manifest["reduction"],
            "origin": "Independent native FASTMEAN calculations; parameter assigned by documented set command"}
    except BaseException as error:
        _failed(engine, job, manifest, error)
        raise


def spectrum_from_rows(rows, window, points, window_function):
    """One-sided calibrated FFT/PSD of uniform interpolation of native TD."""
    import numpy as np
    functions = {"rectangular": np.ones, "hann": np.hanning, "hamming": np.hamming,
                 "bartlett": np.bartlett, "blackman": np.blackman}
    if (isinstance(points, bool) or not isinstance(points, int) or not 16 <= points <= MAX_SPECTRUM_POINTS
            or points & (points-1)):
        raise EngineError(f"Spectrum points must be a power of two from 16 to {MAX_SPECTRUM_POINTS}.")
    if window_function not in functions:
        raise EngineError("window_function must be rectangular, hann, hamming, bartlett or blackman.")
    data = np.asarray(rows, dtype=float)
    if (data.ndim != 2 or data.shape[1] != 2 or len(data) < 2
            or not np.isfinite(data).all() or np.any(np.diff(data[:, 0]) < 0)):
        raise EngineError("Spectrum requires finite native [time,signal] rows in nondecreasing time order.")
    start, end = window
    if start < data[0, 0] or end > data[-1, 0] or end <= start:
        raise EngineError("Native TD data does not cover the requested spectral window.")
    # Preserve BOTH limits of native discontinuities. Interpolation immediately
    # before an event ends at its first (left-limit) sample; immediately after
    # it starts at the last (right-limit) sample. Collapsing the left limit
    # would invent a ramp across the entire preceding interval (e.g. PWM).
    times, first = np.unique(data[:, 0], return_index=True)
    last = np.r_[first[1:]-1, len(data)-1]
    sample_times = np.linspace(start, end, points, endpoint=False)
    preceding = np.searchsorted(times, sample_times, side="right")-1
    following = np.minimum(preceding+1, len(times)-1)
    spans = times[following]-times[preceding]
    fraction = np.divide(sample_times-times[preceding], spans,
                         out=np.zeros(points), where=spans != 0)
    samples = data[last[preceding], 1]*(1-fraction)+data[first[following], 1]*fraction
    weights = functions[window_function](points)
    transformed = np.fft.rfft(samples*weights)
    multiplier = np.full(len(transformed), 2.)
    multiplier[0] = multiplier[-1] = 1.
    calibrated = transformed/weights.sum()*multiplier
    rate = points/(end-start)
    psd = np.abs(transformed)**2/(rate*np.sum(weights**2))*multiplier
    frequency = np.fft.rfftfreq(points, 1/rate)
    output = np.column_stack((frequency, np.abs(calibrated), np.angle(calibrated, deg=True),
                              calibrated.real, calibrated.imag, psd)).tolist()
    return output, {"sample_rate_hz": rate, "frequency_resolution_hz": 1/(end-start),
        "nyquist_hz": rate/2, "uniform_points": points, "window_function": window_function,
        "interpolation": "Piecewise linear between native event limits; exact event uses right limit; no artificial pre-event ramp",
        "amplitude": "One-sided peak amplitude; DC and Nyquist are not doubled; coherent-gain corrected",
        "phase_reference": "Cosine reference at the selected window start",
        "psd": "One-sided signal-unit squared per Hz; window-energy normalized",
        "native_repeated_timestamp_rows": int(len(data)-len(times)),
        "caution": "Interpolation adds no native bandwidth; select a native step fine enough for the highest frequency"}


def run_spectrum(engine, path, signal, window=None, stop=.01, step=1e-6, eps=1e-5,
                 points=4096, window_function="hann", *, definitions=None, overrides=None,
                 initial_conditions="scheme"):
    signal = validate_signal(signal)
    end = number(stop, "Stop")
    interval = _window(window, end)
    # Validate FFT controls before doing any native work.
    spectrum_from_rows([[interval[0], 0.], [interval[1], 0.]], interval, points, window_function)
    command_prelude(definitions, overrides)
    job, manifest = _derived_manifest(engine, path, "spectrum", {"signal": signal, "window": interval,
        "stop": end, "step": step, "eps": eps, "points": points, "window_function": window_function})
    try:
        native = engine.run_transient(job/"circuit.scm", [signal], stop=end, step=step, eps=eps,
            definitions=definitions, overrides=overrides, initial_conditions=initial_conditions)
        _check_cancelled(engine.cancel_event)
        rows, sampling = spectrum_from_rows(native["rows"], interval, points, window_function)
        columns = ["f", "amplitude_peak", "phase_degrees", "real", "imaginary", "psd"]
        csv_path, plot_path = job / "spectrum.csv", job / "spectrum.png"
        _csv_file(csv_path, columns, rows, engine.cancel_event)
        retained = job / "native_transient.csv"
        shutil.copyfile(native["csv_path"], retained)
        native_files = _retain_native_files(native,job,"transient")
        with _RENDER_LOCK:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            figure = Figure(figsize=(10, 6), dpi=140, constrained_layout=True)
            FigureCanvasAgg(figure)
            axes = figure.subplots(2, 1)
            for axis, column, label in zip(axes, (1, 5), ("Peak amplitude", "PSD [signal unit²/Hz]")):
                axis.plot([r[0] for r in rows], [r[column] for r in rows])
                axis.set_ylabel(label)
                axis.grid(True, alpha=.25)
            axes[-1].set_xlabel("Frequency [Hz]")
            figure.suptitle(f"{signal}: NumPy spectrum of native FASTMEAN TD")
            figure.savefig(plot_path)
        origin = "NumPy rFFT/PSD after uniform interpolation of native FASTMEAN transient samples; Matplotlib chart; not native FFT"
        manifest.update({"status": "completed", "columns": columns, "row_count": len(rows),
            "sampling": sampling, "origin": origin, "native_transient_manifest": native["manifest_path"],
            "native_transient_csv_sha256": _sha256(retained), "csv_sha256": _sha256(csv_path),
            "plot_sha256": _sha256(plot_path)})
        engine._manifest(job, manifest)
        return {**_derived_result(engine, job, manifest), "analysis": "spectrum", "origin": origin,
            "columns": columns, "rows": rows, "row_count": len(rows), "sampling": sampling,
            "csv_path": str(csv_path), "plot_path": str(plot_path),
            "native_transient_path": str(retained),
            **{"native_transient_"+key:value for key,value in native_files.items()}}
    except BaseException as error:
        _failed(engine, job, manifest, error)
        raise


def run_harmonics(engine, path, signal, frequencies, window, stop=.01, step=1e-6, eps=1e-5,
                  *, definitions=None, overrides=None):
    signal = validate_signal(signal)
    if not isinstance(frequencies, list) or not 1 <= len(frequencies) <= MAX_SIGNALS//4:
        raise EngineError(f"frequencies must contain 1..{MAX_SIGNALS//4} positive numeric frequencies.")
    frequencies = [number(value, "Harmonic frequency") for value in frequencies]
    if any(value <= 0 for value in frequencies) or len(set(frequencies)) != len(frequencies):
        raise EngineError("Harmonic frequencies must be positive and distinct.")
    end, dt, accuracy = number(stop, "Stop"), number(step, "Step"), number(eps, "EPS")
    if not 0 < dt <= end or end/dt > MAX_TRANSIENT_STEPS or not 0 < accuracy <= .1:
        raise EngineError("Harmonics require 0 < step <= stop, at most one million steps, and 0 < eps <= .1.")
    interval = _window(window, end)
    expressions = [f"{function}({signal},{frequency:.17g},{interval[0]:.17g},{interval[1]:.17g})"
        for frequency in frequencies for function in ("tre", "tim", "tmag", "tph")]
    source = Path(path).expanduser().resolve(strict=True)
    expressions = _signals(expressions, source, "t")
    commands, directives = command_prelude(definitions, overrides)
    cancelled = engine._begin_request()
    job = manifest = None
    try:
        # Run the same topology preflight as every other native transient.
        job, manifest = engine._job(source, "transient", cancelled)
        manifest["analysis"] = "harmonics"
        engine._configure_job(job, manifest, {"signals": expressions, "stop": end, "step": dt,
            "eps": accuracy, "window": interval, "frequencies": frequencies, **directives})
        # Native harmonic expressions export one post-analysis row at t=0.
        # A separate ordinary writer proves full simulation coverage instead
        # of pretending that single row is a complete transient time series.
        engine._execute(job, manifest, 'open "circuit.scm";\n' + commands
            + 'write "native_transient.txt" t ' + signal + ';\n'
            + 'write "native_data.txt" t ' + " ".join(expressions)
            + f';\nsim tmax={end:.17g} step={dt:.17g} eps={accuracy:.17g} sv2scheme=no;\nexit;\n', cancelled)
        time_rows = parse_native_table(job / "native_transient.txt", 2, MAX_TRANSIENT_STEPS+1, cancelled)
        from .engine import _validate_requested_axis
        coverage = _validate_requested_axis(time_rows, "transient", manifest["request"])
        raw = parse_native_table(job / "native_data.txt", 1+len(expressions), 1, cancelled)
        if len(raw) != 1 or raw[0][0] != 0:
            raise EngineError("Native harmonic export must contain one post-analysis row at t=0.")
        values = raw[0][1:]
        rows = [[frequency, *values[4*index:4*index+4]] for index,frequency in enumerate(frequencies)]
        columns = ["f", "real", "imaginary", "magnitude", "phase_degrees"]
        csv_path, native_csv = job / "harmonics.csv", job / "native_transient.csv"
        _csv_file(csv_path, columns, rows, cancelled)
        _csv_file(native_csv, ["t",signal], time_rows, cancelled)
        plot_path = job / "harmonics.png"
        with _RENDER_LOCK:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            figure = Figure(figsize=(9,6), dpi=140, constrained_layout=True)
            FigureCanvasAgg(figure)
            axes = figure.subplots(2,1)
            for axis,column,label in zip(axes,(3,4),("Magnitude (native tmag)","Phase [degrees] (native tph)")):
                axis.plot(frequencies,[row[column] for row in rows],marker="o")
                axis.set_ylabel(label)
                axis.grid(True,alpha=.25)
            axes[-1].set_xlabel("Frequency [Hz]")
            figure.suptitle("Native FASTMEAN harmonic extraction")
            figure.savefig(plot_path)
        origin = "Native FASTMEAN tre/tim/tmag/tph functions; Matplotlib chart of native exported coefficients"
        manifest.update({"status":"completed", "columns":columns, "row_count":len(rows),
            "origin":origin, "axis_validation":coverage, "transient_row_count":len(time_rows),
            "native_data_sha256":_sha256(job/"native_data.txt"), "csv_sha256":_sha256(csv_path)})
        engine._manifest(job,manifest)
        return {**engine._result(job,manifest), "analysis":"harmonics", "origin":origin,
            "columns":columns, "rows":rows, "row_count":len(rows), "csv_path":str(csv_path),
            "plot_path":str(plot_path), "data_path":str(job/"native_data.txt"),
            "native_transient_path":str(native_csv), "axis_validation":coverage,
            "harmonics":[dict(zip(("frequency_hz","real","imaginary","magnitude","phase_degrees"),row)) for row in rows],
            "harmonic_window_s":interval, "transient_row_count":len(time_rows)}
    except BaseException as error:
        if job is not None:
            _failed(engine,job,manifest,error)
        raise
    finally:
        engine._end_request(cancelled)


def run_summary(engine, path, signals, stop=.01, step=1e-6, eps=1e-5,
                definitions=None, overrides=None, fft=None, initial_conditions="scheme"):
    """Evaluate native final statistics or native FFT, with independent coverage.

    Ordinary expressions become native last(expression), so RMS/AVG/MAX and
    instantaneous signals mean final values. FFT expressions must be requested
    together in their own frequency-domain mode; no mixed-axis table is made.
    """
    source = Path(path).expanduser().resolve(strict=True)
    originals = _signals(signals, source, "t")
    end, dt, accuracy = number(stop, "Stop"), number(step, "Step"), number(eps, "EPS")
    if not 0 < dt <= end or end/dt > MAX_TRANSIENT_STEPS or not 0 < accuracy <= .1:
        raise EngineError("Evaluation requires 0 < step <= stop, at most one million steps, and 0 < eps <= .1.")
    commands, directives = command_prelude(definitions, overrides)
    initial_conditions = validate_initial_conditions(initial_conditions)
    is_fft = [bool(re.search(r"(?i)\bFFT\s*\(", value)) for value in originals]
    native_fft = any(is_fft)
    fft_settings = None
    if native_fft:
        if not all(is_fft) or any(re.search(r"(?i)\b(?:last|tre|tim|tmag|tph)\s*\(", value) for value in originals):
            raise EngineError("Native FFT expressions require a separate request; final statistics and time signals cannot share its frequency axis.")
        if fft is None:
            fft = {}
        if not isinstance(fft, dict) or set(fft)-{"window", "points", "harmonics", "window_type"}:
            raise EngineError("fft supports only window, points, harmonics and native window_type.")
        interval = _window(fft.get("window"), end)
        points = fft.get("points", 1024)
        if isinstance(points, bool) or not isinstance(points, int) or not 16 <= points <= 65536 or points & (points-1):
            raise EngineError("Native FFT points must be a power of two from 16 to 65536.")
        harmonics = fft.get("harmonics", min(100, points//2))
        window_type = fft.get("window_type", 0)
        if isinstance(harmonics, bool) or not isinstance(harmonics, int) or not 1 <= harmonics <= points//2:
            raise EngineError("Native FFT harmonics must be an integer from 1 through points/2.")
        if isinstance(window_type, bool) or not isinstance(window_type, int) or window_type not in range(4):
            raise EngineError("Native FFT window_type must be 0, 1, 2 or 3 (native FFTD selector).")
        fft_settings = {"window": interval, "points": points, "harmonics": harmonics, "window_type": window_type}
        expressions, axis = originals, "f"
    else:
        if fft is not None:
            raise EngineError("fft settings require FFT(...) in every requested signal.")
        expressions = [value if re.search(r"(?i)\b(?:last|tre|tim|tmag|tph)\s*\(", value)
                       else f"last({value})" for value in originals]
        expressions = _signals(expressions, source, "t")
        axis = "t"
    cancelled = engine._begin_request()
    job = manifest = None
    try:
        job, manifest = engine._job(source, "transient", cancelled)
        manifest["analysis"] = "native_fft" if native_fft else "summary"
        engine._configure_job(job, manifest, {"signals": expressions, "original_signals": originals,
            "stop": end, "step": dt, "eps": accuracy, "fft": fft_settings,
            "initial_conditions":initial_conditions, **directives})
        configure_initial_conditions(engine,job,manifest,initial_conditions)
        if native_fft:
            _, document, _ = _load(job/"circuit.scm")
            section = document["scm"]["TD"]
            section["FFT"] = 1
            section["FFTD"].update({"StartVal": interval[0], "EndVal": interval[1],
                "PointNum": points, "ShowPointNum": harmonics, "window_type": window_type, "GraphType": 3})
            section["Expressions"] = [{"plot": i+1, "x": "f", "y": value} for i,value in enumerate(expressions)]
            _save_private_changes(engine, job, manifest, {job/"circuit.scm": document})
        engine._execute(job, manifest, 'open "circuit.scm";\n' + commands
            + 'write "native_coverage.txt" t;\n'
            + 'write "native_data.txt" ' + axis + ' ' + " ".join(expressions)
            + f';\nsim tmax={end:.17g} step={dt:.17g} eps={accuracy:.17g} sv2scheme=no;\nexit;\n', cancelled)
        time_rows = parse_native_table(job/"native_coverage.txt", 1, MAX_TRANSIENT_STEPS+1, cancelled)
        from .engine import _validate_requested_axis, _plot_file
        coverage = _validate_requested_axis(time_rows, "transient", manifest["request"])
        expected = harmonics+1 if native_fft else 1
        rows = parse_native_table(job/"native_data.txt", len(originals)+1, expected, cancelled)
        if len(rows) != expected:
            raise EngineError(f"Native evaluation returned {len(rows)} rows; expected {expected}.")
        if native_fft:
            resolution = 1/(interval[1]-interval[0])
            if any(not math.isclose(row[0], index*resolution, rel_tol=1e-9, abs_tol=0.)
                   for index,row in enumerate(rows)):
                raise EngineError("Native FFT bins do not match the requested time window and harmonic grid.")
        elif rows[0][0] != 0:
            raise EngineError("Native final-statistic export must contain one post-analysis row at t=0.")
        columns = ["f" if native_fft else "evaluation_index", *originals]
        csv_path, coverage_path = job/"data.csv", job/"native_coverage.csv"
        _csv_file(csv_path, columns, rows, cancelled)
        _csv_file(coverage_path, ["t"], time_rows, cancelled)
        origin = ("Native FASTMEAN FFT(...) on configured FFTD interval; Matplotlib rendering of exported bins"
                  if native_fft else "Native FASTMEAN final post-analysis expressions; ordinary expressions wrapped in last(...)")
        manifest.update({"status":"completed", "columns":columns, "row_count":len(rows), "origin":origin,
            "axis_validation":coverage, "native_coverage_rows":len(time_rows),
            "native_data_sha256":_sha256(job/"native_data.txt"), "csv_sha256":_sha256(csv_path)})
        result = {**engine._result(job,manifest), "analysis":manifest["analysis"], "origin":origin,
            "columns":columns, "rows":rows, "row_count":len(rows), "csv_path":str(csv_path),
            "data_path":str(job/"native_data.txt"), "native_coverage_path":str(coverage_path),
            "axis_validation":coverage, "native_expressions":expressions}
        if native_fft:
            plot_path = job/"native_fft.png"
            _plot_file(plot_path, columns, rows, "ac", "linear", cancelled)
            result.update(plot_path=str(plot_path), fft=fft_settings,
                frequency_resolution_hz=resolution, native_fft=True)
        else:
            result["values"] = dict(zip(originals, rows[0][1:]))
        engine._manifest(job,manifest)
        return result
    except BaseException as error:
        if job is not None:
            _failed(engine,job,manifest,error)
        raise
    finally:
        engine._end_request(cancelled)
