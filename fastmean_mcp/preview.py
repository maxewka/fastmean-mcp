"""Engineering preview of explicit orthogonal FASTMEAN SCM wires.

This is an MCP drawing of the SCM, not a screenshot of FASTMEAN. The supported
terminal model is the new wired layout's 40-unit half-length. Unknown symbols,
flips and unsupported native wire detours are rejected rather than guessed.
"""
from __future__ import annotations

from collections import Counter
import math
import re
from pathlib import Path
import tempfile
import threading
from typing import Any

from .schematic import _load, _summarize, parse_value

ORIGIN = "MCP schematic preview, not native screenshot"
_SUPPORTED = {200, 300, 400, 900, 1000, 1001, 1002, 2010, 3010, 1101, 6000, 6001, 6002, 6101, 6600, 7100}
_COMPONENTS = {1000: "R", 1001: "C", 1002: "L", 2010: "U", 3010: "I"}
_NATIVE_COMPONENTS = {1101, 6000, 6001, 6002, 6101, 6600, 7100}
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
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value.strip()):
            # Display a native .parameter reference literally, never evaluate it.
            return (value.strip() + " " + unit).rstrip()
        raise PreviewError(f"Preview needs a numeric {unit} value, received {value!r}.") from error
    if not number:
        return f"0 {unit}"
    exponent = max(-12, min(12, 3 * math.floor(math.log10(abs(number)) / 3)))
    prefix = {-12: "p", -9: "n", -6: "µ", -3: "m", 0: "", 3: "k", 6: "M", 9: "G", 12: "T"}[exponent]
    return f"{number / 10 ** exponent:.3g} {prefix}{unit}"


def _source_label(obj: dict) -> str:
    parameters = obj.get("Params") or {}
    mode = parameters.get("ST")
    quantity,unit = ("I","A") if obj.get("Type")==3010 else ("U","V")
    if mode == 1:
        return _quantity((parameters.get("DC") or {}).get(quantity+"0"), unit)
    if mode == 2:
        ac = parameters.get("AC") or {}
        return f"sine: {_quantity(ac.get(quantity+'0'), unit)} / {_quantity(ac.get('F'), 'Hz')}"
    if mode == 3:
        pulse = parameters.get("PULSE") or {}
        return (f"pulse: {_quantity(pulse.get(quantity+'MIN'), unit)} to "
                f"{_quantity(pulse.get(quantity+'MAX'), unit)} / {_quantity(pulse.get('F'), 'Hz')}")
    raise PreviewError(f"Unsupported voltage-source waveform mode {mode!r}; only DC, sine and pulse are rendered.")


def _anchor(obj: dict, pin: int) -> tuple[float, float]:
    x, y = obj["X"], obj["Y"]
    if obj["Type"] in _COMPONENTS:
        direction = _DIRECTIONS[(obj.get("Rot", 0) + (0 if pin == 1 else 2)) % 4]
        return x + 40 * direction[0], y + 40 * direction[1]
    if obj["Type"] in _NATIVE_COMPONENTS:
        from .native_geometry import pin_positions
        return pin_positions(obj)[pin]
    return x, y


