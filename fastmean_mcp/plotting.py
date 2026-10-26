"""Repeatable charts and measurements of registered native FASTMEAN samples.

No solver, expression evaluator, GUI or caller-supplied file path is involved.
Display scaling changes presentation only; measurements retain native values.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import textwrap
from typing import Any

from . import __version__
from .engine import _RENDER_LOCK

MAX_PANELS = 12
MAX_VERTICES = 6000
MAX_PNG_BYTES = 3_900_000
METRICS = ("rms", "mean", "peak", "min", "max", "peak_to_peak")
_COLORS = ("#2563eb", "#0f807b", "#7c3aed", "#c2410c", "#64748b", "#be185d")
_UNITS = {"s": ("t", 1.0), "ms": ("t", 1000.0), "us": ("t", 1e6),
          "Hz": ("f", 1.0), "kHz": ("f", 1e-3), "MHz": ("f", 1e-6)}


class PlotError(ValueError):
    """An invalid chart request or an unusable native data window."""


def _text(value: Any, label: str, maximum: int, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise PlotError(f"{label} must be 1–{maximum} plain text characters without control characters.")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlotError(f"{label} must be a finite number, not a boolean.")
    try:
        number = float(value)
    except OverflowError as error:
        raise PlotError(f"{label} must be finite.") from error
    if not math.isfinite(number):
        raise PlotError(f"{label} must be finite.")
    return number


def _window(value: Any, x, label: str) -> list[float]:
    if value is None:
        return [x[0], x[-1]]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise PlotError(f"{label} must contain [start, stop] in original seconds or Hz.")
    start, stop = (_finite(item, label) for item in value)
    if not x[0] <= start < stop <= x[-1]:
        raise PlotError(f"{label} requires start < stop bracketed by the native data [{x[0]:.17g}, {x[-1]:.17g}]; no extrapolation.")
    return [start, stop]


def clip_window(x, y, window: list[float]) -> tuple[list[float], list[float], int]:
    """Retain adaptive timestamps and interpolate only the exact endpoints."""
    start, stop = window

    def boundary(at):
        right = bisect_left(x, at)
        if right < len(x) and x[right] == at:
            return y[right], 0
        left = right - 1
        weight = (at - x[left]) / (x[right] - x[left])
        # Weighted endpoints avoid overflowing the difference of opposite signs.
        return (1 - weight) * y[left] + weight * y[right], 1

    first, count_a = boundary(start)
    last, count_b = boundary(stop)
    left, right = bisect_right(x, start), bisect_left(x, stop)
    return [start, *x[left:right], stop], [first, *y[left:right], last], count_a + count_b


def measure(x, y, requested: list[str]) -> dict[str, float]:
    """Time-weighted trapezoids, including squared samples for published RMS."""
    duration = x[-1] - x[0]
    maximum = max(abs(value) for value in y)

    def average(values):
        return math.fsum((0.5 * values[i - 1] + 0.5 * values[i])
                         * ((x[i] - x[i - 1]) / duration) for i in range(1, len(x)))

    result = {}
    for metric in requested:
        if metric == "mean":
            value = average(y)
        elif metric == "rms":
            value = maximum * math.sqrt(average([(value / maximum) ** 2 for value in y])) if maximum else 0.0
        elif metric == "peak":
            value = maximum
        elif metric == "min":
            value = min(y)
        elif metric == "max":
            value = max(y)
        else:
            value = max(y) - min(y)
        if not math.isfinite(value):
            raise PlotError(f"{metric} exceeds finite numeric range.")
        result[metric] = value
    return result


def _choices(value, label, allowed):
    if (not isinstance(value, list) or len(value) > len(allowed)
            or any(not isinstance(item, str) or item not in allowed for item in value)
            or len(set(value)) != len(value)):
        raise PlotError(f"{label} must be a unique list drawn from {', '.join(allowed)}.")
    return list(value)


def prepare_plot(store, run_id: str, panels: list[dict] | None = None,
                 display_window: list | None = None, measurement_window: list | None = None,
                 title: str | None = None, subtitle: str | None = None,
                 x_unit: str | None = None) -> dict:
    """Validate and measure before the server creates a destination job."""
    table = store.load_native_data(run_id)
    columns, values, analysis = table["columns"], table["values"], table["analysis"]
    x = values[0]
    display = _window(display_window, x, "display_window")
    measurement = _window(measurement_window, x, "measurement_window")
    title = _text(title, "title", 160, optional=True) or "FASTMEAN native data"
    subtitle = _text(subtitle, "subtitle", 240, optional=True)
    x_unit = x_unit if x_unit is not None else ("Hz" if analysis == "ac" else "s")
    if not isinstance(x_unit, str) or x_unit not in _UNITS or _UNITS[x_unit][0] != columns[0]:
        raise PlotError("x_unit must be s/ms/us for transient data or Hz/kHz/MHz for AC data.")
    x_scale = _UNITS[x_unit][1]
    if not all(math.isfinite(value * x_scale) for value in display):
        raise PlotError("Displayed x axis exceeds finite numeric range.")
    if panels is None:
        panels = [{"signal": signal} for signal in columns[1:]]
    if not isinstance(panels, list) or not 1 <= len(panels) <= MAX_PANELS:
        raise PlotError(f"panels must contain 1–{MAX_PANELS} exact exported signals; select panels explicitly for larger runs.")
    normalized, rendered, measurements, seen = [], [], [], set()
    allowed = {"signal", "label", "unit", "scale", "metrics", "guides", "color"}
    for index, panel in enumerate(panels):
        if not isinstance(panel, dict) or set(panel) - allowed:
            raise PlotError("Each panel must be an object with signal, label, unit, scale, metrics, guides and/or color.")
        signal = panel.get("signal")
        if not isinstance(signal, str) or signal not in columns[1:]:
            raise PlotError("A panel signal must exactly match an exported native CSV column; new expressions are not evaluated.")
        if signal in seen:
            raise PlotError("Duplicate panel signals are not supported.")
        seen.add(signal)
        label = _text(panel.get("label"), "panel label", 80, optional=True)
        unit = _text(panel.get("unit"), "panel unit", 24, optional=True)
        scale = _finite(panel.get("scale", 1), "panel scale")
        if scale <= 0:
            raise PlotError("panel scale must be positive; display_value = native_value * scale.")
        metrics = _choices(panel.get("metrics", ["rms"] if analysis == "transient" else []), "metrics", METRICS)
        guides = _choices(panel.get("guides", []), "guides", ("mean", "rms"))
        metrics = list(dict.fromkeys([*metrics, *guides]))
        if analysis != "transient" and metrics:
            raise PlotError("Time-weighted measurements and guides require transient data; AC panels use metrics=[].")
        color = panel.get("color", _COLORS[index % len(_COLORS)])
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise PlotError("panel color must be a #RRGGBB hexadecimal color.")
        y = values[columns.index(signal)]
        display_x, display_y, _ = clip_window(x, y, display)
        if not all(math.isfinite(value * scale) for value in display_y):
            raise PlotError("Displayed signal exceeds finite numeric range.")
        metric_values, sample_count, interpolated = {}, 0, 0
        if metrics:
            metric_x, metric_y, interpolated = clip_window(x, y, measurement)
            sample_count = len(metric_x)
            metric_values = measure(metric_x, metric_y, metrics)
        display_metrics = {key: value * scale for key, value in metric_values.items()}
        if not all(math.isfinite(value) for value in display_metrics.values()):
            raise PlotError("Displayed measurement exceeds finite numeric range.")
        definition = {"signal": signal, "label": label, "unit": unit, "scale": scale,
                      "metrics": metrics, "guides": guides, "color": color}
        normalized.append(definition)
        rendered.append({"x": display_x, "y": display_y})
        measurements.append({"signal": signal, "unit": unit, "scale": scale,
                             "metrics": metric_values, "display_metrics": display_metrics,
                             "sample_count": sample_count, "interpolated_boundaries": interpolated})
    spec = {"format": "fastmean-mcp-chart-v1", "source_run_id": run_id,
            "analysis": analysis, "title": title, "subtitle": subtitle,
            "display_window": display, "measurement_window": measurement, "x_unit": x_unit,
            "x_scale": x_scale, "x_axis_scale": table["request"].get("scale", "linear") if analysis == "ac" else "linear",
            "panels": normalized,
            "scale_semantics": "display_value = native_value * scale; unit is a caller-supplied display label"}
    measurement_result = {"format": "fastmean-mcp-measurements-v1", "source_run_id": run_id,
        "axis": columns[0], "window": measurement,
        "method": {"mean": "trapezoid(y, t) / duration", "rms": "sqrt(trapezoid(y**2, t) / duration)",
                   "peak": "max(abs(y)) at native samples and interpolated window endpoints",
                   "boundaries": "piecewise-linear interpolation; original adaptive timestamps; no extrapolation",
                   "values": "metrics use native exported column values; display_metrics apply panel scale"},
        "signals": measurements}
    return {"spec": spec, "measurements": measurement_result, "series": rendered,
            "provenance": table["provenance"], "source_row_count": table["row_count"]}


def _decimate(x, y):
    """Bound SVG/PNG vertices while preserving extrema of each display bucket."""
    if len(x) <= MAX_VERTICES:
        return x, y
    stride = math.ceil((len(x) - 2) / ((MAX_VERTICES - 2) // 2))
    selected = [0]
    for start in range(1, len(x) - 1, stride):
        end = min(len(x) - 1, start + stride)
        low = min(range(start, end), key=y.__getitem__)
        high = max(range(start, end), key=y.__getitem__)
        selected.extend(sorted({low, high}))
    selected.append(len(x) - 1)
    return [x[i] for i in selected], [y[i] for i in selected]


def _json_file(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def render_plot(plan: dict, job: Path) -> dict:
    """Render an already validated plan in one new private output directory."""
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    spec, measurements = plan["spec"], plan["measurements"]
    png, svg = job / "plot.png", job / "plot.svg"
    with _RENDER_LOCK, matplotlib.rc_context({"text.usetex": False, "font.family": "DejaVu Sans",
            "svg.fonttype": "none", "svg.hashsalt": "fastmean-mcp-chart-v1",
            "axes.spines.top": False, "axes.spines.right": False}):
        count = len(spec["panels"])
        figure = Figure(figsize=(10.8, max(3.7, 2.0 * count + 2.0)), dpi=120,
                        facecolor="white", layout="constrained")
        FigureCanvasAgg(figure)
        try:
            axes = figure.subplots(count, 1, squeeze=False, sharex=True)[:, 0]
            for axis, panel, series, result in zip(axes, spec["panels"], plan["series"], measurements["signals"]):
                xs, ys = _decimate(series["x"], series["y"])
                axis.plot([value * spec["x_scale"] for value in xs],
                          [value * panel["scale"] for value in ys], color=panel["color"], linewidth=1.5)
                if spec["x_axis_scale"] == "log":
                    axis.set_xscale("log")
                label = panel["signal"] if panel["label"] is None else f"{panel['label']} · {panel['signal']}"
                axis.set_title(textwrap.shorten(label, width=85, placeholder="…"), loc="left", fontsize=9, parse_math=False)
                captions = []
                for name, value in result["display_metrics"].items():
                    suffix = f" {panel['unit']}" if panel["unit"] else ""
                    captions.append(f"{name}: {value:.6g}{suffix}")
                caption = textwrap.fill("  ·  ".join(captions), width=78)
                axis.set_title(caption, loc="right", fontsize=9, color=panel["color"], parse_math=False)
                axis.set_ylabel(panel["unit"] or "Native value", fontsize=9, parse_math=False)
                axis.set_xlim(*(value * spec["x_scale"] for value in spec["display_window"]))
                axis.grid(True, which="both", color="#e2e8f0", alpha=.9)
                axis.tick_params(labelsize=9)
                axis.margins(y=.1)
                for metric in panel["guides"]:
                    axis.axhline(result["display_metrics"][metric], color="#475569", linestyle="--", linewidth=1.0)
            axes[-1].set_xlabel(("Frequency" if spec["analysis"] == "ac" else "Time") + f" ({spec['x_unit']})", parse_math=False)
            # Bound long user captions on the actual fixed-width canvas. This
            # also breaks unspaced captions instead of clipping them at the edge.
            heading = textwrap.fill(spec["title"], width=62, break_on_hyphens=False)
            if spec["subtitle"]:
                heading += "\n" + textwrap.fill(spec["subtitle"], width=62, break_on_hyphens=False)
            dw, mw = spec["display_window"], spec["measurement_window"]
            native_unit = "Hz" if spec["analysis"] == "ac" else "s"
            heading += f"\nDisplay: {dw[0]:.8g}–{dw[1]:.8g} {native_unit}"
            if any(panel["metrics"] for panel in spec["panels"]):
                heading += f" · Measurements: {mw[0]:.8g}–{mw[1]:.8g} {native_unit}"
            figure.suptitle(heading, fontsize=11, parse_math=False)
            figure.supxlabel("Native FASTMEAN numeric export · Matplotlib rendered by MCP · no native GUI capture", fontsize=8, color="#64748b", parse_math=False)
            for dpi in (120, 100, 80):
                figure.savefig(png, format="png", dpi=dpi, metadata={"Software": "FASTMEAN MCP / Matplotlib"})
                if png.stat().st_size < MAX_PNG_BYTES:
                    break
            else:
                raise PlotError("Chart PNG exceeds the inline MCP image budget; select fewer panels or a shorter display window.")
            figure.savefig(svg, format="svg", metadata={"Creator": "FASTMEAN MCP / Matplotlib", "Date": None})
        finally:
            figure.clear()
    if svg.stat().st_size > 8 * 1024 * 1024:
        raise PlotError("Chart SVG exceeds the MCP artifact read budget; select fewer panels.")
    renderer = {"name": "Matplotlib", "version": matplotlib.__version__, "mcp_version": __version__,
                "chart_format": "fastmean-mcp-chart-v1", "graphical_vertices_per_panel": MAX_VERTICES,
                "decimation": "per-bucket minimum/maximum for rendering only; measurements use original samples"}
    manifest = {"analysis": "plot", "status": "completed", "created_utc": datetime.now(timezone.utc).isoformat(),
                "provenance": plan["provenance"], "renderer": renderer, "request": spec,
                "plot_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                "svg_sha256": hashlib.sha256(svg.read_bytes()).hexdigest()}
    spec_path, measurements_path, manifest_path = job / "chart-spec.json", job / "measurements.json", job / "manifest.json"
    _json_file(spec_path, spec)
    _json_file(measurements_path, measurements)
    _json_file(manifest_path, manifest)
    return {"ok": True, "analysis": "plot", "working_dir": str(job), "source_run_id": spec["source_run_id"],
            "plot_path": str(png), "svg_path": str(svg), "spec_path": str(spec_path),
            "measurements_path": str(measurements_path), "manifest_path": str(manifest_path),
            "display_window": spec["display_window"], "measurement_window": spec["measurement_window"],
            "source_row_count": plan["source_row_count"], "panels": spec["panels"],
            "measurements": measurements, "provenance": plan["provenance"], "renderer": renderer,
            "plot_provenance": "Native FASTMEAN numeric export rendered by MCP/Matplotlib; no new simulation or native GUI capture"}
