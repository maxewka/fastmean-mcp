"""Repack an existing linear SCM into physical wires without changing its model.

The original electrical objects and analysis sections are retained.  Only
geometry, connection objects, internal node labels and annotation positions
change.  Compilation happens in a private temporary directory; a completed,
validated file is published without replacing any existing file.
"""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from .schematic import SchemeError, _load, _summarize, _write_document, create_circuit


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_U_CALL = re.compile(r"(?<![A-Za-z0-9_])U\s*\(([^()]*)\)", re.I)
_GEOMETRY = ("ID", "X", "Y", "Rot", "FlipV", "FlipH")
_ANALYSIS_SECTIONS = ("TD", "FD", "AOD", "SOD", "DCOP")


def _analysis_strings(body: dict, text_objects: list[dict]):
    for section in ("TD", "FD"):
        settings = body.get(section)
        if not isinstance(settings, dict):
            continue
        expressions = settings.get("Expressions") or []
        if not isinstance(expressions, list):
            raise SchemeError(f"{section}.Expressions must be a list to preserve analysis references.")
        for expression in expressions:
            if isinstance(expression, dict):
                for axis in ("x", "y"):
                    if isinstance(expression.get(axis), str):
                        yield expression[axis]
    for obj in text_objects:
        params = obj.get("Params") or {}
        text = params.get("Text") if isinstance(params, dict) else None
        # Ordinary explanatory text such as "U(t)" is not a native node lookup.
        # Native directives, including .define and .write, may contain lookups.
        if isinstance(text, str) and re.search(r"^\s*\.[A-Za-z_]", text, re.M):
            yield text


def _external_interfaces(summary: dict, body: dict, notes: list[dict]) -> tuple[dict[str, str], str, str | None]:
    original_ports = summary["ports"]
    component_names = {item["name"] for item in summary["components"]}
    selected: dict[str, str] = {}
    referenced: list[str] = []

    def retain(alias: str) -> None:
        if alias not in original_ports:
            raise SchemeError(f"Cannot preserve U({alias}): it is not an existing named port or component.")
        if not _IDENTIFIER.fullmatch(alias) or alias.casefold() in {"gnd", "ground"}:
            raise SchemeError(f"Port {alias!r} cannot be retained by the ASCII-named layout compiler.")
        node = original_ports[alias]
        if node == "0":
            raise SchemeError(f"External port {alias!r} is grounded; use U(0) before relayout.")
        selected[alias] = node

    for alias in original_ports:
        if alias.casefold() in {"in", "input", "out", "output"}:
            retain(alias)
    for expression in _analysis_strings(body, notes):
        matches = list(_U_CALL.finditer(expression))
        if len(matches) != len(re.findall(r"(?<![A-Za-z0-9_])U\s*\(", expression, re.I)):
            raise SchemeError("Complex nested U(...) references cannot be safely preserved during relayout.")
        for match in matches:
            for token in (part.strip() for part in match[1].split(",")):
                if token == "0":
                    continue
                if token.isdecimal():
                    raise SchemeError("Numeric node-voltage references cannot survive renumbering; add named ports before relayout.")
                if token in component_names:
                    if token in original_ports:
                        raise SchemeError(f"U({token}) is ambiguous between a component and a port.")
                    continue
                retain(token)
                if token not in referenced:
                    referenced.append(token)

    input_name = next((name for name in selected if name.casefold() in {"in", "input"}), None)
    output_name = next((name for name in selected if name.casefold() in {"out", "output"}), None)
    source_node = next((component["nodes"][0] for component in summary["components"]
                        if component["kind"] == "U" and component["nodes"][1] == "0"), None)

    def synthetic(node: str, preferred: str) -> str:
        same = next((name for name, old_node in selected.items() if old_node == node), None)
        if same:
            return same
        original = next((name for name, old_node in original_ports.items()
                         if old_node == node and _IDENTIFIER.fullmatch(name)
                         and name.casefold() not in {"gnd", "ground"}
                         and name not in component_names), None)
        name = original or preferred
        counter = 1
        while name in component_names or (name in selected and selected[name] != node):
            name = f"{preferred}_{counter}"
            counter += 1
        selected[name] = node
        return name

    if input_name is None and source_node is not None:
        input_name = synthetic(source_node, "input")
    if output_name is None:
        output_name = next((name for name in referenced if name != input_name), None)
    if output_name is None:
        candidates = [node for component in reversed(summary["components"])
                      for node in component["nodes"] if node != "0" and node != source_node]
        node = candidates[0] if candidates else source_node
        if node is None:
            node = next((node["name"] for node in summary["nodes"] if node["name"] != "0"), None)
        if node is None:
            raise SchemeError("The circuit has no nonground node to lay out.")
        output_name = synthetic(node, "output")
    return selected, output_name, input_name


