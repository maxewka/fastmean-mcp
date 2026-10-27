# Validation history

Latest release reports: [1.6.0 catalog and analysis checks](VALIDATION-1.6.0.md)
and [1.5.0 layout and installed-package checks](VALIDATION-1.5.0.md).
The entries below retain the capabilities and limitations of their stated version.

## 1.4.0: native transformers, controlled switches and transient events

Local Windows / FASTMEAN 6.1 on 2026-10-27. The full portable suite, with
FASTMEAN deliberately unavailable, passed: **249 passed, 29 skipped,
329 subtests**, 152.74 seconds. The targeted final suite covering schematic
authoring, flyback through real MCP, native TR/SW/diode primitives and repeated
transient events passed: **27 passed, 54 subtests**, 48.45 seconds.

An earlier full native-enabled suite completed with 271 passed, 5 skipped,
337 subtests and one new-test assertion failure. That test incorrectly required
every flyback run to contain an exactly repeated time. The new TR/SW example
has no repeated rows; the original diode-based attempt did. The corrected test
verifies nondecreasing native order and that the reported event count matches
the export. Its full MCP workflow passed in the final targeted suite. Separate
event fixtures retain repeated rows, both boundary states, correct integrals
and peaks; decreasing TD times and duplicate AC frequencies remain errors.

Native tests verify TR ratio n=Np/Ns and winding reversal through all four
rotations; SW control polarity, both power-current directions and hysteresis;
and D anode/cathode order. Slow 0–5 V control ramps with Uon=3 V/Uoff=2 V
leave SW off while rising through 2.2–2.8 V and on while falling through it.
All source circuits are preserved. Preview/routing tests verify exact native
terminal geometry, real wires, phase dots, control signs and caption clearance.

The complete built-in flyback was created, annotated, previewed, exported and
calculated through the official MCP SDK over stdio. Native transient output
covers 0–10 ms with 102,030 rows, step 100 ns and eps=1e-5. On 9–10 ms:
mean output 15.583914 V, output peak-to-peak 0.148951 V, maximum switch voltage
39.991150 V, magnetizing-current range 0.815609–1.779700 A and average diode
current 0.779267 A. Gate-on intervals charge LM while the diode blocks;
gate-off intervals discharge LM into the output. Startup and switching charts
come from `fastmean_plot`; figures and the preview were visually inspected.

The sample saves EPS=1e-5 in its SCM as well as passing it to batch analysis.
The owned installer dry run and upgrade succeeded. Doctor initialized installed
version 1.4.0, discovered 22 tools and successfully called status. All 23
installed Python/data files matched the source. Existing MCP settings and other
server configurations retained their parsed values; the installer saved its
normal private configuration backup. A fresh SDK session launched from the
installed environment outside the checkout repeated the complete flyback
workflow with identical numeric measurements. No Windows settings changed.
These are local results, not a claim of hosted CI execution.

## 1.3.2: finite self-test models and copied root references

Local Windows / FASTMEAN6.1 on 2026-10-27: **244 passed, 5 skipped,
308 subtests**, 111.14seconds. Portable checks with the native executable
deliberately absent: **225 passed, 24 skipped, 306 subtests**, 56.18seconds.
The new SDK regression runs original and annotated projects in both parent and
standalone model contexts. Existing native hierarchy, geometry and numerical
regressions remain included.

A private SDK experiment reproduced a Python-only rejection: a child model's
`_SELF` instance references that same file, but native parent expansion excludes
the test instance. Native netlist export and AC proved the finite behavior. When
selected as the root, that model includes its test instance once; inside the
instance the same file is a child, so its own test elements are excluded.

Authoring, private batch preparation, editing snapshots and transient topology
now distinguish those contexts. File dependencies are copied once and preserved;
active recursion still fails before any native-readable root/model is written.
Missing models, network references and unvalidated external-data fields remain
errors even on test-only branches. The native file graph is retained, rather
than deleting test elements from the model.

Annotation also relocates references to the root when its filename changes.
The original root and model hashes stayed unchanged. The original relative model
tree is retained when possible; renamed-root references use validated relative
private references. Model metadata distinguishes all dependencies from active
dependencies.

Persistent real-SDK sessions verified gains of0.5 in the parent,2/3 in the
standalone test,2/3 after binding the load to a2k parameter, and0.8 after editing
that declaration to4k. The copied standalone test retained2/3. Across those five
cases the maximum AC error was3.34e-16 and the maximum TD voltage-ratio error
was8.05e-16V. Preview images were inspected; these are MCP drawings, not native
screenshots.

