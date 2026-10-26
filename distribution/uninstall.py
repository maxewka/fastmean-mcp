"""Remove only this owned MCP environment; preserve results by default."""
import argparse
from pathlib import Path
from lifecycle import default_root, emit_or_fail, uninstall

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--remove-results", action="store_true",
                        help="Remove only the owned default results folder; custom/external output folders remain")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    emit_or_fail(parser, lambda: uninstall(args.install_dir or default_root(), args.remove_results, args.dry_run))
