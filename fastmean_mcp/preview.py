"""Engineering preview of explicit orthogonal FASTMEAN SCM wires.

This is an MCP drawing of the SCM, not a screenshot of FASTMEAN. The supported
terminal model is the new wired layout's 40-unit half-length. Unknown symbols,
flips and implicit native wire bends are rejected rather than guessed.
"""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
import tempfile
import threading
from typing import Any

from .schematic import _load, _summarize, parse_value

ORIGIN = "MCP schematic preview, not native screenshot"
_SUPPORTED = {200, 300, 400, 900, 1000, 1001, 1002, 2010}
_COMPONENTS = {1000: "R", 1001: "C", 1002: "L", 2010: "U"}
_DIRECTIONS = ((-1, 0), (0, -1), (1, 0), (0, 1))
_RENDER_LOCK = threading.Lock()


class PreviewError(ValueError):
    """The SCM cannot be represented faithfully by the supported preview model."""


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PreviewError(f"{label} must be a finite native coordinate.")
    return float(value)


def _quantity(value: Any, unit: str) -> str:
    try:
        number = parse_value(value)
    except ValueError as error:
        raise PreviewError(f"Preview needs a numeric {unit} value, received {value!r}.") from error
    if not number:
        return f"0 {unit}"
    exponent = max(-12, min(12, 3 * math.floor(math.log10(abs(number)) / 3)))
    prefix = {-12: "p", -9: "n", -6: "µ", -3: "m", 0: "", 3: "k", 6: "M", 9: "G", 12: "T"}[exponent]
    return f"{number / 10 ** exponent:.3g} {prefix}{unit}"


def _source_label(obj: dict) -> str:
    parameters = obj.get("Params") or {}
    mode = parameters.get("ST")
    if mode == 1:
        return _quantity((parameters.get("DC") or {}).get("U0"), "V")
    if mode == 2:
        ac = parameters.get("AC") or {}
        return f"sine: {_quantity(ac.get('U0'), 'V')} / {_quantity(ac.get('F'), 'Hz')}"
    if mode == 3:
        pulse = parameters.get("PULSE") or {}
        return (f"pulse: {_quantity(pulse.get('UMIN'), 'V')} to "
                f"{_quantity(pulse.get('UMAX'), 'V')} / {_quantity(pulse.get('F'), 'Hz')}")
    raise PreviewError(f"Unsupported voltage-source waveform mode {mode!r}; only DC, sine and pulse are rendered.")


def _anchor(obj: dict, pin: int) -> tuple[float, float]:
    x, y = obj["X"], obj["Y"]
    if obj["Type"] in _COMPONENTS:
        direction = _DIRECTIONS[(obj.get("Rot", 0) + (0 if pin == 1 else 2)) % 4]
        return x + 40 * direction[0], y + 40 * direction[1]
    return x, y


