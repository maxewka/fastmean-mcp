"""Check an installed FASTMEAN MCP environment through real stdio MCP."""
import argparse
from pathlib import Path
from lifecycle import default_root, doctor, emit_or_fail

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--skip-protocol", action="store_true")
    args = parser.parse_args()
    emit_or_fail(parser, lambda: doctor(args.install_dir or default_root(), args.skip_protocol))