def _map_connectivity(before: dict, after: dict) -> dict[str, str]:
    new_components = {item["name"]: item for item in after["components"]}
    mapping, reverse = {"0": "0"}, {"0": "0"}
    if len(new_components) != len(before["components"]):
        raise SchemeError("Relayout changed the number or identity of electrical components.")
    for component in before["components"]:
        observed = new_components.get(component["name"])
        if observed is None or observed["kind"] != component["kind"]:
            raise SchemeError("Relayout changed an electrical component type or name.")
        if observed["parameters"] != component["parameters"]:
            raise SchemeError("Relayout changed native electrical parameters.")
        for old, new in zip(component["native_pin_nodes"], observed["native_pin_nodes"]):
            if mapping.setdefault(old, new) != new or reverse.setdefault(new, old) != old:
                raise SchemeError("Relayout changed native terminal connectivity.")
    return mapping


def relayout_circuit(
    source_path: str | Path,
    output_path: str | Path,
    placements: dict[str, dict] | None = None,
    density: str = "compact",
) -> dict[str, Any]:
    """Create a wire-connected copy of an existing R/C/L/U text schematic.

    Named I/O and ports used by native U(...) expressions remain stable. Internal
    node labels can change and are reported in ``node_mapping``. Numeric node
    voltage references and unsupported component types are rejected before the
    destination is created. Native component parameters, math directives, and
    TD/FD/AOD/SOD/DCOP sections are preserved rather than reconstructed.
    """
    source, original, encoding = _load(source_path)
    output = Path(output_path).expanduser().absolute()
    if output.suffix.lower() != ".scm":
        raise SchemeError("Relayout output filename must end in .scm.")
    if os.path.normcase(str(output.resolve())) == os.path.normcase(str(source)):
        raise SchemeError("Relayout must create a new file; the original cannot be overwritten.")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Relayout destination already exists: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {output.parent}")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    before = _summarize(original, source, encoding)
    if before["unsupported_type_ids"] or any(obj["Type"] in {410,420} for obj in original["scm"]["Scheme"].get("Objects") or []):
        from .native_relayout import relayout_native
        return relayout_native(source,output,placements,density)
    if not before["components"]:
        raise SchemeError("Relayout requires at least one supported electrical component.")
    components_by_id = {obj["ID"]: obj for obj in before["objects"] if obj["Type"] in {1000, 1001, 1002, 2010}}
    notes = [obj for obj in before["objects"] if obj["Type"] == 900]
    ports, output_name, input_name = _external_interfaces(before, original["scm"], notes)

    logical_nodes = {"0": "0"}
    components = []
    for item in before["components"]:
        if not _IDENTIFIER.fullmatch(item["name"]):
            raise SchemeError(f"Component {item['name']!r} needs an ASCII identifier before relayout.")
        for node in item["nodes"]:
            if node not in logical_nodes:
                logical_nodes[node] = f"relayout_node_{len(logical_nodes)}"
        # The geometry compiler needs positive literal values. Compile geometry
        # with placeholders, then restore the complete native objects/Params.
        # This also preserves parameter expressions and inactive waveform groups.
        component = {"kind": item["kind"], "name": item["name"],
                     "nodes": [logical_nodes[node] for node in item["nodes"]], "value": 1}
        if item["kind"] in {"C", "L"}:
            component["initial_condition"] = 0
        components.append(component)
    for alias, node in ports.items():
        if node not in logical_nodes:
            raise SchemeError(f"External port {alias!r} is not connected to an electrical component.")
    options: dict[str, str] = {"output": output_name}
    if input_name is not None:
        options["input"] = input_name
    spec: dict[str, Any] = {"components": components,
                            "ports": {alias: logical_nodes[node] for alias, node in ports.items()},
                            "analysis": options}
    spec["layout"] = {"density": density}
    if placements is not None:
        spec["layout"]["placements"] = placements

    # Same-volume staging allows atomic, exclusive hard-link publication on
    # NTFS/POSIX: readers never see a partial file and an existing file is never
    # replaced. TemporaryDirectory unlinks only this freshly created subtree.
    with tempfile.TemporaryDirectory(prefix=".fastmean-relayout-", dir=output.parent) as temporary:
        workspace = Path(temporary).resolve()
        if workspace.parent != output.parent.resolve() or not workspace.name.startswith(".fastmean-relayout-"):
            raise SchemeError("Unexpected relayout staging directory.")
        compiled = create_circuit(spec, workspace / "geometry.scm")
        _, geometry, _ = _load(workspace / "geometry.scm")
        merged = copy.deepcopy(original)
        old_body, new_body = merged["scm"], geometry["scm"]
        old_body.setdefault("General", {}).update(copy.deepcopy(new_body["General"]))
        new_scheme = copy.deepcopy(old_body["Scheme"])
        new_scheme["Objects"] = copy.deepcopy(new_body["Scheme"]["Objects"])
        new_scheme["Wires"] = copy.deepcopy(new_body["Scheme"]["Wires"])
        old_by_name = {component["name"]: components_by_id[component["native_id"]] for component in before["components"]}
        restored = []
        for obj in new_scheme["Objects"]:
            if obj["Type"] in {1000, 1001, 1002, 2010}:
                original_obj = copy.deepcopy(old_by_name[obj["Name"]])
                for key in _GEOMETRY:
                    original_obj[key] = obj[key]
                restored.append(original_obj)
            else:
                restored.append(obj)
        new_scheme["Objects"] = restored
        annotation_mapping = []
        next_id = max(obj["ID"] for obj in restored) + 1
        used_names = {str(obj.get("Name", "")).casefold() for obj in restored}
        left, top, right, bottom = compiled["layout"]["bounds"]
        note_y = bottom + 120
        for index, note in enumerate(notes, 1):
            annotation = copy.deepcopy(note)
            annotation["ID"], annotation["X"], annotation["Y"] = next_id, left + 160, note_y
            old_name = str(annotation.get("Name", f"TEXT{index}"))
            name = old_name
            suffix = 1
            while name.casefold() in used_names:
                name = f"RelayoutText_{index}_{suffix}"
                suffix += 1
            annotation["Name"] = name
            used_names.add(name.casefold())
            new_scheme["Objects"].append(annotation)
            annotation_mapping.append({"source_id": note["ID"], "id": next_id, "source_name": old_name, "name": name})
            next_id += 1
            text = str((annotation.get("Params") or {}).get("Text", ""))
            note_y += max(120, (text.count("\n") + 1) * 24 + 60)
        if notes:
            old_body["General"]["SHeight"] = max(old_body["General"].get("SHeight", 3000), note_y + 400)
        old_body["Scheme"] = new_scheme
        prepared = _write_document(merged, workspace / "ready.scm", overwrite=False)
        _, serialized, _ = _load(prepared)
        after = _summarize(serialized, output.resolve(), "utf-8")
        node_mapping = _map_connectivity(before, after)
        for alias, old_node in ports.items():
            if after["ports"].get(alias) != node_mapping[old_node]:
                raise SchemeError(f"Relayout changed external port {alias!r}.")
        for section in _ANALYSIS_SECTIONS:
            if serialized["scm"].get(section) != original["scm"].get(section):
                raise SchemeError(f"Relayout changed the native {section} analysis section.")
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise SchemeError("Source changed during relayout; no output was published.")
        os.link(prepared, output)

    after.update({"ok": True, "path": str(output.resolve()), "source": str(source),
                  "source_sha256": source_hash, "source_unchanged": True,
                  "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                  "node_mapping": node_mapping, "layout": compiled["layout"],
                  "external_ports": copy.deepcopy(after["ports"]),
                  "port_objects_before": sum(obj["Type"] == 400 for obj in before["objects"]),
                  "port_objects_after": sum(obj["Type"] == 400 for obj in after["objects"]),
                  "removed_internal_ports": sorted(set(before["ports"]) - set(after["ports"])),
                  "annotations": annotation_mapping,
                  "preserved_analysis_sections": [name for name in _ANALYSIS_SECTIONS if name in original["scm"]]})
    return after
