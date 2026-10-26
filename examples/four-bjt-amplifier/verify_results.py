"""Verify time-weighted measurements from the included native sample window.

This performs no circuit simulation. FASTMEAN exported the input CSV; NumPy
integrates it, retaining the native adaptive grid and clipping at exact bounds.
"""
from pathlib import Path
import csv
import hashlib
import json

import numpy as np

ROOT = Path(__file__).resolve().parent


def calculate(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    times = np.array([float(row["t"]) for row in rows])
    start, stop = 0.29, 0.30
    if not (np.all(np.diff(times) > 0) and times[0] <= start and times[-1] >= stop):
        raise ValueError("CSV must bracket the complete 0.29–0.30 s measurement window.")
    grid = np.r_[start, times[(times > start) & (times < stop)], stop]
    values = {key: np.interp(grid, times, [float(row[key]) for row in rows])
              for key in ("U(IN)", "U(OUT)", "I(RL)", "I(VIN)", "U(OUT)*I(RL)")}

    def mean(signal):
        return float(np.trapezoid(signal, grid) / (stop - start))

    def rms(signal):
        return mean(signal * signal) ** 0.5

    return {
        "input_rms_v": rms(values["U(IN)"]),
        "output_rms_v": rms(values["U(OUT)"]),
        "load_rms_a": rms(values["I(RL)"]),
        "load_mean_w": mean(values["U(OUT)*I(RL)"]),
        "input_rms_a": rms(values["I(VIN)"]),
        "input_peak_a": float(np.max(np.abs(values["I(VIN)"]))),
        "output_dc_v": mean(values["U(OUT)"]),
        "output_min_v": float(values["U(OUT)"].min()),
        "output_max_v": float(values["U(OUT)"].max()),
    }


if __name__ == "__main__":
    checksums = json.loads((ROOT / "SHA256.json").read_text(encoding="utf-8"))
    for name, checksum in checksums.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if actual != checksum:
            raise AssertionError(f"SHA256 mismatch: {name}")
    expected = json.loads((ROOT / "measurements.json").read_text(encoding="utf-8"))
    result = calculate(ROOT / expected["csv_path"])
    for key, value in result.items():
        if not np.isclose(value, expected[key], rtol=1e-9, atol=1e-10):
            raise AssertionError(f"{key}: measured {value}, expected {expected[key]}")
    print(json.dumps({"verified": True, "sha256_verified": len(checksums),
                      "window_s": [0.29, 0.30], **result}, indent=2))
