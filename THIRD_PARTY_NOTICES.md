# Third-party notices

The root MIT license covers this project's original MCP adapter, tests, installers and documentation. It does not relicense third-party software or externally authored reference material.

## Python dependencies

Dependencies are installed by pip, not vendored in this source repository. Their distributions contain applicable license and copyright notices, including notices for transitive dependencies and bundled assets.

| Dependency | Upstream license / source |
|---|---|
| MCP Python SDK | [MIT; copyright Anthropic, PBC](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE) |
| PyYAML | [MIT; Ingy döt Net and Kirill Simonov](https://github.com/yaml/pyyaml/blob/main/LICENSE) |
| Matplotlib | [Matplotlib license, based on the PSF license, and included third-party notices](https://matplotlib.org/stable/project/license.html) |
| pytest, development only | [MIT](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |

Pinned runtime versions are in pyproject.toml and requirements.txt. No modification to these upstream dependencies is included here.

## Optional Locale Emulator helper

`font-fix/src/FastmeanRuRunner.cs` adapts Locale Emulator loader ABI and registry-read redirection structures and is **LGPL-3.0-only**, rather than MIT. See [font-fix/NOTICE.md](font-fix/NOTICE.md), [COPYING.LESSER](font-fix/licenses/COPYING.LESSER) and [COPYING](font-fix/licenses/COPYING) for attribution, modifications and full license texts.

The optional source installer obtains the official [Locale Emulator v2.5.0.1 release](https://github.com/xupefei/Locale-Emulator/releases/tag/v2.5.0.1), verifies pinned hashes and builds the helper locally. Locale Emulator binaries are not committed to this repository. The MCP server does not require the helper.

## FASTMEAN and circuit references

FASTMEAN and CIRSYM are separate applications supplied by their respective owners. This project does not distribute their executables, libraries, installation packages, proprietary fonts or manual PDF. Users must obtain an appropriate native installation separately. The included capability guide paraphrases documented commands and links to [FASTMEAN's official symbolic-analysis description](http://www.fastmean.ru/rus/index.php?page=symbolic.php).

The Point75A example credits **Troels Gravesen**, [The Point75 / Going three-way, Figure 31](http://www.troelsgravesen.dk/download/Point75A%26B.pdf), PDF page 11. It transcribes functional circuit connections and nominal values into a new layout, adds separately identified source/load test fixtures and assigns component identifiers absent from the original drawing. The original PDF and images are not redistributed; this project's MIT license does not apply to those external materials. See [the example notes](examples/point75a/README.md) for model assumptions.

Blender MCP and FreeCAD MCP links in the design note acknowledge research references. Their source code is not included or relicensed by this project. This adapter is not an official FASTMEAN, Blender, FreeCAD or OpenAI product.
