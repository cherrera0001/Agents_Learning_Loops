import unittest
from unittest.mock import patch

from app.worker import summarize


class Contract(unittest.TestCase):
    def test_contract(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(summarize(), {"label": "Open tasks", "count": 0})
