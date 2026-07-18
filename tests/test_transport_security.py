import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.config import TransportSecurityConfig
from app.main import create_app
from scripts import run_server


class TransportConfigTests(unittest.TestCase):
    def test_environment_flags_are_strict(self):
        config = TransportSecurityConfig.from_env(
            {"LEITURA_HTTPS": "yes", "LEITURA_LAN_ENABLED": "0"}
        )
        self.assertTrue(config.https_enabled)
        self.assertFalse(config.lan_enabled)
        with self.assertRaises(RuntimeError):
            TransportSecurityConfig.from_env({"LEITURA_HTTPS": "talvez"})

    def test_secure_cookie_follows_https_mode(self):
        secure_app = create_app(TransportSecurityConfig(https_enabled=True))
        session = next(
            item for item in secure_app.user_middleware if item.cls is SessionMiddleware
        )
        self.assertTrue(session.kwargs["https_only"])
        self.assertEqual(session.kwargs["same_site"], "lax")

        @secure_app.get("/_test/session-cookie")
        def set_test_session(request: Request):
            request.session["test"] = True
            return {"ok": True}

        with TestClient(secure_app, base_url="https://reader.local") as client:
            response = client.get("/_test/session-cookie")
        cookie = response.headers["set-cookie"]
        self.assertIn("httponly", cookie.lower())
        self.assertIn("samesite=lax", cookie.lower())
        self.assertIn("secure", cookie.lower())

    def test_transport_endpoint_and_security_headers(self):
        local_app = create_app(TransportSecurityConfig(lan_enabled=True))
        with TestClient(local_app, base_url="http://reader.local") as client:
            response = client.get("/system/transport")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scheme"], "http")
        self.assertTrue(response.json()["lan_enabled"])
        self.assertIsNotNone(response.json()["warning"])
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")


class ServerRunnerTests(unittest.TestCase):
    def test_default_server_is_loopback_http(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            run_server.uvicorn, "run"
        ) as uvicorn_run, patch.object(
            run_server, "_find_existing_server", return_value=None
        ), patch.object(run_server, "_port_is_available", return_value=True):
            exit_code = run_server.main(["--port", "8765", "--no-https"])
        self.assertEqual(exit_code, 0)
        kwargs = uvicorn_run.call_args.kwargs
        self.assertEqual(kwargs["host"], "127.0.0.1")
        self.assertEqual(kwargs["port"], 8765)
        self.assertIsNone(kwargs["ssl_certfile"])
        self.assertFalse(kwargs["proxy_headers"])
        self.assertFalse(kwargs["server_header"])
        self.assertFalse(kwargs["date_header"])

    def test_wildcard_host_requires_explicit_lan(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            run_server.uvicorn, "run"
        ) as uvicorn_run:
            exit_code = run_server.main(["--host", "0.0.0.0", "--no-https"])
        self.assertEqual(exit_code, 2)
        uvicorn_run.assert_not_called()


    def test_specific_network_host_also_requires_explicit_lan(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            run_server.uvicorn, "run"
        ) as uvicorn_run:
            exit_code = run_server.main(["--host", "192.168.1.50", "--no-https"])
        self.assertEqual(exit_code, 2)
        uvicorn_run.assert_not_called()

    def test_incomplete_certificate_pair_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "certificado e chave"):
            run_server._validate_certificate_pair(Path("cert.pem"), None)



    def test_existing_matching_instance_exits_successfully(self):
        existing = run_server.ExistingServer(
            url="https://127.0.0.1:8000",
            https_enabled=True,
            lan_enabled=False,
        )
        with patch.object(
            run_server,
            "_validate_certificate_pair",
            return_value=(Path("cert.pem"), Path("key.pem")),
        ), patch.object(
            run_server, "_find_existing_server", return_value=existing
        ), patch.object(run_server.uvicorn, "run") as uvicorn_run:
            exit_code = run_server.main([])
        self.assertEqual(exit_code, 0)
        uvicorn_run.assert_not_called()

    def test_foreign_service_on_port_is_reported_before_uvicorn(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            run_server, "_find_existing_server", return_value=None
        ), patch.object(
            run_server, "_port_is_available", return_value=False
        ), patch.object(run_server.uvicorn, "run") as uvicorn_run:
            exit_code = run_server.main(["--port", "8000", "--no-https"])
        self.assertEqual(exit_code, 2)
        uvicorn_run.assert_not_called()

    def test_existing_instance_with_different_mode_requires_restart(self):
        existing = run_server.ExistingServer(
            url="http://127.0.0.1:8000",
            https_enabled=False,
            lan_enabled=False,
        )
        with patch.object(
            run_server,
            "_validate_certificate_pair",
            return_value=(Path("cert.pem"), Path("key.pem")),
        ), patch.object(
            run_server, "_find_existing_server", return_value=existing
        ), patch.object(run_server.uvicorn, "run") as uvicorn_run:
            exit_code = run_server.main([])
        self.assertEqual(exit_code, 2)
        uvicorn_run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
