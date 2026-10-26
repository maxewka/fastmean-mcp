"""Render all five saved formulas from the published native CSV; no simulation."""
from pathlib import Path
import csv
import sys

sys.dont_write_bytecode = True

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np

from verify_results import calculate

ROOT = Path(__file__).resolve().parent


def main():
    path = ROOT / "native-transient-last10ms.csv"
    result = calculate(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    time = np.array([float(row["t"]) for row in rows])
    # Display three full periods. Interpolate only the exact display boundary;
    # all intervening points retain the native adaptive timestamps.
    display_time = np.r_[.297, time[(time > .297) & (time < .300)], .300]
    signals = {key: np.interp(display_time, time, [float(row[key]) for row in rows])
               for key in ("U(IN)", "U(OUT)", "I(RL)", "I(VIN)", "U(OUT)*I(RL)")}
    with matplotlib.rc_context({"font.family": "DejaVu Sans", "font.size": 11,
                                "svg.fonttype": "none", "svg.hashsalt": "four-bjt-waveforms",
                                "axes.spines.top": False, "axes.spines.right": False}):
        figure = Figure(figsize=(11, 12), dpi=160, facecolor="white")
        FigureCanvasAgg(figure)
        axes = figure.subplots(5, 1, sharex=True)
        figure.subplots_adjust(left=.115, right=.97, bottom=.09, top=.875, hspace=.32)
        figure.text(.115, .965, "Четыре BJT · пять сигналов TD", fontsize=21,
                    weight="bold", color="#14263c")
        figure.text(.115, .935, "FASTMEAN 6.1 · синус 1 кГц · питание ±38 В · нагрузка 1,25 Ом",
                    fontsize=11.5, color="#516079")
        figure.text(.115, .912, "На графиках: 297–300 мс. Измерения: 290–300 мс, десять периодов.",
                    fontsize=10, color="#64748b")
        specifications = [
            ("U(IN)", "Вход, В", "#64748b", 1,
             f"{result['input_rms_v']:.6f} В RMS"),
            ("U(OUT)", "Выход, В", "#2563eb", 1,
             f"{result['output_rms_v']:.3f} В RMS"),
            ("I(RL)", "Нагрузка, А", "#0f807b", 1,
             f"{result['load_rms_a']:.3f} А RMS"),
            ("I(VIN)", "Входной ток, мА", "#7c3aed", 1000,
             f"{1000 * result['input_rms_a']:.3f} мА RMS · пик {1000 * result['input_peak_a']:.3f} мА"),
            ("U(OUT)*I(RL)", "Мощность, Вт", "#c2410c", 1,
             f"Среднее: {result['load_mean_w']:.3f} Вт"),
        ]
        for axis, (formula, label, color, multiplier, caption) in zip(axes, specifications):
            axis.plot(display_time * 1000, signals[formula] * multiplier, color=color, linewidth=1.85)
            axis.set_ylabel(label, fontsize=10.5)
            axis.set_xlim(297, 300)
            axis.grid(True, color="#e5e7eb", linewidth=.75)
            axis.set_title(formula, loc="left", fontsize=10.5, color="#475569", pad=7)
            axis.set_title(caption, loc="right", fontsize=10.5, color=color, pad=7, weight="bold")
            axis.tick_params(labelsize=10)
            axis.margins(y=.1)
        axes[-1].axhline(result["load_mean_w"], color="#334155", linewidth=1.25, linestyle="--")
        axes[-1].set_xlabel("Время, мс", fontsize=11)
        figure.text(.5, .038, "Числа экспортированы нативным FASTMEAN; графики повторно построены локальным скриптом Matplotlib.",
                    ha="center", fontsize=9, color="#64748b")
        figure.text(.5, .019, "Учебная номинальная PWL-модель · без тепловой проверки и SOA · не проект для сборки",
                    ha="center", fontsize=9, color="#a24c1d")
        figure.savefig(ROOT / "offline-waveforms.png", dpi=160, facecolor="white",
                       metadata={"Creator": "FASTMEAN MCP / Matplotlib"})
        figure.savefig(ROOT / "offline-waveforms.svg", facecolor="white",
                       metadata={"Creator": "FASTMEAN MCP / Matplotlib", "Date": None})
        svg = ROOT / "offline-waveforms.svg"
        svg.write_bytes(b"\n".join(line.rstrip(b" \t\r") for line in svg.read_bytes().split(b"\n")))
        figure.clear()
    print("Rendered offline-waveforms.png/svg from the five published native signal columns.")


if __name__ == "__main__":
    main()
