# Validation history

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
