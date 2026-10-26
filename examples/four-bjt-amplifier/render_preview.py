"""Render showcase figures from preserved SCM geometry, without native analysis.

Uses the repository preview parser and symbol renderer. Only presentation changes:
hide TEXT notes, resolve root parameter labels to their nominal spec values, and
add explanatory headings. The original SCM files are never rewritten.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from fastmean_mcp import preview


def draw(axis, source: Path, numerical_labels: bool = False):
    model = preview._model(source)
    objects = {oid: obj for oid, obj in model["objects"].items() if obj["Type"] != 900}
    values = dict(model["values"])
    if numerical_labels:
        spec = json.loads((ROOT / "project.input.json").read_text(encoding="utf-8"))
        by_name = {c["name"]: c for c in spec["circuit"]["components"]}
        for oid, obj in objects.items():
            component = by_name.get(obj.get("Name"))
            if component and obj["Type"] in {1000, 1001, 1002}:
                values[oid] = preview._quantity(component["value"],
                    {1000: "Ω", 1001: "F", 1002: "H"}[obj["Type"]])
            elif component and obj["Type"] == 2010:
                values[oid] = ("1.414 V peak / 1 kHz" if obj["Name"] == "VIN" else "38 V")
    for oid, obj in objects.items():
        if obj["Type"] == 1101:
            params = obj["Params"]
            values[oid] = preview._quantity(params["Uon"], "V") + " / " + preview._quantity(params["Ron"], "Ω")
        elif obj["Type"] == 6002:
            values[oid] = "h=" + f"{float(obj['Params']['h']):.4g}"
    xs = [obj["X"] for obj in objects.values()]
    ys = [obj["Y"] for obj in objects.values()]
    for obj in objects.values():
        if obj["Type"] in preview._NATIVE_COMPONENTS:
            from fastmean_mcp.native_geometry import body_bounds, pin_positions
            left, top, right, bottom = body_bounds(obj)
            xs.extend([left, right] + [p[0] for p in pin_positions(obj).values()])
            ys.extend([top, bottom] + [p[1] for p in pin_positions(obj).values()])
    axis.set_xlim(min(xs) - 110, max(xs) + 200)
    axis.set_ylim(max(ys) + 95, min(ys) - 100)
    axis.set_aspect("equal")
    axis.axis("off")
    for start, end in model["segments"]:
        axis.plot([start[0], end[0]], [start[1], end[1]], color="#137653",
                  linewidth=1.55, solid_capstyle="round", zorder=1)
    for oid, obj in objects.items():
        x, y, tid, rotation = obj["X"], obj["Y"], obj["Type"], obj["Rot"]
        if tid in preview._COMPONENTS:
            preview._draw_component(axis, obj, values[oid])
            if obj.get("Name") == "VIN":
                axis.texts[-1].set_position((x + 42, y + 48))
            for label in list(axis.texts)[-2:]:
                label.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": .5})
        elif tid in preview._NATIVE_COMPONENTS:
            preview._draw_native_component(axis, obj, values[oid])
            if tid in {1101, 6002}:
                labels = list(axis.texts)[-2:]
                if tid == 1101 and rotation % 2:
                    for label, offset in zip(labels, (-12, 15)):
                        label.set_position((x + 34 if numerical_labels else x - 34, y + offset))
                        label.set_horizontalalignment("left" if numerical_labels else "right")
                elif tid == 6002:
                    for label, offset in zip(labels, (-12, 15)):
                        label.set_position((x - 50, y + offset))
                        label.set_horizontalalignment("right")
                for label in labels:
                    label.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": .5})
        elif tid == 300:
            axis.plot(x, y, "o", color="#137653", markersize=3.6, zorder=6)
        elif tid == 200:
            def ground_point(dx, dy):
                for _ in range(rotation):
                    dx, dy = -dy, dx
                return x + dx, y + dy
            lines = [[ground_point(0, 0), ground_point(0, 14)]]
            lines += [[ground_point(-half, dy), ground_point(half, dy)]
                      for half, dy in ((16, 14), (10, 21), (4, 28))]
            for points in lines:
                axis.plot(*zip(*points), color="#161b22", linewidth=1.55, zorder=4)
        elif tid == 400:
            axis.plot(x, y, "o", markerfacecolor="white", markeredgecolor="#137653",
                      markersize=4.5, zorder=6)
            is_left = rotation == 2
            axis.text(x - 13 if is_left else x + 13, y - 14, str(obj.get("Name", "")),
                      ha="right" if is_left else "left", va="center", fontsize=10,
                      fontweight="bold", color="#137653", zorder=8, parse_math=False)
    axis.apply_aspect()
    # Keep type in proportion to the native coordinate scale.
    points_per_unit = axis.get_window_extent().width * 72 / axis.figure.dpi / (axis.get_xlim()[1] - axis.get_xlim()[0])
    for label in axis.texts:
        label.set_fontsize(label.get_fontsize() * points_per_unit / 0.5)
    return model


def save(figure, name):
    for extension in ("png", "svg"):
        figure.savefig(ROOT / f"{name}.{extension}", dpi=160, facecolor="white",
                       metadata={"Creator": "FASTMEAN MCP / Matplotlib", **({"Date": None} if extension == "svg" else {})})
        if extension == "svg":
            path = ROOT / f"{name}.svg"
            path.write_bytes(b"\n".join(line.rstrip(b" \t\r") for line in path.read_bytes().split(b"\n")))
    figure.clear()


def main():
    with matplotlib.rc_context({"font.family": "DejaVu Sans", "text.usetex": False,
                                "svg.fonttype": "none", "svg.hashsalt": "four-bjt-showcase"}):
        figure = Figure(figsize=(17.5, 15.8), dpi=160, facecolor="white")
        FigureCanvasAgg(figure)
        figure.text(.06, .965, "Усилитель на четырёх BJT", fontsize=23, weight="bold", color="#14263c")
        figure.text(.06, .938, "1 кГц  ·  1 В RMS на входе  ·  ±38 В  ·  1,25 Ом", fontsize=13, color="#516079")
        figure.text(.94, .965, "25,003 В RMS  /  500,10 Вт", ha="right", fontsize=15,
                    weight="bold", color="#137653")
        figure.text(.94, .938, "Учебная номинальная PWL-модель", ha="right", fontsize=12, color="#a24c1d")
        axis = figure.add_axes((.045, .06, .91, .84))
        draw(axis, ROOT / "Amplifier_4BJT.scm", numerical_labels=True)
        figure.text(.5, .025, "Геометрия исходного SCM · D: Uon / Ron · визуализация MCP/Matplotlib · не снимок FASTMEAN",
                    ha="center", fontsize=10, color="#64748b")
        save(figure, "preview")

        figure = Figure(figsize=(16, 13), dpi=160, facecolor="white")
        FigureCanvasAgg(figure)
        figure.text(.055, .965, "Что находится внутри Q1–Q4", fontsize=22, weight="bold", color="#14263c")
        figure.text(.055, .936, "Каждый экземпляр X: 3 сопротивления + 2 PWL-диода + 2 управляемых источника тока",
                    fontsize=12, color="#516079")
        labels = [("NDRV", "Q1 · NPN · MJL4281A"), ("PDRV", "Q2 · PNP · MJL4302A"),
                  ("NOUT", "Q3 · NPN · 2N5686"), ("POUT", "Q4 · PNP · 2N5684")]
        for index, (model, label) in enumerate(labels):
            axis = figure.add_axes((.035 + (index % 2) * .49, .505 - (index // 2) * .445, .46, .37))
            draw(axis, ROOT / "models" / f"{model}.scm")
            axis.set_title(label + "  /  " + model, fontsize=13, weight="bold", color="#14263c", pad=15)
        figure.text(.5, .025, "Фиксированные авторские эквиваленты, не заводские SPICE-модели · геометрия SCM, визуализация MCP/Matplotlib",
                    ha="center", fontsize=10, color="#64748b")
        save(figure, "subcircuit-preview")
    print("Rendered preview.png/svg and subcircuit-preview.png/svg from preserved SCM geometry.")


if __name__ == "__main__":
    main()
