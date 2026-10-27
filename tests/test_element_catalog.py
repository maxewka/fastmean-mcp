"""Portable native-catalog inventory and typed boundary regressions."""
import copy
import math
import unittest

from fastmean_mcp.element_catalog import CatalogError, entries, get_element, get_geometry, inventory_summary, normalize_parameters


class ElementCatalogTests(unittest.TestCase):
    def test_factory_inventory_distinguishes_legacy_internal_and_services(self):
        summary = inventory_summary()
        self.assertEqual(summary["factory_count"], 56)
        self.assertEqual(summary["canonical_count"], 52)
        self.assertEqual(summary["electrical_count"], 46)
        records = entries(include_service=True, include_legacy=True)
        self.assertEqual({entry["typeid"] for entry in records}, set(summary["factory_type_ids"]))
        self.assertEqual(len(records), 56)
        self.assertEqual({entry["kind"] for entry in entries() if entry["internal"]}, {"U_AUX", "I_AUX"})
        self.assertEqual(get_element(2000)["legacy_alias_of"], 2010)
        self.assertEqual(get_element("ccvs")["typeid"], 6003)
        self.assertEqual(get_element("transformer")["typeid"], 6101)
        self.assertTrue(get_element("MOSFET")["native_tested"])
        self.assertFalse(get_element("MOSFET")["native_validation"]["independent_quantitative_cases"])
        self.assertEqual(summary["native_tested_count"], 44)
        with self.assertRaises(KeyError): get_element(True)
        with self.assertRaises(KeyError): get_element("arbitrary_model")

    def test_catalog_returns_defensive_data_and_valid_numeric_templates(self):
        item = get_element("AND")
        item["defaults"]["InpInv"][0] = 1
        item["parameter_schema"]["N"]["maximum"] = 1000
        self.assertEqual(get_element("AND")["defaults"]["InpInv"], [0, 0])
        self.assertEqual(get_element("AND")["parameter_schema"]["N"]["maximum"], 8)
        for item in entries():
            with self.subTest(kind=item["kind"]):
                self.assertEqual(normalize_parameters(item["kind"]), item["defaults"])
                self.assertEqual(item["default_source"], "adapter_numeric_template")
                if item["internal"] or item["kind"] == "X":
                    continue
                geometry = get_geometry(item["kind"])
                count = len(geometry["pin_names"])
                self.assertEqual(set(geometry["base_pin_positions"]), set(range(1, count+1)))
                self.assertEqual(set(geometry["base_pin_directions"]), set(range(1, count+1)))
                self.assertTrue(all(direction in {(-1, 0), (1, 0), (0, -1), (0, 1)}
                    for direction in geometry["base_pin_directions"].values()))

    def test_typed_tables_gain_arrays_and_boolean_native_flags(self):
        raw = {"fn": {"x": ["-1", 0, "2k"], "y": ["-1m", 0, "3m"]}}
        saved = copy.deepcopy(raw)
        self.assertEqual(normalize_parameters("NLR", raw)["fn"], {"x": [-1., 0., 2000.], "y": [-.001, 0., .003]})
        self.assertEqual(raw, saved)
        self.assertEqual(normalize_parameters("SUM", {"N": 5})["k"], [1.]*5)
        self.assertEqual(normalize_parameters("AND", {"N": 8})["InpInv"], [0]*8)
        self.assertEqual(normalize_parameters("SUM", {"N": 2, "k": ["2k", -3]})["k"], [2000., -3.])
        invalid = [
            ("NLR", {"fn": {"x": [0, 0], "y": [0, 1]}}),
            ("NLR", {"fn": {"x": [0, 1], "y": [0]}}),
            ("NLR", {"fn": {"x": [0, 1], "y": [0, math.inf]}}),
            ("NLR", {"fn": {"x": [0, 1], "y": [0, 1], "script": "exit"}}),
            ("SUM", {"N": 6}), ("SUM", {"N": 2, "k": [1]}),
            ("SUM", {"k": ["user_expression", 1]}),
            ("AND", {"N": 9}), ("AND", {"N": True}), ("OR", {"Type": 6911}),
            ("AND", {"InpInv": [True, 0]}), ("DFF", {"HasRS": True}),
            ("MOSFET", {"Model": 3}), ("LINE", {"n": 1.5}),
            ("PWM", {"F": "sin(t)"}), ("PWM", {"K": 101}), ("PWM", {"UInMax": 0}),
            ("SW", {"Ron": 0}), ("SW", {"Ron": 100, "Roff": 1}),
            ("OPAMP_SAT", {"Uhigh": -20}), ("R", {"R": -1}),
            ("OPAMP", {"k": math.nan}), ("H", {"r": True}),
            ("GYR", {"FileName": "external.file"}),
        ]
        for kind, params in invalid:
            with self.subTest(kind=kind, parameters=params), self.assertRaises(ValueError):
                normalize_parameters(kind, params)

    def test_native_geometry_asymmetry_and_dynamic_pin_counts(self):
        self.assertEqual(get_geometry("MOSFET")["base_pin_positions"], {1: (-20, 8), 2: (8, -27), 3: (8, 21)})
        self.assertEqual(get_geometry("TR3")["base_pin_positions"][6], (24, 56))
        self.assertEqual(get_geometry("BALMOD")["base_pin_positions"], {1: (-32, 0), 2: (0, 32), 3: (32, 0)})
        self.assertEqual(get_element("BALMOD")["internal_pin_indices"], [4])
        summer = get_geometry("SUM", {"N": 3, "k": ["a", 1, "-b"]})
        self.assertEqual(summer["pin_names"], ["output", "common", "input1", "input2", "input3"])
        self.assertEqual(summer["base_pin_positions"], {1: (36, 0), 2: (0, 32), 3: (-36, -16), 4: (-36, 0), 5: (-36, 16)})
        self.assertEqual(get_geometry("AND", {"N": 2})["base_pin_positions"], {1: (-32, -8), 2: (-32, 8), 3: (32, 0)})
        self.assertEqual(len(get_geometry("AND", {"N": 8})["pin_names"]), 9)
        self.assertEqual(len(get_geometry("DFF", {"HasRS": 0})["pin_names"]), 4)
        self.assertEqual(len(get_geometry("DFF", {"HasRS": 1})["pin_names"]), 6)
        self.assertEqual(len(get_geometry("JK", {"HasRS": 1})["pin_names"]), 7)
        # Geometry must not evaluate existing native electrical expressions.
        self.assertEqual(get_geometry("TR", {"n": "ratio_parameter"})["body_bounds"], (-16, -24, 16, 24))
        for kind, params in (("SUM", {"N": 6}), ("AND", {"N": 9}), ("DFF", {"HasRS": 1.0})):
            with self.subTest(kind=kind), self.assertRaises(CatalogError):
                get_geometry(kind, params)
