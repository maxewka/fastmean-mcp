"""Deterministic, wire-connected layouts for native two-terminal circuits.

Signal paths run left-to-right, shunts downward, parallel paths above the main
path. A small orthogonal router joins terminals through native CON objects.
Ports name external interfaces only; they never substitute for internal wires.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import heapq
import math
import time
from typing import Any

STEP = 20
PITCH = 320
BRANCH = 200
# Native CON terminal directions, confirmed against bundled FASTMEAN circuits.
DIRECTIONS = ((-1, 0), (0, -1), (1, 0), (0, 1))
PIN_FOR_DIRECTION = {direction: index + 1 for index, direction in enumerate(DIRECTIONS)}
TYPE_IDS = {"R": 1000, "C": 1001, "L": 1002, "U": 2010}


class LayoutError(ValueError):
    pass


@dataclass
class Terminal:
    oid: int
    pin: int
    net: str
    point: tuple[int, int]
    direction: tuple[int, int]


def _object(oid, tid, name, x, y, rot=0):
    return {"ID": oid, "Type": tid, "Name": name, "X": x, "Y": y,
            "Rot": rot, "FlipV": 0, "FlipH": 0, "active_property_page": 0}


def _path(components: list[dict], start: str, end: str) -> tuple[list[str], list[int]]:
    graph = defaultdict(list)
    for index, item in enumerate(components):
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


class _Router:
    def __init__(self, objects: list[dict], terminals: list[Terminal], hubs: dict, ground_y: int, routes: dict | None = None):
        self.objects, self.terminals, self.hubs = objects, terminals, hubs
        self.deadline = time.monotonic() + 20
        self.ground_y = ground_y
        self.routes = routes or {}
        self.graphs: dict[str, dict[tuple[int, int], set]] = {}
        self.reserved = {terminal.point: terminal.net for terminal in terminals}
        if len(self.reserved) != len(terminals):
            raise LayoutError("Component terminals overlap; give the components more room.")
        self.blocked = set()
        for obj in objects:
            if obj["Type"] not in TYPE_IDS.values():
                continue
            x, y = obj["X"], obj["Y"]
            # Physical symbols occupy the central 60x60 box. The first routing
            # step beyond each 40-unit terminal always continues outward.
            for px in range(x - 20, x + 21, STEP):
                for py in range(y - 20, y + 21, STEP):
                    self.blocked.add((px, py))
        points = list(self.reserved) + list(hubs.values()) + [p for paths in self.routes.values() for path in paths for p in path]
        self.bounds = (min(p[0] for p in points) - 240, min(p[1] for p in points) - 240,
                       max(p[0] for p in points) + 240, max(ground_y, max(p[1] for p in points)) + 240)

    def _occupied(self, point, net):
        return [(other, graph[point]) for other, graph in self.graphs.items() if other != net and point in graph]

    def _find(self, start, targets, net, allow_crossings=False):
        xmin, ymin, xmax, ymax = self.bounds
        serial = 0
        tx = [p[0] for p in targets]
        ty = [p[1] for p in targets]
        target_bounds = (min(tx),min(ty),max(tx),max(ty))

        def heuristic(point):
            left,top,right,bottom = target_bounds
            return (max(left-point[0],0,point[0]-right) + max(top-point[1],0,point[1]-bottom)) / STEP

        initial = (start, -1)
        queue = [(heuristic(start), 0., serial, initial)]
        cost, previous = {initial: 0.}, {}
        while queue:
            if serial % 1024 == 0 and time.monotonic() > self.deadline:
                raise LayoutError("Automatic routing exceeded 20 seconds; provide placements or split the circuit into stages.")
            _, distance, _, state = heapq.heappop(queue)
            point, incoming = state
            if distance != cost.get(state):
                continue
            if point in targets:
                path = [point]
                while state != initial:
                    state = previous[state]
                    path.append(state[0])
                return list(reversed(path))
            if len(cost) > 120000:
                break
            for direction_index, direction in enumerate(DIRECTIONS):
                neighbor = (point[0] + direction[0]*STEP, point[1] + direction[1]*STEP)
                if not (xmin <= neighbor[0] <= xmax and ymin <= neighbor[1] <= ymax):
                    continue
                if neighbor in self.blocked:
                    continue
                if neighbor in self.reserved and neighbor != start:
                    # Every native terminal receives exactly one wire. Join a
                    # branch to a wire/CON rather than piggybacking on a pin.
                    continue
                crossing = self._occupied(neighbor, net)
                if crossing:
                    if not allow_crossings:
                        continue
                    if any(len(links) != 2 or {_direction(neighbor, p) for p in links} not in
                           ({(-1, 0), (1, 0)}, {(0, -1), (0, 1)}) or
                           direction in {_direction(neighbor, p) for p in links} or
                           (-direction[0], -direction[1]) in {_direction(neighbor, p) for p in links}
                           for _, links in crossing):
                        continue
                if self._occupied(point, net) and incoming != direction_index:
                    continue  # Crossing has neither a dot nor a turn.
                next_state = (neighbor, direction_index)
                new_cost = distance + 1 + (0.4 if incoming not in {-1, direction_index} else 0) + (12 if crossing else 0)
                if new_cost < cost.get(next_state, math.inf):
                    cost[next_state], previous[next_state] = new_cost, state
                    serial += 1
                    heapq.heappush(queue, (new_cost + heuristic(neighbor), new_cost, serial, next_state))
        return None

    @staticmethod
    def add_path(graph, path):
        for a, b in zip(path, path[1:]):
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)

    def route(self):
        grouped = defaultdict(list)
        for terminal in self.terminals:
            grouped[terminal.net].append(terminal)
        # Ground is a physical bottom rail. Other nodes are routed first so
        # signal wiring stays close to its components.
        for net in sorted(grouped, key=lambda n: (n == "0", list(self.hubs).index(n) if n in self.hubs else 999, n)):
            group = grouped[net]
            root = self.hubs.get(net, group[0].point)
            graph = {root: set()}
            self.graphs[net] = graph
            if net in self.routes:
                for path in self.routes[net]:
                    expanded = []
                    for a,b in zip(path,path[1:]):
                        if a[0] != b[0] and a[1] != b[1]:
                            raise LayoutError("Explicit wire routes must be orthogonal.")
                        direction = _direction(a,b)
                        length = (abs(b[0]-a[0])+abs(b[1]-a[1]))//STEP
                        expanded.extend((a[0]+direction[0]*STEP*i,a[1]+direction[1]*STEP*i) for i in range(length))
                    expanded.append(path[-1])
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
                rail = [(x, self.ground_y) for x in range(min(xs), max(xs) + STEP, STEP)]
                self.add_path(graph, rail)
            for terminal in sorted(group, key=lambda t: (t.point[0], t.point[1], t.oid, t.pin)):
                escape = (terminal.point[0] + terminal.direction[0]*STEP,
                          terminal.point[1] + terminal.direction[1]*STEP)
                if escape in self.blocked or (escape in self.reserved and escape != terminal.point):
                    raise LayoutError("No room for a terminal lead; increase layout spacing.")
                targets = {point for point in graph if point not in self.reserved}
                if not targets:
                    targets = {root}
                path = self._find(escape, targets, net)
                if path is None:
                    path = self._find(escape, targets, net, allow_crossings=True)
                if path is None:
                    raise LayoutError(f"Could not route node {net!r}; supply explicit placements or split the circuit into stages.")
                self.add_path(graph, [terminal.point, *path])
            # Remove unused virtual hub/rail tails; do not leave wire stubs.
            required = {t.point for t in group}
            leaves = deque(p for p, links in graph.items() if len(links) <= 1 and p not in required)
            while leaves:
                point = leaves.popleft()
                for other in graph.pop(point, set()):
                    graph[other].discard(point)
                    if len(graph[other]) <= 1 and other not in required:
                        leaves.append(other)
        return self.graphs

    def validate_geometry(self):
        """Allow plain perpendicular crossings, never ambiguous visual shorts."""
        occupied = defaultdict(list)
        for net, graph in self.graphs.items():
            for point, links in graph.items():
                if point in self.blocked:
                    raise LayoutError(f"Wire for {net!r} crosses a component body.")
                occupied[point].append((net, {_direction(point, p) for p in links}))
        straight_axes = ({(-1, 0), (1, 0)}, {(0, -1), (0, 1)})
        for point, entries in occupied.items():
            if len(entries) <= 1:
                continue
            if (len(entries) != 2 or entries[0][1] not in straight_axes or
                    entries[1][1] not in straight_axes or entries[0][1] == entries[1][1]):
                raise LayoutError("Wires from different nodes overlap or meet at a corner/junction. Move the explicit routes apart.")
        for terminal in self.terminals:
            if len(self.graphs[terminal.net].get(terminal.point, set())) != 1:
                raise LayoutError("A component/port terminal must receive exactly one wire; use a junction for branches.")


def build_layout(components: list[dict], ports: dict[str, str], options: dict,
                 placements: dict[str, dict] | None = None, node_positions: dict | None = None,
                 routes: dict | None = None, port_positions: dict | None = None) -> dict[str, Any]:
    """Return native Objects/Wires plus routing evidence, without file writes.

    Components are already normalized by schematic.create_circuit. Optional
    placements map component names to {x,y,rotation}; coordinates use a 20-unit
    grid and rotation 0/1/2/3. Source terminal1 is negative, terminal2 positive.
    """
    from .schematic import _source_params
    nodes = set(n for item in components for n in item["nodes"])
    source = next((c for c in components if c["kind"] == "U" and c["nodes"][1] == "0"), None)
    start = ports.get(options.get("input"), options.get("input")) or (source["nodes"][0] if source else sorted(nodes-{"0"})[0])
    end = ports.get(options.get("output"), options.get("output")) or ("out" if "out" in nodes else start)
    spine_nodes, spine_edges = _path(components, start, end)
    hubs = {node: (800 + index*PITCH, 1000) for index, node in enumerate(spine_nodes)}
    unresolved = sorted(nodes - {"0"} - set(hubs))
    for index, node in enumerate(unresolved):
        hubs[node] = (800 + (index % max(2, len(spine_nodes)))*PITCH, 1600 + (index // max(2, len(spine_nodes)))*400)
    def coordinate(value):
        if not isinstance(value,dict) or set(value)-{"x","y"}:
            raise LayoutError("Node coordinates require x and y only.")
        point = (value.get("x"),value.get("y"))
        if any(isinstance(v,bool) or not isinstance(v,int) or v % STEP or abs(v)>100000 for v in point):
            raise LayoutError("Coordinates must be integer multiples of 20, within +/-100000.")
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
        a, b = item["nodes"]
        if index in spine_edges:
            left, right = hubs[a], hubs[b]
            x, y = _snap((left[0]+right[0])/2), _snap((left[1]+right[1])/2)
            rotation = _orientation(left, right)
        elif a == "0" or b == "0":
            net = b if a == "0" else a
            count = ground_count[net]
            ground_count[net] += 1
            x, y = hubs[net][0] + count*240, hubs[net][1] + BRANCH
            rotation = 3 if a == "0" else 1
        else:
            pair = tuple(sorted((a, b)))
            count = parallel_count[pair]
            parallel_count[pair] += 1
            left, right = hubs[a], hubs[b]
            x = _snap((left[0]+right[0])/2)
            y = min(left[1], right[1]) - (count+1)*BRANCH
            rotation = 0 if left[0] <= right[0] else 2
        # Public U nodes are +,-, native terminals -,+.
        if item["kind"] == "U":
            rotation = (rotation + 2) % 4
        if item["name"] in explicit:
            override = explicit[item["name"]]
            if not isinstance(override, dict) or set(override)-{"x", "y", "rotation"}:
                raise LayoutError("Each placement supports x, y and rotation only.")
            x, y, rotation = override.get("x", x), override.get("y", y), override.get("rotation", rotation)
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (x,y,rotation)) or x % STEP or y % STEP or abs(x)>100000 or abs(y)>100000 or rotation not in range(4):
                raise LayoutError("Placement coordinates must be integer multiples of 20; rotation must be 0..3.")
        def overlaps():
            return any(abs(x-px)<60 and abs(y-py)<60 for px,py in used_centers)
        while overlaps() and item["name"] not in explicit:
            y -= BRANCH
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
        obj = _object(oid, TYPE_IDS[item["kind"]], item["name"], x,y,rotation)
        if item["kind"] == "U":
            obj["Params"] = _source_params(item["value"], item.get("waveform"))
            native_nodes = list(reversed(item["nodes"]))
        else:
            obj["Params"] = {item["kind"]:item["value"]}
            if item["kind"] in {"C", "L"}:
                obj["Params"]["IC"] = item.get("initial_condition",0)
            native_nodes = item["nodes"]
        # Rotation acts clockwise on the terminal axes in screen coordinates.
        for pin, net in enumerate(native_nodes,1):
            direction = DIRECTIONS[(rotation+(0 if pin==1 else 2))%4]
            terminals.append(Terminal(oid,pin,net,(x+direction[0]*40,y+direction[1]*40),direction))
        objects.append(obj)
        component_names[oid] = item["name"]
        oid += 1
    ground_y = hubs.get("0",(0,max(obj["Y"] for obj in objects)+BRANCH))[1]
    ground_x = hubs.get("0",(_snap((min(obj["X"] for obj in objects)+max(obj["X"] for obj in objects))/2),0))[0]
    # Native GND's electrical attachment is at its X/Y position.
    objects.append(_object(oid,200,"GND1",ground_x,ground_y+80))
    terminals.append(Terminal(oid,1,"0",(ground_x,ground_y+80),(0,-1)))
    hubs["0"] = (ground_x,ground_y)
    oid += 1
    aliases_per_net = defaultdict(int)
    if port_positions is not None and (not isinstance(port_positions,dict) or set(port_positions)-set(ports)):
        raise LayoutError("layout.ports may position declared external port aliases only.")
    for alias, net in ports.items():
        x,y = hubs[net]
        count = aliases_per_net[net]
        aliases_per_net[net] += 1
        is_input = alias == options.get("input") or net == start
        is_output = alias == options.get("output") or net == end
        if count == 0 and (is_input or is_output):
            x += -120 if is_input else 120
            rotation = 2 if is_input else 0
            direction = (1,0) if is_input else (-1,0)
        else:
            y -= 140 + count*80
            rotation, direction = 3, (0,1)
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
        objects.append(_object(oid,400,alias,x,y,rotation))
        terminals.append(Terminal(oid,1,net,(x,y),direction))
        oid += 1
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
    router = _Router(objects,terminals,hubs,ground_y,parsed_routes)
    graphs = router.route()
    router.validate_geometry()
    wires, segments = [], []
    terminal_by_point = {t.point:t for t in terminals}
    for net, graph in graphs.items():
        vertices = {}
        for point, neighbors in graph.items():
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
            for neighbor in graph.get(point,set()):
                if _edge(point,neighbor) in visited:
                    continue
                previous, current = point,neighbor
                visited.add(_edge(previous,current))
                while current not in vertices:
                    following = next(p for p in graph[current] if p!=previous)
                    previous,current = current,following
                    visited.add(_edge(previous,current))
                other = vertices[current]
                end1 = reference if isinstance(reference,tuple) else (reference,PIN_FOR_DIRECTION[_direction(point,neighbor)])
                end2 = other if isinstance(other,tuple) else (other,PIN_FOR_DIRECTION[_direction(current,previous)])
                wires.append({"obj1":{"ID":end1[0],"pin":end1[1]},"obj2":{"ID":end2[0],"pin":end2[1]}})
                segments.append({"net":net,"start":list(point),"end":list(current)})
    xs,ys = [o["X"] for o in objects],[o["Y"] for o in objects]
    return {"objects":objects,"wires":wires,"segments":segments,"component_ids":component_names,
            "style":"orthogonal physical wires; signal path left-to-right; bottom ground rail",
            "bounds":[min(xs)-160,min(ys)-120,max(xs)+220,max(ys)+120],
            "positions":{o["Name"]:{"x":o["X"],"y":o["Y"],"rotation":o["Rot"]} for o in objects if o["Type"] in TYPE_IDS.values()},
            "external_ports":list(ports),"junction_count":sum(o["Type"]==300 for o in objects)}
