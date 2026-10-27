"""Power primitive routing and preview preserve native terminals and polarity."""
from collections import Counter
from pathlib import Path
import tempfile

import pytest

from fastmean_mcp.captions import caption_bounds, native_component_captions, native_component_value
from fastmean_mcp.native_geometry import pin_directions, pin_positions
from fastmean_mcp.preview import ORIGIN, _draw_native_component, render_schematic
from fastmean_mcp.schematic import _load, create_circuit
from fastmean_mcp.wires import terminal, wire_path


@pytest.mark.parametrize("kind,tid,parameters", [
    ("TR", 6101, {"n": 2}),
    ("SW", 6600, {"Uon": 3, "Uoff": 2, "Ron": .05, "Roff": 1e7}),
])
@pytest.mark.parametrize("rotation", range(4))
def test_power_symbol_has_four_distinct_wired_terminals_and_clear_captions(kind, tid, parameters, rotation):
    symbol = {"Type": tid, "X": 1000, "Y": 800, "Rot": rotation,
              "FlipH": 0, "FlipV": 0, "Name": kind+"1", "Params": parameters}
    positions, directions = pin_positions(symbol), pin_directions(symbol)
    # Phase dots and control signs must keep identifying the same electrical
    # pins when the whole symbol is rotated, including its outgoing wires.
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle
    figure = Figure()
    axis = figure.add_subplot()
    _draw_native_component(axis, symbol, native_component_value(symbol))
    def nearest_pin(point):
        return min(positions, key=lambda pin: sum((a-b)**2 for a, b in zip(point, positions[pin])))
    if kind == "TR":
        dots = [patch for patch in axis.patches if isinstance(patch, Circle)]
        assert len(dots) == 2
        assert {nearest_pin(dot.center) for dot in dots} == {1, 3}
    else:
        signs = {text.get_text(): nearest_pin(text.get_position()) for text in axis.texts
                 if text.get_text() in {"+", "−"}}
        assert signs == {"+": 1, "−": 2}
    figure.clear()
    native_directions = ((-1, 0), (0, -1), (1, 0), (0, 1))
    port_positions = {}
    for pin, (x, y) in positions.items():
        dx, dy = directions[pin]
        port_positions[f"P{pin}"] = {
            "x": x+160*dx, "y": y+160*dy,
            "rotation": native_directions.index((-dx, -dy)),
        }
    spec = {"components": [{"kind": kind, "name": kind+"1", "nodes": ["p1", "p2", "p3", "p4"],
                            "parameters": parameters}],
            "ports": {f"P{i}": f"p{i}" for i in range(1, 5)},
            "layout": {"placements": {kind+"1": {"x": 1000, "y": 800, "rotation": rotation}},
                       "ports": port_positions}}
    with tempfile.TemporaryDirectory(prefix="fm-power-preview-") as directory:
        root = Path(directory)
        path = root / f"{kind}-{rotation}.scm"
        result = create_circuit(spec, path, subcircuit=True)
        assert result["components"][0]["native_pin_nodes"] == ["P1", "P2", "P3", "P4"]
        _, document, _ = _load(path)
        objects = {o["ID"]: o for o in document["scm"]["Scheme"]["Objects"]}
        component = next(o for o in objects.values() if o["Type"] == tid)
        endpoint_counts = Counter()
        segments = []
        for wire in document["scm"]["Scheme"]["Wires"]:
            for end in wire.values():
                endpoint_counts[end["ID"], end["pin"]] += 1
            points = wire_path(wire, objects)
            segments.extend(zip(points, points[1:]))
        assert all(endpoint_counts[component["ID"], pin] == 1 for pin in range(1, 5))
        for pin in range(1, 5):
            assert terminal(component, pin) == (positions[pin], directions[pin])
        assert all(a[0] == b[0] or a[1] == b[1] for a, b in segments)
        for caption in native_component_captions(component, native_component_value(component)):
            left, top, right, bottom = caption_bounds(caption)
            for a, b in segments:
                if a[1] == b[1]:
                    assert not (top <= a[1] <= bottom and
                                max(min(a[0], b[0]), left) <= min(max(a[0], b[0]), right))
                else:
                    assert not (left <= a[0] <= right and
                                max(min(a[1], b[1]), top) <= min(max(a[1], b[1]), bottom))
        original = path.read_bytes()
        preview = render_schematic(path, root / "previews")
        assert path.read_bytes() == original
        assert preview["origin"] == ORIGIN
        assert not preview["approximate_wire_routes"]
        svg = Path(preview["svg_path"]).read_text(encoding="utf-8")
        assert native_component_value(component) in svg
        assert all(f"P{i}" in svg for i in range(1, 5))
