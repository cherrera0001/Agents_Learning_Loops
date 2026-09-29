import unittest

from app.api import Application


class BusinessTests(unittest.TestCase):
    def test_create_and_list(self):
        app = Application()
        app.database.initialize()
        try:
            code, tasks = app.handle("/tasks", "demo-token", {"title": " ship "})
            self.assertEqual(code, 200)
            self.assertEqual(tasks, [{"id": 1, "title": "ship", "done": False}])
            with self.assertRaises(ValueError):
                app.handle("/tasks", "demo-token", {"title": " "})
            self.assertEqual(app.handle("/profile", "demo-token"), (200, {"name": "Ada"}))
        finally:
            app.database.close()