The normal installer dry run and upgrade succeeded. Doctor initialized installed
version1.3.2, discovered22 tools and called status. All22 installed Python/data
files matched source bytes, and the Codex configuration was byte-identical. A
fresh SDK session launched from the installed environment repeated all five
native cases with the same bounds. No Windows settings changed.

The first hosted Windows run exposed an overly strict assertion in the new
test: the native reference used an8.3 temporary-directory alias while the
returned path used its long spelling. The test now checks actual file identity.
The failure was reproduced locally with GetShortPathNameW, and the complete
portable suite then passed under that short temporary alias:225 passed,
24 skipped,306 subtests in56.90seconds. Production package bytes were unchanged.

## 1.3.1: active project topology and native open-pin connectors

Local Windows / FASTMEAN6.1 on 2026-10-27: **239 passed, 5 skipped,
308 subtests**, 100.52seconds. Portable checks with FASTMEAN absent:
**221 passed, 23 skipped, 306 subtests**, 62.03seconds. This includes native SDK
regressions for active subcircuit fixtures, cross-boundary loops and an open
resistor pin. No native application or Windows settings were modified.

The owned installation was upgraded normally after its dry run. Doctor
initialized1.3.1 and discovered22 tools; all22 installed Python/data files
matched source bytes. The installed-server SDK session independently repeated
the corrected fixture and cross-boundary rejection. Codex configuration bytes
remained identical during the upgrade.

Two failures were reproduced through real MCP before the fix. A valid RC model
with an underscore-prefixed test source was rejected by Python preflight even
though native netlist expansion excluded that source. A U/C loop closed through
the model boundary passed local checks and timed out after its requested2seconds.
After the fix, the RC calculation completes and the cross-boundary loop is
rejected in roughly0.1second without creating a native process.

Transient preflight now follows active instance contexts. Child test-only
components and their inactive subtrees are excluded; the same names stay active
when that file is selected as the root. Internal nodes of repeated instances
remain distinct, while real native ground is global. PORT rotation/coordinate
order and the declared Pins mapping must agree before interfaces are joined.
Unknown/flipped interfaces, native instance overrides and expansion limits
produce explicit partial-coverage metadata. The circuit still belongs to the
native solver; this check covers independent ideal U/C loops, not every possible
singularity or model equation.

A separate authoring regression exposed single-terminal nets being pruned and
then rejected. A bare unwired pin also caused a native batch timeout. The manual
page12 recommends a connector for such pins: generated schemes now retain one
short wire and one real CON endpoint. Native AC verified zero open-branch current
and the unchanged RC transfer function. No extra load or external PORT is used.

For the sinusoidal RC fixture, native PHI0=0 uses a cosine reference. The native
zero-state initialization/timing samples are retained. The measured transient
deviation from the ideal cosine response was about64.3microvolt;10x finer output
sampling and100x smaller eps did not remove it in this worker. The regression
uses a0.1millivolt bound. AC and transient data provenance remain explicit.

The complete four-BJT example was rebuilt and calculated again through actual
MCP. All five native model instances passed the new interface checks. The root
SCM was byte-identical to the published nominal example; the0.29–0.30s interval
again gave25.002515V RMS,20.002012A RMS and500.100725W. Existing physical-model
limitations remain applicable.

## 1.3.0: existing parameter edits and complete inspection pages

Local Windows / FASTMEAN6.1 on 2026-10-27: **231 passed, 5 skipped,
304 subtests**, 93.62seconds. The portable suite with the executable deliberately
absent passed **214 tests, 22 skipped, 302 subtests**, 54.68seconds. Subsequent
targeted parameter checks covered numeric underflow/extreme exponents and
unsupported parameter-function syntax: **6 passed, 18 subtests**. Platform and
existing policy skips remain; no Windows settings changed.

The normal installer upgraded the owned environment to1.3.0 after a dry run.
Doctor initialized the installed package, discovered22 tools and called status;
all21 installed Python/data files matched the reviewed source. A separate
installed-server stdio session inspected and edited an amplifier parameter,
retaining all12 direct bindings. Configuration semantics and unrelated settings
were preserved; the installer retained its configuration backup.

`fastmean_edit_parameters` changes existing root numeric declaration spans,
retaining quoted labels, comments, CRLF, direct component bindings, all other
TEXT, wires, analysis settings and recursive models. It rejects ambiguous or
overridden targets, nonliteral expressions, invalid direct passive/source ranges
and values that would silently underflow to zero. Source/model snapshots are
checked before publication. The optional expected source digest detects a
resave after inspection. See [the API guide](PARAMETERS.md).

