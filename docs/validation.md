# Validation history

## 1.2.0: saved-data plotting, current sources and reference layouts

Local Windows / FASTMEAN 6.1 checks on 2026-10-26: **196 passed, 5 skipped,
224 subtests**,70.09seconds, with both native flags enabled. Portable checks
with the executable intentionally absent: **179 passed,22 skipped,222 subtests**,
34.49seconds. An additional final regression applies the public amplifier
annotation request and verifies zero caption crossings afterward. Skips concern
platform privileges and the existing PowerShell policy; no settings changed.

The normal Python installer upgraded the owned installation to1.2.0 after a
successful dry run. Doctor completed a real stdio initialize/discovery/status
check with **21 tools**; all19 installed Python/data files matched the reviewed
source bytes. Hosted Windows/Ubuntu checks run separately through the linked
GitHub Actions workflow; local results are not presented as hosted results.

A fresh local session using the official MCP SDK over stdio initialized the
current source as **1.2.0**, discovered **21 tools**, and called status with no
active native operations. Source discovery and the separate installed-package doctor check both passed.
No third-party model-account test is claimed.

- `fastmean_plot` renders registered native AC/transient data as MCP images,
  PNG and SVG without another simulation. Display and measurement windows are
  independent. Transient measurements interpolate interval boundaries and use
  trapezoidal integration on the original timestamps; panel units/scales affect
  displayed metrics while raw metrics retain native values. See
  [plotting definitions and arguments](PLOTTING.md).
- Independent current sources use `nodes=[from,to]`, with positive current from
  the first node to the second, and support DC, sine and pulse authoring.
  Voltage sources retain `nodes=[positive,negative]`. Native current-column sign
  conventions remain separate from these physical direction definitions.
  Native AC fixtures use sine excitation; DC-only sources do not excite AC.
- Routing keeps native terminal anchors, genuine junctions and visible retained
  routing waypoints. Manual positions accept four-unit coordinates; automatic
  spacing remains on a twenty-unit grid. Caption clearance includes primitive,
  controlled-source and subcircuit labels. Optional local ground symbols retain
  the same electrical ground without an artificial bottom return rail.
- The [external-reference benchmark](../benchmarks/reference-circuits/README.md)
  contains our original circuit transcriptions, separately declared nominal
  values and test stimuli, independent analytical expectations and actual MCP
  preview artifacts. Its [sanitized native report](../benchmarks/reference-circuits/validation-report.json)
  separates primary/secondary AC, supported transient checks and runtime
  failures. Original textbook-derived scans remain private; source links and
  image hashes establish provenance without redistributing their pixels.
- The [four-BJT example](../examples/four-bjt-amplifier/README.md) uses fixed
  nominal piecewise-linear equivalents. Its [model notes](../examples/four-bjt-amplifier/MODELS.md)
  distinguish the compact beta form from the historical alpha regression
  fixture and explain the terminal-equivalence calculation. The native netlist
  audit and numerical measurements are distinct from schematic rendering.

FASTMEAN exports numerical samples; MCP renders schematic previews and plots.
Neither preview type is a screenshot of FASTMEAN's UI or proprietary fonts.
The renderer and reference-layout review do not promise pixel-identical copies
or a perfect automatic layout for an arbitrary graph.

The compensated RC benchmark's native transient timed out with both DC and
delayed finite-rise pulse excitation. Its topology is preserved and acceptance
is AC-only; no native transient/DC pass is claimed. The ideal RLC source path
has no finite steady DC current, so its benchmark uses positive-frequency AC.
Phase at its ideal transfer zero is undefined and excluded from the notch
check. The amplifier's nominal PWL results do not establish thermal behavior,
SOA, high-frequency performance or physical hardware suitability.

No native application binaries, proprietary fonts, manual PDFs, original
reference scans, private paths or raw local logs are part of these additions.

## 1.1.0: native projects, annotations, bend cleanup and client profiles

Local Windows / FASTMEAN 6.1 on 2026-10-26: **159 passed, 4 skipped,
158 subtests**, 51.24 seconds, with both native flags enabled. Skips concern
existing symlink privileges and PowerShell policy; no Windows settings changed.
No hosted CI or third-party model account test is claimed for this version.

