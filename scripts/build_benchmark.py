# ruff: noqa: E501 -- authoring fixtures contain verbatim prose and test source
"""Build six public task contracts and evaluator-only defect metadata.

Authoring tool only. Never imported by the solver.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    public = ROOT / "benchmark/public"
    private = ROOT / "benchmark/private"
    public.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    cases = [
        (
            "API returns 500 instead of 401",
            "A request to /profile without a token returns an internal error. The identity API works with demo-token.",
            "Requests without a token or with an unknown token return 401; valid identities return 200.",
            "app/auth.py",
            '    if user is None:\n        raise Unauthorized("authentication required")\n',
            "",
            "authentication",
            "AUTH-01",
            "L1",
            """from app.api import Application
class Contract(unittest.TestCase):
    def test_contract(self):
        app = Application()
        for token in (None, "unknown"):
            self.assertEqual(app.handle("/profile", token)[0], 401)
        self.assertEqual(app.handle("/profile", "demo-token")[0], 200)
""",
        ),
        (
            "Clean environment fails to load application title",
            "Starting the application health check in a clean environment raises AttributeError instead of returning a title. Explicit environment configuration works.",
            "Missing or empty LEDGER_TITLE uses Task Ledger. An explicit title is preserved.",
            "app/config.py",
            'os.getenv("LEDGER_TITLE") or DEFAULT_TITLE',
            'os.getenv("LEDGER_TITLE")',
            "configuration",
            "CONFIG-01",
            "L1",
            """from unittest.mock import patch
from app.config import title
class Contract(unittest.TestCase):
    def test_contract(self):
        for env, expected in (({}, "Task Ledger"), ({"LEDGER_TITLE": ""}, "Task Ledger"), ({"LEDGER_TITLE": "Custom"}, "Custom")):
            with patch.dict("os.environ", env, clear=True):
                self.assertEqual(title(), expected)
""",
        ),
        (
            "Health endpoint fails immediately after startup",
            "Application startup raises ConnectionError: database connection refused. The health endpoint cannot be served.",
            "Application.start completes and /health returns 200 with status ready.",
            "app/api.py",
            "        self.database.initialize()\n",
            "",
            "readiness",
            "READY-01",
            "L1",
            """from app.api import Application
class Contract(unittest.TestCase):
    def test_contract(self):
        app = Application()
        try:
            app.start()
            self.assertEqual(app.handle("/health")[0], 200)
        finally:
            app.database.close()
""",
        ),
        (
            "Middleware crashes before returning 401",
            "Requests to /tasks with an unknown identity fail with TypeError before the middleware can return 401. A valid token succeeds.",
            "Missing and unknown identities receive 401. A valid editor receives a task list.",
            "app/middleware.py",
            '    if principal is None:\n        raise Unauthorized("authentication required")\n',
            "",
            "authentication",
            "AUTH-01",
            "L3",
            """from app.api import Application
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
""",
        ),
        (
            "Report request raises AttributeError on None",
            "The report service raises AttributeError on a None value, resembling the earlier profile crash. This occurs only without explicit environment configuration; the database is available.",
            "Missing or empty LEDGER_REPORT_LABEL uses Open tasks. Configured labels are preserved and count is correct.",
            "app/services/reporting.py",
            'os.getenv("LEDGER_REPORT_LABEL") or DEFAULT_LABEL',
            'os.getenv("LEDGER_REPORT_LABEL")',
            "configuration",
            "CONFIG-01",
            "L5",
            """from unittest.mock import patch
from app.database import Database
from app.services.reporting import report
class Contract(unittest.TestCase):
    def test_contract(self):
        db = Database()
        db.initialize()
        try:
            for env, expected in (({}, "Open tasks"), ({"LEDGER_REPORT_LABEL": ""}, "Open tasks"), ({"LEDGER_REPORT_LABEL": "Mine"}, "Mine")):
                with patch.dict("os.environ", env, clear=True):
                    self.assertEqual(report(db), {"label": expected, "count": 0})
        finally:
            db.close()
""",
        ),
        (
            "Background summary fails before producing a report",
            "The background worker cannot produce its report: the report service fails when querying SQLite. Running the report on an already available database succeeds.",
            "A fresh background summary returns label Open tasks and count 0 without manual setup.",
            "app/worker.py",
            "    database.initialize()\n",
            "",
            "readiness",
            "READY-01",
            "L4",
            """from app.worker import summarize
class Contract(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(summarize(), {"label": "Open tasks", "count": 0})
""",
        ),
    ]
    metadata = {}
    for n, (
        title,
        context,
        expected,
        path,
        before,
        after,
        family,
        cause,
        distance,
        contract,
    ) in enumerate(cases, 1):
        key = f"EXP-{n:02d}"
        task = {
            "id": key,
            "title": title,
            "context": context,
            "expected": expected,
            "observed": context,
            "acceptance_criteria": expected,
            "reproduction": f"python -m experiments reproduce {key}",
            "test_file": f"{key}_test.py",
        }
        (public / f"{key}.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        (public / f"{key}_test.py").write_text("import unittest\n" + contract, encoding="utf-8")
        metadata[key] = {
            "experiment": "software-learning-v1",
            "family": family,
            "difficulty": "L2" if n < 4 else "L3",
            "hidden_cause_id": cause,
            "split": "train" if n < 4 else "transfer",
            "distance": distance,
            "relevant_training_tasks": [] if n < 4 else [f"EXP-{n - 3:02d}"],
            "mutation": {"path": path, "before": before, "after": after},
        }
    (private / "tasks.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (private / "pairs.json").write_text(
        json.dumps(
            {
                "positive": [
                    {
                        "train": f"EXP-{i:02d}",
                        "transfer": f"EXP-{i + 3:02d}",
                        "distance": d,
                    }
                    for i, d in enumerate(["L3", "L5", "L4"], 1)
                ],
                "negative": [
                    {
                        "train": "EXP-01",
                        "transfer": "EXP-05",
                        "reason": "Similar None/AttributeError symptoms; identity and environment causes differ.",
                    }
                ],
                "taxonomy": {
                    "L0": "EXACT",
                    "L1": "PARAPHRASE",
                    "L2": "SEMANTIC",
                    "L3": "CAUSAL",
                    "L4": "MULTI-HOP",
                    "L5": "TRANSFER",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
