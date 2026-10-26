"""Validate reference fixtures through the official MCP SDK stdio client only.

No FASTMEAN implementation modules are imported by this harness. Native data
is checked against independent small complex nodal systems and step formulas.
All generated files and full tool replies stay in private local directories.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import datetime as dt
import json
import math
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "benchmarks/reference-circuits/cases"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def solve(matrix, rhs):
    """Complex Gaussian elimination independent of the native implementation."""
    a = [list(row) + [value] for row, value in zip(matrix, rhs)]
    n = len(a)
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-24:
            raise ValueError("Singular independent oracle")
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        a[col] = [v / divisor for v in a[col]]
        for row in range(n):
            if row != col:
                multiplier = a[row][col]
                a[row] = [v - multiplier*w for v, w in zip(a[row], a[col])]
    return [row[-1] for row in a]


def ac_oracle(spec, frequency):
    nodes = sorted({n for c in spec["components"] for n in c["nodes"]} - {"0"})
    sources = [c for c in spec["components"] if c["kind"] == "U"]
    index = {node: i for i, node in enumerate(nodes)}
    size = len(nodes) + len(sources)
    matrix = [[0j]*size for _ in range(size)]
    rhs = [0j]*size
    s = 2j*math.pi*frequency
    for c in spec["components"]:
        a, b = c["nodes"]
        ia, ib = index.get(a), index.get(b)
        value = c["value"]
        if c["kind"] in {"R", "C", "L"}:
            y = {"R": lambda: 1/value, "C": lambda: s*value,
                 "L": lambda: 1/(s*value)}[c["kind"]]()
            for i in (ia, ib):
                if i is not None:
                    matrix[i][i] += y
            if ia is not None and ib is not None:
                matrix[ia][ib] -= y
                matrix[ib][ia] -= y
        elif c["kind"] == "I":
            if ia is not None:
                rhs[ia] -= value
            if ib is not None:
                rhs[ib] += value
        elif c["kind"] == "U":
            k = len(nodes) + sources.index(c)
            if ia is not None:
                matrix[ia][k] += 1
                matrix[k][ia] += 1
            if ib is not None:
                matrix[ib][k] -= 1
                matrix[k][ib] -= 1
            rhs[k] = value
        else:
            raise ValueError("Unsupported independent oracle primitive")
    voltages = dict(zip(nodes, solve(matrix, rhs)))
    ports = spec["ports"]
    ports = ports if isinstance(ports, dict) else dict(zip(ports, ports))
    return {alias: voltages[node] for alias, node in ports.items()}


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = [{k: float(v) for k, v in row.items()} for row in reader]
        if not rows or any(not math.isfinite(v) for row in rows for v in row.values()):
            raise ValueError("Native CSV has missing or non-finite samples")
        return fields, rows


def ac_check(spec, result):
    fields, rows = read_csv(result["csv_path"])
    axis = fields[0]
    ports = spec["ports"]
    aliases = list(ports)
    worst = {alias: {"scaled_error": 0.0} for alias in aliases}
    failures = 0
    for row in rows:
        expected = ac_oracle(spec, row[axis])
        for alias in aliases:
            magnitude = row[f"mag(U({alias}))"]
            phase = math.radians(row[f"phs(U({alias}))"])
            observed = magnitude*complex(math.cos(phase), math.sin(phase))
            error = abs(observed - expected[alias])
            allowed = 1e-6 + 1e-3*abs(expected[alias])
            scaled = error/allowed
            failures += scaled > 1
            if scaled > worst[alias]["scaled_error"]:
                worst[alias] = {"scaled_error": scaled, "frequency_Hz": row[axis],
                    "absolute_error_V": error, "observed": [observed.real, observed.imag],
                    "expected": [expected[alias].real, expected[alias].imag]}
    return {"passed": not failures, "samples": len(rows), "failed_cells": failures,
            "comparison": "Complex node voltage: abs(error) <= 1e-6 V + 0.1% expected magnitude",
            "worst": worst}


def td_check(case, result):
    fields, rows = read_csv(result["csv_path"])
    axis = fields[0]
    output = "U(out)"
    ident = case["id"]
    if ident == "rc-lowpass":
        target = lambda t: 1-math.exp(-t/.001)
    elif ident == "rc-coupling-highpass":
        target = lambda t: .9*math.exp(-t/.01)
    else:
        dc = case["expected"]["dc"]["node_voltages_V"]
        target = lambda t: dc["out"]
    valid = [row for row in rows if row[axis] > max(1e-8, rows[1][axis] if len(rows)>1 else 0)]
    expected_row = (lambda row: .1*row["U(in)"]) if ident == "compensated-rc-divider" else (lambda row: target(row[axis]))
    worst = max(({"t_s": row[axis], "absolute_error_V": abs(row[output]-expected_row(row)),
                  "observed_V": row[output], "expected_V": expected_row(row)} for row in valid),
                key=lambda x: x["absolute_error_V"])
    full_scale = max(1., abs(target(valid[-1][axis])))
    final_checks = {}
    if ident not in {"rc-lowpass", "rc-coupling-highpass"}:
        for alias, expected in case["expected"]["dc"]["node_voltages_V"].items():
            observed = rows[-1][f"U({alias})"]
            final_checks[alias] = {"observed_V": observed, "expected_V": expected,
                "passed": abs(observed-expected) <= 1e-6+1e-3*abs(expected)}
    return {"passed": worst["absolute_error_V"] <= .001*full_scale and all(c["passed"] for c in final_checks.values()),
            "samples": len(rows), "worst": worst,
            "final_dc": final_checks,
            "last": {key: rows[-1][key] for key in fields},
            "comparison": "After source rise/first timestep: abs(error)<=0.001*max(1 V,abs(ideal output at stop))"}


async def run(args):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = Path(args.report_dir or ROOT / "local/benchmarks" / stamp).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, FASTMEAN_APP_DIR=str(args.app_dir),
               FASTMEAN_OUTPUT_DIR=str(ROOT / "local/runs"), PYTHONUTF8="1")
    parameters = StdioServerParameters(command=sys.executable,
        args=["-X", "utf8", "-m", "fastmean_mcp"], cwd=str(ROOT), env=env)
    summary = {"protocol": "Official MCP SDK stdio; every construction/native operation uses client.call_tool",
               "started_utc": stamp, "cases": []}
    with (report_dir / "server-stderr.log").open("w", encoding="utf-8") as errors:
        async with stdio_client(parameters, errlog=errors) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=180) as client:
                initialized = await client.initialize()
                save(report_dir / "initialize.json", initialized.model_dump(mode="json"))
                listed = await client.list_tools()
                save(report_dir / "tools.json", listed.model_dump(mode="json"))

                async def call(tool, arguments, label):
                    request = client.call_tool(tool, arguments, read_timeout_seconds=90.)
                    result = await asyncio.wait_for(request, timeout=15. if tool == "fastmean_ac" else 90.)
                    data = result.structured_content
                    if data is None:
                        data = {"content": [c.text for c in result.content if c.type == "text"]}
                    save(report_dir / "calls" / (label + ".json"), {"tool": tool,
                         "arguments": arguments, "is_error": result.is_error, "data": data})
                    print(json.dumps({"label": label, "tool": tool, "error": result.is_error,
                                      "run_id": data.get("run_id")}), flush=True)
                    if result.is_error or data.get("ok") is False:
                        raise RuntimeError(str(data)[:2000])
                    return data

                await call("fastmean_status", {}, "status")
                await call("fastmean_example", {"kind": "rc_lowpass"}, "example")
                for path in sorted(CASES.glob("*.json")):
                    case = json.loads(path.read_text(encoding="utf-8"))
                    if args.case and case["id"] not in args.case:
                        continue
                    for mode, key in (("guided", "circuit_spec"), ("automatic", "automatic_circuit_spec")):
                        if args.mode and mode != args.mode:
                            continue
                        label = case["id"] + "_" + mode
                        entry = {"id": case["id"], "mode": mode, "source": case["source"], "checks": {}}
                        summary["cases"].append(entry)
                        try:
                            spec = copy.deepcopy(case[key])
                            created = await call("fastmean_create_circuit", {"spec": spec, "name": label.replace("-", "_")}, label+"_create")
                            entry.update({"path": created["path"], "create_run_id": created.get("run_id")})
                            inspected = await call("fastmean_inspect", {"path": created["path"]}, label+"_inspect")
                            entry["checks"]["inspect"] = {"warnings": inspected.get("warnings", []), "components": len(inspected.get("components", []))}
                            preview = await call("fastmean_preview", {"path": created["path"]}, label+"_preview")
                            entry["preview"] = preview
                            if args.preview_only:
                                entry.update({"numerical_passed": None, "status": "preview_only"})
                                save(report_dir / "summary.json", summary)
                                continue
                            exported = await call("fastmean_export_netlist", {"path": created["path"], "timeout": 15}, label+"_netlist")
                            entry["netlist_run_id"] = exported.get("run_id")
                            aliases = list(spec["ports"])
                            signals = [f"{part}(U({alias}))" for alias in aliases for part in ("mag", "phs")]
                            frequency = spec["analysis"]["frequency"]
                            ac = await call("fastmean_ac", {"path": created["path"], "signals": signals,
                                "fmin": frequency["start"], "fmax": frequency["stop"],
                                "points": frequency["points"], "scale": "log"}, label+"_ac")
                            entry["checks"]["ac"] = ac_check(spec, ac)
                            entry["ac_run_id"] = ac.get("run_id")
                            for variant in case["expected"].get("parameter_variants", []):
                                variant_spec = copy.deepcopy(spec)
                                updates = variant["component_value_overrides"]
                                for component in variant_spec["components"]:
                                    if component["name"] in updates:
                                        component["value"] = updates[component["name"]]
                                changed = await call("fastmean_edit_values", {"path": created["path"],
                                    "updates": updates}, label+"_"+variant["id"]+"_copy")
                                extra = await call("fastmean_ac", {"path": changed["path"], "signals": signals,
                                    "fmin": frequency["start"], "fmax": frequency["stop"],
                                    "points": frequency["points"], "scale": "log"}, label+"_"+variant["id"]+"_ac")
                                entry["checks"]["ac_"+variant["id"]] = ac_check(variant_spec, extra)
                            if case["id"] == "parallel-series-rlc":
                                notch = case["expected"]["ac"]["notch_Hz"]
                                extra = await call("fastmean_ac", {"path": created["path"],
                                    "signals": ["mag(U(out)/U(in))"], "fmin": notch*(1-1e-6),
                                    "fmax": notch*(1+1e-6), "points": 3, "scale": "linear"}, label+"_notch")
                                columns, samples = read_csv(extra["csv_path"])
                                point = min(samples, key=lambda row: abs(row[columns[0]]-notch))
                                entry["checks"]["notch"] = {"passed": abs(point[columns[1]]) <= 1e-4,
                                    "frequency_Hz": point[columns[0]], "native_magnitude": point[columns[1]],
                                    "analytical_notch_Hz": notch}
                            if case["id"] != "parallel-series-rlc" and (case["expected"]["transient"].get("required", True) or args.include_excluded_transients):
                                transient = spec["analysis"]["transient"]
                                waveform = case["expected"]["transient"].get("source_waveform", {"kind": "dc"})
                                updates = {c["name"]: {"value": c["value"], "waveform": waveform}
                                           for c in spec["components"] if c["kind"] in {"U", "I"}}
                                dc_copy = await call("fastmean_edit_values", {"path": created["path"],
                                    "updates": updates, "name": label.replace("-", "_")+"_dc"}, label+"_dc_copy")
                                entry["dc_copy_path"] = dc_copy["path"]
                                td = await call("fastmean_transient", {"path": dc_copy["path"],
                                    "signals": [f"U({alias})" for alias in aliases],
                                    "stop": transient["stop"], "step": transient["step"],
                                    "eps": 1e-6, "timeout": 15}, label+"_td")
                                entry["checks"]["transient"] = td_check(case, td)
                                entry["transient_run_id"] = td.get("run_id")
                            entry["numerical_passed"] = all(c.get("passed", True) for c in entry["checks"].values())
                        except Exception as error:
                            entry["error"] = str(error)
                            entry["numerical_passed"] = False
                        save(report_dir / "summary.json", summary)
                        print(json.dumps({"case": case["id"], "mode": mode,
                                          "passed": entry["numerical_passed"], "error": entry.get("error")}), flush=True)
    summary["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    if not summary["cases"]:
        raise ValueError("No reference cases matched the requested filters")
    summary["numerical_checks_requested"] = not args.preview_only
    summary["all_numerical_passed"] = None if args.preview_only else all(c["numerical_passed"] for c in summary["cases"])
    save(report_dir / "summary.json", summary)
    print(json.dumps({"report_dir": str(report_dir), "variants": len(summary["cases"]),
                      "all_numerical_passed": summary["all_numerical_passed"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", type=Path, default=Path(os.environ.get("FASTMEAN_APP_DIR", "")) if os.environ.get("FASTMEAN_APP_DIR") else Path(os.environ["LOCALAPPDATA"])/"FASTMEAN 6.1")
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--case", action="append")
    parser.add_argument("--mode", choices=["guided", "automatic"])
    parser.add_argument("--include-excluded-transients", action="store_true",
                        help="Retry documented native transient limitations; never alter circuit topology")
    parser.add_argument("--preview-only", action="store_true",
                        help="MCP create/inspect/preview only; no native executable is launched")
    asyncio.run(run(parser.parse_args()))
