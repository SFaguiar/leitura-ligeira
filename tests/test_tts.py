import base64
import json
import unittest
from unittest.mock import patch

from app import tts


class CaptionedStreamRegressionTests(unittest.TestCase):
    def test_missing_timestamps_do_not_discard_generated_audio(self):
        lines = [
            json.dumps(
                {
                    "audio": base64.b64encode(b"first").decode("ascii"),
                    "timestamps": [
                        {"word": "Olá", "start_time": 0.0, "end_time": 0.4}
                    ],
                }
            ),
            json.dumps(
                {
                    "audio": base64.b64encode(b"second").decode("ascii"),
                    "timestamps": None,
                }
            ),
        ]

        audio, words = tts.decode_captioned_lines(lines)

        self.assertEqual(audio, b"firstsecond")
        self.assertEqual(words, [{"word": "Olá", "start": 0.0, "end": 0.4}])

    def test_malformed_base64_is_rejected(self):
        line = json.dumps({"audio": "%%%", "timestamps": []})
        with self.assertRaises(tts.KokoroProtocolError):
            tts.decode_captioned_lines([line])

    @patch("app.tts.httpx.Client")
    @patch("app.tts._audio_only_speech", return_value=b"fallback-audio")
    @patch(
        "app.tts._captioned_speech",
        side_effect=tts.KokoroProtocolError("timestamps ausentes"),
    )
    def test_caption_failure_uses_stable_audio_fallback(
        self, captioned, audio_only, client_factory
    ):
        client_factory.return_value.__enter__.return_value = object()

        audio, words = tts.call_kokoro("Olá mundo.", "pf_dora")

        self.assertEqual(audio, b"fallback-audio")
        self.assertEqual(words, [])
        captioned.assert_called_once()
        audio_only.assert_called_once()


class TtsInputHardeningTests(unittest.TestCase):
    def test_control_characters_are_removed_and_whitespace_is_bounded(self):
        self.assertEqual(
            tts.sanitize_tts_text("  Olá\x00\x07\n\t mundo  "),
            "Olá mundo",
        )

    def test_oversized_text_is_rejected(self):
        with self.assertRaises(ValueError):
            tts.sanitize_tts_text("a" * (tts.MAX_INPUT_CHARS + 1))


if __name__ == "__main__":
    unittest.main()
