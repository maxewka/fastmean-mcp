"""Exact supported native wire bends and lossless removal of redundant CONs.

SCM stores endpoints only. FASTMEAN 6.1 derives bends from pin directions;
it has no serialized free-form polyline. We use the straight, facing L and
opposing-pin midpoint cases only, and retain waypoints for other routes.
The existing geometric path must match exactly before a CON is removed.
"""
from __future__ import annotations

from collections import defaultdict

DIRECTIONS = ((-1, 0), (0, -1), (1, 0), (0, 1))


class WireGeometryError(ValueError):
    pass


def terminal(obj, pin):
    tid, rot = obj['Type'], obj.get('Rot', 0)
    if obj.get('FlipH', 0) or obj.get('FlipV', 0) or rot not in range(4):
        raise WireGeometryError('Unsupported flipped/rotated native wire endpoint.')
    if tid in {1101, 6000, 6001, 6002, 7100}:
        from .native_geometry import pin_positions, pin_directions
        return pin_positions(obj)[pin], pin_directions(obj)[pin]
    p = (obj['X'], obj['Y'])
    if tid in {1000, 1001, 1002, 2010}:
        d = DIRECTIONS[(rot + (0 if pin == 1 else 2)) % 4]
        return (p[0] + 40*d[0], p[1] + 40*d[1]), d
    if tid == 300:
        return p, DIRECTIONS[(pin - 1 + rot) % 4]
    if tid == 400:
        return p, DIRECTIONS[rot]
    if tid == 200:
        return p, DIRECTIONS[(rot + 1) % 4]
    raise WireGeometryError(f'Unsupported wire endpoint Type {tid}.')


def compact_path(points):
    result = []
    for p in points:
        p = tuple(p)
        if result and p == result[-1]:
            continue
        while len(result) >= 2:
            a, b = result[-2:]
            u, v = (b[0]-a[0], b[1]-a[1]), (p[0]-b[0], p[1]-b[1])
            if u[0]*v[1] == u[1]*v[0] and u[0]*v[0] + u[1]*v[1] > 0:
                result.pop()
            else:
                break
        result.append(p)
    return result


def native_path(a, da, b, db):
    """Return a proven native path, rejecting unimplemented detour cases."""
    a, b = tuple(a), tuple(b)
    delta = (b[0]-a[0], b[1]-a[1])
    facing_a = delta[0]*da[0] + delta[1]*da[1] > 0
    facing_b = delta[0]*db[0] + delta[1]*db[1] < 0
    if a == b:
        raise WireGeometryError('A zero-length native wire is ambiguous.')
    if not facing_a or not facing_b:
        raise WireGeometryError('Unsupported implicit native wire bend: pins require a detour.')
    if da == (-db[0], -db[1]):
        axis = 0 if da[0] else 1
        if delta[1-axis] == 0:
            return [a, b]
        if abs(delta[axis]) >= 12:
            # Native integer division places the middle segment toward the
            # lower coordinate, including negative document coordinates.
            mid = min(a[axis], b[axis]) + abs(delta[axis]) // 2
            p, q = list(a), list(b)
            p[axis] = q[axis] = mid
            return _native_snap(compact_path([a, p, q, b]))
    elif da[0]*db[0] + da[1]*db[1] == 0 and abs(delta[0]) >= 12:
        corner = (b[0], a[1]) if da[0] else (a[0], b[1])
        return _native_snap(compact_path([a, corner, b]))
    raise WireGeometryError('Unsupported implicit native wire bend: retain an explicit waypoint.')


def _native_snap(points):
    # Native cleanup rounds intermediate coordinates to four document units
    # using C integer division (truncation toward zero). A single L corner is
    # processed as both the first and last interior vertex.
    points = [list(p) for p in points]
    def snap(value):
        return int((value + 2) / 4) * 4
    for i in range(1, len(points)-1):
        if i == 1:
            axis = 1 if points[i][0] == points[0][0] else 0
            points[i][axis] = snap(points[i][axis])
        if i == len(points)-2:
            axis = 1 if points[i][0] == points[i+1][0] else 0
            points[i][axis] = snap(points[i][axis])
    if any(p[0] != q[0] and p[1] != q[1] for p, q in zip(points, points[1:])):
        raise WireGeometryError('Unsupported implicit native wire bend: native snapping makes a diagonal segment.')
    return compact_path(points)


def wire_path(wire, objects):
    ends = [wire[key] for key in ('obj1', 'obj2')]
    a, da = terminal(objects[ends[0]['ID']], ends[0]['pin'])
    b, db = terminal(objects[ends[1]['ID']], ends[1]['pin'])
    return native_path(a, da, b, db)


def simplify_wires(objects, wires):
    """Remove degree-two CONs only when native routing preserves every bend.

    Mutates the generated lists, not an input SCM. Branches and endpoints are
    untouched. Each component pin still has exactly one native wire.
    """
    by_id = {o['ID']: o for o in objects}
    removed = 0
    while True:
        incident = defaultdict(list)
        for index, w in enumerate(wires):
            for key in ('obj1', 'obj2'):
                incident[w[key]['ID']].append((index, key))
        changed = False
        for oid, obj in list(by_id.items()):
            entries = incident[oid]
            if obj['Type'] != 300 or len(entries) != 2 or entries[0][0] == entries[1][0]:
                continue
            (i, ki), (j, kj) = entries
            wi, wj = wires[i], wires[j]
            ei = wi['obj2' if ki == 'obj1' else 'obj1']
            ej = wj['obj2' if kj == 'obj1' else 'obj1']
            if ei['ID'] == ej['ID']:
                continue
            joined = {'obj1': dict(ei), 'obj2': dict(ej)}
            try:
                first, second = wire_path(wi, by_id), wire_path(wj, by_id)
                if ki == 'obj1': first.reverse()
                if kj == 'obj2': second.reverse()
                old = compact_path(first + second[1:])
                if wire_path(joined, by_id) != old:
                    continue
            except WireGeometryError:
                continue
            wires[i] = joined
            del wires[j]
            del by_id[oid]
            removed += 1
            changed = True
            break
        if not changed:
            break
    objects[:] = [o for o in objects if o['ID'] in by_id]
    return removed
