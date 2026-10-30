import unittest

try:
    from fastapi.testclient import TestClient
    from dc.studio.server import create_app
except Exception:  # optional web dependencies are checked by doctor
    TestClient = None
    create_app = None


@unittest.skipUnless(TestClient and create_app, "FastAPI test dependencies are optional")
class StudioSecurityTests(unittest.TestCase):
    def test_origin_token_and_traversal_guards(self):
        client = TestClient(create_app(lan=False)[0], base_url="http://127.0.0.1")
        self.assertEqual(client.get("/api/health").status_code, 200)
        self.assertEqual(client.post("/api/decisions", json={}, headers={"Origin": "https://attacker.invalid"}).status_code, 403)
        self.assertEqual(client.get("/api/file/..%2Fsecret").status_code, 400)

    def test_lan_requires_session_token(self):
        app, token = create_app(lan=True)
        client = TestClient(app, base_url="http://127.0.0.1")
        payload = {"job_id": "job_missing", "candidate_id": "c_missing", "action": "save"}
        self.assertEqual(client.post("/api/decisions", json=payload).status_code, 403)
        self.assertEqual(client.post("/api/decisions", json=payload, headers={"Origin": "http://127.0.0.1", "X-DC-Token": token}).status_code, 404)
