"""Deterministic, wire-connected layouts for native two-terminal circuits.

Signal paths run left-to-right, shunts downward, parallel paths above the main
path. A small orthogonal router joins terminals through native CON objects.
Ports name external interfaces only; they never substitute for internal wires.
"""
from __future__ import annotations

from collections import defaultdict, deque
import bisect
import copy
from dataclasses import dataclass
import heapq
import math
import time
from typing import Any

STEP = 20
COORDINATE_STEP = 4
PITCH = 320
BRANCH = 200
SPACING = {
    "standard": (PITCH, BRANCH, 240, 600, 400),
    "compact": (240, 160, 200, 400, 320),
}
# Native CON terminal directions, confirmed against bundled FASTMEAN circuits.
DIRECTIONS = ((-1, 0), (0, -1), (1, 0), (0, 1))
PIN_FOR_DIRECTION = {direction: index + 1 for index, direction in enumerate(DIRECTIONS)}
TYPE_IDS = {"R": 1000, "C": 1001, "L": 1002, "U": 2010, "I": 3010}


class LayoutError(ValueError):
    pass


@dataclass
class Terminal:
    oid: int
    pin: int
    net: str
    point: tuple[int, int]
    direction: tuple[int, int]
    lead: tuple[tuple[int, int], ...] = ()


def _object(oid, tid, name, x, y, rot=0):
    return {"ID": oid, "Type": tid, "Name": name, "X": x, "Y": y,
            "Rot": rot, "FlipV": 0, "FlipH": 0, "active_property_page": 0}


def _path(components: list[dict], start: str, end: str) -> tuple[list[str], list[int]]:
    graph = defaultdict(list)
    for index, item in enumerate(components):
        if len(item["nodes"]) != 2:
            continue
        a, b = item["nodes"]
        if a != "0" and b != "0":
            graph[a].append((b, index))
            graph[b].append((a, index))
    queue, previous = deque([start]), {start: None}
    while queue:
        node = queue.popleft()
        if node == end:
            break
        for neighbor, edge in graph[node]:
            if neighbor not in previous:
                previous[neighbor] = (node, edge)
                queue.append(neighbor)
    if end not in previous:
        return [start], []
    nodes, edges = [end], []
    while nodes[-1] != start:
        parent, edge = previous[nodes[-1]]
        nodes.append(parent)
        edges.append(edge)
    return list(reversed(nodes)), list(reversed(edges))


def _orientation(a: tuple[int, int], b: tuple[int, int]) -> int:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) >= abs(dy):
        return 0 if dx >= 0 else 2
    return 1 if dy >= 0 else 3


def _snap(value: float) -> int:
    return round(value / STEP) * STEP


def _edge(a, b):
    return tuple(sorted((a, b)))


def _neighbors(graph, point):
    return graph.get(point, set())


def _direction(a, b):
    return ((b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1]))


def _ground_bounds(obj):
    """Bounds of the actual rotated preview/native ground stem and bars."""
    points = []
    for x,y in ((0,0),(0,28),(-16,14),(16,14),(-10,21),(10,21),(-4,28),(4,28)):
        for _ in range(obj.get("Rot",0)): x,y = -y,x
        points.append((obj["X"]+x,obj["Y"]+y))
    return min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)


