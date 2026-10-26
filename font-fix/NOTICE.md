# Optional Russian UI helper

`src/FastmeanRuRunner.cs` is adapted from the Locale Emulator v2.5.0.1 native
loader ABI and registry-read redirection structures by the
[Locale Emulator contributors](https://github.com/xupefei/Locale-Emulator/tree/v2.5.0.1).
It is distributed under **LGPL-3.0-only**, matching the version identified by
the upstream README. Full GPLv3 and LGPLv3 texts are in
`licenses/COPYING` and `licenses/COPYING.LESSER` (copied beside installed helper files).

Upstream source references:

- [LoaderWrapper.cs](https://github.com/xupefei/Locale-Emulator/blob/v2.5.0.1/LEProc/LoaderWrapper.cs)
- [LERegistryRedirector.cs](https://github.com/xupefei/Locale-Emulator/blob/v2.5.0.1/LEProc/LERegistryRedirector.cs)
- [Locale Emulator source at v2.5.0.1](https://github.com/xupefei/Locale-Emulator/tree/v2.5.0.1)
- [Locale Emulator core source](https://github.com/xupefei/Locale-Emulator-Core)

Local modifications: a minimal x86 launcher, Russian code page / charset,
preservation of the current timezone, two exact process-memory file-type label
read replacements, explicit FASTMEAN/document arguments, no updater, no
elevation fallback, and source-only build/install packaging. The source was
prepared for public distribution on 2026-10-26.

The installer downloads the unmodified **official v2.5.0.1** release and verifies
its SHA256 before extracting only `LoaderDll.dll` and `LocaleEmulator.dll`.
Neither those binaries nor FASTMEAN binaries are included in this repository.
The runtime libraries remain dynamically replaceable with ABI-compatible builds.
FASTMEAN is a separate proprietary application and is not covered by this helper's license.

There is no warranty that a current Windows security policy will allow the
helper to run. Windows Application Control / Smart App Control can block it.
The MCP server does not require this helper.
