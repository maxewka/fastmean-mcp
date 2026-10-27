"""Create portable native subcircuit projects without modifying existing files.

Definitions contain fixed component values.  Native parameter declarations and
per-instance ``Scm``/``Actual`` overrides are deliberately outside this API.
The installed FASTMEAN solver expands Type-7100 instances during analysis.
"""
from __future__ import annotations

import copy
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any

from .schematic import SchemeError, _KIND_ALIASES, _load, create_circuit, read_scheme

SIDES = ("Left", "Top", "Right", "Bottom")
MAX_MODELS = 99  # Engine permits 100 SCM files including the root.
MAX_SPEC_BYTES = 64 * 1024 * 1024
_MODEL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_PIN_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_snapshot(value: Any) -> tuple[dict, bytes]:
    active: set[int] = set()

    def check(item: Any, depth: int = 0) -> None:
        if depth > 64:
            raise SchemeError("Project specification is nested too deeply.")
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                raise SchemeError("Project specification must contain finite JSON numbers.")
            return
        if not isinstance(item, (dict, list)):
            raise SchemeError("Project specification must contain JSON objects, arrays and scalar values.")
        if id(item) in active:
            raise SchemeError("Project specification contains a recursive Python object.")
        active.add(id(item))
        try:
            if isinstance(item, dict):
                if any(not isinstance(key, str) for key in item):
                    raise SchemeError("Project specification object keys must be strings.")
                children = item.values()
            else:
                children = item
            for child in children:
                check(child, depth + 1)
        finally:
            active.remove(id(item))

    check(value)
    if not isinstance(value, dict):
        raise SchemeError("Project specification must be an object.")
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_SPEC_BYTES:
        raise SchemeError("Project specification exceeds the 64 MiB limit.")
    return json.loads(raw), raw


def _model_name(value: Any) -> str:
    if not isinstance(value, str) or not _MODEL_NAME.fullmatch(value):
        raise SchemeError("Model names must be ASCII identifiers of at most 64 characters.")
    if value.upper() in _RESERVED_NAMES:
        raise SchemeError(f"Model name {value!r} is reserved on Windows.")
    return value


def _pins(value: Any, model: str) -> dict[str, list[str]]:
    if not isinstance(value, dict) or set(value) - set(SIDES):
        raise SchemeError(f"{model}: pins must map Left, Top, Right and/or Bottom to lists.")
    result: dict[str, list[str]] = {}
    used: set[str] = set()
    for side in SIDES:
        names = value.get(side, [])
        if not isinstance(names, list):
            raise SchemeError(f"{model}: {side} pins must be a list, not null.")
        result[side] = []
        for name in names:
            if not isinstance(name, str) or not _PIN_NAME.fullmatch(name):
                raise SchemeError(f"{model}: pin names must start with an ASCII letter; private '_' and numeric pin names are unsupported for generation.")
            if name.casefold() in used:
                raise SchemeError(f"{model}: duplicate or ambiguous pin name {name!r}.")
            used.add(name.casefold())
            result[side].append(name)
    if not 1 <= len(used) <= 32:
        raise SchemeError(f"{model}: a subcircuit must expose 1 to 32 pins.")
    return result


def _kind(component: dict) -> str:
    values = [str(component[key]).upper() for key in ("kind", "type") if key in component]
    values = [_KIND_ALIASES.get(value, value) for value in values]
    if len(set(values)) > 1:
        raise SchemeError("Component kind and type disagree.")
    return values[0] if values else ""


