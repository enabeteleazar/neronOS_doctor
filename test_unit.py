import sys, unittest
sys.path.insert(0, "/etc/neron")
from unittest import mock
import requests

from doctor import tester, fixer

class TesterProbeTests(unittest.TestCase):
    def test_probe_success(self):
        class DummyResp:
            def __init__(self):
                self.status_code = 200
                class E:
                    def __init__(self): pass
                    def total_seconds(self): return 0.012
                self.elapsed = E()
        with mock.patch('doctor.tester.requests.get', return_value=DummyResp()):
            res = tester._probe("http://example")
            self.assertEqual(res['code'], 200)
            self.assertTrue(res['ok'])
            self.assertIsNone(res['error'])
            self.assertIsNotNone(res['latency_ms'])

    def test_probe_failure(self):
        with mock.patch('doctor.tester.requests.get', side_effect=requests.ConnectionError("fail")):
            res = tester._probe("http://example")
            self.assertIsNone(res['code'])
            self.assertFalse(res['ok'])
            self.assertIsNotNone(res['error'])

class FixerTests(unittest.TestCase):
    def test_no_systemctl(self):
        with mock.patch('doctor.fixer._systemctl_available', return_value=False):
            res = fixer.apply_fixes({})
            self.assertIsInstance(res, list)
            self.assertFalse(res[0].get('ok'))

    def test_no_action_needed(self):
        report = {'tests': {'server_health': {'ok': True}}, 'monitor': {'services': {'neron-server': {'active': True}}}}
        with mock.patch('doctor.fixer._systemctl_available', return_value=True):
            res = fixer.apply_fixes(report)
            self.assertEqual(res, [{'ok': True, 'message': 'no_action_needed'}])

    def test_restart_called(self):
        report = {'tests': {'server_health': {'ok': False}}}
        with mock.patch('doctor.fixer._systemctl_available', return_value=True), \
             mock.patch('doctor.fixer._restart_service', return_value={'service':'neron-server','ok':True,'attempts':1,'message':'restarted_and_active'}):
            res = fixer.apply_fixes(report)
            self.assertTrue(any(r.get('ok') for r in res))

# New security tests
from fastapi.testclient import TestClient
from doctor import app as doctor_app
from doctor.config import cfg

class SecurityTests(unittest.TestCase):
    def test_config_masks_api_key(self):
        # enable auth and set a known API key
        cfg.API_KEY = "supersecret"
        client = TestClient(doctor_app.app)
        res = client.get("/config", headers={"X-Doctor-Key": "supersecret"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("API_KEY", data)
        self.assertNotEqual(data["API_KEY"], "supersecret")
        self.assertTrue("MASKED" in str(data["API_KEY"]))

if __name__ == '__main__':
    unittest.main()
