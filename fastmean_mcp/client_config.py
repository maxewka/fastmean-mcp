"""Export local stdio configurations without changing an AI client's settings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

CLIENTS = ('generic', 'claude-code', 'claude-desktop', 'kimi', 'deepseek-cline')


def make_config(client: str, python: str, app_dir: str, output_dir: str) -> dict:
    if client not in CLIENTS:
        raise ValueError('Unknown client profile.')
    paths = [Path(value).expanduser().resolve() for value in (python, app_dir, output_dir)]
    interpreter, app, output = paths
    if not interpreter.is_file():
        raise ValueError('The Python executable with fastmean_mcp installed must exist.')
    if not (app / 'Fastmean.exe').is_file():
        raise ValueError('FASTMEAN_APP_DIR must contain the separately installed Fastmean.exe.')
    if not str(output).isascii():
        raise ValueError('Native FASTMEAN batch requires an ASCII output path.')
    if output == app or output.is_relative_to(app):
        raise ValueError('Keep calculation results outside the FASTMEAN installation.')
    if output.exists() and not output.is_dir():
        raise ValueError('Output path must be a directory.')
    entry = {'command': str(interpreter), 'args': ['-X', 'utf8', '-m', 'fastmean_mcp'],
             'env': {'FASTMEAN_APP_DIR': str(app), 'FASTMEAN_OUTPUT_DIR': str(output)}}
    if client == 'claude-code':
        entry['type'] = 'stdio'
    if client == 'deepseek-cline':
        entry.update(disabled=False, autoApprove=[], timeout=120)
    return {'mcpServers': {'fastmean': entry}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=CLIENTS, default='generic')
    parser.add_argument('--python', default=sys.executable,
                        help='Python executable in the installed FASTMEAN MCP environment')
    parser.add_argument('--app-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--write', type=Path, help='Create a new JSON file; never overwrites or merges client settings')
    args = parser.parse_args(argv)
    try:
        config = make_config(args.client, args.python, args.app_dir, args.output_dir)
        text = json.dumps(config, ensure_ascii=False, indent=2) + '\n'
        if args.write:
            with args.write.open('x', encoding='utf-8') as stream:
                stream.write(text)
            print(str(args.write.resolve()))
        else:
            print(text, end='')
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
