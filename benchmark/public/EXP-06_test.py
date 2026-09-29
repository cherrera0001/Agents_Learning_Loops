import unittest

from app.worker import summarize


class Contract(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(summarize(), {"label": "Open tasks", "count": 0})
