"""Create the attributed 20-part MFB example using the official MCP SDK.

Only FASTMEAN calculates the circuit. NumPy solves independent nodal equations
to check the exported response; fastmean_plot renders the native numeric data.
All native workers use fresh private jobs. No desktop control is used.
"""
import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

import numpy as np
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from specification import AC_SIGNALS, CORNER_HZ, OPAMP_GAIN, RESISTANCE, SOURCE_URL, STAGES, TD_SIGNALS, make_spec, stage_values


def nodal_response(frequency):
    """Solve A/B/output for all three cells, independently of MCP/FASTMEAN.

    KCL at A: (A-prev)/R1+(A-out)/R2+(A-B)/R3+s*C2*A=0.
    KCL at B: (B-A)/R3+s*C1*(B-out)=0. Native OPAMP: out=-k*B.
    Its ideal zero output impedance isolates the next cell and the load.
    """
    matrix = np.zeros((9, 9), dtype=complex)
    rhs = np.zeros(9, dtype=complex)
    s = 2j*math.pi*frequency
    for index, (fsf, quality) in enumerate(STAGES):
        a, b, output = 3*index, 3*index+1, 3*index+2
        c1, c2 = stage_values(fsf, quality)
        matrix[a, a], matrix[a, b], matrix[a, output] = 3/RESISTANCE+s*c2, -1/RESISTANCE, -1/RESISTANCE
        if index:
            matrix[a, a-1] = -1/RESISTANCE
        else:
            rhs[a] = 1/RESISTANCE
        matrix[b, a], matrix[b, b], matrix[b, output] = -1/RESISTANCE, 1/RESISTANCE+s*c1, -s*c1
        matrix[output, b], matrix[output, output] = OPAMP_GAIN, 1
    return np.linalg.solve(matrix, rhs)[[2, 5, 8]]


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        columns = next(reader)
        return columns, np.asarray([[float(value) for value in row] for row in reader])


