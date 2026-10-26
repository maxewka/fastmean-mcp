These installers contain only this open source MCP adapter. They do not download
FASTMEAN, its solvers, fonts, or locale-emulation binaries. Install and license
FASTMEAN 6.1/6.0 separately. Windows, an existing Python 3.12+ with `venv`, and
Codex CLI are prerequisites. Dependency installation needs normal pip access.

These automated installers register Codex. For **Claude, Kimi, DeepSeek/Cline**
and a manual installation that does not require Codex, see
[AI client profiles](../docs/ai-clients.md). The installed package can export
fresh client JSON with `python -m fastmean_mcp.client_config`.

From a reviewed checkout, use the existing Python interpreter:

```text
py -3.12 distribution/install.py --dry-run
py -3.12 distribution/install.py
py -3.12 distribution/doctor.py
py -3.12 distribution/uninstall.py --dry-run
py -3.12 distribution/uninstall.py
```

An approved existing Codex Python runtime can run these same Python files.
PowerShell wrappers are optional and require an already permitted PowerShell
host. No script changes or bypasses execution policy, App Control, antivirus,
system locale, registry, or PATH. A managed security block requires the owner's
approved deployment process; it is not removed by these installers.

`install.py` accepts `--app-dir`, `--python`, `--install-dir`, `--output-dir`,
`--codex-home`, `--codex-path`, `--package-path`, `--dry-run`, and
`--replace-existing`. Defaults are `%LOCALAPPDATA%\FastmeanMCP` with its private
`venv`, `tools`, `results`, receipt, log and config backups. The original native
batch CLI requires an ASCII output path; use `--output-dir` when needed.

The installer invokes the documented `codex mcp add ... --env ... -- <command>`
in a temporary configuration home, then updates only `fastmean` tables in the
actual configuration. Unrelated bytes, comments, empty arrays and MCP entries
are preserved. The previous config is copied to a private backup; Windows
replacement preserves the config's existing ACL. Inline/dotted definitions of
an existing `fastmean` entry are rejected instead of rewriting unrelated TOML.
Existing Fastmean tool policies and extra environment variables survive an
upgrade. Replacing an unrelated server named `fastmean` needs the explicit
`--replace-existing` flag.

Doctor imports the installed dependencies, verifies paths and executable hash,
and performs real stdio MCP initialization, tool discovery, and status. It starts
no native circuit analysis. Restart the Codex task/app after installation.

Uninstall removes the entry only if it still points to this owned environment.
It removes the owned venv and unchanged helper files, while preserving modified
helpers and unknown files. Results, private backups, logs, and the receipt remain
by default. `--remove-results` additionally removes only the installer's owned
default `results` folder; custom/external result folders always remain. Run
uninstall using a base Python outside the owned venv because Windows cannot
remove the currently running Python executable.

Official behavior references:
[Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
[Windows ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew).
