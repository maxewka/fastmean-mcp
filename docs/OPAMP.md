# Native three-terminal op-amp

`OPAMP` creates FASTMEAN's native Type 6400 triangle. Its three nodes are
`[noninverting, inverting, output]`, in native pin order. The output voltage is
referenced internally to global ground:

```text
V(output,0) = k * (V(noninverting,0) - V(inverting,0))
```

Supply the finite numeric gain as either `value` or `parameters: {"k": ...}`.
SI strings are converted to numeric SI, as for controlled sources. For example:

```json
{"kind":"OPAMP","name":"OA1","nodes":["0","sum","out"],"parameters":{"k":100000000}}
```

This model has ideal inputs and output, with no supply pins, clipping,
bandwidth, slew rate, noise or output-current limit. It does not represent a
particular commercial amplifier. Add the surrounding feedback network and a
ground reference. For a unity follower, connect the inverting input to the
output; the exact finite-gain transfer is `k/(1+k)`.

At rotation 0, the body is 36×48 native document units and its pins, relative to
the center, are `(-26,-8)`, `(-26,8)`, `(26,0)`. Pin 1 is positive, pin 2 negative,
pin 3 output. Preview and physical wire routing share these native anchors for
all four rotations. Generated flips remain unsupported. The automatic layout
follows the active input through the output and keeps local feedback near its
stage. Ports remain external input/output or measurement interfaces.

In MCP 1.6.0 OPAMP is supported by both the linear CIRSYM adapter and
existing-file relayout. Change gain in a preserved copy with
`fastmean_edit_properties(updates={"A1":{"k":100000}})`, or bind it to a root
parameter with `fastmean_annotate_circuit(bindings={"A1":{"k":"Gain"}},
parameters={"Gain":100000})`. Use the actual instance name in place of A1.
These operations do not give the ideal model physical rail or bandwidth limits.

The [20-part MFB filter](../examples/mfb-filter/README.md) demonstrates three
native op-amps with automatic placement, physical feedback wires, saved graph
formulas and editable passive parameters.

## Evidence and checks

The bundled FASTMEAN 6.1 `ФНЧ_ARC.scm` example contains three Type 6400 records
with parameter `k`. Native netlist export has exactly three node numbers and
that gain. Native pin initialization and coordinate transforms establish the
geometry; AC and transient probes establish the input signs and output
reference. No native program, library or manual is distributed here.

On 2026-10-27 the real official MCP SDK over stdio created and calculated four
circuits: positive and negative open-loop drive at gain 2.5, a follower at
gain 1e15, and an inverting resistor-feedback amplifier at gain 1e5. AC and TD
matched their independently calculated finite-gain transfers, and the source
SCM hashes were unchanged. With the public 20-part authoring check included,
the targeted suite passed **5 tests and 16 subtests**.

```powershell
$env:FASTMEAN_MCP_NATIVE_TEST = '1'
python -m pytest -q tests/test_opamp.py
```

Native tests skip when Windows/FASTMEAN or the opt-in flag is absent. Portable
tests check exact geometry, triangle polarity, validation, authoring and preview.
