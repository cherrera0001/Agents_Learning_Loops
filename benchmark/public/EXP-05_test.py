import unittest
from unittest.mock import patch

from app.database import Database
from app.services.reporting import report


class Contract(unittest.TestCase):
    def test_contract(self):
        db = Database()
        db.initialize()
        try:
            for env, expected in (
                ({}, "Open tasks"),
                ({"LEDGER_REPORT_LABEL": ""}, "Open tasks"),
                ({"LEDGER_REPORT_LABEL": "Mine"}, "Mine"),
            ):
                with patch.dict("os.environ", env, clear=True):
                    self.assertEqual(report(db), {"label": expected, "count": 0})
        finally:
            db.close()
