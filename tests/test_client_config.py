from pathlib import Path
import tempfile
import unittest
from fastmean_mcp.client_config import CLIENTS, make_config, main


class ClientConfigTests(unittest.TestCase):
    def test_profiles_preserve_argv_paths_and_do_not_grant_auto_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); app=root/'App with spaces';app.mkdir()
            (app/'Fastmean.exe').touch(); python=root/'Python with spaces.exe';python.touch()
            for client in CLIENTS:
                with self.subTest(client=client):
                    entry=make_config(client,str(python),str(app),str(root/'results'))['mcpServers']['fastmean']
                    self.assertEqual(entry['command'],str(python))
                    self.assertEqual(entry['args'],['-X','utf8','-m','fastmean_mcp'])
                    self.assertEqual(entry['env']['FASTMEAN_APP_DIR'],str(app))
                    self.assertFalse(entry.get('autoApprove'))
                    self.assertEqual(set(entry['env']),{'FASTMEAN_APP_DIR','FASTMEAN_OUTPUT_DIR'})
            self.assertFalse((root/'results').exists())

    def test_existing_client_config_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'Fastmean.exe').touch(); (root/'python.exe').touch()
            config=root/'existing.json'; config.write_bytes(b'{"unrelated":true}')
            with self.assertRaises(SystemExit):
                main(['--python',str(root/'python.exe'),'--app-dir',str(root),
                      '--output-dir',str(root.parent/'results'), '--write',str(config)])
            self.assertEqual(config.read_bytes(),b'{"unrelated":true}')