async def rebuild(args):
    environment = dict(os.environ, FASTMEAN_OUTPUT_DIR=str(Path(args.output_dir).resolve()))
    if args.app_dir:
        environment["FASTMEAN_APP_DIR"] = str(Path(args.app_dir).resolve())
    parameters = StdioServerParameters(command=sys.executable,
        args=["-X", "utf8", "-m", "fastmean_mcp"], env=environment)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, arguments):
                response = await client.call_tool(name, arguments, read_timeout_seconds=90.0)
                if response.is_error:
                    raise RuntimeError(f"{name}: "+"\n".join(item.text for item in response.content if item.type == "text"))
                result = response.structured_content
                print(json.dumps({"tool": name, "run_id": result.get("run_id"), "path": result.get("path")}), flush=True)
                return result

            status = await call("fastmean_status", {})
            if not status["installed"]:
                raise RuntimeError(status["installation_error"])
            spec, annotation = make_spec()
            created = await call("fastmean_create_circuit", {"spec": spec, "name": "bessel_mfb"})
            annotated = await call("fastmean_annotate_circuit", {"path": created["path"], **annotation})
            source = Path(annotated["path"])
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            preview = await call("fastmean_preview", {"path": str(source), "include_text": False})
            netlist = await call("fastmean_export_netlist", {"path": str(source), "timeout": 20})
            complex_signals = [f"{function}(U({port})/U(IN))" for port in ("S1", "S2", "OUT") for function in ("RE", "IM")]
            ac = await call("fastmean_ac", {"path": str(source), "signals": AC_SIGNALS+complex_signals,
                "fmin": 10, "fmax": 100000, "points": 301, "timeout": 20})
            columns, data = read_csv(ac["csv_path"])
            expected = np.asarray([nodal_response(frequency) for frequency in data[:, 0]])
            native = np.column_stack([data[:, columns.index(f"RE(U({port})/U(IN))")]
                +1j*data[:, columns.index(f"IM(U({port})/U(IN))")] for port in ("S1", "S2", "OUT")])
            absolute_error = float(np.max(np.abs(native-expected)))
            relative_error = float(np.max(np.abs((native-expected)/expected)))
            if absolute_error > 1e-7 or relative_error > 1e-6:
                raise AssertionError(f"Native AC differs from independent 9-node solve: abs={absolute_error}, rel={relative_error}")
            ac_plot = await call("fastmean_plot", {"run_id": ac["run_id"], "title": "20-part Bessel MFB filter: native FASTMEAN AC",
                "x_unit": "kHz", "panels": [{"signal": signal, "label": label, "unit": unit, "metrics": []}
                    for signal, label, unit in zip(AC_SIGNALS,
                        ("Stage 1 gain", "Stages 1+2 gain", "Overall gain", "Overall phase"), ("dB", "dB", "dB", "degrees"))]})
            td = await call("fastmean_transient", {"path": str(source), "signals": TD_SIGNALS,
                "stop": .01, "step": 2e-6, "eps": 1e-6, "timeout": 30})
            _, transient = read_csv(td["csv_path"])
            steady = transient[transient[:, 0] >= .006]
            design = np.column_stack((np.sin(2*math.pi*CORNER_HZ*steady[:, 0]),
                np.cos(2*math.pi*CORNER_HZ*steady[:, 0]), np.ones(len(steady))))
            coefficients = np.linalg.lstsq(design, steady[:, 1:], rcond=None)[0]
            phasors = coefficients[0]+1j*coefficients[1]
            td_ratios = phasors[1:]/phasors[0]
            td_error = float(np.max(np.abs(td_ratios-nodal_response(CORNER_HZ))))
            if td_error > .002:
                raise AssertionError(f"Native TD steady-state differs from independent 1-kHz response: {td_error}")
            td_plot = await call("fastmean_plot", {"run_id": td["run_id"], "title": "20-part Bessel MFB filter: 1-kHz sine",
                "display_window": [.006, .01], "measurement_window": [.006, .01], "x_unit": "ms",
                "panels": [{"signal": signal, "label": label, "unit": "V", "metrics": ["rms"]}
                    for signal, label in zip(TD_SIGNALS, ("Input", "Stage 1 output", "Stage 2 output", "Filter output"))]})
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise AssertionError("A native operation changed the source SCM")
            h = nodal_response(CORNER_HZ)[-1]
            verification = {"reference": SOURCE_URL, "reference_figure": "B-2", "reference_topology_parts": 18,
                "test_fixture_parts": ["VIN", "RL"], "total_parts": 20, "corner_hz": CORNER_HZ,
                "assigned_nominals": True, "native_model": "FASTMEAN ideal three-pin OPAMP, k=1e8",
                "server_version": status["server_version"], "native_executable_sha256": ac["engine"]["sha256"],
                "source_scm_sha256": digest, "source_preserved": True,
                "ac_rows": len(data), "ac_max_absolute_complex_error": absolute_error,
                "ac_max_relative_complex_error": relative_error,
                "ac_oracle": "Independent 9-unknown nodal linear solve, including finite op-amp gain",
                "overall_gain_at_1khz_db": 20*math.log10(abs(h)), "overall_phase_at_1khz_degrees": math.degrees(np.angle(h)),
                "td_rows": len(transient), "td_steady_phasor_max_absolute_error": td_error,
                "td_measurement_window_s": [.006, .01],
                "plot_origin": "FASTMEAN native numeric exports rendered by MCP/Matplotlib",
                "schematic_origin": "MCP drawing of SCM native pins and wires; not native screenshot"}
            receipt = Path(ac["working_dir"]) / "example-workflow.json"
            receipt.write_text(json.dumps({"verification": verification, "created": created, "annotated": annotated,
                "preview": preview, "netlist": netlist, "ac": ac, "ac_plot": ac_plot, "td": td, "td_plot": td_plot},
                ensure_ascii=False, indent=2), encoding="utf-8")
            if args.publish_dir:
                destination = Path(args.publish_dir).resolve()
                destination.mkdir(parents=True, exist_ok=False)
                shutil.copyfile(source, destination/"bessel_mfb.scm")
                public_preview = await call("fastmean_preview", {"path": str(destination/"bessel_mfb.scm"), "include_text": False})
                for target, original in {"schematic.png": public_preview["png_path"],
                    "schematic.svg": public_preview["svg_path"], "ac.png": ac_plot["plot_path"], "transient.png": td_plot["plot_path"]}.items():
                    shutil.copyfile(original, destination/target)
                (destination/"verification.json").write_text(json.dumps(verification, indent=2)+"\n", encoding="utf-8")
            print(json.dumps({"receipt": str(receipt), "verification": verification}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", help="Separately installed FASTMEAN directory")
    parser.add_argument("--output-dir", required=True, help="Writable ASCII folder for fresh registered MCP jobs")
    parser.add_argument("--publish-dir", help="New folder for portable SCM, charts and sanitized verification")
    asyncio.run(rebuild(parser.parse_args()))
