"""Native bend geometry and preservation of visible/electrical branches."""
import copy
import unittest
from fastmean_mcp.wires import native_path, simplify_wires, WireGeometryError


class WireTests(unittest.TestCase):
    def test_native_l_and_midpoint_routes_and_reverse_order(self):
        fixtures = [
            ((100, 100), (1, 0), (240, 200), (0, -1), [(100,100),(240,100),(240,200)]),
            ((100, 100), (1, 0), (244, 200), (-1, 0), [(100,100),(172,100),(172,200),(244,200)]),
            ((120, 100), (0, 1), (200, 246), (0, -1), [(120,100),(120,172),(200,172),(200,246)]),
        ]
        for a, da, b, db, expected in fixtures:
            with self.subTest(a=a,b=b):
                self.assertEqual(native_path(a,da,b,db),expected)
                self.assertEqual(native_path(b,db,a,da),expected[::-1])

    def test_detour_or_native_diagonal_is_not_approximated(self):
        for a,da,b,db in [((100,100),(-1,0),(200,200),(-1,0)),
                          ((100,100),(1,0),(201,200),(0,-1))]:
            with self.assertRaises(WireGeometryError):native_path(a,da,b,db)

    def test_corner_removed_but_three_way_branch_and_route_retained(self):
        def obj(oid,x,y):return dict(ID=oid,Type=300,X=x,Y=y,Rot=0)
        def wire(a,ap,b,bp):return dict(obj1=dict(ID=a,pin=ap),obj2=dict(ID=b,pin=bp))
        objects=[obj(1,100,100),obj(2,200,100),obj(3,200,200),
                 obj(4,300,200),obj(5,200,300)]
        wires=[wire(1,3,2,1),wire(2,4,3,2),wire(3,3,4,1),wire(3,4,5,2)]
        self.assertEqual(simplify_wires(objects,wires),1)
        self.assertEqual({o['ID'] for o in objects},{1,3,4,5})
        self.assertIn(wire(1,3,3,2),wires)
        # No second pass changes an already simplified route or branch.
        before=copy.deepcopy((objects,wires))
        self.assertEqual(simplify_wires(objects,wires),0)
        self.assertEqual((objects,wires),before)
