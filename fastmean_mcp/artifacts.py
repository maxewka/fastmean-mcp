"""Persistent, bounded MCP results and explicitly published job artifacts."""
from __future__ import annotations

import copy
import csv
from array import array
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from typing import Any

MAX_READ_BYTES = 8 * 1024 * 1024
MAX_CSV_BYTES = 256 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
_FORMAT = "fastmean-mcp-artifacts-v1"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_KNOWN = frozenset({"data.csv", "plot.png", "schematic.svg", "schematic.png", "circuit.scm",
    "edited.scm", "native_data.txt", "netlist.txt", "manifest.json", "run.txt", "stdout.txt",
    "stderr.txt", "native_transient.csv", "out", "cir", "human.sym", "mcp-result-full.json"})
_DECLARED = frozenset({"path", "csv_path", "plot_path", "svg_path", "png_path", "data_path",
    "native_data_path", "manifest_path", "script_path", "native_output_path", "input_path",
    "settings_path", "output_path", "stdout_path", "stderr_path", "scm_path", "circuit_path",
    "spec_path", "measurements_path", "native_transient_path", "native_transient_manifest_path",
    "native_transient_script_path", "native_transient_data_path"})
_MIMES = {".csv": "text/csv", ".png": "image/png", ".svg": "image/svg+xml",
          ".scm": "text/plain", ".json": "application/json", ".txt": "text/plain"}
_PRIORITY = frozenset({"ok", "error", "status", "code", "run_id", "resource_uri",
                      "working_dir", "cwd", "count", "truncated"}) | _DECLARED


class ArtifactError(ValueError):
    """Invalid run, unpublished artifact or unsupported artifact operation."""


class _DigestReader(io.RawIOBase):
    """Hash the bytes actually consumed, with a fixed streaming size limit."""

    def __init__(self, raw, maximum_bytes=MAX_CSV_BYTES):
        self.raw, self.digest, self.count = raw, hashlib.sha256(), 0
        self.maximum_bytes = maximum_bytes

    def readable(self):
        return True

    def readinto(self, buffer):
        count = self.raw.readinto(buffer)
        if count:
            self.count += count
            if self.count > self.maximum_bytes:
                raise ArtifactError("CSV exceeds the 256 MiB limit.")
            self.digest.update(memoryview(buffer)[:count])
        return count


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value) or value in {".", ".."}:
        raise ArtifactError(f"{label} must be a plain ASCII basename, without paths.")
    return value


