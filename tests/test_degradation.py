"""R5 regressions: optional services never block core local reading."""

import shutil
import time
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app import database, diagnostics, main, security, tts
from app.config import APP_VERSION, TransportSecurityConfig


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_ROOT = BASE_DIR / "data" / "test-degradation"


class DegradedApplicationTests(unittest.TestCase):
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
        self.client = TestClient(
            main.create_app(TransportSecurityConfig()),
            base_url="http://localhost",
        )

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

    def _csrf(self):
        return self.client.get("/security/csrf").json()["token"]

    def _login(self):
        response = self.client.post(
            "/users",
            headers={security.CSRF_HEADER: self._csrf()},
            json={"name": "Leitor", "password": "Frase-segura-2026"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_public_health_ignores_optional_services(self):
        with mock.patch.object(
            diagnostics, "_probe_json_service", side_effect=AssertionError("optional probe")
        ) as optional_probe:
            response = self.client.get("/system/health")
            anonymous_diagnostics = self.client.get("/system/diagnostics")
        optional_probe.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(anonymous_diagnostics.status_code, 401)
        self.assertEqual(
            response.json(),
            {"version": APP_VERSION, "status": "healthy", "database": "healthy"},
        )
        with mock.patch.object(
            main,
            "database_health",
            return_value={"status": "unavailable", "required": True, "message": "DB"},
        ):
            failed = self.client.get("/system/health")
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.json()["database"], "unavailable")

    def test_diagnostics_reports_degraded_while_library_stays_available(self):
        self._login()
        unavailable = {
            "status": "unavailable",
            "required": False,
            "message": "Serviço opcional indisponível.",
            "latency_ms": 1,
        }
        with mock.patch.object(
            diagnostics, "_probe_json_service", return_value=unavailable
        ):
            report = self.client.get("/system/diagnostics")
        self.assertEqual(report.status_code, 200, report.text)
        payload = report.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["components"]["database"]["status"], "healthy")
        self.assertEqual(payload["components"]["kokoro"]["status"], "unavailable")
        self.assertEqual(payload["components"]["ollama"]["status"], "unavailable")
        self.assertEqual(self.client.get("/documents").status_code, 200)

    def test_tts_unavailable_is_recoverable_and_does_not_break_library(self):
        self._login()
        status = {
            "voices": [],
            "available": False,
            "reason": "Servidor de narração local não está ativo.",
            "retry_after": 5,
        }
        with mock.patch.object(tts, "fetch_voice_status", return_value=status):
            voices = self.client.get("/tts/voices")
            started = time.monotonic()
            block = self.client.post(
                "/documents/999/tts/blocks",
                headers={security.CSRF_HEADER: self._csrf()},
                json={"token": 0, "voice": "pf_dora"},
            )
            elapsed = time.monotonic() - started
        self.assertEqual(voices.status_code, 200)
        self.assertFalse(voices.json()["available"])
        self.assertEqual(block.status_code, 503)
        self.assertEqual(block.headers["retry-after"], "5")
        self.assertLess(elapsed, 0.2)
        self.assertEqual(self.client.get("/documents").status_code, 200)


class DegradedServicePrimitiveTests(unittest.TestCase):
    def test_failed_voice_discovery_uses_negative_cache(self):
        with mock.patch.object(tts, "_voice_cache", []), mock.patch.object(
            tts, "_voice_cache_until", 0.0
        ), mock.patch.object(tts, "_voice_cache_available", None), mock.patch.object(
            tts, "_voice_cache_reason", None
        ), mock.patch.object(tts, "_voice_cache_retry_after", None), mock.patch.object(
            tts.httpx,
            "Client",
            side_effect=httpx.ConnectError("offline"),
        ) as client_factory:
            first = tts.fetch_voice_status(force=True)
            second = tts.fetch_voice_status()
        self.assertFalse(first["available"])
        self.assertEqual(second, first)
        self.assertEqual(client_factory.call_count, 1)

    def test_compose_and_frontend_keep_tts_optional(self):
        compose = (BASE_DIR / "docker-compose.yml").read_text(encoding="utf-8")
        app_section = compose.split("\n  tts:", 1)[0]
        self.assertNotIn("depends_on:", app_section)
        self.assertIn("scripts/container_healthcheck.py", app_section)

        javascript = (BASE_DIR / "static" / "js" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("await loadTtsVoices({ force: true })", javascript)
        self.assertIn("A leitura sem narrador continua disponível.", javascript)
        self.assertIn("ttsToggle.disabled = ttsAvailabilityChecking", javascript)


if __name__ == "__main__":
    unittest.main()