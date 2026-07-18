"""Regressões de segurança da R6."""

import hashlib
import io
import shutil
import socket
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app import database, extraction, main, security
from app.auth import PBKDF2_ITERATIONS, verify_password_details
from app.config import TransportSecurityConfig
from app.routers import tts_routes, users


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_ROOT = BASE_DIR / "data" / "test-security"


class SecurityApplicationTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TEST_ROOT / str(uuid4())
        self.root.mkdir()
        self.db_path = self.root / "data" / "app.db"
        self.secret_path = self.root / "data" / "secret_key"
        self.db_patch = mock.patch.object(database, "DB_PATH", self.db_path)
        self.secret_patch = mock.patch.object(main, "SECRET_KEY_PATH", self.secret_path)
        self.log_patch = mock.patch.object(main, "configure_security_logging")
        self.db_patch.start()
        self.secret_patch.start()
        self.log_patch.start()
        users.LOGIN_RATE_LIMITER = security.AuthenticationRateLimiter()
        self.app = main.create_app(TransportSecurityConfig())
        self.client = TestClient(self.app, base_url="http://localhost")

    def tearDown(self):
        self.client.close()
        self.log_patch.stop()
        self.secret_patch.stop()
        self.db_patch.stop()
        shutil.rmtree(self.root, ignore_errors=True)
        try:
            TEST_ROOT.rmdir()
        except OSError:
            pass

    def _csrf(self, client=None):
        active = client or self.client
        response = active.get("/security/csrf")
        self.assertEqual(response.status_code, 200)
        return response.json()["token"]

    def _create_user(self, name="Samuel", password="Frase-segura-2026"):
        return self.client.post(
            "/users",
            headers={security.CSRF_HEADER: self._csrf()},
            json={"name": name, "password": password},
        )

    def test_csrf_headers_host_and_production_surfaces(self):
        denied = self.client.post(
            "/users", json={"name": "Samuel", "password": "Frase-segura-2026"}
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.headers["x-csrf-required"], "1")

        hostile_host = self.client.get("/", headers={"Host": "evil.example"})
        self.assertEqual(hostile_host.status_code, 400)
        malformed_host = self.client.get("/", headers={"Host": "localhost/evil"})
        self.assertEqual(malformed_host.status_code, 400)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["cross-origin-opener-policy"], "same-origin")
        self.assertNotIn("access-control-allow-origin", response.headers)
        self.assertTrue(response.headers["x-request-id"])
        self.assertEqual(self.client.get("/docs").status_code, 404)
        self.assertEqual(self.client.get("/openapi.json").status_code, 404)

    def test_session_rotates_and_logout_invalidates_replay(self):
        created = self._create_user()
        self.assertEqual(created.status_code, 200, created.text)
        original_cookie = self.client.cookies.get("ll_session")
        self.assertTrue(original_cookie)

        relogin = self.client.post(
            "/login",
            headers={security.CSRF_HEADER: self._csrf()},
            json={"name": "Samuel", "password": "Frase-segura-2026"},
        )
        self.assertEqual(relogin.status_code, 200, relogin.text)
        rotated_cookie = self.client.cookies.get("ll_session")
        self.assertNotEqual(original_cookie, rotated_cookie)
        with TestClient(self.app, base_url="http://localhost") as old_replay:
            old_replay.cookies.set("ll_session", original_cookie)
            self.assertEqual(old_replay.get("/me").status_code, 401)

        logged_out = self.client.post(
            "/logout", headers={security.CSRF_HEADER: self._csrf()}
        )
        self.assertEqual(logged_out.status_code, 200)
        self.assertEqual(self.client.get("/me").status_code, 401)

        with TestClient(self.app, base_url="http://localhost") as replay:
            replay.cookies.set("ll_session", rotated_cookie)
            self.assertEqual(replay.get("/me").status_code, 401)

    def test_login_endpoint_rate_limits_repeated_failures(self):
        self.assertEqual(self._create_user().status_code, 200)
        self.client.post(
            "/logout", headers={security.CSRF_HEADER: self._csrf()}
        )
        token = self._csrf()
        for _ in range(5):
            response = self.client.post(
                "/login",
                headers={security.CSRF_HEADER: token},
                json={"name": "Samuel", "password": "senha-incorreta"},
            )
            self.assertEqual(response.status_code, 401)
        blocked = self.client.post(
            "/login",
            headers={security.CSRF_HEADER: token},
            json={"name": "Samuel", "password": "senha-incorreta"},
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertGreaterEqual(int(blocked.headers["retry-after"]), 1)

    def test_private_document_is_hidden_and_progress_get_is_read_only(self):
        self.assertEqual(self._create_user("Alice").status_code, 200)
        token = self._csrf()
        document = self.client.post(
            "/documents",
            headers={security.CSRF_HEADER: token},
            json={"title": "Privado", "raw_text": "uma duas três", "visibility": "private"},
        )
        self.assertEqual(document.status_code, 200, document.text)
        document_id = document.json()["id"]

        progress = self.client.get(f"/documents/{document_id}/progress")
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(progress.json()["status"], "quero_ler")
        conn = database.get_connection(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM reading_progress").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)

        self.client.post("/logout", headers={security.CSRF_HEADER: token})
        self.assertEqual(self._create_user("Bob", "Outra-frase-segura-2026").status_code, 200)
        self.assertEqual(self.client.get(f"/documents/{document_id}").status_code, 404)

    def test_unexpected_exception_returns_generic_request_id(self):
        @self.app.get("/_security-test/error")
        def explode():
            raise RuntimeError("segredo interno")

        with TestClient(
            self.app,
            base_url="http://localhost",
            raise_server_exceptions=False,
        ) as client:
            response = client.get("/_security-test/error")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Erro interno inesperado.")
        self.assertNotIn("segredo interno", response.text)
        self.assertEqual(response.json()["request_id"], response.headers["x-request-id"])


class SecurityPrimitiveTests(unittest.TestCase):
    def test_rate_limiter_blocks_and_expires_without_unbounded_keys(self):
        now = [100.0]
        limiter = security.AuthenticationRateLimiter(
            account_limit=3,
            ip_limit=20,
            window_seconds=60,
            block_seconds=120,
            max_buckets=4,
            clock=lambda: now[0],
        )
        for _ in range(3):
            limiter.failure("192.0.2.10", "alice")
        self.assertEqual(limiter.retry_after("192.0.2.10", "alice"), 120)
        self.assertEqual(limiter.retry_after("198.51.100.20", "alice"), 120)
        now[0] += 121
        self.assertEqual(limiter.retry_after("192.0.2.10", "alice"), 0)
        for index in range(10):
            limiter.failure(f"192.0.2.{index}", f"user-{index}")
        self.assertLessEqual(len(limiter._buckets), 4)

    def test_legacy_password_is_recognized_for_upgrade(self):
        password = "Frase-segura-2026"
        salt = bytes.fromhex("11" * 16)
        legacy = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        ).hex()
        valid, needs_upgrade = verify_password_details(password, salt.hex(), legacy)
        self.assertTrue(valid)
        self.assertTrue(needs_upgrade)

    def test_upload_requires_safe_name_mime_and_signature(self):
        with self.assertRaisesRegex(ValueError, "Nome"):
            extraction.validate_upload("../book.pdf", "application/pdf", b"%PDF-1.7")
        with self.assertRaisesRegex(ValueError, "assinatura"):
            extraction.validate_upload("book.pdf", "application/pdf", b"<html>")
        with self.assertRaisesRegex(ValueError, "binários"):
            extraction.validate_upload("book.txt", "text/plain", b"abc\x00def")

        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("../escape.xhtml", "texto")
        with self.assertRaisesRegex(ValueError, "caminho interno"):
            extraction.validate_upload(
                "book.epub", "application/epub+zip", payload.getvalue()
            )

    def test_url_validation_rejects_ssrf_credentials_ports_and_downgrade(self):
        for target in (
            "http://127.0.0.1/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data/",
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "redes locais"):
                    extraction._validated_url(target)
        with self.assertRaisesRegex(ValueError, "credenciais"):
            extraction._validated_url("https://user:pass@example.com/")
        with self.assertRaisesRegex(ValueError, "portas 80 e 443"):
            extraction._validated_url("https://example.com:8443/")
        with self.assertRaisesRegex(ValueError, "HTTPS para HTTP"):
            extraction._validated_url("http://example.com/", previous_scheme="https")

        public_dns = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ]
        with mock.patch("app.extraction.socket.getaddrinfo", return_value=public_dns):
            parsed, address, normalized = extraction._validated_url(
                "https://example.com/article#fragment"
            )
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(address, "93.184.216.34")
        self.assertEqual(normalized, "https://example.com/article")

    def test_invalid_remote_content_length_is_rejected(self):
        class FakeResponse:
            status = 200
            headers = {"Content-Length": "not-a-number"}

            def release_conn(self):
                pass

        class FakePool:
            def request(self, *args, **kwargs):
                return FakeResponse()

            def close(self):
                pass

        public_dns = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ]
        with (
            mock.patch("app.extraction.socket.getaddrinfo", return_value=public_dns),
            mock.patch(
                "app.extraction.urllib3.HTTPSConnectionPool", return_value=FakePool()
            ),
        ):
            with self.assertRaisesRegex(ValueError, "tamanho de resposta inválido"):
                extraction._fetch_once("https://example.com/")

    def test_container_contract_remains_least_privilege(self):
        dockerfile = (BASE_DIR / "Dockerfile").read_text(encoding="utf-8")
        compose = (BASE_DIR / "docker-compose.yml").read_text(encoding="utf-8")
        dependabot = (BASE_DIR / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("USER leitura", dockerfile)
        self.assertIn("${LEITURA_BIND_ADDRESS:-127.0.0.1}:8000:8000", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("cap_drop:", compose)
        self.assertIn("- ALL", compose)
        self.assertIn("package-ecosystem: pip", dependabot)
        self.assertIn("package-ecosystem: docker", dependabot)

    def test_tts_single_flight_lock_survives_a_waiting_request(self):
        key = (999, 0, "voice", "model")
        acquired = threading.Event()

        def waiter():
            with tts_routes._block_lock(key):
                acquired.set()

        with tts_routes._block_lock(key):
            worker = threading.Thread(target=waiter)
            worker.start()
            deadline = time.monotonic() + 2
            while tts_routes._lock_users.get(key, 0) < 2 and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(tts_routes._lock_users.get(key), 2)
            self.assertFalse(acquired.is_set())

        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(acquired.is_set())
        self.assertNotIn(key, tts_routes._locks)
        self.assertNotIn(key, tts_routes._lock_users)

    def test_tts_audio_path_cannot_escape_cache(self):
        self.assertIsNone(tts_routes._safe_audio_path("../secret_key"))
        self.assertIsNone(tts_routes._safe_audio_path("folder/audio.mp3"))
        self.assertIsNone(tts_routes._safe_audio_path("C:secret"))


if __name__ == "__main__":
    unittest.main()