def _model(source: Path) -> dict:
    source, document, encoding = _load(source)
    summary = _summarize(document, source, encoding)
    objects = document["scm"]["Scheme"].get("Objects") or []
    wires = document["scm"]["Scheme"].get("Wires") or []
    if not objects or len(objects) > 2000 or len(wires) > 8000:
        raise PreviewError("Preview supports 1 to 2000 objects and at most 8000 explicit wires.")
    by_id, values = {}, {}
    for original in objects:
        obj = dict(original)
        oid, tid = obj["ID"], obj["Type"]
        if tid not in _SUPPORTED:
            raise PreviewError(f"Unsupported preview model Type {tid} ({obj.get('Name', oid)}).")
        obj["X"] = _number(obj.get("X"), "X")
        obj["Y"] = _number(obj.get("Y"), "Y")
        rotation = obj.get("Rot", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, int) or rotation not in range(4):
            raise PreviewError("Native Rot must be 0, 1, 2 or 3.")
        if obj.get("FlipH", 0) or obj.get("FlipV", 0):
            raise PreviewError("Flipped native symbols are not supported by this preview model.")
        obj["Rot"] = rotation
        if tid in {1000, 1001, 1002}:
            kind = _COMPONENTS[tid]
            values[oid] = _quantity((obj.get("Params") or {}).get(kind), {"R": "Ω", "C": "F", "L": "H"}[kind])
        elif tid == 2010:
            values[oid] = _source_label(obj)
        elif tid == 900:
            text = str((obj.get("Params") or {}).get("Text", ""))
            if len(text) > 1000:
                raise PreviewError("A schematic text annotation exceeds the 1000-character preview limit.")
        by_id[oid] = obj
    segments, degrees = [], Counter()
    for wire in wires:
        if set(wire) != {"obj1", "obj2"}:
            raise PreviewError("Explicit wire fields beyond obj1/obj2 are not supported.")
        a, b = wire["obj1"], wire["obj2"]
        start, end = _anchor(by_id[a["ID"]], a["pin"]), _anchor(by_id[b["ID"]], b["pin"])
        if start[0] != end[0] and start[1] != end[1]:
            raise PreviewError("An implicit native wire bend cannot be previewed exactly; use explicit CON waypoints.")
        if start == end:
            raise PreviewError("A zero-length native wire cannot be previewed unambiguously.")
        segments.append((start, end))
        degrees[a["ID"]] += 1
        degrees[b["ID"]] += 1
    return {"source": source, "objects": by_id, "values": values, "segments": segments,
            "degrees": degrees, "warnings": summary["warnings"]}


def _draw_component(axis, obj, value):
    from matplotlib.patches import Circle, Polygon

    x, y = obj["X"], obj["Y"]
    pin_one = _DIRECTIONS[obj["Rot"]]
    ux, uy = -pin_one[0], -pin_one[1]
    vx, vy = -uy, ux

    def point(t, n=0):
        return x + t * ux + n * vx, y + t * uy + n * vy

    def line(points, width=1.55):
        axis.plot(*zip(*points), color="#161b22", linewidth=width, zorder=4, solid_capstyle="round")

    tid = obj["Type"]
    boundary = 23 if tid == 2010 else 22 if tid in {1000, 1002} else 4
    line([point(-40), point(-boundary)])
    line([point(boundary), point(40)])
    if tid == 1000:
        axis.add_patch(Polygon([point(-22, -9), point(22, -9), point(22, 9), point(-22, 9)],
            closed=True, facecolor="white", edgecolor="#161b22", linewidth=1.55, zorder=4))
    elif tid == 1001:
        line([point(-4, -18), point(-4, 18)])
        line([point(4, -18), point(4, 18)])
    elif tid == 1002:
        for index in range(4):
            center = -16.5 + 11 * index
            points = [point(center + 5.5 * math.cos(math.pi * (1 - i / 24)),
                            -12 * math.sin(math.pi * (1 - i / 24))) for i in range(25)]
            line(points)
    else:
        axis.add_patch(Circle((x, y), 23, facecolor="white", edgecolor="#161b22", linewidth=1.55, zorder=4))
        for t, sign in ((-10, "−"), (10, "+")):
            sx, sy = point(t)
            axis.text(sx, sy, sign, ha="center", va="center", fontsize=11,
                      fontweight="bold", color="#161b22", zorder=5, parse_math=False)

    name = str(obj.get("Name", ""))
    if uy:
        lx, ly, align = x + 42, y - 12, "left"
    else:
        lx, ly, align = x, y - 51, "center"
    axis.text(lx, ly, name, ha=align, va="center", fontsize=10, fontweight="bold",
              color="#161b22", zorder=8, parse_math=False)
    axis.text(lx, ly + 24, value, ha=align, va="center", fontsize=9,
              color="#374151", zorder=8, parse_math=False)


