"""Inspect and update existing root numeric parameter declarations losslessly.

Only numeric literal spans are changed. Native expressions are not evaluated;
quotes, comments, bindings, analysis settings and model files remain intact.
"""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import re
from pathlib import Path
from typing import Any

from .schematic import SchemeError, parse_value

_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,63}\Z")
_HEADER = re.compile(r"\.(parameter|param|define|def|global|set)\b", re.I)
_ASSIGN = re.compile(r"\s*([A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*)(?:\s*\([^=;]*\))?\s*=")


def _numeric(value):
    number = parse_value(value)
    if number == 0 and isinstance(value, str):
        coefficient = re.match(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",value.strip())
        try:
            nonzero = coefficient is not None and Decimal(coefficient[0]) != 0
        except InvalidOperation as error:
            raise SchemeError("Parameter exponent is outside the supported numeric range.") from error
        if nonzero:
            raise SchemeError("Parameter value underflows the supported numeric range; it cannot be stored as zero.")
    return number


def _lex(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    """Mask comments and quoted descriptions, retaining original offsets."""
    masked, quotes = list(text), []
    i = 0
    while i < len(text):
        if text[i] == "%":
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            masked[i:end] = " " * (end-i)
            i = end
        elif text[i] == '"':
            end = text.find('"', i+1)
            if end < 0:
                raise SchemeError("Unterminated quoted description in a native directive.")
            quotes.append((i, end+1, text[i+1:end]))
            masked[i:end+1] = " " * (end+1-i)
            i = end+1
        else:
            i += 1
    return "".join(masked), quotes


def _declarations(document: dict) -> tuple[list[dict], list[str]]:
    declarations, issues = [], []
    for obj in document["scm"]["Scheme"].get("Objects") or []:
        if obj.get("Type") != 900:
            continue
        text = (obj.get("Params") or {}).get("Text", "")
        if not isinstance(text, str):
            continue
        # Ordinary explanatory text is not a directive, even if it mentions one.
        try:
            masked, quotes = _lex(text)
        except SchemeError:
            if text.lstrip().startswith("."):
                issues.append(f"TEXT {obj['ID']} has an unterminated quoted directive.")
            continue
        first = len(masked)-len(masked.lstrip())
        if _HEADER.match(masked, first) is None:
            continue
        headers = [m for m in _HEADER.finditer(masked)
                   if m.start() == first or not masked[:m.start()].rsplit(";", 1)[-1].strip()
                   or not masked[:m.start()].rsplit("\n", 1)[-1].strip()]
        for index, header in enumerate(headers):
            stop = headers[index+1].start() if index+1 < len(headers) else len(text)
            mode = header[1].lower()
            mode = {"param": "parameter", "def": "define"}.get(mode, mode)
            cursor = header.end()
            for part in re.finditer(r"[^;]+(?:;|$)", masked[cursor:stop]):
                start, end = cursor+part.start(), cursor+part.end()
                segment = masked[start:end].rstrip(";")
                if not segment.strip():
                    continue
                assign = _ASSIGN.match(segment)
                if assign is None:
                    issues.append(f"TEXT {obj['ID']} contains an unrecognized .{mode} assignment.")
                    continue
                rhs_start = start+assign.end()
                rhs_end = start+len(segment)
                labels = [(a, b, label) for a, b, label in quotes if rhs_start <= a < rhs_end]
                literal_start = rhs_start+len(masked[rhs_start:rhs_end])-len(masked[rhs_start:rhs_end].lstrip())
                literal_end = rhs_start+len(masked[rhs_start:rhs_end].rstrip())
                literal = text[literal_start:literal_end]
                value, reason = None, None
                try:
                    value = _numeric(literal)
                except SchemeError:
                    reason = "Declaration is an expression, not a finite numeric literal."
                if labels and (len(labels) != 1 or masked[labels[0][1]:rhs_end].strip()
                               or labels[0][0] < literal_end):
                    reason = "Description must follow the complete numeric literal."
                if mode == "parameter" and "(" in assign[0]:
                    reason = "A parameter declaration must have a scalar name, not function arguments."
                declarations.append({"name": assign[1], "directive": mode, "value_si": value,
                    "literal": literal, "label": labels[0][2] if len(labels) == 1 else None,
                    "text_object_id": obj["ID"], "span": [literal_start, literal_end], "reason": reason})
    return declarations, issues


def _bindings(document: dict, name: str) -> list[dict]:
    found = []
    for obj in document["scm"]["Scheme"].get("Objects") or []:
        params = obj.get("Params") or {}
        tid = obj.get("Type")
        fields = []
        if tid in {1000, 1001, 1002}:
            field = {1000: "R", 1001: "C", 1002: "L"}[tid]
            fields.append((field, params.get(field)))
        elif tid in {2010, 3010}:
            section = {1: "DC", 2: "AC", 3: "PULSE"}.get(params.get("ST"))
            quantity = "I" if tid == 3010 else "U"
            if section:
                for field, value in (params.get(section) or {}).items():
                    if field in {quantity+"0", quantity+"MAX", quantity+"MIN", "F", "Delay", "TFR", "K", "PHI0"}:
                        fields.append((section+"."+field, value))
        for field, value in fields:
            if isinstance(value, str) and value.strip() == name:
                found.append({"component": obj.get("Name"), "native_type": tid, "field": field})
    return found


def inspect_parameters(document: dict) -> dict:
    declarations, issues = _declarations(document)
    parameters = []
    for item in declarations:
        if item["directive"] != "parameter":
            continue
        reasons = [item["reason"]] if item["reason"] else []
        if issues:
            reasons.append("Other native directives could not be parsed safely.")
        if not _NAME.fullmatch(item["name"]):
            reasons.append("Only plain root ASCII identifiers are editable.")
        if sum(other["name"] == item["name"] for other in declarations) != 1:
            reasons.append("Name has duplicate declarations or a define/global/set override.")
        bindings = _bindings(document, item["name"])
        for binding in bindings:
            target = binding["component"] + "." + binding["field"].rsplit(".", 1)[-1]
            if any(d["directive"] == "set" and d["name"] == target for d in declarations):
                reasons.append(f"A root .set overrides parameter binding {target}.")
        parameters.append({k: copy.deepcopy(item[k]) for k in
            ("name", "value_si", "literal", "label", "text_object_id")})
        parameters[-1].update({"editable": not reasons, "reasons": reasons,
                               "bindings": bindings})
    return {"scope": "root", "parameters": parameters, "issues": issues,
            "dependency_conflicts_checked": False}


def _changes(document: dict, updates: dict) -> tuple[dict, list[dict]]:
    if not isinstance(updates, dict) or not 1 <= len(updates) <= 64:
        raise SchemeError("updates must map 1–64 existing root parameter names to finite SI values.")
    declarations, issues = _declarations(document)
    if issues:
        raise SchemeError("Cannot safely update ambiguous directives: " + "; ".join(issues))
    normalized, changes = {}, []
    inspection = inspect_parameters(document)
    for name, raw in updates.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise SchemeError("Parameter names must be plain root ASCII identifiers of at most64 characters.")
        matches = [p for p in inspection["parameters"] if p["name"] == name]
        if len(matches) != 1 or not matches[0]["editable"]:
            reason = " ".join(matches[0]["reasons"]) if len(matches) == 1 else "Name is absent or duplicated."
            raise SchemeError(f"Parameter {name!r} cannot be updated: {reason} Inspect root_parameters.")
        value = _numeric(raw)
        for binding in matches[0]["bindings"]:
            field = binding["field"]
            target = binding["component"] + "." + field.rsplit(".", 1)[-1]
            if any(d["directive"] == "set" and d["name"] == target for d in declarations):
                raise SchemeError(f"A root .set overrides parameter binding {target}.")
            if (binding["native_type"] in {1000, 1001, 1002} or field.endswith((".F", ".TFR"))) and value <= 0:
                raise SchemeError(f"Parameter {name!r} requires a positive value for {binding['component']}.{field}.")
            if field.endswith(".Delay") and value < 0:
                raise SchemeError(f"Parameter {name!r} cannot make a source delay negative.")
            if field.endswith(".K") and not 0 < value < 100:
                raise SchemeError(f"Parameter {name!r} must keep pulse duty between0 and100.")
        declaration = next(p for p in declarations if p["name"] == name)
        normalized[name] = value
        changes.append({"name": name, "before_si": matches[0]["value_si"], "after_si": value,
                        "text_object_id": declaration["text_object_id"], "span": declaration["span"]})
    return normalized, changes


def edit_parameters(source_path: str | Path, updates: dict, output_path: str | Path, *,
                    expected_source_sha256: str | None = None) -> dict:
    from .annotations import _copy_circuit, _snapshots
    source = Path(source_path).expanduser().resolve(strict=True)
    snapshots = _snapshots(source)
    if expected_source_sha256 is not None:
        if not isinstance(expected_source_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}",expected_source_sha256):
            raise SchemeError("expected_source_sha256 must be a SHA256 hex digest.")
        if snapshots[source]["sha256"] != expected_source_sha256.lower():
            raise SchemeError("Source changed since inspection; no parameter output was published.")
    original = snapshots[source]["document"]
    normalized, changes = _changes(original, updates)
    for path, record in snapshots.items():
        if path == source:
            continue
        declarations, issues = _declarations(record["document"])
        if issues:
            raise SchemeError(f"Unrecognized child directives prevent global-conflict checks: {path.name}")
        if any(d["directive"] == "global" and d["name"] in normalized for d in declarations):
            raise SchemeError(f"A child .global conflicts with a requested root parameter in {path.name}.")

    def transform(document):
        # Compare the complete snapshot, so concurrent source edits cannot
        # silently change which occurrence the preserved offsets address.
        if document != original:
            raise SchemeError("Source changed during parameter editing; no output was published.")
        for path, record in snapshots.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise SchemeError("A source model changed during parameter editing; no output was published.")
        objects = {obj["ID"]: obj for obj in document["scm"]["Scheme"]["Objects"]}
        for oid in {change["text_object_id"] for change in changes}:
            text = objects[oid]["Params"]["Text"]
            for change in sorted((c for c in changes if c["text_object_id"] == oid), key=lambda c:c["span"][0], reverse=True):
                a, b = change["span"]
                text = text[:a] + format(change["after_si"], ".17g") + text[b:]
            objects[oid]["Params"]["Text"] = text

    result = _copy_circuit(source, output_path, root_transform=transform)
    from .schematic import _load
    _, edited, _ = _load(result["path"])
    result.update({"parameter_changes": [{k:v for k,v in c.items() if k != "span"} for c in changes],
                   "root_parameters": inspect_parameters(edited), "analysis_recomputed": False,
                   "descriptions_preserved": True,
                   "next_step": "Run a new native analysis for the edited values; existing explanatory notes retain their original wording."})
    result["root_parameters"]["dependency_conflicts_checked"] = True
    return result
