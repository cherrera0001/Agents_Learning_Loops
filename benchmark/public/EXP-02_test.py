import unittest
from unittest.mock import patch

from app.config import title


class Contract(unittest.TestCase):
    def test_contract(self):
        for env, expected in (
            ({}, "Task Ledger"),
            ({"LEDGER_TITLE": ""}, "Task Ledger"),
            ({"LEDGER_TITLE": "Custom"}, "Custom"),
        ):
            with patch.dict("os.environ", env, clear=True):
                self.assertEqual(title(), expected)
