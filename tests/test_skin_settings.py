import unittest

from pydantic import ValidationError

from app import database
from app.schemas import UserSettingsUpdate


class SkinSettingsTests(unittest.TestCase):
    def test_skin_schema_accepts_only_known_skins(self):
        self.assertEqual(UserSettingsUpdate(skin="library").skin, "library")
        self.assertEqual(UserSettingsUpdate(skin="odysseus").skin, "odysseus")
        with self.assertRaises(ValidationError):
            UserSettingsUpdate(skin="unknown")

    def test_existing_database_receives_library_skin_default(self):
        migrations = dict(database.USER_SETTINGS_MIGRATIONS)
        self.assertIn("skin", migrations)
        self.assertIn("DEFAULT 'library'", migrations["skin"])
        self.assertIn("skin TEXT NOT NULL DEFAULT 'library'", database.SCHEMA)

    def test_neurodiversity_settings_are_bounded_and_profile_safe(self):
        settings = UserSettingsUpdate(
            reader_font="opendyslexic",
            bionic_reading=True,
            zen_mode=True,
            low_stimulation=True,
            reader_column="narrow",
            reader_line_height=2.2,
            reader_letter_spacing=0.12,
            reader_word_spacing=0.3,
            reading_guide=True,
            orp_guide=True,
            flow_auto_follow=False,
        )
        self.assertEqual(settings.reader_font, "opendyslexic")
        self.assertTrue(settings.bionic_reading)
        self.assertEqual(settings.reader_column, "narrow")
        self.assertEqual(settings.reader_line_height, 2.2)
        self.assertFalse(settings.flow_auto_follow)
        for invalid in (
            {"reader_font": "remote-font"},
            {"reader_column": "extra-wide"},
            {"reader_line_height": 2.5},
            {"reader_letter_spacing": 0.17},
            {"reader_word_spacing": 0.41},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                UserSettingsUpdate(**invalid)

    def test_existing_database_receives_neurodiversity_defaults(self):
        migrations = dict(database.USER_SETTINGS_MIGRATIONS)
        expected = {
            "reader_font": "DEFAULT 'system'",
            "bionic_reading": "DEFAULT 0",
            "zen_mode": "DEFAULT 0",
            "low_stimulation": "DEFAULT 0",
            "reader_column": "DEFAULT 'comfortable'",
            "reader_line_height": "DEFAULT 1.9",
            "reader_letter_spacing": "DEFAULT 0",
            "reader_word_spacing": "DEFAULT 0",
            "reading_guide": "DEFAULT 0",
            "orp_guide": "DEFAULT 0",
            "flow_auto_follow": "DEFAULT 1",
        }
        for column, default in expected.items():
            self.assertIn(column, migrations)
            self.assertIn(default, migrations[column])
            self.assertIn(column, database.SCHEMA)


if __name__ == "__main__":
    unittest.main()

