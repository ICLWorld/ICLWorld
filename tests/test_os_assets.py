"""Offline OS proxy tests against the packaged platform and desktop assets.

Run with the platform dependencies installed:
    python -m unittest discover -s tests -p test_os_assets.py -v
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

CODEBASE = Path(__file__).resolve().parents[1]
PLATFORM = CODEBASE / 'environment' / 'platform'
os.environ['VIC_ROOT'] = str(PLATFORM)
sys.path.insert(0, str(PLATFORM / 'services' / 'control'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from vic import os_integration


class PackagedOSAssets(unittest.TestCase):
    def check_condition(self, condition):
        self.assertEqual(os_integration.ROOT, PLATFORM)
        static = CODEBASE / 'environment' / 'os' / 'static'
        class Upstream:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def request(self, method, path, **kwargs):
                name = path.lstrip('/')
                return SimpleNamespace(content=(static / name).read_bytes(), status_code=200,
                    headers={'Content-Type': 'text/javascript' if name.endswith('.js') else 'text/css'})
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / 'os-runs').mkdir()
            (data / 'os-runs/osl_assets.json').write_text(json.dumps({
                'id':'osl_assets', 'status':'running', 'generalization':condition}))
            app = FastAPI()
            os_integration.install_os_routes(app, lambda: None, 'test-only-secret', data,
                source=data, runtime=SimpleNamespace())
            with patch.object(os_integration.httpx, 'AsyncClient', Upstream), TestClient(app) as client:
                for suffix in ['js', 'css']:
                    with self.subTest(condition=condition, suffix=suffix):
                        response = client.get('/os-sim/osl_assets/desktop.' + suffix,
                            headers={'Authorization':'Bearer test-only-secret'})
                        self.assertEqual(response.status_code, 200)
                        content = (static / ('desktop.' + suffix)).read_bytes()
                        if suffix == 'js':
                            content = content.decode().replace('fetch(url,', 'fetch("/os-sim/osl_assets" + url,').replace("${btn('task-info','Task instructions')}", '').encode()
                        if condition == 'E':
                            content += b'\n' + (PLATFORM / 'scripts' / ('os_alternate_desktop.' + suffix)).read_bytes()
                        self.assertEqual(response.content, content)
                        self.assertEqual('aurora' in response.text.lower(), condition == 'E')
    def test_e_serves_alternate_js_and_css(self): self.check_condition('E')
    def test_i_serves_native_js_and_css(self): self.check_condition('I')
    def test_r_serves_native_js_and_css(self): self.check_condition('R')

if __name__ == '__main__':
    unittest.main()
