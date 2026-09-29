import unittest

from app.api import Application


class Contract(unittest.TestCase):
    def test_contract(self):
        app = Application()
        app.start()
        try:
            rejected = app.handle("/tasks")[0]
            self.assertEqual(rejected, 401)
            self.assertEqual(app.handle("/tasks", "guest")[0], rejected)
            self.assertEqual(app.handle("/tasks", "demo-token"), (200, []))
        finally:
            app.database.close()
