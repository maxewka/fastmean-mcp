import unittest
from unittest.mock import patch

from fastmean_mcp.native_geometry import GeometryError, body_bounds, pin_directions, pin_labels, pin_positions


class NativeGeometryTests(unittest.TestCase):
    def symbol(self, tid, rotation=0, **changes):
        return {"Type": tid, "X": 1000, "Y": 800, "Rot": rotation, "FlipV": 0, "FlipH": 0, **changes}

    def test_controlled_sources_use_asymmetric_native_anchors(self):
        for tid in (6000, 6001, 6002):
            with self.subTest(tid=tid):
                obj = self.symbol(tid)
                self.assertEqual(pin_positions(obj), {1:(984,772),2:(984,828),3:(1008,772),4:(1008,828)})
                self.assertEqual(pin_directions(obj), {1:(0,-1),2:(0,1),3:(0,-1),4:(0,1)})
                self.assertEqual(body_bounds(obj), (976,780,1024,820))

    def test_controlled_source_rotation_moves_both_ports_and_directions(self):
        obj = self.symbol(6002, 1)
        self.assertEqual(pin_positions(obj), {1:(1028,784),2:(972,784),3:(1028,808),4:(972,808)})
        self.assertEqual(pin_directions(obj), {1:(1,0),2:(-1,0),3:(1,0),4:(-1,0)})
        self.assertEqual(body_bounds(obj), (980,776,1020,824))

    def test_diode_uses_21_unit_half_length_in_all_rotations(self):
        expected = [((979,800),(1021,800)),((1000,779),(1000,821)),
                    ((1021,800),(979,800)),((1000,821),(1000,779))]
        for rotation, points in enumerate(expected):
            with self.subTest(rotation=rotation):
                self.assertEqual(pin_positions(self.symbol(1101,rotation)), dict(enumerate(points,1)))

    def test_unsupported_orientation_is_rejected_before_routing(self):
        for changes in ({"FlipV":1},{"FlipH":1},{"Rot":4},{"Rot":True},{"X":1.5}):
            with self.subTest(changes=changes), self.assertRaises(GeometryError):
                pin_positions(self.symbol(1101, **changes))

    def test_legacy_geometry_is_not_silently_changed(self):
        with self.assertRaises(GeometryError): pin_positions(self.symbol(1000))

    def test_subcircuit_side_order_and_even_spacing(self):
        obj = self.symbol(7100, Params={"FileName":"a.scm","Pins":{"Left":["B1","B2"],"Top":["C"],"Right":None,"Bottom":["E"]}})
        with patch("fastmean_mcp.native_geometry.subcircuit_size",return_value=(80,80)):
            self.assertEqual(pin_labels(obj), {1:"B1",2:"B2",3:"C",4:"E"})
            self.assertEqual(pin_positions(obj), {1:(952,792),2:(952,808),3:(1000,752),4:(1000,848)})
            self.assertEqual(body_bounds(obj), (960,760,1040,840))

    def test_subcircuit_width_changes_horizontal_pins_only(self):
        obj = self.symbol(7100, Params={"FileName":"hybrid_pi.scm","Pins":{"Left":["B"],"Top":["C"],"Right":[],"Bottom":["E"]}})
        with patch("fastmean_mcp.native_geometry.subcircuit_size",return_value=(128,80)):
            self.assertEqual(pin_positions(obj), {1:(928,800),2:(1000,752),3:(1000,848)})

    def test_subcircuit_duplicate_pins_are_rejected(self):
        obj = self.symbol(7100, Params={"Pins":{"Left":["B"],"Top":["B"]}})
        with self.assertRaises(GeometryError): pin_labels(obj)


if __name__ == "__main__": unittest.main()
