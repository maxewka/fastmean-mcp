"""Read-only SCM inspection with complete, byte-bounded pages and snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .artifacts import MAX_RESPONSE_BYTES
from .parameters import inspect_parameters
from .schematic import SchemeError, _load, _summarize

SECTIONS = ("summary", "components", "nodes", "objects", "texts", "ports",
            "parameters", "analysis", "wires", "warnings", "parameter_issues")


def _bytes(value) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as error:
        raise SchemeError("Inspection contains an unsupported or nonfinite native value.") from error


def _select(value, path):
    if not isinstance(path, list) or len(path) > 24:
        raise SchemeError("detail_path must contain at most24 exact mapping keys or list indices.")
    for part in path:
        if isinstance(value, dict) and isinstance(part, str) and part in value:
            value = value[part]
        elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
            value = value[part]
        else:
            raise SchemeError(f"detail_path has no native field/index {part!r}.")
    return value


def _page(value, offset, limit, budget, *, defer=False):
    """Retain complete entries. Huge properties can be read via detail_path."""
    kind = "mapping" if isinstance(value, dict) else "list" if isinstance(value, list) else "text" if isinstance(value, str) else "scalar"
    if kind == "scalar":
        if offset:
            raise SchemeError("A scalar selection requires offset=0.")
        if _bytes(value) > budget:
            raise SchemeError("Selected native scalar exceeds the inspection response budget.")
        return value, {"kind": kind, "total": 1, "returned_count": 1, "has_more": False, "next_offset": None}
    total = len(value)
    selected = {} if kind == "mapping" else "" if kind == "text" else []
    keys = list(value) if kind == "mapping" else None
    used, count, oversized = _bytes(selected), 0, None
    for index in range(offset, min(offset+limit, total)):
        item = {keys[index]: value[keys[index]]} if kind == "mapping" else value[index]
        cost = _bytes(item)+2
        if used+cost > budget:
            if count == 0:
                oversized = keys[index] if keys is not None else index
                if not defer:
                    raise SchemeError(f"Native item at detail_path + [{oversized!r}] exceeds the response budget; select its fields with detail_path.")
            break
        if kind == "mapping":
            selected[keys[index]] = value[keys[index]]
        elif kind == "text":
            selected += item
        else:
            selected.append(item)
        used += cost
        count += 1
    more = offset+count < total
    info = {"kind": kind, "offset": offset, "limit": limit, "total": total,
            "returned_count": count, "has_more": more,
            "next_offset": offset+count if more and count else None}
    if oversized is not None:
        info["needs_detail_path"] = [oversized]
    return selected, info


def inspect_circuit(path, include_objects=False, *, section="summary", offset=0, limit=100,
                    detail_path=None, expected_source_sha256=None) -> dict[str, Any]:
    if section not in SECTIONS:
        raise SchemeError(f"section must be one of {', '.join(SECTIONS)}.")
    if type(offset) is not int or not 0 <= offset <= 16_777_216:
        raise SchemeError("offset must be an integer from0 to16777216.")
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise SchemeError("limit must be an integer from1 to1000.")
    if type(include_objects) is not bool:
        raise SchemeError("include_objects must be a boolean.")
    if expected_source_sha256 is not None and (not isinstance(expected_source_sha256, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_source_sha256)):
        raise SchemeError("expected_source_sha256 must be a SHA256 hex digest.")
    from pathlib import Path
    source = Path(path).expanduser().resolve(strict=True)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    if expected_source_sha256 is not None and before != expected_source_sha256.lower():
        raise SchemeError("Source changed since the previous inspection page; inspect a new snapshot.")
    source, document, encoding = _load(source)
    summary = _summarize(document, source, encoding)
    if hashlib.sha256(source.read_bytes()).hexdigest() != before:
        raise SchemeError("Source changed while being inspected; retry a new snapshot.")
    parameters = inspect_parameters(document)
    objects = summary["objects"]
    collections = {"components": summary["components"], "nodes": summary["nodes"], "objects": objects,
        "texts": [obj for obj in objects if obj.get("Type") == 900], "ports": summary["ports"],
        "parameters": parameters["parameters"], "analysis": summary["analysis"],
        "wires": document["scm"]["Scheme"].get("Wires") or [],
        "warnings": summary["warnings"], "parameter_issues": parameters["issues"]}
    result = {"path": str(source), "source_sha256": before, "encoding": encoding,
        "format": summary["format"], "version": summary["version"], "section": section,
        "component_count": summary["component_count"], "wire_count": summary["wire_count"],
        "object_count": len(objects), "unsupported_type_ids": summary["unsupported_type_ids"],
        "counts": {name: len(value) for name, value in collections.items()},
        "response_limit_bytes": MAX_RESPONSE_BYTES}
    if section != "summary":
        selection = _select(collections[section], [] if detail_path is None else detail_path)
        result["detail_path"] = [] if detail_path is None else detail_path
        result["data"], result["page"] = _page(selection, offset, limit, MAX_RESPONSE_BYTES-_bytes(result)-1024)
    else:
        if detail_path:
            raise SchemeError("Select a specific section before using detail_path.")
        result["pages"] = {}
        # Separate allocations prevent native Params/USER curves from exhausting
        # the metadata/graph-expression budget, even with include_objects=True.
        budgets = {"ports": 8, "analysis": 24, "parameters": 16, "parameter_issues": 4,
                   "texts": 12, "components": 20, "nodes": 12, "warnings": 4}
        if include_objects:
            budgets["objects"] = 16
        for name, kib in budgets.items():
            values = collections[name]
            if name == "components":
                values = [{k:v for k,v in item.items() if k != "parameters"} for item in values]
            data, page = _page(values, offset, limit, kib*1024, defer=True)
            page["section"] = name
            result["pages"][name] = page
            if name == "parameters":
                result["root_parameters"] = {**parameters, "parameters": data, "issues": []}
            elif name == "parameter_issues":
                result["root_parameters"]["issues"] = data
            else:
                result[name] = data
        result["truncated"] = any(page["has_more"] for page in result["pages"].values())
        result["component_parameters"] = "Compact components omit raw Params; use section=components or objects and detail_path."
    if _bytes(result) > MAX_RESPONSE_BYTES:
        raise SchemeError("Native inspection metadata exceeds the response budget; select a specific section.")
    return result