def _validate_project(spec: dict) -> tuple[dict[str, dict], list[str]]:
    if set(spec) - {"name", "models", "circuit"}:
        raise SchemeError("Project fields are name, models and circuit; parameter overrides are not supported.")
    if "name" in spec and (not isinstance(spec["name"], str) or not spec["name"].strip()
                           or len(spec["name"]) > 200 or "\x00" in spec["name"]):
        raise SchemeError("Project name must be a nonempty string of at most 200 characters.")
    models = spec.get("models")
    if not isinstance(models, dict) or not 1 <= len(models) <= MAX_MODELS:
        raise SchemeError(f"Project models must contain 1 to {MAX_MODELS} named definitions.")
    definitions: dict[str, dict] = {}
    spellings: set[str] = set()
    for raw_name, raw in models.items():
        name = _model_name(raw_name)
        if name.casefold() in spellings:
            raise SchemeError(f"Duplicate or ambiguous model name {name!r}.")
        spellings.add(name.casefold())
        if not isinstance(raw, dict) or set(raw) != {"pins", "circuit"}:
            raise SchemeError(f"{name}: a definition must contain exactly pins and circuit; instance parameters are not supported.")
        pins = _pins(raw["pins"], name)
        circuit = raw["circuit"]
        if not isinstance(circuit, dict):
            raise SchemeError(f"{name}: circuit must be an object.")
        ports = circuit.get("ports")
        expected = {pin for side in SIDES for pin in pins[side]}
        if not isinstance(ports, dict) or set(ports) != expected:
            raise SchemeError(f"{name}: circuit ports must match the declared pins exactly: {sorted(expected)}.")
        definitions[name] = {"pins": pins, "circuit": circuit, "dependencies": []}

    def references(circuit: Any, label: str) -> tuple[list[str], list[str]]:
        if not isinstance(circuit, dict) or not isinstance(circuit.get("components"), list):
            raise SchemeError(f"{label}: circuit needs a components list.")
        found, active_models = set(), set()
        for component in circuit["components"]:
            if not isinstance(component, dict):
                raise SchemeError(f"{label}: each component must be an object.")
            if _kind(component) != "X":
                continue
            if set(component) - {"kind", "type", "name", "model", "connections"}:
                raise SchemeError(f"{label}: X components accept name, model and connections; parameter overrides are not supported.")
            model = component.get("model")
            if not isinstance(model, str) or model not in definitions:
                raise SchemeError(f"{label}: unknown subcircuit model {model!r}.")
            connections = component.get("connections")
            expected = {pin for side in SIDES for pin in definitions[model]["pins"][side]}
            if not isinstance(connections, dict) or set(connections) != expected:
                raise SchemeError(f"{label}.{component.get('name', '?')}: connections must map every {model} pin exactly: {sorted(expected)}.")
            found.add(model)
            if not str(component.get("name", "")).startswith("_"):
                active_models.add(model)
        return sorted(found), sorted(active_models)

    references(spec.get("circuit"), "Root")
    for name, definition in definitions.items():
        definition["dependencies"], definition["active_dependencies"] = references(definition["circuit"], name)
    complete: set[str] = set()
    active: list[str] = []
    order: list[str] = []

    def visit(name: str) -> None:
        if name in active:
            raise SchemeError("Recursive subcircuit model cycle: " + " -> ".join(active + [name]))
        if name in complete:
            return
        active.append(name)
        for child in definitions[name]["active_dependencies"]:
            visit(child)
        active.pop()
        complete.add(name)
        order.append(name)

    for name in definitions:
        visit(name)
    return definitions, order


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def _publish_directory(stage: Path, destination: Path) -> None:
    """Atomically rename a complete directory, failing if a target appeared."""
    if os.name == "nt":
        # Windows rename fails for every existing destination, including an
        # empty directory. os.replace would not provide this guarantee.
        os.rename(stage, destination)
        return
    if sys.platform.startswith("linux"):
        library = ctypes.CDLL(None, use_errno=True)
        rename = getattr(library, "renameat2", None)
        if rename is None:
            raise SchemeError("This platform has no atomic directory rename without replacement.")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(stage), -100, os.fsencode(destination), 1) == 0:  # RENAME_NOREPLACE
            return
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise FileExistsError(code, os.strerror(code), str(destination))
        raise OSError(code, os.strerror(code), str(destination))
    if sys.platform == "darwin":
        library = ctypes.CDLL(None, use_errno=True)
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(os.fsencode(stage), os.fsencode(destination), 4) == 0:  # RENAME_EXCL
            return
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise FileExistsError(code, os.strerror(code), str(destination))
        raise OSError(code, os.strerror(code), str(destination))
    raise SchemeError("This platform has no supported atomic directory rename without replacement.")