def _bound(value: dict, max_bytes: int = MAX_RESPONSE_BYTES) -> dict:
    if not isinstance(value, dict):
        raise ArtifactError("A result must be a JSON object.")
    for factor in (1, 2, 4, 8):
        remaining = [max(1024, min(48 * 1024, max_bytes // 2) // factor), max(80, 1500 // factor)]
        cuts = []

        def cut(path, reason, original=None, kept=None):
            if len(cuts) < 64:
                item = {"path": path[-160:], "reason": reason}
                if original is not None: item["original"] = original
                if kept is not None: item["kept"] = kept
                cuts.append(item)

        def visit(item, path="", depth=0, list_limit=200):
            remaining[1] -= 1
            if depth > 12:
                cut(path, "depth_limit")
                return "[depth limit]"
            if isinstance(item, Path): item = str(item)
            if isinstance(item, str):
                count = min(len(item), 16 * 1024, max(0, remaining[0]))
                remaining[0] -= count
                if count < len(item): cut(path, "text_limit", len(item), count)
                return item[:count]
            if item is None or isinstance(item, bool): return item
            if isinstance(item, int):
                if item.bit_length() > 256:
                    cut(path, "integer_size")
                    return "[integer exceeds 256 bits]"
                return item
            if isinstance(item, float):
                if not math.isfinite(item):
                    cut(path, "nonfinite_number")
                    return repr(item)
                return item
            if isinstance(item, (list, tuple)):
                output = []
                for index, child in enumerate(item[:list_limit]):
                    if remaining[0] <= 0 or remaining[1] <= 0: break
                    output.append(visit(child, f"{path}[{index}]", depth + 1))
                if len(output) < len(item): cut(path, "array_limit", len(item), len(output))
                return output
            if isinstance(item, dict):
                output = {}
                # Preserve control fields and generated paths ahead of verbose
                # tables, model collections and native solver output.
                pairs = sorted(item.items(), key=lambda pair: str(pair[0]) not in _PRIORITY)
                for index, (key, child) in enumerate(pairs):
                    if index >= 200 or remaining[0] <= 0 or remaining[1] <= 0:
                        cut(path, "object_limit", len(item), len(output)); break
                    key = str(key)
                    short_key = key[:128]
                    remaining[0] -= len(short_key)
                    if short_key != key: cut(path, "key_limit", len(key), len(short_key))
                    child_path = f"{path}.{short_key}" if path else short_key
                    if key == "rows" and isinstance(child, (list, tuple)):
                        output["preview_rows"] = visit(child, child_path, depth + 1, 8)
                    else:
                        output[short_key] = visit(child, child_path, depth + 1, 8 if key == "preview_rows" else 200)
                return output
            raise ArtifactError(f"Unsupported result value type: {type(item).__name__}")

        result = visit(value)
        if cuts:
            result["truncated"] = True
            result["truncation"] = cuts
        if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) <= max_bytes:
            return result
    return {"truncated": True, "truncation": [{"path": "", "reason": "response_budget"}],
            "message": "Result exceeds the response budget; use the published artifacts."}


def bounded_result(value: dict) -> dict:
    """Bound read-only responses without writing files or creating directories."""
    return _bound(value)


def _link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _declared_paths(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _DECLARED and isinstance(child, (str, Path)):
                yield Path(child)
            elif isinstance(child, (dict, list, tuple)):
                yield from _declared_paths(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            if isinstance(child, (dict, list, tuple)):
                yield from _declared_paths(child)


def _atomic_json(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                prefix=".mcp-result-", suffix=".tmp", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, default=lambda obj: str(obj) if isinstance(obj, Path) else _unsupported(obj))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _unsupported(value):
    raise ArtifactError(f"Unsupported result value type: {type(value).__name__}")


class ArtifactStore:
    def __init__(self, root: Path):
        # Resolving an absent configured root is read-only; creation belongs to
        # the operation that produces a job, never to discovery or construction.
        self.root = Path(root).expanduser().resolve()

    def _job(self, run_id: str) -> Path:
        name = _name(run_id, "run_id")
        candidate = self.root / name
        if _link(candidate):
            raise ArtifactError("Linked job directories are not supported.")
        resolved = candidate.resolve(strict=True)
        if resolved.parent != self.root or not resolved.is_dir():
            raise ArtifactError("A run must be an existing direct child of the configured output root.")
        return resolved

    def _result_job(self, result: dict) -> Path:
        value = result.get("working_dir") or result.get("cwd")
        if not value:
            value = Path(result["path"]).parent if result.get("path") else None
        if value is None:
            raise ArtifactError("The result must identify its existing working_dir, cwd or file path.")
        raw = Path(value).expanduser()
        if _link(raw): raise ArtifactError("Linked job directories are not supported.")
        resolved = raw.resolve(strict=True)
        if resolved.parent != self.root:
            raise ArtifactError("Result artifacts must belong to one direct child job of the output root.")
        return self._job(resolved.name)

    def _file(self, job: Path, value: Path) -> Path:
        raw = value if value.is_absolute() else job / value
        if ".." in raw.parts:
            raise ArtifactError("Artifact traversal is forbidden.")
        resolved = raw.resolve(strict=True)
        if not resolved.is_relative_to(job) or resolved == job:
            raise ArtifactError("Artifact escapes its published job directory.")
        # Windows may spell the same job prefix as RUNNER~1 or runneradmin.
        # Compare resolved ancestors, but check each original component for a
        # link before resolving it. Resolving the full path alone would hide a
        # symlink/junction that points back inside the otherwise valid job.
        original = raw.absolute()
        ancestors = (original, *original.parents)
        # Use the outermost matching prefix: a link inside the job could point
        # to the output root and re-enter the same job through a second prefix.
        boundary = next((parent for parent in reversed(ancestors)
                         if parent.resolve(strict=True) == job), None)
        if boundary is None:
            raise ArtifactError("Artifact has no matching job directory.")
        for current in ancestors:
            if _link(current):
                raise ArtifactError("Linked artifacts are not supported.")
            if current == boundary:
                break
        if not resolved.is_file(): raise ArtifactError("Artifact is not a regular file.")
        if resolved.suffix.lower() not in _MIMES and resolved.name not in {"out", "cir", "human.sym"}:
            raise ArtifactError("Unsupported artifact file format.")
        if len(resolved.relative_to(job).as_posix()) > 256:
            raise ArtifactError("Artifact relative path is too long.")
        return resolved

    def _catalog(self, job: Path, result: dict) -> list[dict]:
        candidates = [job / name for name in sorted(_KNOWN)]
        candidates.extend(_declared_paths(result))
        seen, names, catalog = set(), set(), []
        for candidate in candidates:
            try:
                path = self._file(job, candidate)
                if path in seen: continue
                name = _name(path.name, "artifact name")
            except (ArtifactError, OSError, ValueError):
                continue
            seen.add(path)
            if name in names:
                base, suffix = path.stem, path.suffix
                counter = 2
                while True:
                    marker = f"-{counter}"
                    name = f"{base[:128 - len(suffix) - len(marker)]}{marker}{suffix}"
                    if name not in names: break
                    counter += 1
                name = _name(name, "artifact name")
            names.add(name)
            size = path.stat().st_size
            item = {"name": name, "uri": f"fastmean://artifacts/{job.name}/{name}",
                    "mime_type": _MIMES.get(path.suffix.lower(), "text/plain"), "size": size,
                    "relative_path": path.relative_to(job).as_posix()}
            if size <= MAX_READ_BYTES:
                item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            elif path.suffix.lower() == ".csv" and size <= MAX_CSV_BYTES:
                # Paged data must retain the same integrity guarantee as small
                # resource reads, without loading a whole large table in RAM.
                with path.open("rb") as raw, io.BufferedReader(_DigestReader(raw)) as stream:
                    while stream.read(1024 * 1024):
                        pass
                    item["sha256"] = stream.raw.digest.hexdigest()
                    if stream.raw.count != size:
                        raise ArtifactError("CSV changed during publication.")
            catalog.append(item)
            if len(catalog) >= 100: break
        return catalog

    def publish(self, result: dict) -> dict:
        if not isinstance(result, dict): raise ArtifactError("A result must be a JSON object.")
        job = self._result_job(result)
        _atomic_json(job / "mcp-result-full.json", result)
        catalog = self._catalog(job, result)
        for budget in (MAX_RESPONSE_BYTES // 3, 16 * 1024, 4096):
            record = _bound(result, budget)
            record.update({"record_format": _FORMAT, "run_id": job.name,
                "resource_uri": f"fastmean://runs/{job.name}", "artifacts": catalog,
                # Keep the validated declarations even when a large preceding
                # payload caused their source fields to be trimmed. These are
                # relative paths established by _catalog, never caller paths
                # accepted by the read API.
                "published_artifact_paths": [item["relative_path"] for item in catalog],
                "published_utc": datetime.now(timezone.utc).isoformat()})
            if len(json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8")) <= MAX_RESPONSE_BYTES:
                break
        else:
            raise ArtifactError("Artifact catalog exceeds the response budget.")
        _atomic_json(job / "mcp-result.json", record)
        return copy.deepcopy(record)

    def get_run(self, run_id: str) -> dict:
        job = self._job(run_id)
        record_path = job / "mcp-result.json"
        if _link(record_path) or not record_path.is_file() or record_path.stat().st_size > MAX_RESPONSE_BYTES:
            raise ArtifactError("Run has no recognized bounded result record.")
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ArtifactError("Run result record is unreadable.") from error
        if not isinstance(record, dict) or record.get("record_format") != _FORMAT or record.get("run_id") != run_id or record.get("resource_uri") != f"fastmean://runs/{run_id}" or not isinstance(record.get("artifacts"), list) or len(record["artifacts"]) > 100:
            raise ArtifactError("Run has no recognized result record.")
        names = set()
        for entry in record["artifacts"]:
            if not isinstance(entry, dict):
                raise ArtifactError("Run has an invalid artifact catalog entry.")
            name = _name(entry.get("name"), "artifact name")
            relative, size, digest = entry.get("relative_path"), entry.get("size"), entry.get("sha256")
            if (name in names or entry.get("uri") != f"fastmean://artifacts/{run_id}/{name}"
                    or not isinstance(relative, str) or not relative or len(relative) > 256
                    or "\\" in relative or "\x00" in relative or PureWindowsPath(relative).drive
                    or any(part in {"", ".", ".."} for part in relative.split("/"))
                    or isinstance(size, bool) or not isinstance(size, int) or not 0 <= size < 2 ** 63
                    or ("sha256" in entry and (not isinstance(digest, str)
                        or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)))):
                raise ArtifactError("Run has an invalid artifact catalog entry.")
            suffix, basename = Path(relative).suffix.lower(), Path(relative).name
            if ((suffix not in _MIMES and basename not in {"out", "cir", "human.sym"})
                    or entry.get("mime_type") != _MIMES.get(suffix, "text/plain")):
                raise ArtifactError("Run has an invalid artifact catalog MIME type or file format.")
            names.add(name)
        return record

    def list_runs(self, limit: int = 20) -> dict:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ArtifactError("limit must be an integer from 1 to 100.")
        if not self.root.exists(): return {"runs": [], "count": 0, "truncated": False}
        records = []
        for child in self.root.iterdir():
            try:
                if not child.is_dir() or _link(child): continue
                record = self.get_run(child.name)
            except (ArtifactError, OSError): continue
            records.append({key: record[key] for key in ("run_id", "resource_uri", "published_utc", "analysis", "origin", "ok") if key in record})
        records.sort(key=lambda item: str(item.get("published_utc", "")), reverse=True)
        return bounded_result({"count": len(records), "truncated": len(records) > limit, "runs": records[:limit]})

    def _artifact(self, run_id: str, name: str) -> tuple[Path, dict, dict]:
        name = _name(name, "artifact name")
        record = self.get_run(run_id)
        entry = next((item for item in record["artifacts"] if isinstance(item, dict) and item.get("name") == name), None)
        if entry is None: raise ArtifactError("Artifact was not published for this run.")
        job = self._job(run_id)
        relative = entry.get("relative_path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ArtifactError("Invalid artifact catalog path.")
        path = self._file(job, Path(relative))
        # Re-establish authorization from the recorded result, not only from a
        # catalog entry: an unrelated file with an allowed suffix is insufficient.
        declared = set()
        for value in _declared_paths(record):
            try: declared.add(self._file(job, value))
            except (ArtifactError, OSError, ValueError): pass
        published_paths = record.get("published_artifact_paths", [])
        persisted_declaration = (isinstance(published_paths, list)
                                 and relative in published_paths)
        if not (path.parent == job and path.name in _KNOWN) and path not in declared and not persisted_declaration:
            raise ArtifactError("Artifact is not a known or explicitly declared result file.")
        if path.stat().st_size != entry.get("size"):
            raise ArtifactError("Artifact changed after publication.")
        return path, entry, record

    def read_artifact(self, run_id: str, name: str) -> bytes:
        path, entry, _ = self._artifact(run_id, name)
        if path.stat().st_size > MAX_READ_BYTES:
            raise ArtifactError("Artifact exceeds 8 MiB; use paged CSV data or its local file.")
        data = path.read_bytes()
        if len(data) > MAX_READ_BYTES: raise ArtifactError("Artifact exceeds 8 MiB.")
        if entry.get("sha256") and hashlib.sha256(data).hexdigest() != entry["sha256"].lower():
            raise ArtifactError("Artifact changed after publication.")
        return data

    def read_data(self, run_id: str, offset: int = 0, limit: int = 200) -> dict:
        if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 1000000:
            raise ArtifactError("offset must be an integer from 0 to 1000000.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ArtifactError("limit must be an integer from 1 to 500.")
        record = self.get_run(run_id)
        primary = "spectrum.csv" if record.get("analysis") == "spectrum" else "data.csv"
        choices = sorted((item for item in record["artifacts"] if isinstance(item, dict)
                          and str(item.get("name", "")).lower().endswith(".csv")
                          and (record.get("analysis") != "spectrum" or item.get("name") == primary)),
                         key=lambda item: (item["name"] != primary, item["name"]))
        if not choices: raise ArtifactError("Run has no published CSV data.")
        path, entry, _ = self._artifact(run_id, choices[0]["name"])
        if entry["size"] > MAX_CSV_BYTES:
            raise ArtifactError("CSV exceeds the 256 MiB limit.")
        expected_hash = entry.get("sha256")
        if expected_hash is None and entry["name"] == primary:
            # Older releases omitted catalog hashes above 8 MiB, but the
            # authenticated native manifest still carries the original digest.
            try:
                manifest = json.loads(self.read_artifact(run_id, "manifest.json").decode("utf-8"))
                if isinstance(manifest, dict):
                    expected_hash = manifest.get("csv_sha256")
            except (ArtifactError, OSError, UnicodeError, json.JSONDecodeError) as error:
                raise ArtifactError("CSV has no readable publication SHA256 provenance.") from error
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
            raise ArtifactError("CSV has no recognized publication SHA256 provenance.")
        rows, more, byte_count = [], False, 0
        try:
            with path.open("rb") as raw, io.TextIOWrapper(io.BufferedReader(_DigestReader(raw)),
                    encoding="utf-8-sig", newline="") as stream:
                if os.fstat(raw.fileno()).st_size != entry["size"]:
                    raise ArtifactError("Artifact changed after publication.")
                reader = csv.reader(stream)
                header = next(reader, None)
                if not header or len(header) > 64 or len(set(header)) != len(header) or any(not item for item in header) or sum(len(item.encode("utf-8")) for item in header) > 8192:
                    raise ArtifactError("CSV has an invalid or oversized column header.")
                for index, raw in enumerate(reader):
                    if len(raw) != len(header): raise ArtifactError(f"CSV row {index + 1} has the wrong column count.")
                    try: row = [float(item) for item in raw]
                    except ValueError as error: raise ArtifactError(f"CSV row {index + 1} is not numeric.") from error
                    if not all(math.isfinite(item) for item in row): raise ArtifactError(f"CSV row {index + 1} has a nonfinite number.")
                    if index < offset: continue
                    row_bytes = len(json.dumps(row).encode("ascii")) + 1
                    if len(rows) >= limit or byte_count + row_bytes > 96 * 1024:
                        more = True; break
                    rows.append(row); byte_count += row_bytes
                # TextIOWrapper may have decoded bytes ahead of the requested
                # page; those are already hashed. Drain the remaining binary
                # stream without parsing or retaining unrequested rows.
                while stream.buffer.read(1024 * 1024):
                    pass
                hashed = stream.buffer.raw
                digest, bytes_read = hashed.digest.hexdigest(), hashed.count
                if bytes_read != entry["size"] or digest != expected_hash.lower():
                    raise ArtifactError("CSV SHA256 changed after publication.")
        except (OSError, UnicodeError, csv.Error) as error:
            raise ArtifactError(f"Could not read numeric CSV data: {error}") from error
        return {"run_id": run_id, "columns": header, "rows": rows, "offset": offset,
                "limit": limit, "returned_count": len(rows), "has_more": more,
                "next_offset": offset + len(rows) if more else None,
                "csv_artifact": entry["name"], "resource_uri": entry["uri"], "csv_sha256": digest}

    def _verified_source(self, run_id: str, name: str, expected_hash: str) -> dict:
        """Authenticate a fixed, already-published transform-source artifact."""
        path, entry, _ = self._artifact(run_id, name)
        if entry["relative_path"] != name:
            raise ArtifactError("Analysis source must be its fixed registered job artifact.")
        if entry["size"] > MAX_CSV_BYTES:
            raise ArtifactError("Analysis source exceeds the 256 MiB limit.")
        with path.open("rb") as raw, io.BufferedReader(_DigestReader(raw)) as stream:
            if os.fstat(raw.fileno()).st_size != entry["size"]:
                raise ArtifactError("Analysis source changed after publication.")
            while stream.read(1024*1024):
                pass
            digest, size = stream.raw.digest.hexdigest(), stream.raw.count
        if (size != entry["size"] or digest != expected_hash.lower()
                or entry.get("sha256") and digest != entry["sha256"].lower()):
            raise ArtifactError("Analysis source SHA256 changed after publication.")
        return {"artifact": name, "resource_uri": entry["uri"], "sha256": digest}

    def load_native_data(self, run_id: str) -> dict:
        """Read a verified registered numeric table for internal replotting.

        Each analysis has a fixed table filename. Frequency transforms retain
        an authenticated native source artifact as well as the plotted CSV.
        This does not expose arbitrary paths or enlarge the resource-read limit.
        """
        record = self.get_run(run_id)
        analysis = record.get("analysis")
        if analysis not in {"ac", "transient", "native_fft", "spectrum"}:
            raise ArtifactError("Select an original native AC/transient/FFT or registered spectrum run, not a preview or plot run.")
        manifest = json.loads(self.read_artifact(run_id, "manifest.json").decode("utf-8"))
        if (not isinstance(manifest, dict) or manifest.get("status") != "completed"
                or manifest.get("analysis") != analysis
                or not isinstance(manifest.get("engine"), dict)
                or manifest["engine"].get("name") != "FASTMEAN native CLI"):
            raise ArtifactError("Run has no completed native FASTMEAN data manifest.")
        primary = "spectrum.csv" if analysis == "spectrum" else "data.csv"
        source_key = "native_transient_csv_sha256" if analysis == "spectrum" else "native_data_sha256"
        expected_hash, native_hash = manifest.get("csv_sha256"), manifest.get(source_key)
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value)
               for value in (expected_hash, native_hash)):
            raise ArtifactError("Analysis manifest has no recognized CSV/native-source SHA256 provenance.")
        native_source = None
        if analysis in {"native_fft", "spectrum"}:
            if (not isinstance(manifest.get("source_sha256"), str)
                    or not re.fullmatch(r"[0-9a-fA-F]{64}", manifest["source_sha256"])):
                raise ArtifactError("Frequency analysis has no recognized source-SCM SHA256 provenance.")
            native_source = self._verified_source(run_id,
                "native_transient.csv" if analysis == "spectrum" else "native_data.txt", native_hash)
        path, entry, _ = self._artifact(run_id, primary)
        if entry["relative_path"] != primary:
            raise ArtifactError("Analysis CSV must be its fixed registered job artifact.")
        frequency = analysis != "transient"
        maximum_rows = 10000 if analysis == "ac" else 262145 if frequency else 1000001
        if path.stat().st_size > MAX_CSV_BYTES:
            raise ArtifactError("Analysis CSV exceeds the 256 MiB limit.")
        try:
            with path.open("rb") as raw:
                if os.fstat(raw.fileno()).st_size != entry["size"]:
                    raise ArtifactError("Artifact changed after publication.")
                hashed = _DigestReader(raw)
                with io.TextIOWrapper(io.BufferedReader(hashed), encoding="utf-8-sig", newline="") as stream:
                    reader = csv.reader(stream)
                    header = next(reader, None)
                    expected_axis = "f" if frequency else "t"
                    if (not header or not 2 <= len(header) <= 31 or header[0] != expected_axis
                            or len(set(header)) != len(header)
                            or any(not item or len(item) > 512 for item in header)
                            or sum(len(item.encode("utf-8")) for item in header) > 32768
                            or header != manifest.get("columns")):
                        raise ArtifactError("Analysis CSV has invalid, duplicate or mismatched columns.")
                    values = [array("d") for _ in header]
                    count, previous, repeated = 0, None, 0
                    for row in reader:
                        count += 1
                        if count > maximum_rows:
                            raise ArtifactError("Analysis CSV exceeds its analysis row limit.")
                        if len(row) != len(header):
                            raise ArtifactError(f"CSV row {count} has the wrong column count.")
                        numbers = [float(item) for item in row]
                        if not all(math.isfinite(item) for item in numbers):
                            raise ArtifactError(f"CSV row {count} contains nonfinite values.")
                        if ((previous is not None and (numbers[0] < previous
                                or frequency and numbers[0] == previous))
                                or numbers[0] < 0 or analysis == "ac" and numbers[0] == 0):
                            raise ArtifactError("CSV axis must be nondecreasing for transient data and strictly increasing for frequency data; only AC excludes zero.")
                        if previous is not None and numbers[0] == previous:
                            repeated += 1
                        previous = numbers[0]
                        for column, number in zip(values, numbers):
                            column.append(number)
                    digest, bytes_read = hashed.digest.hexdigest(), hashed.count
            if digest != expected_hash.lower() or entry.get("sha256") and digest != entry["sha256"].lower():
                raise ArtifactError("Native CSV SHA256 changed after publication.")
            if bytes_read != entry["size"] or count != manifest.get("row_count") or count < 2:
                raise ArtifactError("Analysis CSV size or row count disagrees with its manifest.")
            if values[0][-1] <= values[0][0]:
                raise ArtifactError("Analysis CSV axis must span a positive interval.")
        except (OSError, UnicodeError, csv.Error, ValueError, TypeError) as error:
            if isinstance(error, ArtifactError):
                raise
            raise ArtifactError(f"Could not read verified analysis CSV data: {error}") from error
        origin = ("NumPy rFFT/PSD derived from native FASTMEAN transient samples; not native FFT"
                  if analysis == "spectrum" else "Native FASTMEAN FFT numeric export"
                  if analysis == "native_fft" else "Native FASTMEAN numeric export")
        provenance = {"source_run_id": run_id, "source_resource_uri": record["resource_uri"],
            "analysis_kind": analysis, "data_origin": origin,
            "csv_resource_uri": entry["uri"], "csv_sha256": digest,
            source_key: native_hash.lower(), "source_sha256": manifest.get("source_sha256"),
            "engine": {key: value for key, value in manifest["engine"].items() if key in {"name", "sha256"}},
            "axis_ordering": "strictly_increasing" if frequency else "nondecreasing",
            "repeated_timestamp_rows": repeated, "exported_row_order_preserved": True,
            "native_row_order_preserved": analysis != "spectrum",
            "simultaneous_samples": "not applicable to frequency bins" if frequency else "retained in native order; zero-duration intervals contribute no integral",
            "native_request": manifest.get("request", {})}
        if native_source is not None:
            provenance["verified_native_source"] = native_source
        if analysis == "spectrum":
            provenance["transform"] = {"name": "NumPy rFFT/PSD", "sampling": manifest.get("sampling", {})}
        return {"columns": header, "values": values, "row_count": count,
                "analysis": analysis, "request": manifest.get("request", {}),
                "data_origin": origin, "provenance": provenance}