class _Router:
    """Route on exact native pin axes, rather than adapting pins to a grid.

    The public placement grid is an authoring constraint, not wire geometry.
    Coordinate compression keeps off-grid diode/source/box pins exact while
    avoiding the cost and little staircase bends of a fine uniform grid.
    """
    BEND_COST = 80

    def __init__(self, objects: list[dict], terminals: list[Terminal], hubs: dict,
                 ground_y: int, routes: dict | None = None, hard_hubs=(), local_ground_pairs=()):
        self.objects, self.terminals, self.hubs = objects, terminals, hubs
        self.hard_hubs = set(hard_hubs)
        self.deadline = time.monotonic() + 20
        self.ground_y = ground_y
        self.routes = routes or {}
        self.local_ground_pairs = local_ground_pairs
        self.graphs: dict[str, dict[tuple[int, int], set]] = {}
        self.open_ends = {}
        self.reserved = {terminal.point: terminal.net for terminal in terminals}
        self.anchors = {point:net for net,point in hubs.items() if net in self.hard_hubs or net in self.routes}
        if len(self.reserved) != len(terminals):
            raise LayoutError("Component terminals overlap; give the components more room.")
        self.escapes = {}
        for terminal in terminals:
            if terminal.lead:
                point = terminal.lead[-1]
                if self.escapes.setdefault(point, terminal.net) != terminal.net:
                    raise LayoutError("Terminal routing escapes for different nodes overlap; increase placement spacing.")
        rectangles = []
        self.caption_rectangles = []
        for obj in objects:
            if obj["Type"] == 200:
                rectangles.append(_ground_bounds(obj))
            elif obj["Type"] in TYPE_IDS.values():
                x, y = obj["X"], obj["Y"]
                rectangles.append((x-20, y-20, x+20, y+20))
            elif obj["Type"] in {1101, 6000, 6001, 6002, 6101, 6600, 7100}:
                from .native_geometry import body_bounds
                rectangles.append(body_bounds(obj))
            from .captions import CAPTION_TYPES, caption_bounds, native_component_captions, native_component_value
            if obj["Type"] in CAPTION_TYPES:
                for caption in native_component_captions(obj,native_component_value(obj)):
                    left,top,right,bottom = caption_bounds(caption)
                    # Text bounds include fractional font metrics. Round the
                    # clearance outward onto native-compatible axes, avoiding
                    # hundreds of nearly duplicate rows on a populated sheet.
                    self.caption_rectangles.append((
                        math.floor(left/COORDINATE_STEP)*COORDINATE_STEP,
                        math.floor(top/COORDINATE_STEP)*COORDINATE_STEP,
                        math.ceil(right/COORDINATE_STEP)*COORDINATE_STEP,
                        math.ceil(bottom/COORDINATE_STEP)*COORDINATE_STEP))
        points = list(self.reserved) + list(hubs.values())
        points += [p for paths in self.routes.values() for path in paths for p in path]
        for terminal in terminals:
            points.extend(self._lead(terminal))
        from .wires import native_path, WireGeometryError
        by_net = defaultdict(list)
        for terminal in terminals: by_net[terminal.net].append(terminal)
        for group in by_net.values():
            if len(group) != 2: continue
            a,b = group
            try:
                points.extend(native_path(a.point,a.direction,b.point,b.direction))
            except WireGeometryError:
                pass
        xs = {p[0] for p in points}
        ys = {p[1] for p in points} | {ground_y}
        for left, top, right, bottom in rectangles:
            xs.update((left-20, left, right, right+20))
            ys.update((top-20, top, bottom, bottom+20))
        for left,top,right,bottom in self.caption_rectangles:
            xs.update((left-8,left,right,right+8))
            ys.update((top-8,top,bottom,bottom+8))
        # Native implicit bends clean up their interior coordinates to four
        # units. Nearby compatible channels let the serializer remove a CON
        # instead of preserving an avoidable bend on a diode's odd pin axis.
        xs.update(int((value+2)/4)*4 for value in tuple(xs))
        ys.update(int((value+2)/4)*4 for value in tuple(ys))
        xs.update((min(xs)-160, max(xs)+160))
        ys.update((min(ys)-160, max(ys)+160))
        self.xs, self.ys = sorted(xs), sorted(ys)
        self.xindex = {x:i for i,x in enumerate(self.xs)}
        self.yindex = {y:i for i,y in enumerate(self.ys)}
        for terminal in terminals:
            for point in self._expand(self._lead(terminal))[1:]:
                if self.escapes.setdefault(point,terminal.net) != terminal.net:
                    raise LayoutError("Terminal routing escapes for different nodes overlap; increase placement spacing.")
        for a,b in local_ground_pairs:
            for point in self._expand([a.point,b.point]):
                if self.escapes.setdefault(point,"0") != "0":
                    raise LayoutError("A local ground wire overlaps another terminal lead; move the component or use rail grounding.")
        self.blocked = set()
        for left, top, right, bottom in rectangles:
            for x in self.xs[bisect.bisect_left(self.xs,left):bisect.bisect_right(self.xs,right)]:
                for y in self.ys[bisect.bisect_left(self.ys,top):bisect.bisect_right(self.ys,bottom)]:
                    self.blocked.add((x,y))
        # Ground's connection is at the edge of its visible glyph bounds.
        # Keep that one attachment accessible while reserving the stem/bars.
        for obj in objects:
            if obj["Type"] == 200: self.blocked.discard((obj["X"],obj["Y"]))
        for net in self.hard_hubs:
            if self.hubs[net] in self.blocked:
                raise LayoutError(f"Explicit node anchor {net!r} is inside a component body; move layout.nodes[{net!r}].")
        self.caption_blocked = set()
        for left,top,right,bottom in self.caption_rectangles:
            for x in self.xs[bisect.bisect_left(self.xs,left):bisect.bisect_right(self.xs,right)]:
                for y in self.ys[bisect.bisect_left(self.ys,top):bisect.bisect_right(self.ys,bottom)]:
                    self.caption_blocked.add((x,y))
        self.occupancy = defaultdict(list)

    @staticmethod
    def _lead(terminal):
        return list(terminal.lead) if terminal.lead else [terminal.point, (
            terminal.point[0]+terminal.direction[0]*STEP,
            terminal.point[1]+terminal.direction[1]*STEP)]

    def _expand(self, path):
        """Split every axis-aligned edge at the coordinate graph's vertices."""
        expanded = []
        for a,b in zip(path,path[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                raise LayoutError("Explicit wire routes must be orthogonal.")
            if a == b:
                continue
            values = self.xs if a[1] == b[1] else self.ys
            axis = 0 if a[1] == b[1] else 1
            low, high = sorted((a[axis],b[axis]))
            cuts = values[bisect.bisect_left(values,low):bisect.bisect_right(values,high)]
            if a[axis] > b[axis]: cuts = cuts[::-1]
            expanded.extend((v,a[1]) if axis == 0 else (a[0],v) for v in cuts[:-1])
        expanded.append(path[-1])
        return expanded

    def _occupied(self, point, net):
        return self.occupancy.get(point, ())

    def _find(self, start, targets, net, allow_crossings=False, incoming=-1, allow_labels=False):
        tx = [p[0] for p in targets]
        ty = [p[1] for p in targets]
        target_bounds = (min(tx),min(ty),max(tx),max(ty))
        def heuristic(point):
            left,top,right,bottom = target_bounds
            return max(left-point[0],0,point[0]-right) + max(top-point[1],0,point[1]-bottom)
        initial = (start, incoming)
        serial = 0
        queue = [(heuristic(start),0,serial,initial)]
        cost, previous = {initial:0}, {}
        while queue:
            if serial % 1024 == 0 and time.monotonic() > self.deadline:
                raise LayoutError("Automatic routing exceeded 20 seconds; provide placements or split the circuit into stages.")
            _, distance, _, state = heapq.heappop(queue)
            point, incoming = state
            if distance != cost.get(state): continue
            if point in targets:
                path = [point]
                while state != initial:
                    state = previous[state]
                    path.append(state[0])
                return list(reversed(path))
            if len(cost) > 240000: break
            ix, iy = self.xindex[point[0]], self.yindex[point[1]]
            neighbors = ((ix-1,iy),(ix,iy-1),(ix+1,iy),(ix,iy+1))
            for direction_index, (nx,ny) in enumerate(neighbors):
                if not (0 <= nx < len(self.xs) and 0 <= ny < len(self.ys)): continue
                direction = DIRECTIONS[direction_index]
                if incoming >= 0 and direction_index == (incoming+2)%4: continue
                neighbor = self.xs[nx],self.ys[ny]
                if neighbor in self.blocked: continue
                if not allow_labels and neighbor in self.caption_blocked: continue
                if neighbor in self.reserved and neighbor != start: continue
                if neighbor in self.anchors and self.anchors[neighbor] != net: continue
                if neighbor in self.escapes and self.escapes[neighbor] != net: continue
                crossing = self._occupied(neighbor,net)
                if crossing:
                    if not allow_crossings: continue
                    if any(len(links) != 2 or {_direction(neighbor,p) for p in links} not in
                           ({(-1,0),(1,0)},{(0,-1),(0,1)}) or
                           direction in {_direction(neighbor,p) for p in links} or
                           (-direction[0],-direction[1]) in {_direction(neighbor,p) for p in links}
                           for _,links in crossing): continue
                if self._occupied(point,net) and incoming != direction_index: continue
                next_state = neighbor,direction_index
                length = abs(point[0]-neighbor[0])+abs(point[1]-neighbor[1])
                bend = incoming not in {-1,direction_index}
                native_corner = all(value >= 0 and value % 4 == 0 for value in point)
                new_cost = (distance + length + self.BEND_COST*bend
                            + (80 if bend and not native_corner else 0)
                            + (2000 if crossing else 0))
                if new_cost < cost.get(next_state,math.inf):
                    cost[next_state],previous[next_state] = new_cost,state
                    serial += 1
                    heapq.heappush(queue,(new_cost+heuristic(neighbor),new_cost,serial,next_state))
        return None

    @staticmethod
    def add_path(graph,path):
        for a,b in zip(path,path[1:]):
            if a == b: continue
            graph.setdefault(a,set()).add(b)
            graph.setdefault(b,set()).add(a)

    def _native_pair(self, net, group):
        """Use one native wire when its exact proven path is unobstructed."""
        if len(group) != 2 or net in self.routes or net == "0": return None
        from .wires import native_path, WireGeometryError
        a,b = group
        try:
            path = native_path(a.point,a.direction,b.point,b.direction)
        except WireGeometryError:
            return None
        expanded = self._expand(path)
        if net in self.hard_hubs and self.hubs[net] not in expanded: return None
        endpoints = {a.point,b.point}
        if any(p in self.blocked or p in self.caption_blocked or self._occupied(p,net) or
               (p in self.reserved and p not in endpoints) or
               (p in self.escapes and self.escapes[p] != net) or
               (p in self.anchors and self.anchors[p] != net) for p in expanded):
            return None
        graph = {}
        self.add_path(graph,expanded)
        return graph

    def _balanced_trunk(self,net,group):
        """Join facing branch rows on a middle rail when every lead permits it.

        This is deliberately limited to a fully unobstructed trunk with all
        pins facing it. It does not impose a bus on arbitrary multiport nets.
        """
        if len(group) < 3 or net == "0" or net in self.routes: return None
        vertical = sum(t.direction[1] != 0 for t in group)
        horizontal = vertical >= len(group)-vertical
        axis,across = (0,1) if horizontal else (1,0)
        coordinates = sorted(t.point[across] for t in group)
        level = self.hubs[net][across] if net in self.hard_hubs else coordinates[len(coordinates)//2]
        if not (min(coordinates) < level < max(coordinates)): return None
        low,high = min(t.point[axis] for t in group),max(t.point[axis] for t in group)
        if net in self.hard_hubs:
            low,high = min(low,self.hubs[net][axis]),max(high,self.hubs[net][axis])
        if low == high: return None
        for terminal in group:
            delta = level-terminal.point[across]
            if delta:
                if terminal.direction[axis] or delta*terminal.direction[across] <= 0: return None
            elif not ((terminal.point[axis] == low and terminal.direction[axis] == 1) or
                      (terminal.point[axis] == high and terminal.direction[axis] == -1)):
                return None
        a,b = ((low,level),(high,level)) if horizontal else ((level,low),(level,high))
        path = self._expand([a,b])
        own_ends = {t.point for t in group}
        if any(p in self.blocked or p in self.caption_blocked or self._occupied(p,net) or
               (p in self.reserved and p not in own_ends) or
               (p in self.escapes and self.escapes[p] != net) or
               (p in self.anchors and self.anchors[p] != net) for p in path): return None
        graph = {}
        self.add_path(graph,path)
        return graph

    def route(self):
        grouped = defaultdict(list)
        for terminal in self.terminals: grouped[terminal.net].append(terminal)
        # Large shared buses establish clean trunks before local branches.
        def order(net):
            points = sorted(t.point for t in grouped[net])
            return net == "0", -len(points), tuple(points), net
        for net in sorted(grouped,key=order):
            group = sorted(grouped[net],key=lambda t:(t.point,t.direction,t.pin))
            if len(group) == 1:
                if net in self.routes:
                    raise LayoutError(f"Explicit route for single-terminal node {net!r} needs another component or port endpoint.")
                # FASTMEAN recommends a CON for an otherwise unconnected pin.
                # Preserve this one native endpoint during leaf cleanup; a bare
                # component pin can make the native batch worker wait on an error.
                lead = self._expand(self._lead(group[0]))
                if any(p in self.blocked or self._occupied(p,net) or
                       (p in self.reserved and p != group[0].point) for p in lead[1:]):
                    raise LayoutError(f"No room for an open-pin connector on {net!r}; move the component.")
                graph = {}
                self.add_path(graph,lead)
                self.graphs[net] = graph
                self.open_ends[net] = {lead[-1]}
                for point,links in graph.items(): self.occupancy[point].append((net,links))
                continue
            if net == "0" and self.local_ground_pairs:
                graph = {}
                for a,b in self.local_ground_pairs:
                    path = self._expand([a.point,b.point])
                    endpoints = {a.point,b.point}
                    if any(p in self.blocked or self._occupied(p,net) or
                           (p in self.reserved and p not in endpoints) for p in path):
                        raise LayoutError("A local ground wire crosses a component or terminal; move the component or use rail grounding.")
                    self.add_path(graph,path)
                self.graphs[net] = graph
                continue
            direct = self._native_pair(net,group)
            if direct is not None:
                self.graphs[net] = direct
                for point,links in direct.items(): self.occupancy[point].append((net,links))
                continue
            first = group[0]
            root = self.hubs[net] if net in self.hard_hubs or net in self.routes or net == "0" else self._lead(first)[-1]
            if root in self.reserved or root in self.blocked:
                root = self._lead(first)[-1]
            graph = {root:set()}
            self.graphs[net] = graph
            if net in self.routes:
                for path in self.routes[net]:
                    expanded = self._expand(path)
                    if any(p in self.blocked or (p in self.reserved and self.reserved[p] != net) for p in expanded):
                        raise LayoutError(f"Explicit route for {net!r} crosses a component or another terminal.")
                    self.add_path(graph,expanded)
                seen,queue = {root},deque([root])
                while queue:
                    for neighbor in graph[queue.popleft()]-seen:
                        seen.add(neighbor);queue.append(neighbor)
                if len(seen) != len(graph):
                    raise LayoutError(f"Explicit routes for {net!r} must form one connected tree through its node anchor.")
            elif net == "0":
                xs = [t.point[0] for t in group]
                self.add_path(graph,self._expand([(min(xs),self.ground_y),(max(xs),self.ground_y)]))
            else:
                trunk = self._balanced_trunk(net,group)
                if trunk is not None:
                    graph = trunk
                    self.graphs[net] = graph
            for terminal in group:
                lead = self._expand(self._lead(terminal))
                # Join an existing trunk as soon as the outward lead reaches
                # it. Continuing past it and routing back creates a tiny loop.
                contact = next((i for i,p in enumerate(lead[1:],1) if p in graph),None)
                if contact is not None: lead = lead[:contact+1]
                escape = lead[-1]
                if any(p in self.blocked or (p in self.reserved and p != terminal.point) for p in lead[1:]):
                    raise LayoutError("No room for a terminal lead; increase layout spacing.")
                targets = {point for point in graph if point not in self.reserved} or {root}
                incoming = DIRECTIONS.index(terminal.direction)
                path = self._find(escape,targets,net,incoming=incoming)
                if path is None: path = self._find(escape,targets,net,allow_crossings=True,incoming=incoming)
                if path is None: path = self._find(escape,targets,net,incoming=incoming,allow_labels=True)
                if path is None: path = self._find(escape,targets,net,allow_crossings=True,incoming=incoming,allow_labels=True)
                if path is None:
                    raise LayoutError(f"Could not route node {net!r}; supply explicit placements or split the circuit into stages.")
                self.add_path(graph,[*lead[:-1],*path])
            _prune_unused_leaves(graph,{t.point for t in group})
            for point,links in graph.items(): self.occupancy[point].append((net,links))
        return self.graphs

    def validate_geometry(self):
        """Allow plain perpendicular crossings, never ambiguous visual shorts."""
        occupied = defaultdict(list)
        for net,graph in self.graphs.items():
            for point,links in graph.items():
                if point in self.blocked:
                    raise LayoutError(f"Wire for {net!r} crosses a component body.")
                occupied[point].append((net,{_direction(point,p) for p in links}))
        straight_axes = ({(-1,0),(1,0)},{(0,-1),(0,1)})
        for point,entries in occupied.items():
            if len(entries) <= 1: continue
            if (len(entries) != 2 or entries[0][1] not in straight_axes or
                    entries[1][1] not in straight_axes or entries[0][1] == entries[1][1]):
                raise LayoutError("Wires from different nodes overlap or meet at a corner/junction. Move the explicit routes apart.")
        for terminal in self.terminals:
            if len(self.graphs[terminal.net].get(terminal.point,set())) != 1:
                raise LayoutError("A component/port terminal must receive exactly one wire; use a junction for branches.")


def _validate_segments(segments):
    """Check exact native leads and compressed orthogonal routing segments."""
    for index, first in enumerate(segments):
        a,b = first["start"],first["end"]
        horizontal = a[1] == b[1]
        for second in segments[index+1:]:
            if first["net"] == second["net"]:
                continue
            c,d = second["start"],second["end"]
            other_horizontal = c[1] == d[1]
            if horizontal == other_horizontal:
                fixed,axis = (1,0) if horizontal else (0,1)
                if a[fixed] == c[fixed] and max(min(a[axis],b[axis]),min(c[axis],d[axis])) <= min(max(a[axis],b[axis]),max(c[axis],d[axis])):
                    raise LayoutError("Wires from different nodes overlap or touch at a terminal lead.")
            else:
                h1,h2,v1,v2 = (a,b,c,d) if horizontal else (c,d,a,b)
                x,y = v1[0],h1[1]
                if min(h1[0],h2[0]) <= x <= max(h1[0],h2[0]) and min(v1[1],v2[1]) <= y <= max(v1[1],v2[1]):
                    if not (min(h1[0],h2[0]) < x < max(h1[0],h2[0]) and min(v1[1],v2[1]) < y < max(v1[1],v2[1])):
                        raise LayoutError("Different nodes meet at a terminal lead or wire corner.")


def _split_overlapping_edges(graph):
    """Split coarse edges at native lead vertices before assigning CON pins.

    An eight-unit adapter may lie inside a later twenty-unit routing edge.
    Retaining both edges would give one junction two wires in the same
    direction; FASTMEAN stores only one wire per native pin.
    """
    rows,columns = defaultdict(set),defaultdict(set)
    for x,y in graph:
        rows[y].add(x);columns[x].add(y)
    rows={y:sorted(xs) for y,xs in rows.items()}
    columns={x:sorted(ys) for x,ys in columns.items()}
    result={point:set() for point in graph}
    visited=set()
    for start,neighbors in sorted(graph.items()):
        for end in sorted(neighbors):
            edge=_edge(start,end)
            if edge in visited:continue
            visited.add(edge)
            horizontal=start[1]==end[1]
            axis=0 if horizontal else 1
            values=rows[start[1]] if horizontal else columns[start[0]]
            low,high=sorted((start[axis],end[axis]))
            cuts=values[bisect.bisect_left(values,low):bisect.bisect_right(values,high)]
            points=[(value,start[1]) if horizontal else (start[0],value) for value in cuts]
            _Router.add_path(result,points)
    return result


def _prune_unused_leaves(graph, required):
    """Discard routing stubs after all collinear edges have been normalized.

    Native leads need not fall on the placement grid. Splitting an overlapping
    lead and routing edge can turn a previously degree-two vertex into a leaf,
    so pruning only before that split leaves a dangling native CON.
    """
    leaves = deque(sorted(point for point, links in graph.items()
                          if len(links) <= 1 and point not in required))
    while leaves:
        point = leaves.popleft()
        if point not in graph or point in required or len(graph[point]) > 1:
            continue
        for other in sorted(graph.pop(point)):
            graph[other].discard(point)
            if len(graph[other]) <= 1 and other not in required:
                leaves.append(other)
    return graph


def build_layout(components: list[dict], ports: dict[str, str], options: dict,
                 placements: dict[str, dict] | None = None, node_positions: dict | None = None,
                 routes: dict | None = None, port_positions: dict | None = None,
                 density: str = "compact", interface_pins: dict | None = None,
                 ground_style: str = "rail") -> dict[str, Any]:
    """Return native Objects/Wires plus routing evidence, without file writes.

    Components are already normalized by schematic.create_circuit. Optional
    placements map component names to {x,y,rotation}; explicit coordinates use
    a 4-unit grid and rotation 0/1/2/3. Automatic spacing remains 20 units.
    Voltage-source terminal1 is negative, terminal2 positive.
    """
    from .schematic import _source_params
    if not isinstance(density, str) or density not in SPACING:
        raise LayoutError("layout.density must be compact or standard.")
    if not isinstance(ground_style,str) or ground_style not in {"rail","local"}:
        raise LayoutError("layout.ground_style must be rail or local.")
    if ground_style == "local" and routes and "0" in routes:
        raise LayoutError("Explicit ground routes require layout.ground_style=rail.")
    pitch, branch, shunt_pitch, extra_gap, row_gap = SPACING[density]
    nodes = set(n for item in components for n in item["nodes"])
    source = next((c for c in components if c["kind"] == "U" and c["nodes"][1] == "0"), None)
    start = ports.get(options.get("input"), options.get("input")) or (source["nodes"][0] if source else sorted(nodes-{"0"})[0])
    end = ports.get(options.get("output"), options.get("output")) or ("out" if "out" in nodes else start)
    spine_nodes, spine_edges = _path(components, start, end)
    hubs = {node: (800 + index*pitch, 1000) for index, node in enumerate(spine_nodes)}
    unresolved = sorted(nodes - {"0"} - set(hubs))
    for index, node in enumerate(unresolved):
        hubs[node] = (800 + (index % max(2, len(spine_nodes)))*pitch,
                      1000 + extra_gap + (index // max(2, len(spine_nodes)))*row_gap)
    def coordinate(value):
        if not isinstance(value,dict) or set(value)-{"x","y"}:
            raise LayoutError("Node coordinates require x and y only.")
        point = (value.get("x"),value.get("y"))
        if any(isinstance(v,bool) or not isinstance(v,int) or v % COORDINATE_STEP or abs(v)>100000 for v in point):
            raise LayoutError("Coordinates must be integer multiples of 4, within +/-100000.")
        return point
    if node_positions is not None:
        if not isinstance(node_positions,dict) or set(node_positions)-nodes:
            raise LayoutError("layout.nodes must map existing circuit nodes to x/y coordinates.")
        hubs.update({net:coordinate(value) for net,value in node_positions.items()})
    positions, used_centers = {}, set()
    ground_count, parallel_count = defaultdict(int), defaultdict(int)
    if placements is not None and not isinstance(placements, dict):
        raise LayoutError("layout.placements must map component names to positions.")
    explicit = placements or {}
    if set(explicit) - {c["name"] for c in components}:
        raise LayoutError("Explicit placement names must match existing components.")
    for index, item in enumerate(components):
        a, b = item["nodes"][:2] if len(item["nodes"]) >= 2 else (item["nodes"][0], item["nodes"][0])
        if len(item["nodes"]) != 2:
            # Multiport internals do not define a unique signal direction.
            # Explicit placements give the author control over functional stages.
            x, y, rotation = 800 + (index % 4)*pitch, 1000 + (index//4)*2*branch, 0
        elif index in spine_edges:
            left, right = hubs[a], hubs[b]
            x, y = _snap((left[0]+right[0])/2), _snap((left[1]+right[1])/2)
            rotation = _orientation(left, right)
        elif a == "0" or b == "0":
            net = b if a == "0" else a
            count = ground_count[net]
            ground_count[net] += 1
            x, y = hubs[net][0] + count*shunt_pitch, hubs[net][1] + branch
            rotation = 3 if a == "0" else 1
        else:
            pair = tuple(sorted((a, b)))
            count = parallel_count[pair]
            parallel_count[pair] += 1
            left, right = hubs[a], hubs[b]
            x = _snap((left[0]+right[0])/2)
            y = min(left[1], right[1]) - (count+1)*branch
            rotation = 0 if left[0] <= right[0] else 2
        # Public U nodes are +,-, native terminals -,+.
        if item["kind"] == "U":
            rotation = (rotation + 2) % 4
        if item["name"] in explicit:
            override = explicit[item["name"]]
            if not isinstance(override, dict) or set(override)-{"x", "y", "rotation"}:
                raise LayoutError("Each placement supports x, y and rotation only.")
            x, y, rotation = override.get("x", x), override.get("y", y), override.get("rotation", rotation)
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (x,y,rotation)) or x % COORDINATE_STEP or y % COORDINATE_STEP or abs(x)>100000 or abs(y)>100000 or rotation not in range(4):
                raise LayoutError("Placement coordinates must be integer multiples of 4; rotation must be 0..3.")
        def overlaps():
            return any(abs(x-px)<60 and abs(y-py)<60 for px,py in used_centers)
        while overlaps() and item["name"] not in explicit:
            y -= branch
        if overlaps():
            raise LayoutError("Component bodies overlap; increase explicit placement spacing.")
        used_centers.add((x,y))
        positions[index] = (x,y,rotation)
    # Reserve an outer margin even for many parallel branches.
    shift_x = 0 if explicit else max(0, 400 - min(x for x,y,r in positions.values()))
    shift_y = 0 if explicit else max(0, 400 - min(y for x,y,r in positions.values()))
    hubs = {net:(x+shift_x,y+shift_y) for net,(x,y) in hubs.items()}
    objects, terminals = [], []
    oid = 1
    component_names = {}
    for index, item in enumerate(components):
        x,y,rotation = positions[index]
        x,y = x+shift_x,y+shift_y
        obj = _object(oid, item.get("_native_type", TYPE_IDS.get(item["kind"])), item["name"], x,y,rotation)
        if "_native_params" in item:
            obj["Params"] = copy.deepcopy(item["_native_params"])
            native_nodes = item["_native_nodes"]
        elif item["kind"] == "U":
            obj["Params"] = _source_params(item["value"], item.get("waveform"))
            native_nodes = list(reversed(item["nodes"]))
        else:
            obj["Params"] = {item["kind"]:item["value"]}
            if item["kind"] in {"C", "L"}:
                obj["Params"]["IC"] = item.get("initial_condition",0)
            native_nodes = item["nodes"]
        # Rotation acts clockwise on the terminal axes in screen coordinates.
        if item["kind"] in TYPE_IDS:
            for pin, net in enumerate(native_nodes,1):
                direction = DIRECTIONS[(rotation+(0 if pin==1 else 2))%4]
                terminals.append(Terminal(oid,pin,net,(x+direction[0]*40,y+direction[1]*40),direction))
        else:
            from .native_geometry import pin_positions, pin_directions
            anchors, directions = pin_positions(obj), pin_directions(obj)
            for pin, net in enumerate(native_nodes,1):
                point, direction = anchors[pin], directions[pin]
                dx,dy = direction
                lead = (point,(point[0]+dx*STEP,point[1]+dy*STEP))
                terminals.append(Terminal(oid,pin,net,point,direction,lead))
        objects.append(obj)
        component_names[oid] = item["name"]
        oid += 1
    body_rectangles = []
    for obj in objects:
        if obj["Type"] in TYPE_IDS.values():
            x,y = obj["X"],obj["Y"]
            bounds = (x-30,y-30,x+30,y+30)
        else:
            from .native_geometry import body_bounds
            bounds = body_bounds(obj)
        for old in body_rectangles:
            if max(bounds[0],old[0]) < min(bounds[2],old[2]) and max(bounds[1],old[1]) < min(bounds[3],old[3]):
                raise LayoutError("Component bodies overlap; increase explicit placement spacing.")
        body_rectangles.append(bounds)
    ground_y = hubs.get("0",(0,max(obj["Y"] for obj in objects)+branch))[1]
    ground_x = hubs.get("0",(_snap((min(obj["X"] for obj in objects)+max(obj["X"] for obj in objects))/2),0))[0]
    # Native GND's electrical attachment is at its X/Y position.
    local_ground_pairs = []
    ground_rectangles = []
    def add_ground(obj):
        bounds = _ground_bounds(obj)
        if any(max(bounds[0],other[0]) < min(bounds[2],other[2]) and
               max(bounds[1],other[1]) < min(bounds[3],other[3])
               for other in body_rectangles+ground_rectangles):
            raise LayoutError("A ground glyph overlaps a component body or another ground glyph; move the component or ground anchor.")
        if any(bounds[0] <= t.point[0] <= bounds[2] and bounds[1] <= t.point[1] <= bounds[3]
               for t in terminals):
            raise LayoutError("A ground glyph overlaps another terminal; move the component or ground anchor.")
        ground_rectangles.append(bounds)
        objects.append(obj)
    if "0" in nodes:
        if ground_style == "local":
            grounded = [t for t in terminals if t.net == "0"]
            for index,terminal in enumerate(grounded,1):
                dx,dy = terminal.direction
                point = terminal.point[0]+80*dx,terminal.point[1]+80*dy
                direction = -dx,-dy
                rotation = (DIRECTIONS.index(direction)-1)%4
                add_ground(_object(oid,200,f"GND{index}",*point,rotation))
                ground = Terminal(oid,1,"0",point,direction)
                terminals.append(ground)
                local_ground_pairs.append((terminal,ground))
                oid += 1
        else:
            add_ground(_object(oid,200,"GND1",ground_x,ground_y+80))
            terminals.append(Terminal(oid,1,"0",(ground_x,ground_y+80),(0,-1)))
            hubs["0"] = (ground_x,ground_y)
            oid += 1
    aliases_per_net = defaultdict(int)
    interface_positions = {}
    if interface_pins is not None:
        sides = ("Left","Top","Right","Bottom")
        if not isinstance(interface_pins,dict) or set(interface_pins)-set(sides):
            raise LayoutError("Subcircuit interface must specify native pin sides.")
        labels=[name for side in sides for name in interface_pins.get(side) or []]
        if len(labels)!=len(set(labels)) or set(labels)!=set(ports):
            raise LayoutError("Subcircuit interface must match its declared external ports exactly.")
        xmin,xmax = min(o["X"] for o in objects)-160,max(o["X"] for o in objects)+160
        ymin,ymax = min(o["Y"] for o in objects)-160,max(o["Y"] for o in objects)+160
        for side,rot in zip(sides,(2,3,0,1)):
            names=interface_pins.get(side) or []
            centre=_snap((ymin+ymax)/2) if side in {"Left","Right"} else _snap((xmin+xmax)/2)
            first=_snap(centre-50*(len(names)-1))
            for index,name in enumerate(names):
                along=first+index*100
                point=(xmin if side=="Left" else xmax,along) if side in {"Left","Right"} else (along,ymin if side=="Top" else ymax)
                interface_positions[name]=(*point,rot)
    if port_positions is not None and (not isinstance(port_positions,dict) or set(port_positions)-set(ports)):
        raise LayoutError("layout.ports may position declared external port aliases only.")
    for alias, net in ports.items():
        x,y = hubs[net]
        count = aliases_per_net[net]
        aliases_per_net[net] += 1
        is_output = alias == options.get("output") or net == end
        # An implicit start can equal the output when no input was declared
        # (e.g. a Norton/current-divider circuit). Preserve explicit input
        # priority, but let a declared output face right in that case.
        is_input = alias == options.get("input") or (net == start and not is_output)
        if count == 0 and (is_input or is_output):
            x += -120 if is_input else 120
            rotation = 2 if is_input else 0
            direction = (1,0) if is_input else (-1,0)
        else:
            y -= 140 + count*80
            rotation, direction = 3, (0,1)
        if alias in interface_positions:
            x,y,rotation=interface_positions[alias]
            direction=DIRECTIONS[rotation]
        occupied_points = {terminal.point for terminal in terminals}
        while (x,y) in occupied_points:
            y -= 80
        if port_positions and alias in port_positions:
            specified = port_positions[alias]
            if not isinstance(specified,dict) or set(specified)-{"x","y","rotation"}:
                raise LayoutError("A port position supports x, y and rotation.")
            x,y = coordinate({k:v for k,v in specified.items() if k != "rotation"})
            rotation = specified.get("rotation",rotation)
            if isinstance(rotation,bool) or not isinstance(rotation,int) or rotation not in range(4):
                raise LayoutError("Port rotation must be 0..3.")
            direction = DIRECTIONS[rotation]
            # PORT Rot0 opens left, Rot1 up, Rot2 right, Rot3 down.
        if alias in interface_positions and rotation != interface_positions[alias][2]:
            raise LayoutError(f"Port {alias!r} must face its declared subcircuit interface side.")
        objects.append(_object(oid,400,alias,x,y,rotation))
        terminals.append(Terminal(oid,1,net,(x,y),direction))
        oid += 1
    if interface_pins is not None:
        by_name={o["Name"]:o for o in objects if o["Type"]==400}
        for side in ("Left","Top","Right","Bottom"):
            axis="Y" if side in {"Left","Right"} else "X"
            coordinates=[by_name[name][axis] for name in interface_pins.get(side) or []]
            if any(a>=b for a,b in zip(coordinates,coordinates[1:])):
                raise LayoutError("Ports on a subcircuit side must appear in declared coordinate order.")
    parsed_routes = {}
    if routes is not None:
        if not isinstance(routes,dict) or set(routes)-nodes:
            raise LayoutError("layout.routes must refer to existing circuit nodes.")
        for net,paths in routes.items():
            if not isinstance(paths,list) or not paths or len(paths)>100:
                raise LayoutError("Each routed net needs 1..100 connected polylines.")
            parsed_routes[net] = []
            for path in paths:
                if not isinstance(path,list) or not 2<=len(path)<=500:
                    raise LayoutError("A routed polyline needs 2..500 points.")
                parsed_routes[net].append([coordinate({"x":p[0],"y":p[1]}) if isinstance(p,(list,tuple)) and len(p)==2 else coordinate(None) for p in path])
    router = _Router(objects,terminals,hubs,ground_y,parsed_routes,
                     hard_hubs=set(node_positions or {}),
                     local_ground_pairs=local_ground_pairs)
    graphs = router.route()
    for net,graph in list(graphs.items()):
        graphs[net] = _prune_unused_leaves(_split_overlapping_edges(graph),
                                          {t.point for t in terminals if t.net == net} | router.open_ends.get(net,set()))
    router.validate_geometry()
    wires, segments = [], []
    terminal_by_point = {t.point:t for t in terminals}
    for net, graph in graphs.items():
        vertices = {}
        for point, neighbors in sorted(graph.items()):
            straight = (len(neighbors)==2 and {_direction(point,p) for p in neighbors} in
                        ({(-1,0),(1,0)}, {(0,-1),(0,1)}))
            if point in terminal_by_point:
                terminal = terminal_by_point[point]
                vertices[point] = (terminal.oid,terminal.pin)
            elif not straight:
                objects.append(_object(oid,300,f"CON{oid}",*point))
                vertices[point] = oid
                oid += 1
        visited = set()
        for point, reference in vertices.items():
            for neighbor in sorted(graph.get(point,set())):
                if _edge(point,neighbor) in visited:
                    continue
                previous, current = point,neighbor
                visited.add(_edge(previous,current))
                while current not in vertices:
                    following = next(p for p in sorted(graph[current]) if p!=previous)
                    previous,current = current,following
                    visited.add(_edge(previous,current))
                other = vertices[current]
                end1 = reference if isinstance(reference,tuple) else (reference,PIN_FOR_DIRECTION[_direction(point,neighbor)])
                end2 = other if isinstance(other,tuple) else (other,PIN_FOR_DIRECTION[_direction(current,previous)])
                wires.append({"obj1":{"ID":end1[0],"pin":end1[1]},"obj2":{"ID":end2[0],"pin":end2[1]}})
                segments.append({"net":net,"start":list(point),"end":list(current)})
    _validate_segments(segments)
    from .wires import simplify_wires
    removed_waypoints = simplify_wires(objects, wires)
    used_pins=set()
    for wire in wires:
        for end in (wire["obj1"],wire["obj2"]):
            terminal=end["ID"],end["pin"]
            if terminal in used_pins:
                raise LayoutError("A native junction direction received multiple wires; route through separate junctions.")
            used_pins.add(terminal)
    xs,ys = [o["X"] for o in objects],[o["Y"] for o in objects]
    return {"objects":objects,"wires":wires,"segments":segments,"component_ids":component_names,
            "style":("orthogonal physical wires; signal path left-to-right; "
                     + ("local native grounds" if ground_style == "local" else "bottom ground rail")),
            "density":density,
            "ground_style":ground_style,
            "removed_redundant_waypoints":removed_waypoints,
            "open_pin_connector_count":len(router.open_ends),
            "requires_native_scale100":any(o["Type"]==7100 for o in objects),
            "bounds":[min(xs)-160,min(ys)-120,max(xs)+220,max(ys)+120],
            "positions":{o["Name"]:{"x":o["X"],"y":o["Y"],"rotation":o["Rot"]} for o in objects if o["ID"] in component_names},
            "external_ports":list(ports),"junction_count":sum(o["Type"]==300 for o in objects)}