def _model(source: Path) -> dict:
    source, document, encoding = _load(source)
    summary = _summarize(document, source, encoding)
    objects = document["scm"]["Scheme"].get("Objects") or []
    wires = document["scm"]["Scheme"].get("Wires") or []
    if not objects or len(objects) > 2000 or len(wires) > 8000:
        raise PreviewError("Preview supports 1 to 2000 objects and at most 8000 explicit wires.")
    by_id, values = {}, {}
    from .schematic import _analysis_defaults
    defaults = _analysis_defaults()["SOD"]
    style = document["scm"].get("SOD") or {}
    custom_style = any(style.get(key, defaults[key]) != defaults[key]
                       for key in ("FontID", "FontParam", "FontNodes", "ShowID", "ShowParam"))
    for original in objects:
        obj = dict(original)
        oid, tid = obj["ID"], obj["Type"]
        if tid not in _SUPPORTED:
            raise PreviewError(f"Unsupported preview model Type {tid} ({obj.get('Name', oid)}).")
        obj["X"] = _number(obj.get("X"), "X")
        obj["Y"] = _number(obj.get("Y"), "Y")
        if tid in _NATIVE_COMPONENTS:
            if not obj["X"].is_integer() or not obj["Y"].is_integer():
                raise PreviewError("Native primitive coordinates must be integers.")
            obj["X"], obj["Y"] = int(obj["X"]), int(obj["Y"])
            if tid == 7100:
                obj["_geometry_scale"] = (document["scm"].get("General") or {}).get("Scale", 100)
                obj["_geometry_custom_style"] = custom_style
        rotation = obj.get("Rot", 0)
        if isinstance(rotation, bool) or not isinstance(rotation, int) or rotation not in range(4):
            raise PreviewError("Native Rot must be 0, 1, 2 or 3.")
        if obj.get("FlipH", 0) or obj.get("FlipV", 0):
            raise PreviewError("Flipped native symbols are not supported by this preview model.")
        obj["Rot"] = rotation
        if tid in {1000, 1001, 1002}:
            kind = _COMPONENTS[tid]
            values[oid] = _quantity((obj.get("Params") or {}).get(kind), {"R": "Ω", "C": "F", "L": "H"}[kind])
        elif tid in {2010, 3010}:
            values[oid] = _source_label(obj)
        elif tid == 1101:
            params = obj.get("Params") or {}
            values[oid] = "Uon=" + _quantity(params.get("Uon"), "V") + "; Ron=" + _quantity(params.get("Ron"), "Ω")
        elif tid in {6000, 6001, 6002}:
            key, unit = {6000: ("g", "S"), 6001: ("k", ""), 6002: ("h", "")}[tid]
            values[oid] = key + "=" + _quantity((obj.get("Params") or {}).get(key), unit).rstrip()
        elif tid == 6101:
            values[oid] = "n=" + _quantity((obj.get("Params") or {}).get("n"), "").rstrip()
        elif tid == 6600:
            params = obj.get("Params") or {}
            values[oid] = "Uon=" + _quantity(params.get("Uon"), "V") + "; Uoff=" + _quantity(params.get("Uoff"), "V")
        elif tid == 7100:
            values[oid] = Path(str((obj.get("Params") or {}).get("FileName", "")).replace("\\", "/")).stem
        elif tid == 900:
            text = str((obj.get("Params") or {}).get("Text", ""))
            if len(text) > 1000:
                raise PreviewError("A schematic text annotation exceeds the 1000-character preview limit.")
        by_id[oid] = obj
        if tid in _NATIVE_COMPONENTS:
            # Validate geometry even if an object happens to have no wires.
            from .native_geometry import body_bounds, pin_positions
            try:
                body_bounds(obj)
                pin_positions(obj)
            except ValueError as error:
                raise PreviewError(str(error)) from error
    segments, degrees = [], Counter()
    for wire in wires:
        if set(wire) != {"obj1", "obj2"}:
            raise PreviewError("Explicit wire fields beyond obj1/obj2 are not supported.")
        a, b = wire["obj1"], wire["obj2"]
        from .wires import wire_path, WireGeometryError
        try:
            points = wire_path(wire, by_id)
        except WireGeometryError as error:
            raise PreviewError(str(error)) from error
        segments.extend(zip(points, points[1:]))
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
    boundary = 23 if tid in {2010,3010} else 22 if tid in {1000, 1002} else 4
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
        if tid == 3010:
            axis.annotate("", xy=point(13), xytext=point(-13), arrowprops={"arrowstyle":"-|>","color":"#161b22","lw":1.55},zorder=5)
        else:
            for t, sign in ((-10, "−"), (10, "+")):
                sx, sy = point(t)
                axis.text(sx, sy, sign, ha="center", va="center", fontsize=11,
                          fontweight="bold", color="#161b22", zorder=5, parse_math=False)

    from .captions import native_component_captions
    for caption in native_component_captions(obj, value):
        caption = dict(caption)
        text = caption.pop("text")
        axis.text(s=text, va="center", color="#161b22", zorder=8,
                  parse_math=False, **caption)