def create_project(spec: dict, destination: str | Path) -> dict:
    """Create a fresh portable native project with fixed numeric submodels.

    ``models`` maps model identifiers to ``pins`` side lists and a ``circuit``.
    An X component names a model and maps all exposed pins to parent nodes in
    ``connections``. All source specifications are retained as UTF-8 JSON.
    Existing destinations are never merged, removed or replaced. Validation
    and staging failures leave the destination absent and clean up our stage.
    """
    snapshot, original_json = _json_snapshot(spec)
    definitions, order = _validate_project(snapshot)
    raw_destination = Path(destination).expanduser()
    if ".." in raw_destination.parts or raw_destination.name in {"", ".", ".."}:
        raise SchemeError("Project destination must name a fresh directory without '..' traversal.")
    parent = raw_destination.absolute().parent.resolve(strict=True)
    if not parent.is_dir():
        raise SchemeError("Project destination parent must be an existing directory.")
    target = parent / raw_destination.name
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Project destination already exists: {target}")
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.creating-", dir=parent))
    warnings: list[str] = []
    try:
        (stage / "models").mkdir()
        model_context = {name: {"pins": copy.deepcopy(definition["pins"]), "path": name + ".scm"}
                         for name, definition in definitions.items()}
        for name in order:
            child_spec = copy.deepcopy(definitions[name]["circuit"])
            ordered_pins = [pin for side in SIDES for pin in definitions[name]["pins"][side]]
            # Keep object order inspectable. Native electrical order itself is
            # rebuilt from PORT orientation and side coordinates; interface_pins
            # makes the layout compiler validate that contract independently.
            child_spec["ports"] = {pin: child_spec["ports"][pin] for pin in ordered_pins}
            result = create_circuit(child_spec, stage / "models" / (name + ".scm"),
                                    model_context=copy.deepcopy(model_context), subcircuit=True,
                                    interface_pins=copy.deepcopy(definitions[name]["pins"]))
            exposed = result.get("ports")
            expected = {pin for side in SIDES for pin in definitions[name]["pins"][side]}
            if not isinstance(exposed, dict) or set(exposed) != expected:
                raise SchemeError(f"{name}: generated native ports do not match the declared subcircuit pins.")
            actual_order = [obj.get("Name") for obj in result.get("objects", []) if obj.get("Type") == 400]
            if actual_order != ordered_pins:
                raise SchemeError(f"{name}: generated native PORT object order does not match the declared pin slots.")
            warnings.extend(f"{name}: {warning}" for warning in result.get("warnings", []))
            test_only = [component.get("name") for component in definitions[name]["circuit"]["components"]
                         if isinstance(component.get("name"), str) and component["name"].startswith("_")]
            if test_only:
                warnings.append(f"{name}: native parent expansion excludes test-only components: {', '.join(test_only)}.")
            _write_json(stage / "models" / (name + ".spec.json"), definitions[name]["circuit"])
        root_context = {name: {"pins": copy.deepcopy(definition["pins"]), "path": f"models/{name}.scm"}
                        for name, definition in definitions.items()}
        root_result = create_circuit(copy.deepcopy(snapshot["circuit"]), stage / "main.scm",
                                     model_context=root_context, subcircuit=False)
        warnings.extend(str(warning) for warning in root_result.get("warnings", []))
        _write_json(stage / "main.spec.json", snapshot["circuit"])
        with (stage / "project.spec.json").open("xb") as stream:
            stream.write(original_json)
        models = [{"name": name, "path": f"models/{name}.scm", "sha256": _hash(stage / "models" / (name + ".scm")),
                   "pins": definition["pins"], "dependencies": definition["dependencies"],
                   "active_dependencies": definition["active_dependencies"],
                   "native_port_order": [pin for side in SIDES for pin in definition["pins"][side]]}
                  for name, definition in definitions.items()]
        files = [{"path": path.relative_to(stage).as_posix(), "sha256": _hash(path), "bytes": path.stat().st_size}
                 for path in sorted(stage.rglob("*")) if path.is_file()]
        if sum(item["bytes"] for item in files if item["path"].lower().endswith(".scm")) > MAX_SPEC_BYTES:
            raise SchemeError("Generated SCM models exceed the native 64 MiB project limit.")
        manifest = {"format": "fastmean-mcp-project", "schema_version": 1,
                    "name": snapshot.get("name", target.name),
                    "created_utc": datetime.now(timezone.utc).isoformat(), "root": "main.scm",
                    "spec": "project.spec.json", "models": models, "files": files,
                    "parameter_overrides_supported": False, "warnings": warnings}
        _write_json(stage / "project.manifest.json", manifest)
        _publish_directory(stage, target)
    finally:
        # Only the exact directory created by mkdtemp above belongs to us.
        if stage.exists():
            shutil.rmtree(stage)
    return {"project_dir": str(target), "path": str(target / "main.scm"),
            "sha256": _hash(target / "main.scm"),
            "models": [{**model, "relative_path": model["path"], "path": str(target / model["path"])} for model in models],
            "files": [{**item, "relative_path": item["path"], "path": str(target / item["path"])} for item in files],
            "spec_path": str(target / "project.spec.json"),
            "manifest_path": str(target / "project.manifest.json"),
            "manifest_sha256": _hash(target / "project.manifest.json"), "warnings": warnings}


def inspect_definition(path: str | Path) -> dict:
    """Report native external PORT names and direct SCM references read-only.

    A child SCM declares ports; its parent instance determines their side and
    terminal order. No side layout or native parameter behavior is inferred.
    """
    source = Path(path).expanduser().resolve(strict=True)
    before = _hash(source)
    _, document, _ = _load(source)
    summary = read_scheme(source)
    if _hash(source) != before:
        raise SchemeError("Subcircuit definition changed while being inspected.")
    objects = document["scm"]["Scheme"].get("Objects") or []
    ports = {name: node for name, node in summary["ports"].items() if not name.startswith("_")}
    private_ports = [name for name in summary["ports"] if name.startswith("_")]
    test_only = [str(obj.get("Name")) for obj in objects
                 if obj.get("Type") not in {200, 300, 400, 900} and str(obj.get("Name", "")).startswith("_")]
    dependencies = [{"name": str(obj.get("Name", "")), "path": (obj.get("Params") or {}).get("FileName"),
                     "pins": copy.deepcopy((obj.get("Params") or {}).get("Pins"))}
                    for obj in objects if obj.get("Type") == 7100]
    warnings = list(summary.get("warnings", []))
    if test_only:
        warnings.append("Native parent expansion excludes underscore-prefixed test components.")
    return {"path": str(source), "sha256": before, "external_ports": list(ports), "ports": ports,
            "private_ports": private_ports, "test_only_components": test_only,
            "dependencies": dependencies, "pin_sides": None, "warnings": warnings}
