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


if __name__ == "__main__":
    unittest.main()

