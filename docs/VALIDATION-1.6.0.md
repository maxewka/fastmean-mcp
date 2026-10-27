# MCP 1.6.0 validation

Checked on Windows with separately installed FASTMEAN 6.1 on 2026-10-27.
Native executable SHA256:
`a001582ada87cdf013605f43b019957ae23204ef4bfcc33be02a0681b186ee25`.
Native executables, the manual PDF, private job directories and installation
receipts are not distributed. Native integration checks used the official MCP SDK stdio
transport; no desktop automation was used. Original input SCM files were kept.

## Catalog coverage

The native reader factory contains **56 TypeIDs**: **44 ordinary electrical
classes**, six service classes, two internal auxiliary sources and four legacy
source aliases. The [catalog](ELEMENT-CATALOG.md) distinguishes these groups.

- All **43 ordinary non-X classes** were created and previewed through MCP,
  exported by FASTMEAN, and exercised in a native transient calculation.
- The first F/H fixtures put an ideal voltage drive across their current-control
  sensor. Corrected independent current-drive fixtures verified both source
  types with control reversal, output reversal and both reversals: **eight
  cases**, each in native AC and TD.
- F with h=2 and a 1 kΩ load gives Uout/Ibias=2000 Ω; H with r=1000 gives
  1000 Ω. A single reversal changes the sign; reversing both restores it.
  TD residuals were below `6e-15` V in these fixtures.
- A nested X circuit and its relaid-out copy both gave an AC ratio of 0.5.
- Eight-input AND/OR/XOR and five-input SUM passed native checks before and
  after relayout. Five unit SUM inputs with coefficients 1–5 produced 15 V.
- DFF and JK with HasRS=1 produced finite native transient samples; their
  complementary outputs summed to 5 V in the checked fixtures.
- Captions were checked against outward terminal paths at all rotations.
  Seven actual SDK cases covered TR3, MOSFET, DFF/JK with and without HasRS,
  and AND8. Before/after relayout exports and 83 total native TD rows per side
  agreed exactly; input hashes were preserved.
- Triangle and PWL modes were checked for both voltage and current sources.
  A PWL voltage fixture had a maximum residual of about 0.45 mV, equivalent
  to 0.30 µs on its steepest slope, below the requested 2 µs step. Original
  native timing samples were retained.

These are bounded operational checks of representative fixtures, not validation
of every switching state, semiconductor operating region, device rating or
physical transistor model. Some preview symbols are functional engineering
blocks with native pin anchors rather than copies of GUI glyphs.

## Symbolic and numerical agreement

Fourteen cases compare actual CIRSYM expressions with native complex AC data:
R/C/L/U/I, UNISTOR, G/E, GYR, TR/TR3, OPAMP, SUM and nested X. At four
frequencies the maximum absolute difference was below `5.6e-16` for these
fixtures except the large-gain GYR case, whose absolute difference was about
`1.1e-10`. Source files remained unchanged.

Four additional F/H cases, with baseline and reversed output polarity for each
source type, matched native AC. A separate two-level X regression using long
element names also matched AC, exercising the native-alias collision fix.

The conversion uses short unique native aliases and a retained name map.
This fixes CIRSYM collisions between long names and qualified subcircuit names.
SUM conversion follows the native export order: N, coefficients, output,
common, inputs. Current probes are series sensors, not parallel shorts.
Symbolic analysis remains linear and zero-state; no other solver substitutes
for CIRSYM.

An additional open-loop OPAMP fixture with finite k=10^15 matched native AC
and CIRSYM. Such gains remain finite controlled-source models; the converter
does not silently replace them with an ideal nullor.

## Analysis operations

Native SDK checks covered DC operating points, explicit source bias, generated
define/set commands, write-after sampling, three initial-condition modes,
saving final state, and a three-value RC AC sweep against an analytic result.
Per-instance initial-condition preparation left the shared sibling unchanged.

| Operation | Observed result for the checked fixture |
|---|---|
| Native summary RMS of unit sine | 0.707106781120075 |
| Native summary mean | approximately `7.85e-10` |
| Native harmonic magnitude at 1 kHz | 0.99999651 |
| Native second harmonic | approximately `8.1e-14` |
| Native FFT: 41 bins at 250 Hz spacing | peak at 1 kHz, amplitude 0.9999967100 |
| NumPy rFFT of native TD samples | peak at 1 kHz, amplitude 0.9999906418 |

Native FFT and harmonic functions are evaluated by FASTMEAN. NumPy spectrum
interpolates the native time samples and computes a separate rFFT/PSD with
recorded window and normalization. A separate ordinary native time writer
confirms simulation coverage for post-analysis exports. Summary results are
not represented as invented transient time series.

Actual SDK replot calls for native FFT and NumPy spectrum succeeded with a
deliberately absent FASTMEAN installation, proving they start no simulation.
Both retained zero-Hz bins and kHz display units, verified registered source
hashes, and kept native and NumPy provenance distinct.

Properties checks changed a resistor to 2 kΩ, saved a native function and FD
formula, and retained source hashes. Native AC agreed with the independent
expectation within `3.11e-15`. Portable tests exercise catalog bounds, dynamic
pin counts, table validation, source timing and preserved inactive modes.

A typed `.parameter` binding to TR3.n1 was changed from 2 to 4 through MCP.
Native gain changed from 0.5 to 0.25 on that secondary; the n2=3 secondary
remained at 1/3. This checks scalar-field binding and selective parameter edits
against the real native transformer calculation.

## Deliberate boundaries

Digital service contacts 410/420 bind to external DLL-module pins, rather than
ordinary circuit ports. Unbound experimental contacts caused a native access
violation; the identical NOT circuit with normal PORT/400 worked. MCP therefore
does not generate or execute that unsupported DLL context. This is not counted
as a working native component fixture. Internal auxiliary sources and legacy
aliases are inventory records, not additional ordinary electrical classes.

The release does not claim automation of every GUI dialog, arbitrary SPICE/DLL
imports or calibration of every model. Proprietary runtime/license limits still
apply. Windows locale, security settings, registry and PATH were not changed.

## Release installation checks

The full portable suite passed **327 tests**, with **38 native-dependent skips**
and **737 passing subtests**. The official SDK remains pinned at 2.3.0.
The complete native-enabled suite then passed **360 tests**, with **5 skips**
and **764 passing subtests**.

The normal installer upgraded the private environment to 1.6.0. Doctor performed
real stdio initialization, discovered **29 tools**, and completed status without
starting native analysis. All **30 packaged source/data files** were byte-checked
against the reviewed checkout from an external working directory.

An installed-package SDK workflow created and annotated a TR3 circuit, edited
its shared ratio parameter and ran native AC/DC/FFT plus a registered FFT chart.
AC gain was exactly 0.25, the checked DC output was 0.5 V, and the FFT peak was
1000 Hz at 0.2499967125 V. Original SCM hashes were retained. Other Codex settings
and the Fastmean entry retained their semantics; installation changed only the
owned entry's TOML header spelling. A connection/app restart is needed to load
the updated tools in an existing client session.

For source-independent checks, run:

```text
python -m pip install -r requirements-dev.txt -e .
python -m pytest -q
```

Additional native suites require a separate FASTMEAN installation and
`FASTMEAN_MCP_NATIVE_TEST=1`, `FASTMEAN_RELAYOUT_NATIVE=1`. CI without FASTMEAN
checks portable adapter behavior and skips native cases. Its actual result is
available in [GitHub Actions](https://github.com/maxewka/fastmean-mcp/actions).
