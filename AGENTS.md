# Working on FASTMEAN MCP

This repository contains the adapter and an optional locale-helper source, not FASTMEAN itself. Read README.md, distribution/README.md and the relevant source before changing installation or engine behavior.

## When the user asks to install this MCP

Treat an explicit installation request as authorization to complete the normal reversible installation. Do not stop at a plan or ask for the same permission again. Inspect prerequisites and the dry-run result before applying installation.

1. Work from a reviewed checkout. Find an existing Python 3.12+ with venv, the Codex CLI and separately installed FASTMEAN 6.1/6.0. The installer discovers standard application directories. If a required program is absent, report that concrete blocker rather than downloading a proprietary application or changing machine policies.
2. Run `distribution/install.py --dry-run` with that Python. Pass --app-dir, --install-dir or --output-dir only when needed or requested. Native output needs a writable ASCII path. Resolve a dry-run error before proceeding.
3. Run the same installer without --dry-run. It owns a dedicated environment and updates only the fastmean MCP entry. Do not rewrite the whole TOML, replace unrelated servers, empty tool policies or remove extra environment variables. Replacing an unrelated server named fastmean requires explicit user authorization before --replace-existing.
4. Run `distribution/doctor.py` with --install-dir when non-default. Report its actual initialize/tool-discovery/status result. Doctor starts no native analysis. Explain that the connection or app must restart before a new task can use the tools.
5. If removal is requested, inspect `distribution/uninstall.py --dry-run`, then use the owned uninstaller from a Python outside its venv. Preserve results and backups unless their removal was specifically requested.

Use Python entry points as the primary installation path. Do not change or bypass PowerShell execution policy, App Control, Smart App Control, antivirus, UAC, registry, PATH or Windows locale. Do not add policy-bypass switches, elevation fallbacks or alternate loaders. If an enforced policy blocks an operation, report the action and the policy's stated reason.

The font-fix helper is optional and separately LGPL-licensed. Do not build, download its runtime, install fonts, create shortcuts or launch it implicitly during MCP installation. For an explicit helper request, follow font-fix/README.md; if Windows blocks it, keep MCP usable and report that limitation.

## Development boundaries

- Preserve input SCM files. Use fresh job directories outside the native installation and registered artifacts rather than an arbitrary file-read endpoint.
- Keep solver provenance explicit: FASTMEAN exports numbers, CIRSYM exports symbolic expressions, Matplotlib renders charts, preview.py renders SCM drawings. A preview is not a native screenshot.
- Keep real orthogonal wires, correct terminal polarity and junctions. Ports identify external interfaces. Validate connectivity and inspect a preview after layout changes.
- Do not publish native executables, libraries, proprietary fonts, manual PDFs, private installation logs, absolute user paths or unlicensed reference images. Retain Point75A attribution and distinguish its 25 reference elements from four test fixtures.
- Use the pinned official MCP SDK. Do not replace native regression checks with fabricated solver results or claim CI that has not run.

Run `python -m pip install -r requirements-dev.txt -e .` and `python -m pytest -q`. CI runs without FASTMEAN; native cases skip when its executable is absent. On Windows with FASTMEAN, test_engine can start it automatically. FASTMEAN_MCP_NATIVE_TEST=1 and FASTMEAN_RELAYOUT_NATIVE=1 enable additional native suites. Use private temporary directories and terminate only owned processes.
