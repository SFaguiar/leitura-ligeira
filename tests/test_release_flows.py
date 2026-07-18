"""Integrated release journeys across API, SQLite, restart, and TTS cache."""

import shutil
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app import database, main, security, tts
from app.config import TransportSecurityConfig
from app.routers import import_routes, tts_routes, users


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_ROOT = BASE_DIR / "data" / "test-release-flows"
PASSWORD = "Frase-segura-Release-2026"


class ReleaseFlowTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TEST_ROOT / str(uuid4())
        self.root.mkdir()
        self.db_path = self.root / "data" / "app.db"
        self.secret_path = self.root / "data" / "secret_key"
        self.tts_dir = self.root / "data" / "tts"
        self.db_patch = mock.patch.object(database, "DB_PATH", self.db_path)
        self.secret_patch = mock.patch.object(main, "SECRET_KEY_PATH", self.secret_path)
        self.tts_dir_patch = mock.patch.object(tts_routes, "TTS_DIR", self.tts_dir)
        self.log_patch = mock.patch.object(main, "configure_security_logging")
        self.db_patch.start()
        self.secret_patch.start()
        self.tts_dir_patch.start()
        self.log_patch.start()
        users.LOGIN_RATE_LIMITER = security.AuthenticationRateLimiter()
        self.client = self._new_client()

    def tearDown(self):
        self.client.close()
        self.log_patch.stop()
        self.tts_dir_patch.stop()
        self.secret_patch.stop()
        self.db_patch.stop()
        shutil.rmtree(self.root, ignore_errors=True)
        try:
            TEST_ROOT.rmdir()
        except OSError:
            pass

    def _new_client(self):
        return TestClient(
            main.create_app(TransportSecurityConfig()),
            base_url="http://localhost",
        )

    def _csrf(self):
        response = self.client.get("/security/csrf")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    def _mutate(self, method: str, path: str, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers[security.CSRF_HEADER] = self._csrf()
        return self.client.request(method, path, headers=headers, **kwargs)

    def _create_user(self, name="Leitor Release"):
        response = self._mutate(
            "POST",
            "/users",
            json={"name": name, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _login(self, name="Leitor Release"):
        response = self._mutate(
            "POST",
            "/login",
            json={"name": name, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _create_document(self, title: str, text: str):
        response = self._mutate(
            "POST",
            "/documents",
            json={"title": title, "raw_text": text, "visibility": "house"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _save_progress(self, document_id: int, **payload):
        response = self._mutate(
            "PUT",
            f"/documents/{document_id}/progress",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_library_import_search_collections_and_all_shelves(self):
        self._create_user()
        statuses = ["quero_ler", "lendo", "lido", "abandonado"]
        documents = []
        for index, status in enumerate(statuses):
            document = self._create_document(
                f"Prateleira {status}",
                f"conteúdo exclusivo {status} marcador-{index}",
            )
            self._save_progress(document["id"], position=0, status=status)
            documents.append(document)

        uploaded = self._mutate(
            "POST",
            "/documents/upload",
            data={"title": "Upload Safira", "visibility": "house"},
            files={"file": ("safira.txt", b"safira azul texto importado", "text/plain")},
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        uploaded_doc = uploaded.json()
        self.assertEqual(uploaded_doc["source_type"], "upload")

        with mock.patch.object(
            import_routes,
            "extract_url",
            return_value=("conteúdo remoto âmbar validado", "Página Âmbar"),
        ):
            imported_url = self._mutate(
                "POST",
                "/documents/url",
                json={"url": "https://example.com/leitura", "title": "", "visibility": "house"},
            )
        self.assertEqual(imported_url.status_code, 200, imported_url.text)
        self.assertEqual(imported_url.json()["source_type"], "url")

        patched = self._mutate(
            "PATCH",
            f"/documents/{uploaded_doc['id']}",
            json={"collection": "Clássicos Locais"},
        )
        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertEqual(patched.json()["collection"], "Clássicos Locais")

        search = self.client.get("/documents", params={"q": "safira azul"})
        self.assertEqual(search.status_code, 200, search.text)
        self.assertEqual([item["id"] for item in search.json()], [uploaded_doc["id"]])

        summaries = self.client.get("/documents").json()
        by_id = {item["id"]: item for item in summaries}
        for document, status in zip(documents, statuses, strict=True):
            self.assertEqual(by_id[document["id"]]["progress_status"], status)
        self.assertEqual(by_id[uploaded_doc["id"]]["collection"], "Clássicos Locais")
        abandoned = documents[-1]
        self.assertEqual(
            self.client.get(f"/documents/{abandoned['id']}/progress").json()["status"],
            "abandonado",
        )

    def test_focus_flow_dashboard_skins_and_opt_out(self):
        self._create_user()
        document = self._create_document(
            "Sessões Foco e Fluxo",
            " ".join(f"palavra-{index}" for index in range(120)),
        )
        focus = self._mutate(
            "POST",
            "/sessions",
            json={"document_id": document["id"], "mode": "focus", "start_pointer": 0},
        ).json()["session_id"]
        focus_update = self._mutate(
            "PATCH",
            f"/sessions/{focus}",
            json={"end_pointer": 30, "position": 30, "ended_at": True, "avg_wpm": 600},
        )
        self.assertEqual(focus_update.status_code, 200, focus_update.text)

        flow = self._mutate(
            "POST",
            "/sessions",
            json={"document_id": document["id"], "mode": "flow", "start_pointer": 30},
        ).json()["session_id"]
        flow_update = self._mutate(
            "PATCH",
            f"/sessions/{flow}",
            json={"end_pointer": 80, "position": 80, "ended_at": True, "avg_wpm": 800},
        )
        self.assertEqual(flow_update.status_code, 200, flow_update.text)
        self._save_progress(document["id"], position=80, status="lido")

        settings = self._mutate(
            "PUT",
            "/me/settings",
            json={"skin": "odysseus"},
        )
        self.assertEqual(settings.status_code, 200, settings.text)
        self.assertEqual(settings.json()["skin"], "odysseus")

        dashboard = self.client.get("/stats/dashboard", params={"scope": "me", "days": 30})
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        payload = dashboard.json()
        self.assertEqual(payload["summary"]["sessions"], 2)
        self.assertEqual({item["mode"] for item in payload["modes"]}, {"focus", "flow"})
        self.assertEqual(payload["summary"]["completed_documents"], 1)

        disabled = self._mutate(
            "PUT",
            "/me/settings",
            json={"collect_stats": False, "skin": "library"},
        )
        self.assertFalse(disabled.json()["collect_stats"])
        self.assertEqual(disabled.json()["skin"], "library")
        opted_out_session = self._mutate(
            "POST",
            "/sessions",
            json={"document_id": document["id"], "mode": "focus", "start_pointer": 80},
        )
        self.assertEqual(opted_out_session.status_code, 200, opted_out_session.text)
        self.assertIsNone(opted_out_session.json()["session_id"])
        self.assertFalse(self.client.get("/stats/dashboard").json()["collecting"])

    def test_restart_during_reading_preserves_progress_and_logout_revokes(self):
        self._create_user()
        first = self._create_document("Antes do reinício", "um dois três quatro cinco seis")
        second = self._create_document("Depois do reinício", "sete oito nove dez onze doze")
        session_id = self._mutate(
            "POST",
            "/sessions",
            json={"document_id": first["id"], "mode": "focus", "start_pointer": 0},
        ).json()["session_id"]
        heartbeat = self._mutate(
            "PATCH",
            f"/sessions/{session_id}",
            json={"end_pointer": 4, "position": 4, "ended_at": False, "avg_wpm": 480},
        )
        self.assertEqual(heartbeat.status_code, 200, heartbeat.text)

        self.client.close()
        self.client = self._new_client()
        self._login()
        resumed = self.client.get(f"/documents/{first['id']}/progress")
        self.assertEqual(resumed.status_code, 200, resumed.text)
        self.assertEqual(resumed.json()["position"], 4)
        switched = self._mutate(
            "POST",
            "/sessions",
            json={"document_id": second["id"], "mode": "flow", "start_pointer": 0},
        )
        self.assertIsNotNone(switched.json()["session_id"])

        logout = self._mutate("POST", "/logout")
        self.assertEqual(logout.status_code, 200, logout.text)
        self.assertEqual(self.client.get("/me").status_code, 401)

        self.client.close()
        self.client = self._new_client()
        self._login()
        persisted = self.client.get("/documents").json()
        self.assertEqual({item["id"] for item in persisted}, {first["id"], second["id"]})

    def test_tts_generation_is_idempotent_and_audio_remains_authenticated(self):
        self._create_user()
        words = [f"token{index}" for index in range(300)]
        document = self._create_document("TTS release", " ".join(words))
        audio = b"ID3-release-gate-audio"
        kokoro_words = [
            {"word": word, "start": index * 0.01, "end": (index + 1) * 0.01}
            for index, word in enumerate(words[:250])
        ]
        voice_status = {
            "voices": ["pf_dora"],
            "available": True,
            "reason": None,
            "retry_after": None,
        }
        with mock.patch.object(
            tts, "fetch_voice_status", return_value=voice_status
        ), mock.patch.object(
            tts, "call_kokoro", return_value=(audio, kokoro_words)
        ) as generator:
            first = self._mutate(
                "POST",
                f"/documents/{document['id']}/tts/blocks",
                json={"token": 0, "voice": "pf_dora"},
            )
            second = self._mutate(
                "POST",
                f"/documents/{document['id']}/tts/blocks",
                json={"token": 100, "voice": "pf_dora"},
            )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        generator.assert_called_once()
        fetched_audio = self.client.get(first.json()["audio_url"])
        self.assertEqual(fetched_audio.status_code, 200)
        self.assertEqual(fetched_audio.content, audio)
        self._mutate("POST", "/logout")
        self.assertEqual(self.client.get(first.json()["audio_url"]).status_code, 401)


if __name__ == "__main__":
    unittest.main()