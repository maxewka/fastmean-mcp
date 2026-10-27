"""Caption clearance against actual rotated catalog bodies and terminal leads."""
import unittest

from fastmean_mcp.captions import caption_bounds, native_component_captions, native_component_value
from fastmean_mcp.element_catalog import entries, get_element
from fastmean_mcp.native_geometry import body_bounds, pin_directions, pin_positions


def intersects(a,b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def ray_intersects(rect,point,direction):
    """A stronger check than the finite straight leads reserved by the router."""
    x,y = point
    dx,dy = direction
    if dx:
        return rect[1] <= y <= rect[3] and (rect[2] >= x if dx > 0 else rect[0] <= x)
    return rect[0] <= x <= rect[2] and (rect[3] >= y if dy > 0 else rect[1] <= y)


class CatalogCaptionTests(unittest.TestCase):
    def check_clearance(self,kind,rotation,parameters=None):
        entry = get_element(kind)
        obj = {"Type":entry["typeid"],"Name":"DUT_"+kind,"X":137,"Y":-83,"Rot":rotation,
               "Params":{**entry["defaults"],**(parameters or {})}}
        before = repr(obj)
        captions = native_component_captions(obj,native_component_value(obj))
        self.assertEqual(repr(obj),before)
        self.assertEqual(len(captions),2)
        rectangles = [caption_bounds(caption) for caption in captions]
        self.assertFalse(intersects(*rectangles),"Name and value overlap")
        for rectangle in rectangles:
            self.assertFalse(intersects(rectangle,body_bounds(obj)),"Caption overlaps the symbol")
            for pin,point in pin_positions(obj).items():
                self.assertFalse(ray_intersects(rectangle,point,pin_directions(obj)[pin]),
                    f"Caption overlaps outward terminal {pin}")

    def test_mosfet_and_three_winding_transformer_all_rotations(self):
        for kind in ("MOSFET","TR3"):
            for rotation in range(4):
                with self.subTest(kind=kind,rotation=rotation):
                    self.check_clearance(kind,rotation)

    def test_flipflops_with_and_without_async_pins_all_rotations(self):
        for kind in ("DFF","JK"):
            for has_rs in (0,1):
                for rotation in range(4):
                    with self.subTest(kind=kind,has_rs=has_rs,rotation=rotation):
                        self.check_clearance(kind,rotation,{"HasRS":has_rs})

    def test_every_new_catalog_family_and_maximum_fanin_has_clear_captions(self):
        legacy = {1000,1001,1002,2010,3010,1101,6000,6001,6002,6101,6400,6600}
        for entry in entries():
            if entry["typeid"] in legacy or entry["internal"] or entry["kind"] == "X":
                continue
            parameters = {"N":8} if entry["kind"] in {"AND","OR","XOR"} else {"N":5} if entry["kind"] == "SUM" else None
            if parameters and entry["kind"] == "SUM": parameters["k"] = [1.]*5
            for rotation in range(4):
                with self.subTest(kind=entry["kind"],rotation=rotation):
                    self.check_clearance(entry["kind"],rotation,parameters)

    def test_existing_primitive_caption_positions_stay_unchanged(self):
        expected = {
            (1000,0):[(100,149,"center"),(100,173,"center")],
            (1000,1):[(142,188,"left"),(142,212,"left")],
            (6000,0):[(152,188,"left"),(152,212,"left")],
            (6000,1):[(100,136,"center"),(100,158,"center")],
            (6101,0):[(100,136,"center"),(100,158,"center")],
            (6400,0):[(100,136,"center"),(100,158,"center")],
            (6600,0):[(148,188,"left"),(148,212,"left")],
        }
        for (typeid,rotation),positions in expected.items():
            with self.subTest(typeid=typeid,rotation=rotation):
                obj = {"Type":typeid,"Name":"DUT","X":100,"Y":200,"Rot":rotation}
                self.assertEqual([(c["x"],c["y"],c["ha"]) for c in native_component_captions(obj,"value")],positions)
