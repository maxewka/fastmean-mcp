"""Add root parameters, native notes and graph expressions to a fresh SCM copy.

Original SCM/model files are never rewritten. Subcircuit dependencies are
validated and packaged with relative references. This module does not launch
FASTMEAN, create child parameters or set per-instance model overrides.
"""
from __future__ import annotations

import copy
import hashlib
import math
import os
from pathlib import Path, PureWindowsPath
import re
import tempfile
from typing import Any, Callable

from .engine import MAX_MODEL_FILES, MAX_PROJECT_BYTES, MAX_SIGNALS, _dependency_path, _validate_active_dependencies, prepare_copy, validate_signal
from .schematic import SchemeError, _load, _summarize, _write_document, parse_value

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_DEFINITION = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^;=]*\))?\s*=")
_DIRECTIVE = re.compile(r"(?<![A-Za-z0-9_])\.[A-Za-z_]")
_ANALYSIS = ("TD", "FD", "AOD", "SOD", "DCOP")
_RESERVED = {"i", "p", "t", "f", "pi", "e", "u", "db", "mag", "phs", "rms", "avg",
             "sin", "cos", "tan", "exp", "log", "sqrt", "write", "open", "exit", "sim", "ac"}
_FONT = {"lfHeight": -16, "lfWidth": 0, "lfEscapement": 0, "lfOrientation": 0,
         "lfWeight": 0, "lfItalic": 0, "lfUnderline": 0, "lfStrikeOut": 0,
         "lfCharSet": 204, "lfOutPrecision": 0, "lfClipPrecision": 0,
         "lfQuality": 0, "lfPitchAndFamily": 0, "lfFaceName": "Courier New"}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshots(source: Path) -> dict[Path, dict]:
    records: dict[Path, dict] = {}
    total = 0

    def visit(path: Path) -> None:
        nonlocal total
        if path in records:
            return
        if len(records) >= MAX_MODEL_FILES:
            raise SchemeError(f"Project exceeds {MAX_MODEL_FILES} SCM model files.")
        total += path.stat().st_size
        if total > MAX_PROJECT_BYTES:
            raise SchemeError("Project SCM dependencies exceed the 64 MiB limit.")
        before = _hash(path)
        _, document, encoding = _load(path)
        if _hash(path) != before:
            raise SchemeError(f"Source model changed while being read: {path}")
        _summarize(document, path, encoding)
        records[path] = {"document": document, "sha256": before, "dependencies": []}
        for obj in document["scm"]["Scheme"].get("Objects") or []:
            if obj["Type"] == 7100:
                child = _dependency_path(path.parent, (obj.get("Params") or {}).get("FileName"))
                records[path]["dependencies"].append((str(obj.get("Name", "")), child))
                visit(child)

    visit(source)
    _validate_active_dependencies(source, {path: record["dependencies"] for path, record in records.items()})
    return records