`fastmean_inspect` now uses actual UTF-8 byte budgets and complete paged entries.
The amplifier summary includes all **36 components, 23 nodes, four ports,
seven constants, 12 direct bindings, 11 TEXT objects and five saved TD formulas**
in about33KiB. `include_objects` adds a separate raw-object page. Selected
sections and nested `detail_path` reads can recover large native waveform arrays
or text chunks without recursive cuts. Snapshot hashes prevent mixing pages
from different saves. Inspection creates no files or native processes.

The official MCP SDK stdio workflow discovered **22 tools**, created and
annotated an RC filter, changed `R0` from1k to2k, inspected its retained binding,
ran native AC and transient, then returned a plot through MCP. Independent
equations gave the new cutoff **79.57747154595Hz**. Maximum AC magnitude error
was **6.67e-16**; transient deviation from the ideal step response was
**2.50e-7V**, consistent with the source's finite rise time. The returned chart
was visually checked. No direct implementation calls authored those deliverables.

The same MCP workflow edited the amplifier's `Rload`, shared `Rf` and `Vrail`,
retained all12 bindings and four model files, and exported the native expanded
netlist. FASTMEAN confirmed2ohm load, both3k feedback resistors and both40V
supply source values. This is a separate variation; no25V/500W result is claimed
for those changed settings. The original nominal example and model hashes
remained intact. Hosted CI is separate from these local checks.

## 1.2.1: preservation, result integrity and native failure detection

Local Windows / FASTMEAN 6.1 on 2026-10-27: **220 passed, 5 skipped,
285 subtests**, 74.12 seconds. After a final axis-column collision guard,
the complete engine tests passed again: **24 passed, 48 subtests**. The final
portable suite with FASTMEAN intentionally absent passed **203 tests,
22 skipped, 283 subtests**, 38.55 seconds. Existing platform/policy skips
remain; no Windows settings were changed.

The normal installer upgraded the owned environment to **1.2.1** after a dry
run. Doctor initialized the installed server through real stdio, discovered
**21 tools** and successfully called status. The Codex configuration remained
byte-for-byte unchanged during this upgrade.

- Editing a hierarchical circuit now copies and registers its complete model
  tree. Repeated/nested definitions remain reusable after the source folder is
  unavailable. For external or absolute references, only the necessary model
  paths and requested fields change; original native settings, custom fields
  and literals are preserved. Waveform edits retain omitted phase/delay,
  user-defined curves and inactive source modes. Explicit amplitude/high takes
  precedence over the supplied base value, as during circuit creation.
- Repeated annotation places new notes after the full extent of existing
  multiline TEXT. Plot panel names and metric summaries wrap on separate lines;
  regression checks inspect actual rendered text bounds.
- Paged CSV reads authenticate the whole file, even outside the selected page.
  Large CSVs use streaming SHA256, with the old native-manifest fallback for
  pre-1.2.1 catalogues. Inline images follow the registered resource reader's
  integrity checks. Malformed catalogues produce a domain error. All **327**
  existing local result records passed the stricter catalogue validation.
- Native completion now requires the requested axis interval and AC sampling
  grid. Duplicate expressions and signal/axis name collisions are rejected
  before launch. Symbolic output probes must connect to electrical components;
  missing CIRSYM executable/settings files are reported before netlist export.
- TD checks each private SCM for a local loop containing only ideal independent
  voltage sources and capacitors and at least one voltage source. This is a
  documented FASTMEAN transient limitation, not a netlist repair. Pure capacitor
  cycles are allowed by this check; cross-subcircuit cycles and other singular
  topologies are outside its scope. No implicit resistance or model change is
  introduced.

Real official-SDK stdio checks exercised create/project/edit/inspect/preview,
native AC/TD, pagination and plotting without desktop automation. An edited
hierarchical divider produced the independently expected gain **2/3** at all
five AC points. The ideal compensated-divider TD request was rejected without
creating a native process, while its sine-excited AC gain remained **0.1**.
A separate, explicitly modified fixture with **100 ohm** source resistance
completed TD; its 5,004 samples agreed with the finite-rise analytical response
within **8.87e-13 V**. Earlier timeout reports remain historical evidence for the
unmodified ideal circuit, not successful TD results.

The complete four-BJT example was freshly rebuilt and calculated through MCP:
31,204 adaptive native samples covered exactly 0–0.30 s, with **25.002515 V RMS,
20.002012 A RMS and 500.100725 W** on 0.29–0.30 s. Its root SCM matched the
published example byte-for-byte. The returned MCP graph was visually checked;
the existing model/SOA/thermal limitations still apply. Hosted CI is separate
from these local checks and is available through the repository workflow.

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
