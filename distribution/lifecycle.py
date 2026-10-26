"""User-level Windows installation lifecycle; standard Python, no shell eval."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4

import manage_config

OWNER = "fastmean-mcp-local"
TOOLS = ("lifecycle.py", "manage_config.py", "probe.py", "doctor.py", "uninstall.py",
         "common.ps1", "doctor.ps1", "uninstall.ps1")


class InstallError(ValueError):
    pass


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def full(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def within(path: Path, parent: Path) -> bool:
    return full(path).is_relative_to(full(parent))


def no_reparse(path: Path) -> None:
    # Check the textual path before resolve(), which would hide a junction.
    candidate = Path(os.path.abspath(Path(path).expanduser()))
    if str(candidate).startswith(("\\\\", "//")):
        raise InstallError("Choose a local installation directory, not a network share.")
    for item in (candidate, *candidate.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise InstallError(f"Refusing installation/removal through a symlink or junction: {item}")


def default_root() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise InstallError("LOCALAPPDATA is missing. Use a normal Windows user session.")
    return full(Path(value) / "FastmeanMCP")


def require_windows() -> None:
    if os.name != "nt":
        raise InstallError("FASTMEAN native integration requires Windows.")


def find_app(explicit: str | Path | None) -> Path:
    selected = explicit or os.environ.get("FASTMEAN_APP_DIR")
    candidates = [full(selected)] if selected else [Path(os.environ.get("LOCALAPPDATA", "")) / name
                                                   for name in ("FASTMEAN 6.1", "FASTMEAN 6.0")]
    for candidate in candidates:
        if (candidate / "Fastmean.exe").is_file():
            return full(candidate)
    raise InstallError("Install a separately licensed FASTMEAN 6.1/6.0 first, then pass --app-dir \"C:\\path\\FASTMEAN\". Proprietary binaries are never downloaded.")


def find_python(explicit: str | Path | None = None) -> Path:
    candidate = full(explicit or sys.executable)
    code = "import json,sys,venv; print(json.dumps({'version':list(sys.version_info[:3]),'exe':sys.executable}))"
    try:
        result = subprocess.run([str(candidate), "-X", "utf8", "-I", "-c", code],
                                capture_output=True, timeout=15, check=True)
        info = json.loads(result.stdout)
        if tuple(info["version"]) >= (3, 12):
            return full(info["exe"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    raise InstallError("Python 3.12+ with venv is required. Use py -3.12 distribution/install.py or pass --python C:\\path\\python.exe. No Python, PATH or execution-policy changes are made automatically.")


def find_codex(explicit: str | Path | None = None) -> Path:
    if explicit:
        candidate = full(explicit)
        if candidate.is_file():
            return candidate
        raise InstallError(f"Codex CLI was not found: {candidate}")
    located = shutil.which("codex.exe") or shutil.which("codex")
    if located:
        return full(located)
    directory = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    candidates = list(directory.glob("*/codex.exe"))
    if candidates:
        return full(max(candidates, key=lambda path: path.stat().st_mtime))
    raise InstallError("Install/open Codex first, or pass --codex-path C:\\path\\codex.exe. No global package or PATH changes are made.")


def read_state(root: Path) -> dict | None:
    path = root / "install-state.json"
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(state, dict) or state.get("owner") != OWNER or full(state.get("install_root", "")) != full(root):
        raise InstallError(f"Unrecognized installation ownership marker: {path}")
    return state


def write_state(root: Path, state: dict) -> None:
    temporary = root / ("install-state." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, root / "install-state.json")
    finally:
        temporary.unlink(missing_ok=True)


def protect_private(root: Path) -> None:
    """Set a private DACL on this owned folder only, never on Windows folders."""
    no_reparse(root)
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        root.chmod(0o700)
        return
    import ctypes
    from ctypes import wintypes
    whoami = Path(os.environ["SystemRoot"]) / "System32" / "whoami.exe"
    identity = subprocess.run([str(whoami), "/user", "/fo", "csv", "/nh"],
                              capture_output=True, timeout=10, check=True)
    match = re.search(rb"S-1-\d+(?:-\d+)+", identity.stdout)
    if not match:
        raise InstallError("Cannot determine current Windows user SID for private backup permissions.")
    sid = match.group().decode("ascii")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
    advapi.SetFileSecurityW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    descriptor = wintypes.LPVOID()
    sddl = f"D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)"
    if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not advapi.SetFileSecurityW(str(root), 4 | 0x80000000, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


@contextmanager
def installation_lock(root: Path):
    with (root / "install.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise InstallError("Another installer/uninstaller owns this directory. Wait for it to finish.") from error
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _run_logged(command: list[str], root: Path, label: str, timeout: int) -> None:
    log = root / "install.log"
    print(f"{label}. Private log: {log}", flush=True)
    with log.open("ab") as stream:
        stream.write(("\n" + utc() + " " + label + "\n").encode())
        with subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT) as process:
            try:
                code = process.wait(timeout=timeout)
            except BaseException as error:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
                if isinstance(error, subprocess.TimeoutExpired):
                    raise InstallError(f"{label} timed out. Its owned process was stopped; inspect {log} and retry.") from error
                raise
    if code:
        raise InstallError(f"{label} failed with exit code {code}. Inspect the private log {log}, fix the reported prerequisite/dependency error, and rerun.")


def install(args: argparse.Namespace) -> dict:
    require_windows()
    root_input = Path(args.install_dir) if args.install_dir else default_root()
    no_reparse(root_input)
    root = full(root_input)
    if root == Path(root.anchor):
        raise InstallError("Choose a dedicated user directory, not a drive root.")
    app = find_app(args.app_dir)
    output = full(args.output_dir or root / "results")
    if not str(output).isascii():
        raise InstallError("Original FASTMEAN batch requires an ASCII output path. Pass --output-dir with a writable ASCII directory; Russian source names remain supported.")
    if within(root, app) or within(app, root) or within(output, app):
        raise InstallError("Keep the MCP installation/results and proprietary FASTMEAN installation in separate directories.")
    if output.exists() and not output.is_dir():
        raise InstallError("Output directory already exists as a file.")
    home = full(args.codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    for name in ("venv", "tools", "config-backups"):
        if within(output, root / name) or within(home, root / name):
            raise InstallError(f"Output/Codex configuration cannot be inside the owned {name} directory.")
    previous = read_state(root)
    if previous is None and root.exists() and any(root.iterdir()):
        raise InstallError(f"Install directory is not empty and has no ownership marker: {root}. Choose an empty dedicated directory.")
    python = find_python(args.python)
    codex = find_codex(args.codex_path)
    package = full(args.package_path or Path(__file__).resolve().parent.parent)
    if not ((package / "pyproject.toml").is_file() or (package.is_file() and package.suffix.lower() == ".whl")):
        raise InstallError("--package-path must be the reviewed project folder or a local release .whl file.")
    venv = root / "venv"
    venv_python = venv / "Scripts" / "python.exe"
    no_reparse(venv_python)
    package_command = [str(venv_python), "-X", "utf8", "-m", "pip", "install", "--upgrade",
                       "--disable-pip-version-check", "--no-warn-script-location", str(package)]
    plan = {"action": "install_or_upgrade", "app_dir": str(app), "base_python": str(python),
            "install_root": str(root), "venv_python": str(venv_python), "package_path": str(package),
            "output_dir": str(output), "codex": str(codex), "codex_config": str(home / "config.toml"),
            "package_command": package_command, "config_handling": "CLI in isolated staging; only fastmean tables merged; unrelated bytes preserved",
            "windows_settings_changed": False, "proprietary_binaries_downloaded": False}
    if args.dry_run:
        return plan
    protect_private(root)
    with installation_lock(root):
        # Recheck after locking; another completed operation may have changed it.
        previous = read_state(root)
        created_output = not output.exists()
        output.mkdir(parents=True, exist_ok=True)
        state = {"schema_version": 1, "owner": OWNER,
                 "install_id": previous.get("install_id") if previous else uuid4().hex,
                 "status": "installing", "install_root": str(root), "base_python": str(python),
                 "venv_python": str(venv_python), "app_dir": str(app), "output_dir": str(output),
                 "results_owned": bool((previous or {}).get("results_owned")) or (created_output and output == root / "results"),
                 "codex_path": str(codex), "codex_home": str(home), "package_path": str(package),
                 "installed_utc": utc(), "owned_paths": ["venv", "tools"], "tools_files": [],
                 "config_registration": None}
        write_state(root, state)
        try:
            if not venv_python.is_file():
                if venv.exists():
                    raise InstallError("An incomplete owned venv exists. Review/remove that venv only, then rerun.")
                _run_logged([str(python), "-X", "utf8", "-m", "venv", str(venv)], root, "Creating private venv", 180)
            no_reparse(venv_python)
            find_python(venv_python)
            _run_logged(package_command, root, "Installing reviewed package and pinned dependencies", 600)
            tools = root / "tools"
            no_reparse(tools)
            tools.mkdir(exist_ok=True)
            for name in TOOLS:
                source = Path(__file__).parent / name
                target = tools / name
                if full(source) != full(target):
                    shutil.copyfile(source, target)
                state["tools_files"].append({"name": name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
            write_state(root, state)
            state["config_registration"] = manage_config.register(codex, home, venv_python, app,
                                                                  output, root, args.replace_existing)
            state["status"] = "installed"
            write_state(root, state)
            if not args.skip_doctor:
                doctor(root, skip_protocol=False)
            return {"ok": True, "status": "installed", "install_root": str(root), "output_dir": str(output),
                    "config_registration": state["config_registration"], "doctor_passed": not args.skip_doctor,
                    "next_step": "Restart the Codex task/app to load fastmean.", "windows_settings_changed": False}
        except BaseException as error:
            state.update(status="failed", last_error=str(error))
            write_state(root, state)
            raise


def doctor(root: Path, skip_protocol: bool = False) -> dict:
    root = full(root)
    state = read_state(root)
    if not state:
        raise InstallError(f"No owned FASTMEAN MCP installation was found at {root}. Run install.py first.")
    python = root / "venv" / "Scripts" / "python.exe"
    find_python(python)
    command = [str(python), "-X", "utf8", str(Path(__file__).parent / "probe.py"),
               "--python", str(python), "--app-dir", state["app_dir"],
               "--output-dir", state["output_dir"], "--config-home", state["codex_home"]]
    if skip_protocol:
        command.append("--skip-protocol")
    result = subprocess.run(command, capture_output=True, timeout=45)
    if result.returncode:
        raise InstallError(result.stderr.decode("utf-8", errors="replace")[-5000:])
    return json.loads(result.stdout)


def _remove_owned_tree(target: Path, root: Path, marker: str | None = None) -> None:
    if not target.exists():
        return
    if full(target) == full(root) or not within(target, root):
        raise InstallError(f"Refusing recursive removal outside the explicit owned root: {target}")
    no_reparse(target)
    if marker and not (target / marker).is_file():
        raise InstallError(f"Owned directory marker is missing: {target / marker}; review before removing.")
    for parent, directories, files in os.walk(target, followlinks=False):
        for name in directories + files:
            item = Path(parent) / name
            if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                raise InstallError(f"Owned tree contains a link/junction; review before removing: {item}")
    shutil.rmtree(target)


def uninstall(root_input: Path, remove_results: bool = False, dry_run: bool = False) -> dict:
    require_windows()
    no_reparse(root_input)
    root = full(root_input)
    state = read_state(root)
    if state is None:
        raise InstallError(f"No owned FASTMEAN MCP installation was found at {root}.")
    plan = {"action": "uninstall", "install_root": str(root), "remove_owned_mcp_entry": "fastmean",
            "keep_results": not remove_results, "output_dir": state["output_dir"],
            "keep_private_backups_and_receipt": True, "windows_settings_changed": False}
    if dry_run:
        return plan
    if within(Path(sys.executable), root / "venv"):
        raise InstallError("Run uninstall.py with an existing base Python outside this owned venv (for example py -3.12). Windows cannot remove its running Python executable. No files or configuration were changed.")
    with installation_lock(root):
        expected_python = root / "venv" / "Scripts" / "python.exe"
        removed = manage_config.remove(full(state["codex_home"]), expected_python, root)
        _remove_owned_tree(root / "venv", root, "pyvenv.cfg")
        preserved = []
        tools = root / "tools"
        no_reparse(tools)
        for record in state.get("tools_files", []):
            name = record["name"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                raise InstallError("Invalid helper filename in the ownership receipt.")
            target = tools / name
            if target.is_symlink() or (target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() != record["sha256"]):
                preserved.append(str(target))
            elif target.is_file():
                target.unlink()
        cache = tools / "__pycache__"
        if cache.is_dir():
            no_reparse(cache)
            modules = {Path(record["name"]).stem for record in state.get("tools_files", [])
                       if record["name"].endswith(".py")}
            for item in cache.iterdir():
                match = re.fullmatch(r"(.+)\.cpython-\d+(?:\.opt-\d+)?\.pyc", item.name)
                if match and match[1] in modules and item.is_file() and not item.is_symlink():
                    item.unlink()
            if not any(cache.iterdir()):
                cache.rmdir()
        if tools.is_dir() and not any(tools.iterdir()):
            tools.rmdir()
        output = full(state["output_dir"])
        results_removed = False
        if remove_results and state.get("results_owned") and output == root / "results":
            _remove_owned_tree(output, root)
            results_removed = True
        state.update(status="uninstalled", uninstalled_utc=utc())
        write_state(root, state)
        return {**plan, "ok": True, "status": "uninstalled", "config_registration": removed,
                "results_removed": results_removed, "preserved_modified_helpers": preserved}


def installation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install FASTMEAN MCP for the current Windows user; no Windows setting changes.")
    parser.add_argument("--app-dir")
    parser.add_argument("--python", help="Existing Python 3.12+ executable; default is the interpreter running this script")
    parser.add_argument("--install-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--codex-home")
    parser.add_argument("--codex-path")
    parser.add_argument("--package-path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--skip-doctor", action="store_true")
    return parser


def emit_or_fail(parser: argparse.ArgumentParser, action) -> None:
    try:
        result = action()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (InstallError, manage_config.ConfigError, OSError, subprocess.SubprocessError, ValueError) as error:
        parser.exit(1, f"FASTMEAN MCP: {error}\nNo Windows locale, security, PATH, or machine-wide settings were changed.\n")