def _draw_native_component(axis, obj, value):
    """Engineering symbols with the exact native connection coordinates."""
    from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle
    from .native_geometry import body_bounds, pin_directions, pin_labels, pin_positions
    points, directions = pin_positions(obj), pin_directions(obj)
    left, top, right, bottom = body_bounds(obj)
    tid = obj["Type"]

    def line(a, b):
        axis.plot([a[0], b[0]], [a[1], b[1]], color="#161b22", linewidth=1.55, zorder=4)

    def inset(pin, distance):
        point, direction = points[pin], directions[pin]
        return point[0] - direction[0] * distance, point[1] - direction[1] * distance

    def symbol_point(x, y):
        for _ in range(obj["Rot"]):
            x, y = -y, x
        return obj["X"] + x, obj["Y"] + y

    if tid == 1101:
        a, b = points[1], points[2]
        length = math.hypot(b[0]-a[0], b[1]-a[1])
        ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
        cx, cy = (a[0]+b[0])/2, (a[1]+b[1])/2
        def point(t, n=0):
            return cx+t*ux-n*uy, cy+t*uy+n*ux
        line(a, point(-10))
        line(point(11), b)
        axis.add_patch(Polygon([point(-10,-10), point(-10,10), point(8)], closed=True,
                               facecolor="white", edgecolor="#161b22", linewidth=1.55, zorder=4))
        line(point(11,-12), point(11,12))  # Native pin1 anode → pin2 cathode.
    elif tid == 6101:
        # Two isolated windings. The corners retain the native horizontal
        # terminal directions at (+/-24,+/-32), outside the winding body.
        for side, pins in ((-1, (1, 2)), (1, (3, 4))):
            winding_x = side * 10
            for pin, y in zip(pins, (-32, 32)):
                corner = symbol_point(winding_x, y)
                line(points[pin], corner)
                line(corner, symbol_point(winding_x, -24 if y < 0 else 24))
            for turn in range(4):
                center_y = -18 + 12 * turn
                coil = [symbol_point(winding_x - side * 5 * math.sin(math.pi * i / 24),
                                     center_y - 6 * math.cos(math.pi * i / 24))
                        for i in range(25)]
                axis.plot(*zip(*coil), color="#161b22", linewidth=1.55, zorder=4)
            # Native V(1)-V(2) = n * (V(3)-V(4)): pins 1 and 3
            # identify corresponding winding ends for positive n.
            axis.add_patch(Circle(symbol_point(side * 14, -21), 1.7,
                                  facecolor="#161b22", edgecolor="none", zorder=5))
        for x in (-1.5, 1.5):
            line(symbol_point(x, -23), symbol_point(x, 23))
    elif tid == 6600:
        # An open contact is the schematic symbol, not the computed state.
        # Control and switched terminals are separate electrical branches.
        for pin, y in ((1, -16), (2, 16), (3, -12), (4, 12)):
            line(points[pin], symbol_point(-16 if pin < 3 else 16, y))
        for y, sign in ((-8, "+"), (8, "−")):
            x, transformed_y = symbol_point(-16, y)
            axis.text(x, transformed_y, sign, ha="center", va="center", fontsize=8,
                      color="#161b22", zorder=8, parse_math=False)
        for y in (-12, 12):
            axis.add_patch(Circle(symbol_point(16, y), 1.7, facecolor="white",
                                  edgecolor="#161b22", linewidth=1.2, zorder=5))
        line(symbol_point(16, 12), symbol_point(7, -8))
        axis.plot(*zip(symbol_point(-7, 0), symbol_point(10, 0)), color="#6b7280",
                  linewidth=1, linestyle="--", zorder=4)
    else:
        axis.add_patch(Rectangle((left, top), right-left, bottom-top, facecolor="white",
                                 edgecolor="#161b22", linewidth=1.55, zorder=4))
        for pin, anchor in points.items():
            dx, dy = directions[pin]
            edge = ((left if dx < 0 else right), anchor[1]) if dx else (anchor[0], top if dy < 0 else bottom)
            line(anchor, edge)
        if tid == 7100:
            for pin, label in pin_labels(obj).items():
                x, y = inset(pin, 12)
                dx, dy = directions[pin]
                axis.text(x, y, label, ha="left" if dx < 0 else "right" if dx > 0 else "center",
                          va="top" if dy < 0 else "bottom" if dy > 0 else "center",
                          fontsize=8, color="#374151", zorder=8, parse_math=False)
            cx, cy = (left+right)/2, (top+bottom)/2
            axis.text(cx, cy-10, str(obj.get("Name", "")), ha="center", va="center", fontsize=10,
                      fontweight="bold", color="#161b22", zorder=8, parse_math=False)
            axis.text(cx, cy+12, value, ha="center", va="center", fontsize=9,
                      color="#374151", zorder=8, parse_math=False)
            return
        for pin, sign in ((1, "+"), (2, "−")):
            x, y = inset(pin, 15)
            axis.text(x, y, sign, ha="center", va="center", fontsize=8,
                      color="#161b22", zorder=8, parse_math=False)
        if tid in {6000, 6002}:
            axis.add_patch(FancyArrowPatch(inset(4, 16), inset(3, 16), arrowstyle="-|>",
                           mutation_scale=9, linewidth=1.25, color="#161b22", zorder=6))
        else:
            # Retain native output numbering without assuming a voltage polarity
            # beyond the inspected native four-terminal order.
            for pin in (3, 4):
                x, y = inset(pin, 15)
                axis.text(x, y, str(pin), ha="center", va="center", fontsize=7,
                          color="#374151", zorder=8, parse_math=False)
    if tid in {1101, 6000, 6001, 6002, 6101, 6600}:
        from .captions import native_component_captions
        for caption in native_component_captions(obj, value):
            caption = dict(caption)
            text = caption.pop("text")
            axis.text(s=text, va="center", color="#161b22", zorder=8,
                      parse_math=False, **caption)
    else:
        axis.text((left+right)/2, top-40, str(obj.get("Name", "")), ha="center", va="center",
                  fontsize=10, fontweight="bold", color="#161b22", zorder=8, parse_math=False)
        axis.text((left+right)/2, top-18, value, ha="center", va="center", fontsize=8,
                  color="#374151", zorder=8, parse_math=False)


