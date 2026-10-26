"""Primary installer: run with existing Python 3.12+, no PowerShell policy changes."""
import sys

if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12+ is required. Use py -3.12 distribution/install.py or an approved existing Codex Python runtime.")

from lifecycle import emit_or_fail, install, installation_parser

if __name__ == "__main__":
    parser = installation_parser()
    args = parser.parse_args()
    emit_or_fail(parser, lambda: install(args))
