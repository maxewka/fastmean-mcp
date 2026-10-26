"""Register one MCP server without reserializing unrelated Codex configuration.

The official CLI generates the transport in an isolated CODEX_HOME. Only the
fastmean tables are replaced in the real file. Unrelated TOML bytes, empty
arrays, comments, and settings survive unchanged. No credentials are printed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, time, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
from uuid import uuid4


class ConfigError(ValueError):
    pass


def _parse(text: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Codex configuration is not valid TOML: {error}") from error


def _probe_path(value, path=()):
    if isinstance(value, dict):
        if value.get("__fastmean_header_probe__") is True:
            return path
        for key, child in value.items():
            found = _probe_path(child, path + (key,))
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _probe_path(child, path)
            if found is not None:
                return found
    return None


def table_headers(text: str) -> list[tuple[int, tuple[str, ...]]]:
    """Find real table headers, excluding apparent headers in TOML strings."""
    headers, offset, mode = [], 0, None
    for line in text.splitlines(keepends=True):
        if mode is None and re.match(r"^\s*\[", line):
            try:
                parsed = tomllib.loads(line + "\n__fastmean_header_probe__ = true\n")
                path = _probe_path(parsed)
            except tomllib.TOMLDecodeError:
                path = None
            if path:
                headers.append((offset, path))
                offset += len(line)
                continue
        at = 0
        while at < len(line):
            char = line[at]
            if mode in ('"""', "'''"):
                if mode == '"""' and char == "\\":
                    at += 2
                elif line.startswith(mode, at):
                    quote = mode[0]
                    while at < len(line) and line[at] == quote:
                        at += 1
                    mode = None
                else:
                    at += 1
            elif mode in ('"', "'"):
                if mode == '"' and char == "\\":
                    at += 2
                elif char == mode:
                    mode = None
                    at += 1
                else:
                    at += 1
            elif char == "#":
                break
            elif line.startswith('"""', at) or line.startswith("'''", at):
                mode = line[at:at + 3]
                at += 3
            elif char in ('"', "'"):
                mode = char
                at += 1
            else:
                at += 1
        offset += len(line)
    return headers


def _server(document: dict) -> dict | None:
    servers = document.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ConfigError("mcp_servers must be a TOML table.")
    entry = servers.get("fastmean")
    if entry is not None and not isinstance(entry, dict):
        raise ConfigError("mcp_servers.fastmean must be a TOML table.")
    return entry


def _without_server(document: dict) -> dict:
    result = deepcopy(document)
    servers = result.get("mcp_servers")
    if isinstance(servers, dict):
        servers.pop("fastmean", None)
        if not servers:
            result.pop("mcp_servers", None)
    return result


