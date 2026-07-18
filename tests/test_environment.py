import unittest
from pathlib import Path

from scripts import check_environment


BASE_DIR = Path(__file__).resolve().parents[1]


class EnvironmentLockTests(unittest.TestCase):
    def test_lock_contains_only_exact_unique_pins(self):
        pins = check_environment.read_lock()
        self.assertGreaterEqual(len(pins), 35)
        for required in (
            "fastapi",
            "uvicorn",
            "itsdangerous",
            "python-multipart",
            "pymupdf",
            "ebooklib",
            "trafilatura",
            "httpx",
        ):
            self.assertIn(required, pins)

    def test_current_runtime_matches_lock(self):
        self.assertEqual(check_environment.check_runtime(), [])

    def test_python_supported_range_is_explicit(self):
        self.assertIsNotNone(check_environment.python_version_error((3, 13, 10)))
        self.assertIsNone(check_environment.python_version_error((3, 13, 11)))
        self.assertIsNone(check_environment.python_version_error((3, 13, 99)))
        self.assertIsNotNone(check_environment.python_version_error((3, 14, 0)))

    def test_dependency_drift_reports_missing_and_wrong_versions(self):
        pins = {
            "fastapi": ("fastapi", "1.0"),
            "httpx": ("httpx", "2.0"),
        }
        errors = check_environment.dependency_errors(
            pins, installed={"fastapi": "0.9"}
        )
        self.assertEqual(
            errors,
            [
                "fastapi: instalado 0.9, esperado 1.0",
                "httpx: ausente (esperado 2.0)",
            ],
        )

    def test_dockerfile_pins_python_tag_and_digest(self):
        dockerfile = (BASE_DIR / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python:3.13.11-slim-bookworm@sha256:", dockerfile)
        self.assertIn("-r requirements.lock", dockerfile)
        dockerignore = (BASE_DIR / ".dockerignore").read_text(encoding="utf-8")
        for sensitive_path in ("data", "backups", "certs", ".env"):
            self.assertIn(sensitive_path, dockerignore)


if __name__ == "__main__":
    unittest.main()