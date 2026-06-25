import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.dependencies import get_user_manager
import backend.dependencies as dependencies
from backend.routers.auth import router as auth_router
from db.user_manager import UserManager


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        from db.pg_pool import clear_all_tables
        clear_all_tables()
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.user_manager = UserManager(db_path=str(Path(self.tmpdir.name) / "users.db"))
        app = FastAPI()
        app.include_router(auth_router)
        app.dependency_overrides[get_user_manager] = lambda: self.user_manager
        self.client = TestClient(app)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_register_creates_user_with_default_user_role_and_token(self):
        response = self.client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "correct horse battery staple"},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["token_type"], "bearer")
        self.assertIsInstance(body["access_token"], str)
        self.assertGreater(len(body["access_token"]), 20)
        self.assertEqual(body["user"]["username"], "alice")
        self.assertEqual(body["user"]["role"], "user")
        self.assertIn("id", body["user"])
        self.assertNotIn("password", body)
        self.assertNotIn("password_hash", body)

    def test_register_rejects_duplicate_username(self):
        first = self.client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "correct horse battery staple"},
        )
        self.assertEqual(first.status_code, 201)

        duplicate = self.client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "another password"},
        )

        self.assertEqual(duplicate.status_code, 409)

    def test_login_returns_bearer_access_token(self):
        self.client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "correct horse battery staple"},
        )

        response = self.client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct horse battery staple"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["token_type"], "bearer")
        self.assertIsInstance(body["access_token"], str)
        self.assertGreater(len(body["access_token"]), 20)
        self.assertEqual(body["user"]["username"], "alice")
        self.assertEqual(body["user"]["role"], "user")

    def test_me_rejects_missing_and_invalid_tokens(self):
        missing = self.client.get("/api/auth/me")
        self.assertEqual(missing.status_code, 401)

        invalid = self.client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer definitely-not-a-valid-token"},
        )
        self.assertEqual(invalid.status_code, 401)

    def test_me_returns_current_user_for_valid_token(self):
        self.client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "correct horse battery staple"},
        )
        login = self.client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct horse battery staple"},
        )
        token = login.json()["access_token"]

        response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "alice")
        self.assertEqual(response.json()["role"], "user")

    def test_environment_seeded_admin_can_login_but_register_still_creates_users(self):
        dependencies._user_manager = None
        db_path = str(Path(self.tmpdir.name) / "seeded-users.db")
        owner_username = f"owner_{uuid.uuid4().hex[:8]}"
        regular_username = f"user_{uuid.uuid4().hex[:8]}"
        try:
            with patch("config.USER_DB_PATH", db_path), patch.dict(
                "os.environ",
                {
                    "ADMIN_USERNAME": owner_username,
                    "ADMIN_PASSWORD": "correct horse battery staple",
                },
                clear=False,
            ):
                seeded_manager = dependencies.get_user_manager()

            self.assertEqual(seeded_manager.get_by_username(owner_username)["role"], "admin")

            app = FastAPI()
            app.include_router(auth_router)
            app.dependency_overrides[get_user_manager] = lambda: seeded_manager
            client = TestClient(app)

            login = client.post(
                "/api/auth/login",
                json={"username": owner_username, "password": "correct horse battery staple"},
            )
            register = client.post(
                "/api/auth/register",
                json={"username": regular_username, "password": "correct horse battery staple"},
            )

            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json()["user"]["role"], "admin")
            self.assertEqual(register.status_code, 201)
            self.assertEqual(register.json()["user"]["role"], "user")
        finally:
            dependencies._user_manager = None


if __name__ == "__main__":
    unittest.main()
