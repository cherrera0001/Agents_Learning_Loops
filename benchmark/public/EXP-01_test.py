import unittest

from app.api import Application


class Contract(unittest.TestCase):
    def test_contract(self):
        app = Application()
        for token in (None, "unknown"):
            self.assertEqual(app.handle("/profile", token)[0], 401)
        self.assertEqual(app.handle("/profile", "demo-token")[0], 200)