The same checkout was also checked with FASTMEAN intentionally unavailable,
matching the CI configuration: **143 passed, 20 skipped, 158 subtests**,
26.70 seconds. All five generated client profiles independently initialized
the installed 1.1.0 server, discovered 20 tools and called status successfully.
Installed Python module bytes match the reviewed source; installer doctor passed.

- 20 tools initialize through the actual pinned MCP SDK stdio protocol.
- Native asymmetric three-pin and repeated two-level model tests verify pin
  mapping, independent internal nodes, half-voltage gain and source preservation.
  AC test fixtures use sine excitation (a DC-only source does not excite AC).
- Annotation creates portable model copies, root .parameter bindings, integer
  TEXT positions and saved graph expressions. Empty expression lists clear
  the requested section; omitted lists preserve it. Preview scales note text
  with geometry, preventing overlap on large annotated sheets.
- Endpoint-derived L and midpoint bends were checked against the native routing
  routine in 563 supported coordinate/direction cases with no mismatches.
  Native four-unit rounding is included; unsupported detours remain explicit.
  Degree-two CON removal requires an identical geometric path. Branches remain,
  and preview displays every retained CON rather than hiding routing waypoints.
- A private four-BJT amplifier project lost **85 redundant CON objects** across
  its main sheet and four equivalent-model sheets. Independent flattening of
  the logical JSON and the native netlist agreed on **60 leaf components,
  136 terminals, 43 nodes**, with no split or merged nodes.
- The same amplifier's native transient, measured over 0.29–0.30 s, produced
  **25.002515 V RMS, 20.002012 A RMS and 500.100725 W** into 1.25 ohm.
  Root parameter annotation and bend cleanup preserved the original numerical
  result. Input was 0.999983 V RMS / 66.8034 mA RMS / 94.4609 mA peak.
  These are nominal PWL equivalent-model results, not manufacturer SPICE, SOA,
  thermal, bandwidth or hardware validation. Ordinary FD was not valid for that
  nonlinear example; its saved FD traces were cleared instead of misreported.
- Export profiles cover Claude Code/Desktop, Kimi CLI and DeepSeek via Cline.
  They keep argv boundaries and local paths, contain no provider credentials,
  grant no automatic approvals and never replace an existing client config.

Private native files, manuals, transistor worksheets and application code are
not included in the distributed adapter.

## Subcircuit development checks

On 2026-10-26, **68 selected offline checks passed**, including genuine stdio
initialization/discovery of 20 tools, existing circuit creation and schema-error
recovery. These checks started no FASTMEAN process and used no desktop control.

Coverage includes complete pin maps, dynamic three-pin Type-7100 inspection,
fixed primitive parameter validation, cycle detection including aliases,
atomic project publication without replacement, original JSON/hash retention,
nested artifact retrieval, and public normalized-spec round trips. Genuine MCP
calls created a nested project, retrieved its original JSON through a resource,
changed a model's value and rebuilt a new project while preserving the first.
MCP preview returned PNG and SVG using native pin geometry. Literal numeric
parameter identifiers display without evaluation; unsupported expressions,
flips and custom Type-7100 scale/font contexts are rejected. Explicit
open preparation was tested with a mocked process launcher: recursive private
models and their source/copy hashes were verified without opening a GUI.

Genuine stdio calls also added numeric R0/C0 root parameters, bound R/C values,
explanatory native TEXT and prepared TD/FD expressions, then inspected and
previewed the result. Nested projects retained their short relative model
captions through annotation, and every original model stayed unchanged.

A separate native batch export checked an asymmetric three-pin passive model
with B on the left, E on top and C below. With child PORT orientation and
coordinates matching these sides, native output mapped B to IN, C to OUT and
E to ground, including the intended RBC and RCE connections. This guards a
silent terminal swap: FASTMEAN rebuilds its external interface from child PORT
geometry rather than relying on cached parent labels. No GUI was used.

These are intermediate adapter checks, not native validation of transistor
models or amplifier performance. Native numerical hierarchy/amplifier checks
are tracked separately.

## 1.0.2: compact automatic spacing

Local Windows checks on 2026-10-26, using Python's UTF-8 mode:

- Portable suite with FASTMEAN deliberately unavailable: **95 passed,
  17 skipped**, 91 subtests. No native calculations were started.
- Compact RC, RLC and divider drawings retain the same electrical terminal
  partitions, parameters, ports and analysis settings. Their drawing bounds
  occupy at least 15% less area than the standard preset.
