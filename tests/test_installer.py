"""Installer isolation and exact preservation of unrelated Codex configuration."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
DISTRIBUTION = PROJECT / "distribution"
spec = importlib.util.spec_from_file_location("installer_config", DISTRIBUTION / "manage_config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
sys.path.insert(0, str(DISTRIBUTION))
import lifecycle


class ConfigPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fastmean-installer-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_multiline_fake_headers_comments_empty_arrays_and_bom_survive(self):
        original = b'\xef\xbb\xbf' + '''# personal configuration\r
model = "keep-model"\r
empty = []\r
description = """\r
[mcp_servers.fastmean]\r
This is only text, not a server.\r
"""\r
\r
[mcp_servers.other]\r
command = "other.exe"\r
enabled_tools = [] # intentionally none\r
args = ["--keep"]\r
\r
[projects.'C:\\my project']\r
trust_level = "trusted"\r
'''.encode()
        entry = {"command": "C:\\venv\\python.exe", "args": ["-X", "utf8", "-m", "fastmean_mcp"],
                 "enabled_tools": [], "env": {"FASTMEAN_APP_DIR": "C:\\Программы\\FASTMEAN"}}
        merged = config.merge_server(original, entry)
        self.assertTrue(merged.startswith(original))
        self.assertTrue(merged.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(tomllib.loads(merged.decode("utf-8-sig"))["mcp_servers"]["fastmean"], entry)
        removed = config.merge_server(merged, None)
        self.assertTrue(removed.startswith(original))
        self.assertEqual(tomllib.loads(removed.decode("utf-8-sig")), tomllib.loads(original.decode("utf-8-sig")))

    def test_quoted_fastmean_tables_are_replaced_without_touching_neighbors(self):
        left = '# keep\nempty=[]\n[mcp_servers.other]\ncommand="other"\n'
        right = '[projects."sample"]\ntrust_level="trusted"\n'
        original = (left + '[mcp_servers."fastmean"]\ncommand="old"\n'
                    + '[mcp_servers."fastmean".env]\nOLD="yes"\n' + right).encode()
        entry = {"command": "new", "args": [], "tools": {"fastmean_ac": {"approval_mode": "prompt"}}}
        merged = config.merge_server(original, entry).decode()
        self.assertIn(left, merged)
        self.assertIn(right, merged)
        self.assertNotIn('command="old"', merged)
        self.assertEqual(tomllib.loads(merged)["mcp_servers"]["fastmean"], entry)

    def test_inline_server_syntax_is_rejected_instead_of_rewriting_other_tables(self):
        with self.assertRaisesRegex(config.ConfigError, "inline/dotted"):
            config.merge_server(b'mcp_servers = { fastmean = { command="old" }, other={command="safe"} }\n', {"command": "new"})

    def test_concurrent_change_is_not_overwritten(self):
        target = self.root / "config.toml"
        target.write_bytes(b'new_user_setting = []\n')
        with self.assertRaisesRegex(config.ConfigError, "changed"):
            config._replace_config(target, b'old=true\n', b'changed=true\n', True)
        self.assertEqual(target.read_bytes(), b'new_user_setting = []\n')

    def test_uninstall_preserves_entry_if_someone_repointed_it(self):
        home = self.root / "codex"
        home.mkdir()
        target = home / "config.toml"
        original = b'[mcp_servers.fastmean]\ncommand="someone_else.exe"\nargs=[]\n'
        target.write_bytes(original)
        with self.assertRaisesRegex(config.ConfigError, "no longer points"):
            config.remove(home, self.root / "owned" / "python.exe", self.root / "private")
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse((self.root / "private").exists())

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI required for isolated registration test")
    def test_real_codex_staged_registration_upgrade_and_remove_preserve_unrelated_bytes(self):
        home = self.root / "isolated-codex"
        home.mkdir()
        target = home / "config.toml"
        original = b'# never reserialize this\nmodel="preserved"\nempty=[]\n[mcp_servers.other]\ncommand="other"\nenabled_tools=[]\n'
        target.write_bytes(original)
        state = self.root / "private-state"
        result = config.register(Path(shutil.which("codex")), home, Path(sys.executable),
                                 self.root / "licensed-app", self.root / "results", state)
        self.assertEqual(Path(result["backup_path"]).read_bytes(), original)
        self.assertTrue(target.read_bytes().startswith(original))
        entry = tomllib.loads(target.read_text())["mcp_servers"]["fastmean"]
        entry["enabled_tools"] = []
        entry["env"]["FAKE_SECRET_FOR_TEST"] = "not-public"
        target.write_bytes(config.merge_server(target.read_bytes(), entry))
        updated = config.register(Path(shutil.which("codex")), home, Path(sys.executable),
                                  self.root / "licensed-app", self.root / "results", state)
        self.assertEqual(updated["status"], "unchanged")
        self.assertNotIn("not-public", json.dumps(updated))
        actual = tomllib.loads(target.read_text())["mcp_servers"]["fastmean"]
        self.assertEqual(actual["enabled_tools"], [])
        self.assertEqual(actual["env"]["FAKE_SECRET_FOR_TEST"], "not-public")
        config.remove(home, Path(sys.executable), state)
        self.assertTrue(target.read_bytes().startswith(original))
        self.assertEqual(tomllib.loads(target.read_text()), tomllib.loads(original.decode()))


@unittest.skipUnless(os.name == "nt", "Native Windows installer required")
class PythonInstallerTests(unittest.TestCase):
    def test_primary_python_dryrun_needs_no_powershell_and_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-python-installer-") as temporary:
            root = Path(temporary)
            app = root / "licensed-app"
            app.mkdir()
            (app / "Fastmean.exe").write_bytes(b"fixture; never execute")
            fake_codex = root / "codex.exe"
            fake_codex.write_bytes(b"fixture; dry-run never executes")
            destination = root / "not-created"
            result = subprocess.run([sys.executable, "-X", "utf8", str(DISTRIBUTION / "install.py"),
                "--dry-run", "--install-dir", str(destination), "--app-dir", str(app),
                "--codex-path", str(fake_codex)], capture_output=True, text=True, encoding="utf-8", timeout=25)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertFalse(plan["windows_settings_changed"])
            self.assertFalse(plan["proprietary_binaries_downloaded"])
            self.assertFalse(destination.exists())

    def test_uninstall_removes_only_owned_entry_and_files_and_preserves_results(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-owned-uninstall-") as temporary:
            root = Path(temporary) / "owned"
            root.mkdir()
            venv = root / "venv"
            venv.mkdir()
            (venv / "pyvenv.cfg").write_text("home = fixture")
            (venv / "owned.txt").write_text("owned environment")
            python = venv / "Scripts" / "python.exe"
            tools = root / "tools"
            tools.mkdir()
            (tools / "unchanged.py").write_text("owned")
            (tools / "modified.py").write_text("user modified")
            (tools / "notes.txt").write_text("unrelated user note")
            output = root / "results"
            output.mkdir()
            (output / "important.csv").write_text("preserve")
            home = root / "isolated-codex"
            home.mkdir()
            original = b'# unrelated\nempty=[]\n[mcp_servers.other]\ncommand="keep.exe"\n'
            entry = {"command": str(python), "args": ["-X", "utf8", "-m", "fastmean_mcp"]}
            (home / "config.toml").write_bytes(config.merge_server(original, entry))
            state = {"owner": lifecycle.OWNER, "install_root": str(root), "codex_home": str(home),
                     "output_dir": str(output), "results_owned": True,
                     "tools_files": [{"name": "unchanged.py", "sha256": lifecycle.hashlib.sha256(b"owned").hexdigest()},
                                     {"name": "modified.py", "sha256": "old-hash"}]}
            lifecycle.write_state(root, state)
            before = (home / "config.toml").read_bytes()
            with patch.object(lifecycle.sys, "executable", str(python)):
                with self.assertRaisesRegex(lifecycle.InstallError, "base Python"):
                    lifecycle.uninstall(root)
            self.assertEqual((home / "config.toml").read_bytes(), before)
            self.assertTrue(venv.is_dir())
            result = lifecycle.uninstall(root)
            self.assertFalse(venv.exists())
            self.assertFalse((tools / "unchanged.py").exists())
            self.assertTrue((tools / "modified.py").is_file())
            self.assertTrue((tools / "notes.txt").is_file())
            self.assertTrue((output / "important.csv").is_file())
            self.assertEqual(tomllib.loads((home / "config.toml").read_text()), tomllib.loads(original.decode()))
            self.assertEqual(len(result["preserved_modified_helpers"]), 1)
            self.assertEqual(len(list((root / "config-backups").glob("*.toml"))), 1)
            again = lifecycle.uninstall(root, remove_results=True)
            self.assertTrue(again["results_removed"])
            self.assertFalse(output.exists())
            self.assertTrue((tools / "notes.txt").is_file())


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell required")
class PowerShellInstallerTests(unittest.TestCase):
    def test_all_scripts_parse(self):
        for script in DISTRIBUTION.glob("*.ps1"):
            code = "$t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($env:FASTMEAN_SCRIPT_TO_PARSE,[ref]$t,[ref]$e);if($e){$e|Out-String|Write-Error;exit 1}"
            result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", code],
                env=dict(os.environ, FASTMEAN_SCRIPT_TO_PARSE=str(script)), capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_dryrun_and_whatif_make_no_directories(self):
        with tempfile.TemporaryDirectory(prefix="fastmean-ps-installer-") as temporary:
            root = Path(temporary)
            app = root / "licensed-app"
            app.mkdir()
            (app / "Fastmean.exe").write_bytes(b"fixture; never execute")
            fake_codex = root / "codex.exe"
            fake_codex.write_bytes(b"fixture; dry-run does not execute")
            for option in ("-DryRun", "-WhatIf"):
                destination = root / ("never-created" + option)
                result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-File",
                    str(DISTRIBUTION / "install.ps1"), option, "-InstallRoot", str(destination),
                    "-AppDir", str(app), "-PythonPath", sys.executable, "-CodexPath", str(fake_codex)],
                    capture_output=True, text=True, timeout=30)
                if result.returncode and "UnauthorizedAccess" in result.stderr and "scripts is disabled" in result.stderr:
                    self.skipTest("This PowerShell host forbids scripts. No execution-policy change or bypass is performed.")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('"windows_settings_changed":', result.stdout)
                self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
