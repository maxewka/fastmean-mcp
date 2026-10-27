# Claude, Kimi, DeepSeek and other MCP clients

FASTMEAN MCP is a local **stdio server**, independent of the language model.
The Windows client runs the server next to the separately installed FASTMEAN.
No model API key belongs in this server. Select/authenticate your model in the
client; its usual tool permissions remain in effect. Authoring, subcircuits,
parameters, saved graph expressions and native calculations use the same tools.
Computer Use is not required. `fastmean_open` is optional and only for an explicit
request to open the desktop application.

Graphs are delivered through MCP as actual `ImageContent` blocks, with linked
PNG/SVG files and structured measurements. After a native calculation, use
`fastmean_plot` to choose its display and measurement windows, units and metric
captions. The AI can inspect the returned image directly when its MCP host
forwards image content. See [the plotting workflow](PLOTTING.md).

| Model/provider | Local MCP host | Configuration profile |
| --- | --- | --- |
| Anthropic Claude | Claude Code | `claude-code` |
| Anthropic Claude | Claude Desktop | `claude-desktop` |
| Moonshot Kimi | Kimi Code CLI | `kimi` |
| DeepSeek | Cline with DeepSeek selected as provider | `deepseek-cline` |
| Other tool-capable models | A client supporting local stdio MCP | `generic` |

The public chat websites and a bare model API do not execute a local stdio
process themselves. In particular, DeepSeek needs a host such as Cline to
translate model tool calls into MCP operations. This is not a hosted HTTP MCP
endpoint; do not paste a local executable path into a remote connector URL.

## Install without Codex

Use an existing Python 3.12+ and a reviewed checkout/release. No Codex CLI is
required for the following manual installation:

```powershell
py -3.12 -m venv C:\Tools\FastmeanMCP\venv
C:\Tools\FastmeanMCP\venv\Scripts\python.exe -m pip install C:\path\to\fastmean-mcp
```

If already installed for Codex, reuse that environment's `venv\Scripts\python.exe`.
The automated `distribution/install.py` still registers **Codex only**; it is not
an installer for all the clients listed above.

## Generate a configuration

Run with the installed MCP Python. Replace the example paths with your own:

```powershell
C:\Tools\FastmeanMCP\venv\Scripts\python.exe -X utf8 -m fastmean_mcp.client_config --client kimi --app-dir "C:\path\to\FASTMEAN 6.1" --output-dir C:\FastmeanResults --write C:\FastmeanResults-kimi.json
```

Select any profile from the table. The helper writes a **new** JSON file or prints
JSON when `--write` is omitted. It does not overwrite client settings, insert
keys, enable automatic approvals, or change Windows settings. Use absolute paths
and an ASCII output directory. Keep `command` and `args` separate; no shell is
needed even when paths contain spaces.

### Claude Code / Desktop

For Code, load the generated file with
`claude --mcp-config C:\FastmeanResults-claude.json`, or merge its `fastmean` entry
into the project's `.mcp.json`. In Claude Code, `/mcp` shows connection status.
For Desktop, merge the generated `mcpServers.fastmean` entry into
`%APPDATA%\Claude\claude_desktop_config.json`, preserving other entries, then
restart the client. Do not replace its entire existing configuration.

### Kimi Code CLI

Load without modifying global settings:
`kimi --mcp-config-file C:\FastmeanResults-kimi.json`.
Alternatively merge the entry into the MCP configuration used by your installed
Kimi CLI version. `/mcp` shows connected tools; `kimi mcp test fastmean` checks a
persistently registered server.

### DeepSeek through Cline

Choose DeepSeek in Cline's provider settings and authenticate there. Open Cline's
MCP configuration and merge the generated `mcpServers.fastmean` entry. Its empty
`autoApprove` list keeps normal tool confirmation enabled. The server has no
dependency on a specific DeepSeek model identifier; select a currently available
tool-capable model in Cline.

## Verify and use

Start a fresh client connection and ask it to call `fastmean_status`,
`fastmean_example`, then `fastmean_create_circuit` and `fastmean_preview` on that
example. Expected discovery: **22 tools**. For a native smoke test, run
`fastmean_ac` on the RC example and inspect the returned native data/manifest.
For nonlinear amplifiers, use `fastmean_transient`.

Keep the calculation's `run_id` and pass it to `fastmean_plot`. The response
includes a new plot `run_id`, inline PNG, SVG, saved chart specification,
measurements and provenance. Use each returned resource URI with MCP
`resources/read` to retrieve a file, or `fastmean_get_result` with the plot ID to
recover its image after reconnecting. `fastmean_read_data` pages the original
native CSV. Plotting saved data starts no native solver.

For the five-signal amplifier example, export `U(IN)`, `U(OUT)`, `I(RL)`,
`I(VIN)` and `U(OUT)*I(RL)` through `fastmean_transient`. Then request
`display_window=[0.297,0.3]`, `measurement_window=[0.29,0.3]` and `x_unit="ms"`.
Use `scale=1000`, `unit="mA"` on the input-current panel and `metrics=["mean"]`,
`guides=["mean"]` on the native power column. The full JSON arguments and
time-weighted measurement definitions are in [PLOTTING.md](PLOTTING.md). The
amplifier results describe its [nominal PWL model](../examples/four-bjt-amplifier/README.md).

Suggested instruction for any client:

> Use FASTMEAN MCP to produce a portable SCM with adjacent components, actual
> wires and native subcircuits. Put only important values in .parameter TEXT,
> save tested graph expressions and short explanatory TEXT. Preview and verify
> native connectivity/numeric results. Preserve the original file. Return the
> final SCM and its models directory. Use fastmean_plot on the native run_id
> for annotated images and measurements through MCP, with explicit measurement
> and display windows. Open desktop windows only on an explicit request.

Authoring supports independent voltage sources `U/V` and current sources `I`
with DC, sine or pulse waveforms. Voltage-source nodes are `[positive, negative]`;
current-source nodes are `[from, to]` for positive current. Preview, value edits
and root DC/sine amplitude parameter bindings include `I`. Symbolic analysis
and `fastmean_relayout` retain their R/C/L/U scope.

Manual component, node, route and port coordinates use multiples of four;
automatic spacing remains on 20-unit intervals. Choose
`layout.ground_style="local"` for individual native ground glyphs or `"rail"`
for the default bottom return rail. Review the preview before accepting layout;
dense or reference-specific drawings may need explicit placements/routes.
The [external reference benchmark](../benchmarks/reference-circuits/README.md)
keeps reference-guided and automatic inputs separate, with analytical
expectations and source attribution. Its input files alone do not establish
native numerical agreement or visual fidelity.

The generated configurations and real stdio discovery are tested locally.
Provider logins and end-to-end calls from Claude/Kimi/Cline have not been tested
here; successful protocol tests are not a claim of access to those accounts.

Official references (checked 2026-10-26):

- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Local MCP / Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Kimi MCP](https://moonshotai.github.io/kimi-cli/en/customization/mcp.html)
- [Cline MCP](https://docs.cline.bot/mcp/mcp-overview)
- [Cline DeepSeek provider](https://github.com/cline/cline/blob/main/docs/provider-config/deepseek.mdx)
- [DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls/)