def _validated_request(document: dict, parameters: Any, bindings: Any, descriptions: Any,
                       td_signals: Any, fd_signals: Any) -> tuple[dict, dict, list, dict]:
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict) or len(parameters) > 64:
        raise SchemeError("parameters must map at most 64 ASCII identifiers to finite numeric SI values.")
    objects = document["scm"]["Scheme"].get("Objects") or []
    names: dict[str, list[dict]] = {}
    existing = set(_RESERVED)
    for obj in objects:
        name = str(obj.get("Name", ""))
        names.setdefault(name, []).append(obj)
        existing.add(name.casefold())
        if obj["Type"] == 900:
            text = (obj.get("Params") or {}).get("Text", "")
            if isinstance(text, str) and _DIRECTIVE.search(text):
                existing.update(match[1].casefold() for match in _DEFINITION.finditer(text))
    numeric, spellings = {}, set()
    for name, value in parameters.items():
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise SchemeError("Parameter names must be ASCII identifiers of at most 64 characters.")
        folded = name.casefold()
        if folded in existing or folded in spellings:
            raise SchemeError(f"Parameter name {name!r} collides with an existing name, definition or native symbol.")
        spellings.add(folded)
        numeric[name] = parse_value(value)
    if bindings is None:
        bindings = {}
    if not isinstance(bindings, dict) or len(bindings) > 200:
        raise SchemeError("bindings must map existing root component names to parameter names.")
    normalized = {}
    for name, parameter in bindings.items():
        if not isinstance(name, str) or name not in names or len(names[name]) != 1:
            raise SchemeError(f"Binding component {name!r} is missing or ambiguous; use its exact native name.")
        if not isinstance(parameter, str) or parameter not in numeric:
            raise SchemeError(f"Binding {name!r} must refer to a parameter declared in this request.")
        obj = names[name][0]
        tid, params = obj["Type"], obj.get("Params") or {}
        if tid not in {1000, 1001, 1002, 2010,3010}:
            raise SchemeError(f"Binding {name!r} supports only root R/C/L and DC/sine independent-source amplitude.")
        if tid in {1000, 1001, 1002} and numeric[parameter] <= 0:
            raise SchemeError(f"Passive binding {name!r} requires a positive parameter value.")
        if tid in {2010,3010} and (params.get("ST") not in {1, 2} or
                            not isinstance(params.get({1: "DC", 2: "AC"}.get(params.get("ST"))), dict)):
            raise SchemeError(f"Source binding {name!r} requires a complete DC or sine waveform.")
        normalized[name] = parameter
    if descriptions is None:
        descriptions = []
    if not isinstance(descriptions, list) or len(descriptions) > 32:
        raise SchemeError("descriptions must contain at most 32 plain text notes.")
    for text in descriptions:
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise SchemeError("Each description must contain 1 to 1000 text characters.")
        if any(ord(char) < 32 and char not in "\r\n\t" for char in text) or _DIRECTIVE.search(text):
            raise SchemeError("Descriptions must be ordinary text; native directives and control characters are forbidden.")
    formulas = {}
    for section, signals in (("TD", td_signals), ("FD", fd_signals)):
        if signals is None:
            continue
        if not isinstance(signals, list) or not 0 <= len(signals) <= MAX_SIGNALS:
            raise SchemeError(f"{section} signals must contain 0 to {MAX_SIGNALS} mathematical expressions; [] clears saved traces.")
        formulas[section] = [validate_signal(value) for value in signals]
    return numeric, normalized, list(descriptions), formulas


