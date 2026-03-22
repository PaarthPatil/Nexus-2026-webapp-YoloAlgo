import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend import main  # noqa: E402


class BackendApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(main.app)
        cls.client = cls._client_cm.__enter__()
        login_response = cls.client.post(
            "/api/auth/login",
            json={"username": main.ADMIN_USERNAME, "password": main.ADMIN_PASSWORD},
        )
        if login_response.status_code != 200:
            raise RuntimeError(f"Unable to login in tests: {login_response.text}")
        token = login_response.json()["access_token"]
        cls.auth_headers = {"Authorization": f"Bearer {token}"}

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)

    def test_health_reports_dependency_state(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertIn("vision_ready", payload)
        self.assertIn("missing_dependencies", payload)

    def test_protected_route_requires_auth(self):
        response = self.client.get("/api/sessions/current")
        self.assertEqual(response.status_code, 401)

    def test_start_session_without_video_source_returns_400(self):
        response = self.client.post(
            "/api/sessions/start",
            headers=self.auth_headers,
            json={"video_source": "   "},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("video_source is required", response.text)

    def test_start_session_dependency_error_is_client_error(self):
        with patch.object(
            main.vision,
            "start_session",
            side_effect=RuntimeError("Missing Python dependency 'pandas' for YOLOv5 local repo mode."),
        ):
            response = self.client.post(
                "/api/sessions/start",
                headers=self.auth_headers,
                json={"video_source": 0, "count_mode": "roi_current"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing Python dependency", response.text)

    def test_stop_session_without_body_returns_backend_message_not_422(self):
        response = self.client.post(
            "/api/sessions/stop",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("No session is available to stop", response.text)

    def test_generate_challan_without_body_returns_400(self):
        response = self.client.post(
            "/api/challans/generate",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("session_id is required", response.text)


if __name__ == "__main__":
    unittest.main()