def _scalar(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_scalar(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(_scalar(str(key)) + " = " + _scalar(child)
                                 for key, child in value.items()) + " }"
    raise ConfigError(f"Cannot safely serialize fastmean setting type {type(value).__name__}.")


def _server_text(entry: dict) -> str:
    lines = []
    def table(path: tuple[str, ...], mapping: dict):
        lines.append("[" + ".".join(_scalar(part) for part in path) + "]")
        for key, value in mapping.items():
            if not isinstance(value, dict):
                lines.append(_scalar(str(key)) + " = " + _scalar(value))
        lines.append("")
        for key, value in mapping.items():
            if isinstance(value, dict):
                table(path + (str(key),), value)
    table(("mcp_servers", "fastmean"), entry)
    return "\n".join(lines).rstrip() + "\n"


def merge_server(original: bytes, entry: dict | None) -> bytes:
    """Replace/remove one ordinary table, proving other parsed values survive."""
    try:
        text = original.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ConfigError("Codex config.toml must be UTF-8; no changes were made.") from error
    before = _parse(text)
    previous = _server(before)
    headers = table_headers(text)
    target = lambda path: len(path) >= 2 and path[:2] == ("mcp_servers", "fastmean")
    if previous is not None and not any(target(path) for _, path in headers):
        raise ConfigError("fastmean uses inline/dotted TOML syntax. Convert it to [mcp_servers.fastmean] before installing; no unrelated config was rewritten.")
    kept = [text[:headers[0][0]]] if headers else [text]
    for index, (start, path) in enumerate(headers):
        end = headers[index + 1][0] if index + 1 < len(headers) else len(text)
        if not target(path):
            kept.append(text[start:end])
    merged = "".join(kept)
    if entry is not None:
        newline = "\r\n" if "\r\n" in text else "\n"
        if merged and not merged.endswith(("\n", "\r")):
            merged += newline
        if merged and not merged.endswith(newline * 2):
            merged += newline
        merged += _server_text(entry).replace("\n", newline)
    after = _parse(merged)
    if _without_server(before) != _without_server(after) or _server(after) != entry:
        raise ConfigError("Refusing a config edit that changes unrelated settings or fails server validation.")
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    return bom + merged.encode("utf-8")


@contextmanager
def _locked_existing(path: Path):
    """Deny concurrent Windows writers while replacing an existing config."""
    if os.name != "nt":
        yield
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 1 | 4, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ConfigError("Codex config is busy or not writable. Retry after other configuration edits finish.")
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


def _replace_config(path: Path, expected: bytes, replacement: bytes, existed: bool) -> None:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ConfigError("Codex config.toml is a link. Review/edit its real file explicitly; no link was replaced.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".fastmean-" + uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(replacement)
        if existed:
            with _locked_existing(path):
                if path.read_bytes() != expected:
                    raise ConfigError("Codex configuration changed during installation; no settings were overwritten. Retry.")
                if os.name == "nt":
                    # Flags zero preserve original ACLs/attributes; never use
                    # IGNORE_ACL_ERRORS. Official Microsoft ReplaceFileW API.
                    import ctypes
                    from ctypes import wintypes
                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel.ReplaceFileW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                        wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
                    kernel.ReplaceFileW.restype = wintypes.BOOL
                    if not kernel.ReplaceFileW(str(path), str(temporary), None, 0, None, None):
                        raise ctypes.WinError(ctypes.get_last_error())
                else:
                    os.chmod(temporary, path.stat().st_mode & 0o777)
                    os.replace(temporary, path)
        else:
            with path.open("xb") as stream:
                stream.write(replacement)
    finally:
        temporary.unlink(missing_ok=True)


def _backup(state_dir: Path, original: bytes, operation: str) -> Path:
    directory = state_dir / "config-backups"
    if directory.is_symlink() or (hasattr(directory, "is_junction") and directory.is_junction()) or not directory.resolve().is_relative_to(state_dir.resolve()):
        raise ConfigError("Private backup directory resolves outside the owned installation; no backup/config write was made.")
    directory.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + uuid4().hex[:8]
    path = directory / (name + "_" + operation + ".toml")
    with path.open("xb") as stream:
        stream.write(original)
    return path


def register(codex: Path, config_home: Path, python: Path, app_dir: Path,
             output_dir: Path, state_dir: Path, replace_existing: bool = False) -> dict:
    config = config_home / "config.toml"
    existed = config.exists()
    original = config.read_bytes() if existed else b""
    old = _server(_parse(original.decode("utf-8-sig")))
    old_args = old.get("args", []) if old else []
    ours = isinstance(old_args, list) and any(old_args[i:i + 2] == ["-m", "fastmean_mcp"]
                                                for i in range(max(0, len(old_args) - 1)))
    if old is not None and not ours and not replace_existing:
        raise ConfigError("A different 'fastmean' MCP entry already exists. Review it and pass -ReplaceExisting only if replacing it is intended.")
    state_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="config-stage-", dir=state_dir) as temporary:
        staging = Path(temporary)
        environment = dict(os.environ, CODEX_HOME=str(staging))
        command = [str(codex), "mcp", "add", "fastmean",
                   "--env", "FASTMEAN_APP_DIR=" + str(app_dir),
                   "--env", "FASTMEAN_OUTPUT_DIR=" + str(output_dir),
                   "--env", "PYTHONUTF8=1", "--", str(python), "-X", "utf8", "-m", "fastmean_mcp"]
        result = subprocess.run(command, cwd=staging, env=environment, capture_output=True, timeout=30)
        if result.returncode:
            raise ConfigError("codex mcp add failed in the private staging configuration: " + result.stderr.decode("utf-8", errors="replace")[-2000:])
        generated = _server(_parse((staging / "config.toml").read_text(encoding="utf-8-sig")))
        if not generated or generated.get("command") != str(python):
            raise ConfigError("Codex CLI generated an unexpected MCP configuration; actual config was not changed.")
    entry = deepcopy(old) if ours else {}
    if not isinstance(entry.get("env", {}), dict):
        raise ConfigError("Existing fastmean.env is not a TOML table; review it before upgrading.")
    entry.update({"command": generated["command"], "args": generated["args"]})
    entry["env"] = {**entry.get("env", {}), **generated.get("env", {})}
    entry.setdefault("startup_timeout_sec", 30)
    entry.setdefault("tool_timeout_sec", 90)
    replacement = merge_server(original, entry)
    backup = None
    if replacement != original:
        backup = _backup(state_dir, original, "install")
        _replace_config(config, original, replacement, existed)
    return {"status": "registered" if replacement != original else "unchanged",
            "config_path": str(config), "backup_path": str(backup) if backup else None,
            "command": str(python), "args": entry["args"],
            "config_sha256": hashlib.sha256(replacement).hexdigest()}


def remove(config_home: Path, python: Path, state_dir: Path) -> dict:
    config = config_home / "config.toml"
    if not config.is_file():
        return {"status": "already_absent", "config_path": str(config)}
    original = config.read_bytes()
    entry = _server(_parse(original.decode("utf-8-sig")))
    if entry is None:
        return {"status": "already_absent", "config_path": str(config)}
    actual = Path(entry.get("command", "")).resolve(strict=False)
    expected = python.resolve(strict=False)
    if actual != expected or entry.get("args") != ["-X", "utf8", "-m", "fastmean_mcp"]:
        raise ConfigError("The current fastmean entry no longer points to this installation. It was preserved; review it before uninstalling.")
    replacement = merge_server(original, None)
    backup = _backup(state_dir, original, "uninstall")
    _replace_config(config, original, replacement, True)
    return {"status": "removed", "config_path": str(config), "backup_path": str(backup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["register", "remove"])
    parser.add_argument("--config-home", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--codex", type=Path)
    parser.add_argument("--app-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "register":
            if not all((args.codex, args.app_dir, args.output_dir)):
                parser.error("register requires --codex, --app-dir and --output-dir")
            result = register(args.codex, args.config_home, args.python, args.app_dir,
                              args.output_dir, args.state_dir, args.replace_existing)
        else:
            result = remove(args.config_home, args.python, args.state_dir)
        print(json.dumps(result, ensure_ascii=False))
    except (ConfigError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"FASTMEAN MCP configuration error: {error}\n")


if __name__ == "__main__":
    main()
