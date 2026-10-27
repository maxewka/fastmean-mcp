"""Native pins for diodes, controlled sources, transformers, switches and boxes.

Offsets are in SCM document units, independent of display zoom. The fixed
geometry and rotation were checked against FASTMEAN 6.1's pin initialization
and coordinate transformation routines. In particular controlled-source
outputs are asymmetric about the object's origin; a symmetric drawing would
place wires on the wrong pins.
"""
from __future__ import annotations

SIDES = ("Left", "Top", "Right", "Bottom")
_SIDE_DIRECTIONS = ((-1, 0), (0, -1), (1, 0), (0, 1))


class GeometryError(ValueError):
    """Native symbol geometry is unsupported or incompletely specified."""


def _integer(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GeometryError(f"{name} must be an integer native coordinate.")
    return value


def _transform(obj: dict, point: tuple[int, int], *, translate: bool) -> tuple[int, int]:
    rotation = _integer(obj.get("Rot", 0), "Rot")
    if rotation not in range(4):
        raise GeometryError("Native rotation must be 0, 1, 2 or 3.")
    if obj.get("FlipV", 0) or obj.get("FlipH", 0):
        raise GeometryError("Flipped generated native symbols are not supported.")
    x, y = point
    for _ in range(rotation):
        x, y = -y, x
    if translate:
        x += _integer(obj.get("X"), "X")
        y += _integer(obj.get("Y"), "Y")
    return x, y


def pin_labels(obj: dict) -> dict[int, str]:
    """Return native side-order labels for a Type7100 box."""
    if obj.get("Type") != 7100:
        return {}
    pins = (obj.get("Params") or {}).get("Pins")
    if not isinstance(pins, dict) or set(pins) - set(SIDES):
        raise GeometryError("A subcircuit needs native Left/Top/Right/Bottom pin lists.")
    labels = []
    for side in SIDES:
        names = pins.get(side) or []
        if not isinstance(names, list) or any(not isinstance(name, str) or not name for name in names):
            raise GeometryError("Subcircuit side pins must be lists of nonempty names.")
        labels.extend(names)
    if not labels or len(labels) > 256 or len(set(labels)) != len(labels):
        raise GeometryError("Subcircuit pin names must be nonempty and unique.")
    return dict(enumerate(labels, 1))


def subcircuit_size(obj: dict) -> tuple[int, int]:
    """Resolve the font-dependent native box size before routing its pins.

    A caller must not substitute an estimated filename width here: FASTMEAN
    sizes the box using its visible caption and side-label text metrics.
    """
    from .native_text import text_extent
    pins = (obj.get("Params") or {}).get("Pins")
    pin_labels(obj)
    caption = str((obj.get("Params") or {}).get("FileName", ""))
    if not caption or len(caption) > 20 or not caption.isascii():
        raise GeometryError("Generated subcircuit model paths must use at most20 ASCII characters; shorten the model name.")
    if obj.get("_geometry_scale",100) != 100 or obj.get("_geometry_custom_style",False):
        raise GeometryError("Subcircuit preview/routing requires generated default caption fonts and Scale100.")
    def extent(text, kind):
        try:
            return text_extent(text,kind)
        except KeyError as error:
            raise GeometryError("Generated subcircuit captions and pins must use printable ASCII.") from error
    side_widths = {side:max((extent(name,"pin")[0] for name in pins.get(side) or []),default=0) for side in SIDES}
    captions = [extent(str(obj.get("Name","")),"name"),extent(caption,"value")]
    capw = max(w+4 for w,h in captions)
    caph = sum(h+4 for w,h in captions)
    if obj.get("Rot",0) in (1,3):
        capw,caph = caph,capw
    width = max(56,16*max(len(pins.get("Top") or []),len(pins.get("Bottom") or []))
                +2*max(side_widths["Left"],side_widths["Right"])+16+capw)
    height = max(56,16*max(len(pins.get("Left") or []),len(pins.get("Right") or []))
                 +2*max(side_widths["Top"],side_widths["Bottom"])+16+caph)
    return width,height


def _subcircuit_geometry(obj: dict, width: int, height: int):
    width, height = _integer(width, "Box width"), _integer(height, "Box height")
    if width < 56 or height < 56:
        raise GeometryError("Native subcircuit boxes are at least 56 units on each axis.")
    pin_labels(obj)
    points, directions, index = {}, {}, 1
    sides = (obj["Params"]["Pins"])
    for side, direction in zip(SIDES, _SIDE_DIRECTIONS):
        names = sides.get(side) or []
        start = -8 * (len(names) - 1)
        for offset, _ in enumerate(names):
            along = start + 16 * offset
            if side == "Left": point = (-(width // 2) - 8, along)
            elif side == "Top": point = (along, -(height // 2) - 8)
            elif side == "Right": point = (width // 2 + 8, along)
            else: point = (along, height // 2 + 8)
            points[index], directions[index] = point, direction
            index += 1
    return points, directions, (-(width // 2), -(height // 2), width // 2, height // 2)


def _base_geometry(obj: dict):
    tid = obj.get("Type")
    if tid == 1101:
        # Width=height=24; native pin lead adds nine units to each half-width.
        return {1: (-21, 0), 2: (21, 0)}, {1: (-1, 0), 2: (1, 0)}, (-12, -12, 12, 12)
    if tid in {6000, 6001, 6002}:
        return ({1: (-16, -28), 2: (-16, 28), 3: (8, -28), 4: (8, 28)},
                {1: (0, -1), 2: (0, 1), 3: (0, -1), 4: (0, 1)}, (-24, -20, 24, 20))
    if tid == 6101:
        # Native IdealTrans: width 32, height 48, eight-unit leads.
        return ({1: (-24, -32), 2: (-24, 32), 3: (24, -32), 4: (24, 32)},
                {1: (-1, 0), 2: (-1, 0), 3: (1, 0), 4: (1, 0)}, (-16, -24, 16, 24))
    if tid == 6600:
        # Native VCSwitch: width=height=40; control pair at left.
        return ({1: (-16, -28), 2: (-16, 28), 3: (16, -28), 4: (16, 28)},
                {1: (0, -1), 2: (0, 1), 3: (0, -1), 4: (0, 1)}, (-20, -20, 20, 20))
    if tid == 7100:
        return _subcircuit_geometry(obj, *subcircuit_size(obj))
    raise GeometryError(f"Native geometry for component type {tid!r} is unsupported.")


def pin_positions(obj: dict) -> dict[int, tuple[int, int]]:
    return {pin: _transform(obj, point, translate=True) for pin, point in _base_geometry(obj)[0].items()}


def pin_directions(obj: dict) -> dict[int, tuple[int, int]]:
    return {pin: _transform(obj, direction, translate=False) for pin, direction in _base_geometry(obj)[1].items()}


def body_bounds(obj: dict) -> tuple[int, int, int, int]:
    left, top, right, bottom = _base_geometry(obj)[2]
    corners = [_transform(obj, point, translate=True) for point in
               ((left, top), (right, top), (right, bottom), (left, bottom))]
    return min(x for x, y in corners), min(y for x, y in corners), max(x for x, y in corners), max(y for x, y in corners)
