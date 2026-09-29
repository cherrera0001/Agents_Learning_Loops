import unittest

from app.api import Application


class Contract(unittest.TestCase):
    def test_contract(self):
        app = Application()
        app.database.initialize()
        try:
            for token in (None, "unknown"):
                self.assertEqual(app.handle("/tasks", token)[0], 401)
            self.assertEqual(app.handle("/tasks", "demo-token"), (200, []))
        finally:
            app.database.close()
