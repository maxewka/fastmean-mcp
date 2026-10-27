# Native transformers and controlled switches

Version 1.4.0 adds transformer and voltage-controlled switch authoring to the
existing `fastmean_create_circuit` and `fastmean_create_project` tools. No
separate solver or fabricated waveforms are involved. `fastmean_status`, the
tool descriptions and `fastmean_search_manual` advertise this support;
`fastmean_example(kind="flyback")` provides a complete editable starting point.

## Transformer: TR / TRANSFORMER

```json
{"kind":"TR","name":"TR1","nodes":["p1","p2","s1","s2"],"value":2}
```

Native type **6101**, parameter `n`. Supply either `value` or
`parameters={"n":2}`, not both. `n=Nprimary/Nsecondary` must be finite and
positive; reverse one winding's nodes to reverse polarity.

| Native pin | Public node | Meaning |
| --- | --- | --- |
| 1 | p1 | Dotted primary end |
| 2 | p2 | Undotted primary end |
| 3 | s1 | Dotted secondary end |
| 4 | s2 | Undotted secondary end |

The relation is `V(p1)-V(p2) = n * (V(s1)-V(s2))`. Thus 10 V on the primary
with `n=2` produces 5 V on the secondary. The transformer is ideal and has no
magnetic energy storage. A flyback model needs an explicit magnetizing
inductance across its primary. Leakage, winding resistance, saturation and
interwinding capacitance are not implicit parameters of this element.

Each galvanically separate circuit needs a voltage reference, as required by
the native manual. This constructor uses node `0` for ground; its example
uses a common numerical reference for both windings. It does not model a
floating isolated output or insulation performance.

## Voltage-controlled switch: SW / VCSWITCH

```json
{"kind":"SW","name":"SW1","nodes":["gate","0","drain","0"],
 "parameters":{"Ron":0.05,"Roff":"10M","Uon":3,"Uoff":2}}
```

Native type **6600**, with all four numeric parameters required. The nodes
are **[control+, control−, switched terminal 1, switched terminal 2]**. The
control voltage is `V(control+)-V(control−)`. The switched branch conducts
in either direction. The control pair is separate from the switched pair;
ports and wires must not join them unintentionally.

`Uon` and `Uoff` are the turn-on and turn-off voltage thresholds. Between
distinct thresholds the switch retains its previous state (hysteresis). The accepted
range is `Uoff <= Uon` and `0 < Ron <= Roff`, with finite SI values. This is
the native piecewise-linear switch, not a MOSFET device model: it has no gate
charge, body diode, capacitances or thermal behavior. A native pulse voltage
source supplies the PWM drive in the example.

## Diode polarity

The existing `D` element uses **[anode, cathode]**, native pins 1 and 2. Its
parameters remain `Ron`, `Roff`, `Uon`. Both numerical checks and the preview
agree on this order. For flyback, reverse the secondary winding relative to
the primary so that the output diode conducts during the switch-off interval.

## Editing, inspection and rendering

Both new primitives work in root circuits and fixed subcircuit definitions.
`fastmean_inspect` returns their native types, numeric parameters, pin roles
and terminal order. `fastmean_preview` draws actual routed connections, winding
polarity dots, and switch control signs, including all four rotations.
The picture is an MCP rendering of SCM objects, not a native screenshot.

To change `n` or switch parameters, edit the saved JSON specification and
create a new circuit/project. `fastmean_edit_values` and generated parameter
bindings remain limited to their documented R/C/L/U/I scope. The symbolic
and relayout adapters retain their existing R/C/L/U restrictions. These
restrictions do not prevent native transient analysis of TR/SW circuits.

Transient exports can contain multiple native states at the same timestamp.
MCP preserves them in order, including both sides of the jump; mean/RMS give
zero-duration intervals zero weight. Decreasing times, missing end coverage,
nonfinite values and malformed columns are still rejected. See
[plotting event semantics](PLOTTING.md#switching-events).

## Evidence and reproducible checks

The installed FASTMEAN 6.1 `DC-DC преобразователь.scm` example contains the
native ideal transformer record. Native constructor, pin initialization and
serialization routines establish the TR/SW fields and geometry. Source
evidence was checked against executable SHA256
`a001582ada87cdf013605f43b019957ae23204ef4bfcc33be02a0681b186ee25`.
The FASTMEAN 6.0 user manual, page 11, describes ground references for
galvanically separate parts of a circuit. No native binary or manual is
redistributed here.

Real FASTMEAN probes verify transformer ratio and reversal, switch control
polarity and bidirectional conduction, and diode orientation. Regression tests
cover these cases independently of generated images. The full flyback check
uses the official MCP SDK over stdio, checks the output against the CCM
estimate, verifies magnetizing-current slopes and rectifier/switch phasing,
and requests the chart through `fastmean_plot`.

```powershell
$env:FASTMEAN_MCP_NATIVE_TEST = '1'
python -m pytest -q tests/test_power_primitives_native.py tests/test_flyback.py
```

Native tests skip when FASTMEAN is absent. Portable authoring, validation,
geometry and event-processing tests do not require it.
