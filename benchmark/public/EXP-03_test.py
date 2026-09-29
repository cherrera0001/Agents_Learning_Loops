import unittest

from app.api import Application


class Contract(unittest.TestCase):
    def test_contract(self):
        app = Application()
        try:
            app.start()
            self.assertEqual(app.handle("/health")[0], 200)
        finally:
            app.database.close()
