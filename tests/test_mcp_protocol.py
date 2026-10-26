"""Real stdio MCP integration tests using the official mcp Python SDK.

Run from the package directory with its MCP-enabled Python environment:
    python -m unittest discover -s tests -p test_mcp_protocol.py -v

Native AC is opt-in because it starts the installed FASTMEAN program:
    $env:FASTMEAN_MCP_NATIVE_TEST = '1'
    python -m unittest discover -s tests -p test_mcp_protocol.py -v

All created circuits, scripts, numeric exports and plots belong to a temporary
FASTMEAN_OUTPUT_DIR. Tests never call fastmean_open or operate a desktop UI.
Set FASTMEAN_MCP_TEST_SERVER to test another installed server.py entry point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import base64
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PACKAGE_DIR = Path(__file__).resolve().parents[1]
SERVER_PATH = Path(os.environ.get("FASTMEAN_MCP_TEST_SERVER", PACKAGE_DIR / "server.py")).resolve()
REQUIRED_TOOLS = {
    "fastmean_status", "fastmean_example", "fastmean_create_circuit", "fastmean_edit_values",
    "fastmean_ac", "fastmean_transient", "fastmean_symbolic", "fastmean_inspect",
    "fastmean_list_examples", "fastmean_open", "fastmean_search_manual",
    "fastmean_relayout", "fastmean_preview", "fastmean_list_runs",
    "fastmean_get_result", "fastmean_read_data", "fastmean_cancel",
}
NATIVE_ENABLED = os.environ.get("FASTMEAN_MCP_NATIVE_TEST", "").lower() in {"1", "true", "yes"}


def payload(result):
    """Decode standard structuredContent, with a text-content JSON fallback."""
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    text = "\n".join(item.text for item in result.content if getattr(item, "type", None) == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # MCP SDK 2.x prefixes ToolError text with "Error executing tool ...".
        # The adapter's domain-error JSON remains intact after that prefix.
        start = text.find('{"ok":')
        if start >= 0:
            try:
                return json.JSONDecoder().raw_decode(text[start:])[0]
            except json.JSONDecodeError:
                pass
        return text


def returned_paths(value):
    """Collect file-path strings without depending on cosmetic result labels."""
    if isinstance(value, dict):
        for child in value.values():
            yield from returned_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from returned_paths(child)
    elif isinstance(value, str) and "\n" not in value and len(value) < 32768:
        try:
            candidate = Path(value)
            if candidate.is_file():
                yield candidate.resolve()
        except (OSError, ValueError):
            pass


def csv_numeric_rows(path, min_columns=3):
    """Read exported numeric rows independently of the application parser."""
    text = path.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = []
    for row in csv.reader(io.StringIO(text), dialect):
        if len(row) < min_columns:
            continue
        try:
            values = [float(value.strip()) for value in row]
        except ValueError:
            continue
        if all(math.isfinite(value) for value in values):
            rows.append(values)
    return rows


def resource_bytes(result):
    blocks = []
    for item in result.contents:
        blob = getattr(item, "blob", None)
        text = getattr(item, "text", None)
        if blob is not None:
            blocks.append(base64.b64decode(blob, validate=True))
        elif text is not None:
            blocks.append(text.encode("utf-8"))
    return b"".join(blocks)


def filesystem_snapshot(root):
    return {path.relative_to(root).as_posix(): "directory" if path.is_dir() else
            hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob("*")}


class OwnedNativeHandle:
    """An exact Windows handle to a native PID declared by this test's job."""
    def __init__(self, pid):
        import ctypes
        from ctypes import wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        # SYNCHRONIZE + TERMINATE; cleanup may stop only this exact test child.
        self.handle = self.api.OpenProcess(0x00100000 | 0x0001, False, pid)
        if not self.handle:
            raise OSError(f"Native PID {pid} already exited or cannot be observed.")

    def running(self):
        return self.api.WaitForSingleObject(self.handle, 0) == 258

    def close(self):
        if self.handle:
            if self.running():
                # Failure cleanup only, after assertions of server cleanup.
                self.api.TerminateProcess(self.handle, 1)
                self.api.WaitForSingleObject(self.handle, 5000)
            self.api.CloseHandle(self.handle)
            self.handle = None


class McpProtocolTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def session(self, output_dir, app_dir=None):
        self.assertTrue(SERVER_PATH.is_file(), f"MCP entry point is absent: {SERVER_PATH}")
        environment = dict(os.environ)
        environment.update({"FASTMEAN_OUTPUT_DIR": str(output_dir), "PYTHONUTF8": "1",
                            "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
        if app_dir is not None:
            environment["FASTMEAN_APP_DIR"] = str(app_dir)
        parameters = StdioServerParameters(command=sys.executable,
            args=["-X", "utf8", str(SERVER_PATH)], cwd=str(SERVER_PATH.parent), env=environment)
        # Keep transport diagnostics off protocol stdout. Contexts enter and exit
        # within the same asyncio task, as required by the SDK/AnyIO scopes.
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
            try:
                async with stdio_client(parameters, errlog=errors) as (read, write):
                    async with ClientSession(read, write, read_timeout_seconds=180) as client:
                        initialized = await client.initialize()
                        self.assertTrue(initialized.protocol_version)
                        self.assertTrue(initialized.server_info.name)
                        yield client
            except BaseException:
                errors.seek(0)
                diagnostics = errors.read()
                if diagnostics:
                    print("\nMCP server stderr:\n" + diagnostics[-12000:], file=sys.stderr)
                raise

    async def call_success(self, client, name, arguments=None):
        result = await client.call_tool(name, arguments or {})
        self.assertFalse(result.is_error, f"{name} failed: {payload(result)!r}")
        data = payload(result)
        self.assertIsInstance(data, dict, f"{name} must return a structured JSON object")
        self.assertFalse(data.get("ok") is False, f"{name} reported failure: {data!r}")
        return data

    async def create_rc(self, client, output_dir):
        example = await self.call_success(client, "fastmean_example", {"kind": "rc_lowpass"})
        spec = example.get("spec", example)
        self.assertIsInstance(spec.get("components"), list)
        self.assertGreaterEqual(len(spec["components"]), 3)
        created = await self.call_success(client, "fastmean_create_circuit",
            {"spec": spec, "name": "protocol_rc"})
        circuit = Path(created["path"]).resolve()
        self.assertTrue(circuit.is_relative_to(output_dir.resolve()),
                        "Created circuits must respect FASTMEAN_OUTPUT_DIR")
        self.assertEqual(circuit.suffix.lower(), ".scm")
        self.assertGreater(circuit.stat().st_size, 0)
        return spec, circuit

    async def wait_for_running_native(self, client, task, output_dir, source):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if task.done():
                self.fail(f"Long native request ended before cancellation: {payload(task.result())!r}")
            status = await asyncio.wait_for(self.call_success(client, "fastmean_status"), timeout=3)
            active = next((entry for entry in status["active_operations"]
                           if entry["name"] == "transient" and Path(entry["source_path"]) == source), None)
            if active:
                for path in output_dir.glob("*/manifest.json"):
                    try:
                        manifest = json.loads(path.read_text(encoding="utf-8"))
                        if manifest.get("analysis") != "transient" or manifest.get("status") != "running":
                            continue
                        if Path(manifest["source_path"]) != source or not manifest.get("owned_pid"):
                            continue
                        handle = OwnedNativeHandle(manifest["owned_pid"])
                        if handle.running():
                            return active, path, handle
                        handle.close()
                    except (OSError, ValueError, KeyError):
                        continue  # Manifest publication can race this read.
            await asyncio.sleep(.05)
        self.fail("No running owned native PID appeared within 15 seconds.")

    async def cancellation_roundtrip(self, sdk_cancel=False):
        with tempfile.TemporaryDirectory(prefix="fastmean-mcp-cancellation-") as temporary:
            output = Path(temporary)
            # This process belongs to the test, but is unrelated to the MCP job.
            # Server cancellation must leave it alive.
            unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            handle, task, operation_id = None, None, None
            try:
                async with self.session(output) as client:
                    _, source = await self.create_rc(client, output)
                    source_before = source.read_bytes()
                    task = asyncio.create_task(client.call_tool("fastmean_transient", {
                        "path": str(source), "signals": ["U(out)"], "stop": 1., "step": 1e-6, "eps": 1e-8}))
                    try:
                        active, manifest_path, handle = await self.wait_for_running_native(client, task, output, source)
                        operation_id = active["operation_id"]
                        if sdk_cancel:
                            # Official SDK sends notifications/cancelled when an
                            # outstanding stdio request task is abandoned.
                            task.cancel()
                            with self.assertRaises(asyncio.CancelledError):
                                await task
                        else:
                            cancelled = await self.call_success(client, "fastmean_cancel", {"operation_id": operation_id})
                            self.assertTrue(cancelled["cancellation_requested"])
                            rejected = await asyncio.wait_for(task, timeout=10)
                            self.assertTrue(rejected.is_error, repr(payload(rejected)))
                            self.assertIn("cancel", str(payload(rejected)).lower())
                        deadline = time.monotonic() + 10
                        while time.monotonic() < deadline:
                            status = await self.call_success(client, "fastmean_status")
                            try:
                                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                            except (OSError, ValueError):
                                manifest = {}
                            if not status["active_operations"] and not handle.running() and manifest.get("status") == "cancelled":
                                break
                            await asyncio.sleep(.05)
                        self.assertEqual(status["active_operations"], [])
                        self.assertFalse(handle.running(), "Cancellation must reap the exact native child")
                        self.assertEqual(manifest.get("status"), "cancelled", repr(manifest))
                        self.assertIsNone(unrelated.poll(), "An unrelated process was stopped by native cancellation")
                        self.assertEqual(source.read_bytes(), source_before)
                        # The same connection and native solver remain usable.
                        recovered = await self.call_success(client, "fastmean_ac", {
                            "path": str(source), "signals": ["mag(U(out)/U(in))"],
                            "fmin": 1, "fmax": 1000, "points": 5})
                        page = await self.call_success(client, "fastmean_read_data", {"run_id": recovered["run_id"]})
                        self.assertEqual(page["returned_count"], 5)
                        for frequency, magnitude in page["rows"]:
                            expected = 1 / math.sqrt(1 + (2 * math.pi * frequency * .001) ** 2)
                            self.assertAlmostEqual(magnitude, expected, delta=1e-7)
                    finally:
                        if task is not None and not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                        if operation_id is not None:
                            # Best-effort protocol cleanup on an assertion error;
                            # never close or terminate any existing user process.
                            try:
                                await asyncio.wait_for(client.call_tool("fastmean_cancel", {"operation_id": operation_id}), timeout=3)
                            except Exception:
                                pass
            finally:
                if handle is not None:
                    handle.close()
                if unrelated.poll() is None:
                    unrelated.terminate()
                unrelated.wait(timeout=5)

    @unittest.skipUnless(os.name == "nt" and NATIVE_ENABLED,
        "Set FASTMEAN_MCP_NATIVE_TEST=1 on Windows to start native FASTMEAN")
    async def test_native_explicit_cancellation_stops_owned_pid_and_recovers(self):
        await self.cancellation_roundtrip(sdk_cancel=False)

    @unittest.skipUnless(os.name == "nt" and NATIVE_ENABLED,
        "Set FASTMEAN_MCP_NATIVE_TEST=1 on Windows to start native FASTMEAN")
    async def test_native_sdk_task_cancellation_stops_owned_pid_and_recovers(self):
        await self.cancellation_roundtrip(sdk_cancel=True)

    async def test_initialize_tools_create_inspect_and_error_recovery(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-mcp-protocol-") as temporary:
            output_dir = Path(temporary)
            async with self.session(output_dir) as client:
                listed = await client.list_tools()
                names = {tool.name for tool in listed.tools}
                self.assertEqual(len(REQUIRED_TOOLS), 17)
                self.assertFalse(REQUIRED_TOOLS - names,
                                 f"Missing tools: {sorted(REQUIRED_TOOLS - names)}")
                for tool in listed.tools:
                    self.assertEqual(tool.input_schema.get("type"), "object", tool.name)

                await self.call_success(client, "fastmean_status")
                spec, circuit = await self.create_rc(client, output_dir)
                inspected = await self.call_success(client, "fastmean_inspect", {"path": str(circuit)})
                components = inspected["components"]
                self.assertEqual({item["name"] for item in components},
                                 {item["name"] for item in spec["components"]})

                missing = output_dir / "absent.scm"
                failed = await client.call_tool("fastmean_inspect", {"path": str(missing)})
                error = payload(failed)
                reported_error = failed.is_error or (isinstance(error, dict) and
                    (error.get("ok") is False or bool(error.get("error"))))
                self.assertTrue(reported_error, f"Missing file was not an error: {error!r}")
                self.assertIsInstance(error, dict, repr(error))
                self.assertEqual(error["error"]["code"], "not_found")
                self.assertIn("absent.scm", error["error"]["message"])
                self.assertFalse(missing.exists())

                # An invalid request must not terminate or desynchronize stdio.
                await self.call_success(client, "fastmean_status")
                after_error = await client.list_tools()
                self.assertEqual({tool.name for tool in after_error.tools}, names)

    async def test_offline_discovery_and_schema_rejections_do_not_write_results(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-mcp-offline-") as temporary:
            root = Path(temporary)
            output = root / "not-created-by-discovery"
            async with self.session(output, app_dir=root / "not-installed") as client:
                status = await self.call_success(client, "fastmean_status")
                self.assertFalse(status["installed"])
                self.assertIn("FASTMEAN_APP_DIR", status["installation_error"])
                self.assertEqual(status["active_operations"], [])
                names = {tool.name for tool in (await client.list_tools()).tools}
                self.assertFalse(REQUIRED_TOOLS - names)
                runs = await self.call_success(client, "fastmean_list_runs")
                self.assertEqual(runs["runs"], [])
                guide = resource_bytes(await client.read_resource("fastmean://guide"))
                self.assertIn(b"FASTMEAN", guide)
                await self.call_success(client, "fastmean_search_manual", {"query": "save_netlist"})
                self.assertFalse(output.exists(), "Read-only offline discovery must not create an output directory")
                _, source = await self.create_rc(client, output)
                before = filesystem_snapshot(output)
                invalid = [
                    {"points": 1, "signals": ["U(out)"]},
                    {"points": 10001, "signals": ["U(out)"]},
                    {"points": "not-a-number", "signals": ["U(out)"]},
                    {"signals": []}, {"signals": "U(out)"},
                    {"signals": ["U(out)"] * 31},
                ]
                for values in invalid:
                    with self.subTest(arguments=values):
                        rejected = await client.call_tool("fastmean_ac", {"path": str(source), **values})
                        self.assertTrue(rejected.is_error, repr(payload(rejected)))
                        self.assertIn("point" if "points" in values else "signal", str(payload(rejected)).lower())
                        self.assertEqual(filesystem_snapshot(output), before,
                                         "Schema rejection must happen before creating job files/directories")
                await self.call_success(client, "fastmean_status")

    async def test_preview_resources_and_persisted_results_survive_server_restart(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-mcp-preview-") as temporary:
            root = Path(temporary)
            output = root / "runs"
            missing_app = root / "not-installed"
            async with self.session(output, app_dir=missing_app) as client:
                _, source = await self.create_rc(client, output)
                source_before = source.read_bytes()
                raw = await client.call_tool("fastmean_preview", {"path": str(source)})
                self.assertFalse(raw.is_error, repr(payload(raw)))
                preview = payload(raw)
                run_id = preview["run_id"]
                images = [item for item in raw.content if getattr(item, "type", None) == "image"]
                self.assertTrue(images)
                self.assertEqual(base64.b64decode(images[0].data, validate=True)[:8], b"\x89PNG\r\n\x1a\n")
                links = {str(item.uri) for item in raw.content if getattr(item, "type", None) == "resource_link"}
                png = next(item for item in preview["artifacts"] if item["mime_type"] == "image/png")
                svg = next(item for item in preview["artifacts"] if item["mime_type"] == "image/svg+xml")
                self.assertIn(png["uri"], links)
                png_bytes = resource_bytes(await client.read_resource(png["uri"]))
                self.assertEqual(png_bytes, Path(preview["png_path"]).read_bytes())
                self.assertIn(b"<svg", resource_bytes(await client.read_resource(svg["uri"]))[:1000])
                record = json.loads(resource_bytes(await client.read_resource(preview["resource_uri"])))
                self.assertEqual(record["run_id"], run_id)
                self.assertEqual(source.read_bytes(), source_before)
                before = filesystem_snapshot(output)
            async with self.session(output, app_dir=missing_app) as restarted:
                history = await self.call_success(restarted, "fastmean_list_runs")
                self.assertIn(run_id, {item["run_id"] for item in history["runs"]})
                reopened = await restarted.call_tool("fastmean_get_result", {"run_id": run_id})
                self.assertFalse(reopened.is_error, repr(payload(reopened)))
                self.assertEqual(payload(reopened)["run_id"], run_id)
                self.assertTrue(any(getattr(item, "type", None) == "image" for item in reopened.content))
                self.assertEqual(resource_bytes(await restarted.read_resource(png["uri"])), png_bytes)
                self.assertEqual(filesystem_snapshot(output), before,
                                 "Retrieval must not republish or mutate persisted records after restart")

    @unittest.skipUnless(os.name == "nt" and NATIVE_ENABLED,
        "Set FASTMEAN_MCP_NATIVE_TEST=1 on Windows to start native FASTMEAN")
    async def test_native_ac_through_stdio_matches_rc_transfer_function(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-mcp-native-") as temporary:
            output_dir = Path(temporary)
            async with self.session(output_dir) as client:
                _, circuit = await self.create_rc(client, output_dir)
                raw_result = await client.call_tool("fastmean_ac", {
                    "path": str(circuit),
                    "signals": ["db(U(out)/U(in))", "phs(U(out)/U(in))"],
                    "fmin": 1, "fmax": 100000, "points": 21,
                })
                self.assertFalse(raw_result.is_error, f"Native AC failed: {payload(raw_result)!r}")
                result = payload(raw_result)
                self.assertIsInstance(result, dict)
                self.assertFalse(result.get("ok") is False, repr(result))
                images = [item for item in raw_result.content if getattr(item, "type", None) == "image"]
                self.assertTrue(images, "AC must return an inline MCP ImageContent, not only a PNG path")
                self.assertEqual(images[0].mime_type, "image/png")
                inline_png = base64.b64decode(images[0].data, validate=True)
                self.assertEqual(inline_png[:8], b"\x89PNG\r\n\x1a\n")
                artifacts = set(returned_paths(result))
                csv_paths = sorted(path for path in artifacts if path.suffix.lower() == ".csv")
                plot_paths = sorted(path for path in artifacts if path.suffix.lower() == ".png")
                self.assertTrue(csv_paths, f"No numeric CSV artifact returned: {result!r}")
                self.assertTrue(plot_paths, f"No PNG plot artifact returned: {result!r}")
                for path in csv_paths + plot_paths:
                    self.assertTrue(path.is_relative_to(output_dir.resolve()), str(path))
                self.assertEqual(plot_paths[0].read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

                rows = csv_numeric_rows(csv_paths[0])
                self.assertGreaterEqual(len(rows), 20)
                frequencies = [row[0] for row in rows]
                self.assertTrue(all(left < right for left, right in zip(frequencies, frequencies[1:])))
                self.assertAlmostEqual(frequencies[0], 1, delta=0.001)
                self.assertAlmostEqual(frequencies[-1], 100000, delta=100)
                # Independent physical oracle for the 1 kohm / 1 uF example.
                # Checks the actual native numerical response, including phase.
                for row in (rows[0], rows[len(rows) // 2], rows[-1]):
                    frequency, gain_db, phase_degrees = row[:3]
                    omega_tau = 2 * math.pi * frequency * 1000 * 1e-6
                    self.assertAlmostEqual(gain_db, -10 * math.log10(1 + omega_tau ** 2), delta=0.1)
                    self.assertAlmostEqual(phase_degrees, -math.degrees(math.atan(omega_tau)), delta=0.2)

                # Native data remain available beyond the bounded inline preview.
                run_id = result["run_id"]
                self.assertNotIn("rows", result)
                self.assertLessEqual(len(result["preview_rows"]), 8)
                history = await self.call_success(client, "fastmean_list_runs", {"limit": 100})
                self.assertIn(run_id, {item["run_id"] for item in history["runs"]})
                persisted_before = filesystem_snapshot(output_dir)
                reopened = await client.call_tool("fastmean_get_result", {"run_id": run_id})
                self.assertFalse(reopened.is_error, repr(payload(reopened)))
                self.assertEqual(payload(reopened)["run_id"], run_id)
                self.assertTrue(any(getattr(item, "type", None) == "image" for item in reopened.content))
                resource = json.loads(resource_bytes(await client.read_resource(result["resource_uri"])))
                self.assertEqual(resource["run_id"], run_id)
                csv_artifact = next(item for item in result["artifacts"] if item["name"] == "data.csv")
                self.assertEqual(resource_bytes(await client.read_resource(csv_artifact["uri"])), csv_paths[0].read_bytes())
                paged = []
                offset = 0
                while True:
                    page = await self.call_success(client, "fastmean_read_data",
                        {"run_id": run_id, "offset": offset, "limit": 7})
                    self.assertEqual(page["offset"], offset)
                    self.assertEqual(page["columns"], result["columns"])
                    self.assertEqual(page["returned_count"], len(page["rows"]))
                    self.assertLessEqual(len(page["rows"]), 7)
                    paged.extend(page["rows"])
                    if not page["has_more"]:
                        self.assertIsNone(page["next_offset"])
                        break
                    self.assertEqual(page["next_offset"], offset + len(page["rows"]))
                    offset = page["next_offset"]
                self.assertEqual(paged, rows)
                beyond = await self.call_success(client, "fastmean_read_data",
                    {"run_id": run_id, "offset": len(rows), "limit": 7})
                self.assertEqual(beyond["rows"], [])
                self.assertFalse(beyond["has_more"])
                self.assertIsNone(beyond["next_offset"])
                self.assertEqual(filesystem_snapshot(output_dir), persisted_before)

    @unittest.skipUnless(os.name == "nt" and NATIVE_ENABLED,
        "Set FASTMEAN_MCP_NATIVE_TEST=1 on Windows to start native FASTMEAN")
    async def test_native_transient_and_symbolic_through_stdio(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-mcp-time-symbolic-") as temporary:
            output_dir = Path(temporary)
            async with self.session(output_dir) as client:
                guide = await client.read_resource("fastmean://guide")
                guide_text = "\n".join(getattr(item, "text", "") for item in guide.contents)
                self.assertIn("FASTMEAN", guide_text.upper())
                self.assertGreater(len(guide_text), 100)

                _, original = await self.create_rc(client, output_dir)
                original_bytes = original.read_bytes()
                edited = await self.call_success(client, "fastmean_edit_values", {
                    "path": str(original),
                    "updates": {"U1": {"value": 1, "waveform": {"kind": "dc"}}},
                })
                dc_circuit = Path(edited["path"]).resolve()
                self.assertNotEqual(dc_circuit, original)
                self.assertTrue(dc_circuit.is_relative_to(output_dir.resolve()))
                self.assertTrue(dc_circuit.is_file())

                raw_transient = await client.call_tool("fastmean_transient", {
                    "path": str(dc_circuit), "signals": ["U(out)"],
                    "stop": 0.005, "step": 1e-5,
                })
                self.assertFalse(raw_transient.is_error, repr(payload(raw_transient)))
                transient = payload(raw_transient)
                self.assertIsInstance(transient, dict)
                self.assertFalse(transient.get("ok") is False, repr(transient))
                csv_paths = sorted(path for path in returned_paths(transient)
                                   if path.suffix.lower() == ".csv")
                self.assertTrue(csv_paths, f"Transient returned no numeric CSV: {transient!r}")
                self.assertTrue(csv_paths[0].is_relative_to(output_dir.resolve()))
                rows = csv_numeric_rows(csv_paths[0], min_columns=2)
                self.assertGreaterEqual(len(rows), 400)
                self.assertAlmostEqual(rows[-1][0], 0.005, delta=1e-5)
                self.assertGreater(rows[-1][1], 0)
                # Native step response of R=1 kohm, C=1 uF, source=1 V.
                self.assertAlmostEqual(rows[-1][1], 1 - math.exp(-5), delta=0.002)

                raw_symbolic = await client.call_tool("fastmean_symbolic", {
                    "path": str(original), "output": "out", "input": "in",
                })
                self.assertFalse(raw_symbolic.is_error, repr(payload(raw_symbolic)))
                symbolic = payload(raw_symbolic)
                self.assertIsInstance(symbolic, dict)
                self.assertTrue(symbolic.get("ok"), repr(symbolic))
                equations = symbolic.get("equations", [])
                self.assertTrue(equations, f"Native symbolic result has no equations: {symbolic!r}")
                self.assertTrue(any("p" in str(equation.get("expression", "")).lower()
                                    for equation in equations), repr(equations))
                transfer = symbolic.get("transfer_function", {})
                self.assertTrue(transfer.get("expression"), repr(transfer))
                self.assertEqual(transfer.get("input_parameter"), "E_U1")
                self.assertEqual(original.read_bytes(), original_bytes,
                                 "Native analysis and value edits must preserve the source SCM")
                await self.call_success(client, "fastmean_status")


if __name__ == "__main__":
    unittest.main()