- Installed stdio MCP 1.0.2 initialized and returned all 17 tools. Creation
  defaults to compact; both relayout density values work, preserve the input,
  and appear in the actual MCP input schema. Unrelated configuration bytes
  were preserved. The installer doctor passed.
- Preview of the compact RLC drawing was visually inspected. Native symbol
  geometry and the 20-unit grid remain unchanged. Long labels still require
  visual review. These checks do not validate new transistor models.

## 1.0.1: Windows path aliases

The first hosted Ubuntu test run passed. The Windows run exposed DOS 8.3
temporary-directory aliases: nested declared artifacts were omitted when the
raw job prefix used a short name, and three tests compared path spellings
instead of canonical locations. Version 1.0.1 fixes artifact lookup and the
three test assertions. The containment check remains strict; original path
components are checked for symlinks/junctions before canonical comparison.

Local Windows validation on 2026-10-26:

- Full suite with native flags: **105 passed, 4 skipped**, 84 subtests,
  37.02 seconds. Three skips concern symlink privileges, one the existing
  PowerShell script policy.
- A genuine `GetShortPathNameW` alias successfully published and reopened a
  nested SVG. Executable-path regressions also passed under an actual short
  TEMP path. A separate regression rejects links pointing back inside a job;
  local Windows skipped link creation when the required privilege was absent.
- A real unprivileged Windows junction that left and re-entered the same job
  was separately rejected. Genuine DOS 8.3 aliases remain accepted.
- Full suite without the native application and with TEMP/TMP set to an actual
  short DOS 8.3 path: **92 passed, 17 skipped**, 84 subtests, 13.90 seconds.

Hosted CI outcomes are available on the repository's Actions page; these local
numbers do not claim an unobserved hosted result.

## 1.0.0: initial local validation

Checked on Windows on 2026-10-26 with an independently installed FASTMEAN 6.1
and MCP Python SDK 2.3.0. These are local results, not a claim that hosted CI
has run or that every FASTMEAN installation behaves identically.

- Full suite with native flags enabled: **104 passed, 2 skipped**, 84 subtests,
  42.25 seconds. Skips were unavailable Windows symlink privileges and a
  PowerShell host blocked by the existing execution policy. No policy changed.
- Same Windows host with an intentionally absent FASTMEAN path and native
  flags disabled: **91 passed, 15 skipped**, 84 subtests, 13.79 seconds.
- Real SDK stdio suite: **7 passed**. Includes preview/resources, saved results
  across restart, AC/transient/CIRSYM, explicit cancellation and SDK request
  cancellation. Each cancellation stopped the owned native process, left an
  unrelated process alive, and permitted the same session to calculate again.
- Point75A: 29 physical elements, four external ports, preserved explicit
  placements and orthogonal wires. Opened and visually inspected in FASTMEAN.
  At 101 frequencies from 10 Hz to 40 kHz, all three complex output responses
  agreed with an independent complex KCL oracle to relative error below
  **1.2e-13**. Resistive loads and ideal coils are model assumptions.
- RC/RLC analytical responses, source polarity, component initial conditions,
  linear/log sweeps, relative subcircuit dependencies and native symbolic
  singular-output rejection have native regression coverage.
- Installer fresh install, upgrade, doctor and uninstall completed in an
  isolated environment. Unrelated config bytes, empty arrays, comments,
  tool policies, extra environment variables and retained results survived.
- Built wheel installed into a fresh private target and was exercised from
  another working directory with isolated Python: initialize, version, all
  17 tools, packaged guide, status and examples passed.

The legacy Russian GUI still displays some corrupt unit labels on a system
with another ANSI code page. MCP preview uses readable Unicode labels. The
optional locale helper was built and its pinned downloads verified, but was
not launched through the Windows Application Control block. There is no claim
that the helper is permitted by this machine's security policy.

Native executable SHA256 used for these checks:
`a001582ada87cdf013605f43b019957ae23204ef4bfcc33be02a0681b186ee25`.
The native application, private coursework, PDFs and raw local validation logs
are not distributed.

The 1.2.0 layout holdout also rebuilt the attributed Point75A reference through
actual MCP create/preview calls:29components,4ports,24 genuine junctions,
zero retained routing waypoints and no warnings. Visual review found clean
three-stage wiring and readable labels. This holdout started no native solver;
its purpose was independent layout coverage beyond the small reference cases.
