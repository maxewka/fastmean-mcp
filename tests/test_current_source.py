"""Independent-current-source schema, polarity and parameter contracts."""
from pathlib import Path
import tempfile
import unittest
from fastmean_mcp.schematic import create_circuit,read_scheme,edit_component_values,_load
from fastmean_mcp.annotations import annotate_circuit
from fastmean_mcp.preview import render_schematic
from fastmean_mcp.relayout import relayout_circuit
from fastmean_mcp.schematic import SchemeError


def current_spec(waveform=None):
    return {"components":[{"kind":"I","name":"I1","nodes":["0","out"],"value":"1m","waveform":waveform},
                          {"kind":"R","name":"R1","nodes":["out","0"],"value":"1k"}],
            "ports":["out"],"analysis":{"output":"out"},
            "layout":{"placements":{"I1":{"x":400,"y":600,"rotation":3},"R1":{"x":800,"y":600,"rotation":1}}}}


class CurrentSourceTests(unittest.TestCase):
    def test_legacy_relayout_rejects_current_source_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.scm';create_circuit(current_spec(),source)
            original=source.read_bytes();target=root/'relayout.scm'
            self.assertIn(3010,read_scheme(source)['unsupported_type_ids'])
            with self.assertRaisesRegex(SchemeError,'R/C/L/U only'):
                relayout_circuit(source,target)
            self.assertFalse(target.exists())
            self.assertEqual(source.read_bytes(),original)

    def test_current_templates_do_not_retain_voltage_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for index,waveform in enumerate((None,{"kind":"sine","frequency":1000},{"kind":"pulse","high":"2m","low":0})):
                path=root/f"c{index}.scm";result=create_circuit(current_spec(waveform),path)
                item=next(c for c in result['components'] if c['name']=='I1')
                self.assertEqual(item['nodes'],['0','out'])
                self.assertEqual(item['polarity'],'positive_current_from_node1_to_node2')
                _,doc,_=_load(path);obj=next(o for o in doc['scm']['Scheme']['Objects'] if o['Type']==3010)
                self.assertEqual(obj['Params']['DC']['I0'],.001)
                self.assertNotIn('U0',obj['Params']['DC'])
                self.assertIn('IMAX',obj['Params']['PULSE']);self.assertIn('I',obj['Params']['USER'])
                self.assertEqual(read_scheme(path)['components'][0]['kind'],'I')
                preview=render_schematic(path,root/'preview')
                self.assertTrue(Path(preview['svg_path']).is_file())

    def test_current_amplitude_edit_and_parameter_binding_preserve_direction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.scm';create_circuit(current_spec(),source)
            edited=root/'edited.scm';result=edit_component_values(source,{'I1':'2m'},edited)
            self.assertEqual(result['components'][0]['value'],.002)
            self.assertEqual(result['components'][0]['nodes'],['0','out'])
            target=root/'parameter.scm';annotate_circuit(source,target,parameters={'DriveCurrent':'1m'},bindings={'I1':'DriveCurrent'})
            _,doc,_=_load(target);obj=next(o for o in doc['scm']['Scheme']['Objects'] if o['Type']==3010)
            self.assertEqual(obj['Params']['DC']['I0'],'DriveCurrent')
