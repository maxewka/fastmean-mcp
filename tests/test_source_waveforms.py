"""Native source modes: safe table authoring and lossless field updates."""
import copy
import unittest

from fastmean_mcp.schematic import SchemeError
from fastmean_mcp.source_waveforms import source_parameters, patch_source, describe_source


class WaveformTests(unittest.TestCase):
    def test_all_native_source_modes_and_current_names(self):
        for current in (False,True):
            for mode,number in (("dc",1),("sine",2),("pulse",3),("triangle",4),("pwl",5)):
                with self.subTest(current=current,mode=mode):
                    params=source_parameters(2,{"kind":mode},current=current)
                    self.assertEqual(params["ST"],number)
                    _,wave=describe_source(params,current=current)
                    self.assertEqual(wave["kind"],mode)
                    if current:
                        self.assertNotIn("U0",params["AC"])
                        self.assertIn("I",params["USER"])

    def test_pwl_scaling_periodicity_and_numeric_points_round_trip(self):
        wave={"kind":"pwl","points":[[0,0],["1m",2],["2m",-1]],
              "time_scale":2,"scale":3,"offset":.5,"periodic":True,"periods":4,"delay":"1m"}
        params=source_parameters(1,wave)
        self.assertEqual(params["USER"]["U"],{"x":[0,.001,.002],"y":[0,2,-1]})
        self.assertEqual(params["USER"]["ScaleT"],2)
        self.assertEqual(params["USER"]["PER"],1)
        _,inspection=describe_source(params)
        self.assertEqual(inspection["points"],[[0,0],[.001,2],[.002,-1]])
        self.assertTrue(inspection["periodic"])

    def test_selective_edit_preserves_waveform_points_phase_and_inactive_modes(self):
        original=source_parameters(1,{"kind":"pwl","points":[[0,0],[1,2],[2,0]],"offset":.5})
        original["AC"]["PHI0"]=33
        original["USER"]["future_native_field"]="preserve"
        before=copy.deepcopy(original)
        edited=patch_source(original,1,{"kind":"pwl","scale":2})
        self.assertEqual(original,before)
        self.assertEqual(edited["USER"]["U"],before["USER"]["U"])
        self.assertEqual(edited["USER"]["OffsetU"],.5)
        self.assertEqual(edited["USER"]["future_native_field"],"preserve")
        self.assertEqual(edited["AC"],before["AC"])
        self.assertEqual(edited["USER"]["ScaleU"],2)

    def test_bad_tables_and_mode_properties_are_rejected(self):
        for wave in ({"kind":"pwl","points":[[0,1],[0,2]]},
                     {"kind":"pwl","points":[[0,1],[1,float("nan")]]},
                     {"kind":"pwl","points":[[0,1]]},
                     {"kind":"triangle","rise_time":1},
                     {"kind":"sine","periods":0},
                     {"kind":"sine","finite_duration":"yes"},
                     {"kind":"pwl","time_scale":0}):
            with self.subTest(wave=wave),self.assertRaises(SchemeError):
                source_parameters(1,wave)

    def test_sine_delay_seconds_convert_to_native_periods_and_patch_uses_existing_frequency(self):
        params=source_parameters(1,{'kind':'sine','frequency':2000,'delay':.0007})
        self.assertAlmostEqual(params['AC']['Delay'],1.4)
        _,wave=describe_source(params)
        self.assertAlmostEqual(wave['delay'],.0007)
        self.assertAlmostEqual(wave['delay_periods'],1.4)
        edited=patch_source(params,1,{'kind':'sine','delay':.0002})
        self.assertAlmostEqual(edited['AC']['Delay'],.4)
        self.assertEqual(edited['AC']['F'],2000)
        native=source_parameters(1,{'kind':'sine','frequency':2000,'delay_periods':.7})
        self.assertEqual(native['AC']['Delay'],.7)
        fractional=source_parameters(1,{'kind':'sine','finite_duration':True,'periods':1.5})
        self.assertEqual(fractional['AC']['NP'],1.5)


if __name__=="__main__":unittest.main()