def render_schematic(path: Path, output_dir: Path, *, include_text: bool = True) -> dict:
    """Return fresh SVG/PNG previews reconstructed from native object IDs/pins.

    Supports the wired layout's unflipped R/C/L/U/I symbols and explicit
    orthogonal wire segments. All validation precedes artifact creation.
    """
    model = _model(Path(path))
    if not isinstance(include_text, bool):
        raise PreviewError("include_text must be a boolean.")
    omitted_text = sum(obj["Type"] == 900 for obj in model["objects"].values()) if not include_text else 0
    objects = {oid: obj for oid, obj in model["objects"].items() if include_text or obj["Type"] != 900}
    xs = [obj["X"] for obj in objects.values()]
    ys = [obj["Y"] for obj in objects.values()]
    for obj in objects.values():
        if obj["Type"] in _NATIVE_COMPONENTS:
            from .native_geometry import body_bounds, pin_positions
            left, top, right, bottom = body_bounds(obj)
            xs.extend([left, right] + [point[0] for point in pin_positions(obj).values()])
            ys.extend([top, bottom] + [point[1] for point in pin_positions(obj).values()])
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
                elif tid in _NATIVE_COMPONENTS:
                    _draw_native_component(axis, obj, model["values"][oid])
                elif tid == 300:
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
                    text = str((obj.get("Params") or {}).get("Text", "")).replace("\r\n", "\n").replace("\r", "\n")
                    axis.text(x, y, text, ha="left", va="top", fontsize=9,
                              color="#374151", zorder=8, parse_math=False)
            # Text must scale with document geometry too. Fixed point sizes
            # caused long .parameter blocks and small subcircuit captions to
            # overlap when an annotated sheet was fitted to the preview.
            axis.apply_aspect()
            pixels_per_unit = axis.get_window_extent().height / span_y
            text_scale = pixels_per_unit * 96 / figure.dpi
            for label in axis.texts:
                label.set_fontsize(label.get_fontsize() * text_scale)
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
            "source_path": str(model["source"]), "component_count": sum(o["Type"] in _COMPONENTS or o["Type"] in _NATIVE_COMPONENTS for o in objects.values()),
            "port_count": sum(o["Type"] == 400 for o in objects.values()), "wire_count": len(model["segments"]),
            "junction_count": sum(o["Type"] == 300 and model["degrees"][oid] >= 3 for oid, o in objects.items()),
            "routing_waypoint_count": sum(o["Type"] == 300 and model["degrees"][oid] == 2 for oid, o in objects.items()),
            "geometry": "SCM native pin anchors and explicit orthogonal wires; R/C/L/U/I terminals ±40; native D/G/E/F/TR/SW/X geometry",
            "approximate_wire_routes": False, "text_objects_included": include_text,
            "omitted_text_objects": omitted_text, "warnings": model["warnings"]}