def _text_objects(document: dict, parameters: dict, descriptions: list[str], bindings: dict) -> list[str]:
    objects = document["scm"]["Scheme"].setdefault("Objects", [])
    oid = max((obj["ID"] for obj in objects), default=0) + 1
    coordinates = [(obj.get("X"), obj.get("Y")) for obj in objects]
    coordinates = [(float(x), float(y)) for x, y in coordinates
                   if isinstance(x, (int, float)) and isinstance(y, (int, float))
                   and math.isfinite(x) and math.isfinite(y)]
    # The native YAML reader stores object coordinates as integers, even
    # though Matplotlib previews accept fractional coordinates.
    x = int(round(min((point[0] for point in coordinates), default=0)))
    bottom = max((point[1] for point in coordinates), default=0)
    for obj in objects:
        if obj.get("Type") != 900:
            continue
        top = obj.get("Y")
        params = obj.get("Params") or {}
        text = params.get("Text")
        if not isinstance(top, (int, float)) or not math.isfinite(top) or not isinstance(text, str):
            continue
        font = params.get("Font") or {}
        height = font.get("lfHeight", -16) if isinstance(font, dict) else -16
        if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height):
            height = -16
        line_height = max(22, math.ceil(abs(height) * 1.375))
        # Existing multiline notes occupy space below their anchor. In
        # particular a previous .parameter block can exceed the 120-unit gap.
        extent = line_height * max(1, len(text.splitlines()))
        if obj.get("Rot", 0):
            extent = max(extent, abs(height) * max((len(line.expandtabs(8)) for line in text.splitlines()), default=0))
        bottom = max(bottom, top + extent)
    y = math.ceil(bottom) + 120
    texts = []
    entries = list(parameters.items())
    units: dict[str, set[str]] = {}
    for obj in objects:
        parameter = bindings.get(obj.get("Name"))
        if parameter is not None:
            units.setdefault(parameter, set()).add({1000: "ohm", 1001: "F", 1002: "H", 2010: "V",3010:"A"}[obj["Type"]])

    def declaration(name: str, value: float) -> str:
        choices = units.get(name, set())
        label = f"{name} [{next(iter(choices))}]" if len(choices) == 1 else name
        # Retain the quoted-label and CRLF declaration format exercised by
        # FASTMEAN6.1 native QA; unquoted labels are not separately tested.
        return f'{name}={value:.17g} "{label}";'
    # Bound both row count and actual length, including quoted descriptions.
    block = ".parameter\r\n"
    count = 0
    for name, value in entries:
        row = declaration(name, value) + "\r\n"
        if count and (count == 8 or len(block) + len(row) > 1000):
            texts.append(block)
            block, count = ".parameter\r\n", 0
        block += row
        count += 1
    if count:
        texts.append(block)
    texts.extend(text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n") for text in descriptions)
    for index, text in enumerate(texts):
        objects.append({"ID": oid + index, "Type": 900, "Name": f"MCP_NOTE_{oid+index}",
                        "X": x, "Y": y, "Rot": 0, "FlipV": 0, "FlipH": 0, "active_property_page": 0,
                        "Params": {"Text": text, "Color": "00808000", "Font": copy.deepcopy(_FONT)}})
        y += 35 + 22 * len(text.splitlines())
    if texts:
        general = document["scm"].setdefault("General", {})
        if not isinstance(general, dict):
            raise SchemeError("Native General settings must be a mapping.")
        # Courier New has a 16-unit font height. Reserving that much width per
        # character and 22 units per line is deliberately generous, including
        # Cyrillic/formula glyphs and expanded tabs. Keep the existing viewport.
        note_objects = objects[-len(texts):]
        right = max(obj["X"] + 16 * max((len(line.expandtabs(8)) for line in text.splitlines()), default=0)
                    for obj, text in zip(note_objects, texts)) + 120
        bottom = max(obj["Y"] + 22 * max(1, len(text.splitlines()))
                     for obj, text in zip(note_objects, texts)) + 120
        for key, required in (("SWidth", right), ("SHeight", bottom)):
            current = general.get(key, 0)
            if isinstance(current, bool) or not isinstance(current, (int, float)) or not math.isfinite(current):
                raise SchemeError(f"Native General.{key} must be a finite sheet dimension.")
            general[key] = max(math.ceil(current), required)
    return texts


def _portable_tree(records: dict, source: Path, output: Path) -> tuple[bool, str]:
    """Prefer original short model captions without overwriting any sibling."""
    for path, record in records.items():
        if path != source:
            if not path.is_relative_to(source.parent):
                return False, "A model lies outside the original project directory."
            target = output.parent / path.relative_to(source.parent)
            if target == output or target.exists() or target.is_symlink():
                return False, "An original relative model destination is already occupied."
            for parent in target.parents:
                if parent == output.parent:
                    break
                if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                    return False, "A relative model destination has an unsafe parent."
        for obj in record["document"]["scm"]["Scheme"].get("Objects") or []:
            if obj["Type"] != 7100:
                continue
            reference = obj["Params"]["FileName"]
            native = PureWindowsPath(reference)
            normalized = Path(reference.replace("\\", "/"))
            if native.drive or native.root or normalized.is_absolute() or ".." in normalized.parts:
                return False, "Original model references are not a self-contained relative tree."
            if output.name != source.name and _dependency_path(path.parent, reference) == source:
                return False, "A reference to the renamed root must be relocated with its copied models."
    return True, "Original relative model paths and child bytes are preserved."


def annotate_circuit(source_path: str | Path, output_path: str | Path,
                     parameters: dict | None = None, bindings: dict | None = None,
                     descriptions: list[str] | None = None, td_signals: list[str] | None = None,
                     fd_signals: list[str] | None = None) -> dict[str, Any]:
    """Create a fresh portable copy with root .parameter declarations and notes.

    Parameters are finite literal SI values, and bindings address existing root
    R/C/L values or the active DC/sine source amplitude. Native child models and
    per-instance parameter overrides are not authored. Expressions are validated
    mathematics, not script fragments. Existing analysis settings are retained.
    """
    return _copy_circuit(source_path, output_path, parameters, bindings, descriptions,
                         td_signals, fd_signals)


def _copy_circuit(source_path: str | Path, output_path: str | Path,
                  parameters: dict | None = None, bindings: dict | None = None,
                  descriptions: list[str] | None = None, td_signals: list[str] | None = None,
                  fd_signals: list[str] | None = None, *,
                  root_transform: Callable[[dict], None] | None = None) -> dict[str, Any]:
    """Publish a complete portable copy, optionally changing its staged root.

    The internal transform runs before publication, so value editing shares the
    same dependency snapshot, exclusive creation and rollback guarantees as
    annotation. It is never exposed as a protocol argument.
    """
    source = Path(source_path).expanduser().resolve(strict=True)
    output = Path(output_path).expanduser().absolute()
    if output.suffix.lower() != ".scm":
        raise SchemeError("Annotation output filename must end in .scm.")
    if output.resolve(strict=False) == source:
        raise SchemeError("Annotations must create a new file; the original cannot be overwritten.")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Annotation destination already exists: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {output.parent}")
    records = _snapshots(source)
    original = records[source]["document"]
    numeric, normalized, notes, requested = _validated_request(original, parameters, bindings, descriptions, td_signals, fd_signals)
    portable, portability_reason = _portable_tree(records, source, output)
    final_models = []
    copied_pairs: dict[Path, Path] = {}
    texts = []
    with tempfile.TemporaryDirectory(prefix=".fastmean-annotations-", dir=output.parent) as temporary:
        workspace = Path(temporary).resolve()
        prepared = prepare_copy(source, workspace / output.name)

        def pair(original_path: Path, private_path: Path) -> None:
            if original_path in copied_pairs:
                if copied_pairs[original_path] != private_path:
                    raise SchemeError("A repeated model was copied inconsistently.")
                return
            copied_pairs[original_path] = private_path
            _, private, _ = _load(private_path)
            originals = {obj["ID"]: obj for obj in records[original_path]["document"]["scm"]["Scheme"].get("Objects") or []}
            for obj in private["scm"]["Scheme"].get("Objects") or []:
                if obj["Type"] != 7100:
                    continue
                old = _dependency_path(original_path.parent, originals[obj["ID"]]["Params"]["FileName"])
                new = _dependency_path(private_path.parent, obj["Params"]["FileName"])
                if not new.is_relative_to(workspace):
                    raise SchemeError("Prepared subcircuit escaped its private workspace.")
                pair(old, new)

        pair(source, prepared)
        if portable:
            # prepare_copy has validated every directive/dependency/cycle. Its
            # absolute worker references are useful for batch jobs but change
            # native model captions. Publish an unchanged short relative tree.
            for original_path in copied_pairs:
                if original_path == source:
                    continue
                private_path = workspace / original_path.relative_to(source.parent)
                private_path.parent.mkdir(parents=True, exist_ok=True)
                with private_path.open("xb") as stream:
                    stream.write(original_path.read_bytes())
                copied_pairs[original_path] = private_path
        for original_path, private_path in copied_pairs.items():
            if portable and original_path != source:
                continue
            # Preparation validates directives and every dependency but its
            # batch copy suppresses UI/state settings and normalizes literals.
            # Authoring must retain the original document, changing only the
            # requested root fields and references to the packaged models.
            document = copy.deepcopy(records[original_path]["document"])
            body = document["scm"]
            if original_path == source:
                for section in _ANALYSIS:
                    if section in original["scm"]:
                        body[section] = copy.deepcopy(original["scm"][section])
                    else:
                        body.pop(section, None)
                for obj in body["Scheme"].get("Objects") or []:
                    parameter = normalized.get(obj.get("Name"))
                    if parameter is None:
                        continue
                    params = obj["Params"]
                    if obj["Type"] in {1000, 1001, 1002}:
                        params[{1000: "R", 1001: "C", 1002: "L"}[obj["Type"]]] = parameter
                    else:
                        params[{1: "DC", 2: "AC"}[params["ST"]]]["I0" if obj["Type"]==3010 else "U0"] = parameter
                texts = _text_objects(document, numeric, notes, normalized)
                for section, signals in requested.items():
                    settings = body.setdefault(section, {})
                    settings["ExprRowOffset"] = 0
                    settings["Expressions"] = [{"plot": index+1, "x": "t" if section == "TD" else "f", "y": signal}
                                               for index, signal in enumerate(signals)]
                if root_transform is not None:
                    root_transform(document)
            for obj in body["Scheme"].get("Objects") or []:
                if obj["Type"] == 7100 and not portable:
                    original_child = _dependency_path(original_path.parent, obj["Params"]["FileName"])
                    child = copied_pairs[original_child]
                    obj["Params"]["FileName"] = Path(os.path.relpath(child, private_path.parent)).as_posix()
            _summarize(document, private_path, "utf-8")
            _write_document(document, private_path, overwrite=True)
        for path, record in records.items():
            if _hash(path) != record["sha256"]:
                raise SchemeError(f"Source model changed during annotation: {path}")

        # Dependencies become visible first, the complete root last. Every final
        # filename is created exclusively; rollback unlinks only our own inodes.
        linked: list[tuple[Path, Path]] = []
        made_directories: list[Path] = []
        try:
            for private in copied_pairs.values():
                if private == prepared:
                    continue
                target = output.parent / private.relative_to(workspace)
                missing = []
                parent = target.parent
                while parent != output.parent and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                if parent.is_symlink() or not parent.is_dir():
                    raise SchemeError("Model publication parent is not a regular directory.")
                for parent in reversed(missing):
                    parent.mkdir(exist_ok=False)
                    made_directories.append(parent)
                os.link(private, target)
                linked.append((private, target))
            os.link(prepared, output)
            linked.append((prepared, output))
            for original_path, private in copied_pairs.items():
                target = output.parent / private.relative_to(workspace)
                final_models.append({"source_path": str(original_path), "source_sha256": records[original_path]["sha256"],
                                     "private_path": str(target.resolve()), "private_sha256": _hash(target)})
        except BaseException:
            for private, target in reversed(linked):
                try:
                    if target.exists() and os.path.samefile(private, target):
                        target.unlink()
                except OSError:
                    pass
            for directory in reversed(made_directories):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            raise
    _, final_document, _ = _load(output)
    formulas = {section: [item.get("y") for item in (final_document["scm"].get(section) or {}).get("Expressions", [])
                          if isinstance(item, dict)] for section in ("TD", "FD")}
    captions_ok = all(len(obj["Params"]["FileName"]) <= 20
                      for record in records.values()
                      for obj in record["document"]["scm"]["Scheme"].get("Objects") or [] if obj["Type"] == 7100)
    return {"path": str(output.resolve()), "working_dir": str(output.parent.resolve()),
            "source_path": str(source), "source_sha256": records[source]["sha256"],
            "source_unchanged": all(_hash(path) == record["sha256"] for path, record in records.items()),
            "private_schematic_sha256": _hash(output), "source_models": final_models,
            "parameters": numeric, "bindings": normalized, "formulas": formulas,
            "texts": texts, "text_count": len(texts),
            "dependency_layout": "original_relative_tree" if portable else "validated_private_assets",
            "portability_note": portability_reason,
            "preview_unsupported": bool(len(records) > 1 and (not portable or not captions_ok)),
            "dependency_paths": [item["private_path"] for item in final_models if item["source_path"] != str(source)]}