def render_schematic(path: Path, output_dir: Path) -> dict:
    """Return fresh SVG/PNG previews reconstructed from native object IDs/pins.

    Supports the wired layout's unflipped R/C/L/U symbols and explicit
    orthogonal wire segments. All validation precedes artifact creation.
    """
    model = _model(Path(path))
    objects = model["objects"]
    xs = [obj["X"] for obj in objects.values()]
    ys = [obj["Y"] for obj in objects.values()]
    xmin, xmax, ymin, ymax = min(xs) - 110, max(xs) + 235, min(ys) - 105, max(ys) + 90
    span_x, span_y = max(300, xmax - xmin), max(220, ymax - ymin)
    width = max(7, min(24, span_x / 105))
    height = max(4, min(20, width * span_y / span_x))

    with _RENDER_LOCK:
        import matplotlib
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        with matplotlib.rc_context({"font.family": "DejaVu Sans", "text.usetex": False,
                                    "svg.fonttype": "none", "svg.hashsalt": "fastmean-preview"}):
            figure = Figure(figsize=(width, height), dpi=145, facecolor="white")
            FigureCanvasAgg(figure)
            axis = figure.add_axes((0.035, 0.075, 0.93, 0.85))
            axis.set_xlim(xmin, xmax)
            axis.set_ylim(ymax, ymin)
            axis.set_aspect("equal", adjustable="box")
            axis.axis("off")
            figure.suptitle(model["source"].stem, x=0.5, y=0.97, fontsize=13, fontweight="bold", parse_math=False)
            figure.text(0.5, 0.027, ORIGIN, ha="center", color="#6b7280", fontsize=8)
            for start, end in model["segments"]:
                axis.plot([start[0], end[0]], [start[1], end[1]], color="#137653", linewidth=1.6,
                          solid_capstyle="round", zorder=1)
            for oid, obj in objects.items():
                x, y, tid, rotation = obj["X"], obj["Y"], obj["Type"], obj["Rot"]
                if tid in _COMPONENTS:
                    _draw_component(axis, obj, model["values"][oid])
                elif tid == 300 and model["degrees"][oid] >= 3:
                    axis.plot(x, y, "o", color="#137653", markersize=4.5, zorder=6)
                elif tid == 200:
                    # The native electrical point is X/Y; the ground glyph is
                    # drawn below it, without shifting its incoming wire.
                    def ground_point(dx, dy):
                        for _ in range(rotation):
                            dx, dy = -dy, dx
                        return x + dx, y + dy
                    lines = [[ground_point(0, 0), ground_point(0, 14)]]
                    lines += [[ground_point(-half, dy), ground_point(half, dy)]
                              for half, dy in ((16, 14), (10, 21), (4, 28))]
                    for points in lines:
                        axis.plot(*zip(*points), color="#161b22", linewidth=1.6, zorder=4)
                elif tid == 400:
                    axis.plot(x, y, "o", markerfacecolor="white", markeredgecolor="#137653",
                              markersize=5, zorder=6)
                    is_left = rotation == 2
                    axis.text(x - 13 if is_left else x + 13, y - 14, str(obj.get("Name", "")),
                              ha="right" if is_left else "left", va="center", fontsize=10,
                              fontweight="bold", color="#137653", zorder=8, parse_math=False)
                elif tid == 900:
                    text = str((obj.get("Params") or {}).get("Text", ""))
                    axis.text(x, y, text, ha="left", va="top", fontsize=9,
                              color="#374151", zorder=8, parse_math=False)
            destination = Path(output_dir).expanduser().resolve()
            destination.mkdir(parents=True, exist_ok=True)
            job = Path(tempfile.mkdtemp(prefix="schematic-preview-", dir=destination))
            svg_path, png_path = job / "schematic.svg", job / "schematic.png"
            try:
                for target, format_name in ((svg_path, "svg"), (png_path, "png")):
                    with target.open("xb") as stream:
                        figure.savefig(stream, format=format_name, facecolor="white")
            finally:
                figure.clear()
    return {"svg_path": str(svg_path), "png_path": str(png_path), "origin": ORIGIN,
            "source_path": str(model["source"]), "component_count": sum(o["Type"] in _COMPONENTS for o in objects.values()),
            "port_count": sum(o["Type"] == 400 for o in objects.values()), "wire_count": len(model["segments"]),
            "junction_count": sum(o["Type"] == 300 and model["degrees"][oid] >= 3 for oid, o in objects.items()),
            "geometry": "SCM object/pin anchors; explicit orthogonal wires; 40-unit component terminals",
            "approximate_wire_routes": False, "warnings": model["warnings"]}
