# MCP 1.5.0 validation

Checked on Windows with separately installed FASTMEAN 6.1 on 2026-10-27.
The native executable SHA256 was
`a001582ada87cdf013605f43b019957ae23204ef4bfcc33be02a0681b186ee25`.
Native binaries, private job receipts and installation logs are not distributed.

- Full native suite: **284 passed, 5 skipped, 363 subtests passed**.
- Portable suite with an intentionally absent native application:
  **259 passed, 30 skipped, 345 subtests passed**.
- Installed package: **1.5.0**, pinned official MCP SDK **2.3.0**.
- Doctor initialized the real stdio protocol, discovered **22 tools**, and
  successfully called status. Doctor starts no native calculation.
- Existing unrelated MCP/configuration semantics and extra Fastmean settings
  were preserved. No Windows locale or security settings were changed.

## Layout and native results

Five automatic layout cases were created, inspected, previewed and calculated
through the official MCP SDK: an embedded test circuit, nested subcircuits,
an asymmetric subcircuit, an ideal transformer and a voltage-controlled switch.
Saved analysis settings and formulas were retained. Every corresponding exported
numeric sample was identical before and after layout changes.

| Case | Component-center vertical span, before → after | Wire length, before → after |
|---|---:|---:|
| Embedded test circuit | 880 → 320 | 2786 → 1754 |
| Nested subcircuits | 160 → 0 | 1668 → 348 |
| Asymmetric subcircuit | 400 → 0 | 1620 → 800 |
| Transformer | 560 → 120 | 3556 → 1620 |
| Switch | 560 → 300 | 5772 → 2204 |

Lengths are native document units. These cases validate the changed placement
rules; they do not guarantee optimal placement for every possible topology.
Explicit component coordinates and routes remain authoritative.

## Public 20-part example

The [MFB filter](../examples/mfb-filter/README.md) uses no supplied component
coordinates. The source SDK workflow and the installed-package SDK workflow
both created the same portable SCM, parameters, TEXT, saved formulas and charts.
Native AC exports contain 301 rows; TD exports contain 5004 rows. An independent
nine-unknown nodal solve gives maximum complex AC error below `1.6e-12`.
The steady-state TD phasor check gives error below `5.4e-12`.

The native three-terminal OPAMP was also checked with positive and negative
open-loop drive, a follower and an inverting feedback amplifier. It is an ideal
finite-gain model: supply limits, current limits, noise and bandwidth are absent.
See [the model contract](OPAMP.md).

All schematic images are MCP previews of native pin/wire geometry. Charts are
Matplotlib renderings of FASTMEAN numeric exports. No desktop automation was
used, and original input SCM files were preserved.
