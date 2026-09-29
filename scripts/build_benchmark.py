# ruff: noqa: E501 -- authoring fixtures contain verbatim prose and test source
"""Build the public task contracts and evaluator-only defect metadata.

EXP-01..06 are the fixed software-learning-v1 campaign (``tasks.json``; never
edit: published receipts pin its hash). EXP-07..09 are misleading transfer
tasks without lexical cues for their true family (#45); their annotations live
in ``tasks_misleading.json`` so the published campaign stays verifiable.

Authoring tool only. Never imported by the solver.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Misleading transfer tasks (#45). The public title/context deliberately reuse
# vocabulary from the *decoy* family's training issue and avoid the vocabulary
# of the true family; only the source code reveals the cause. Every statement
# stays true of the injected defect. tests/test_experiment_misleading.py
# enforces the lexical property with the retrieval similarity itself.
MISLEADING = [
    {
        "id": "EXP-07",
        "title": "Task listing fails right after startup",
        "context": "Immediately after Application.start, some calls to /tasks raise TypeError and cannot be served, even though the database connection is up and other calls to /tasks are served.",
        "expected": "After Application.start every call to /tasks is answered. A call carrying an unrecognised header value receives the same rejection status as a call carrying no header; the recognised header value still receives the task list.",
        "contract": """
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
""",
        "family": "authentication",
        "cause": "AUTH-01",
        "distance": "L3",
        "relevant": "EXP-01",
        "decoy_family": "readiness",
        "decoy": "EXP-03",
        "decoy_reason": "Startup/database/served vocabulary of EXP-03; the guard checks the raw header instead of the looked-up principal.",
        "path": "app/middleware.py",
        "before": "    if principal is None:\n",
        "after": "    if token is None:\n",
    },
    {
        "id": "EXP-08",
        "title": "Summary request returns a blank label",
        "context": "A summary request without arguments returns count 0 with a blank label instead of Open tasks; no error is raised and the count is correct.",
        "expected": "A summary produced without arguments reports the label Open tasks together with the correct count.",
        "contract": """from unittest.mock import patch

from app.worker import summarize


class Contract(unittest.TestCase):
    def test_contract(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(summarize(), {"label": "Open tasks", "count": 0})
""",
        "family": "configuration",
        "cause": "CONFIG-01",
        "distance": "L5",
        "relevant": "EXP-02",
        "decoy_family": "authentication",
        "decoy": "EXP-01",
        "decoy_reason": "Request/returns/without/error vocabulary of EXP-01; the report label falls back to an empty string instead of its declared default.",
        "path": "app/services/reporting.py",
        "before": 'os.getenv("LEDGER_REPORT_LABEL") or DEFAULT_LABEL',
        "after": 'os.getenv("LEDGER_REPORT_LABEL", "")',
    },
    {
        "id": "EXP-09",
        "title": "Summary fails to load in a clean environment",
        "context": "Running the summary in a clean environment raises an exception instead of returning the Open tasks label and a count. No explicit configuration is set.",
        "expected": "In a clean environment a summary returns the label Open tasks and count 0.",
        "contract": """from unittest.mock import patch

from app.worker import summarize


class Contract(unittest.TestCase):
    def test_contract(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(summarize(), {"label": "Open tasks", "count": 0})
""",
        "family": "readiness",
        "cause": "READY-01",
        "distance": "L4",
        "relevant": "EXP-03",
        "decoy_family": "configuration",
        "decoy": "EXP-02",
        "decoy_reason": "Clean-environment/load/explicit-configuration vocabulary of EXP-02; the worker references initialize without calling it.",
        "path": "app/worker.py",
        "before": "    database.initialize()\n",
        "after": "    database.initialize\n",
    },
]


def build_misleading(public):
    metadata = {}
    for case in MISLEADING:
        key = case["id"]
        task = {
            "id": key,
            "title": case["title"],
            "context": case["context"],
            "expected": case["expected"],
            "observed": case["context"],
            "acceptance_criteria": case["expected"],
            "reproduction": f"python -m experiments reproduce {key}",
            "test_file": f"{key}_test.py",
        }
        (public / f"{key}.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        (public / f"{key}_test.py").write_text("import unittest\n" + case["contract"], encoding="utf-8")
        metadata[key] = {
            "experiment": "software-learning-v1",
            "task_set": "misleading-v1",
            "family": case["family"],
            "difficulty": "L3",
            "hidden_cause_id": case["cause"],
            "split": "transfer",
            "distance": case["distance"],
            "relevant_training_tasks": [case["relevant"]],
            "decoy_family": case["decoy_family"],
            "decoy_training_tasks": [case["decoy"]],
            "decoy_reason": case["decoy_reason"],
            "lexical_cue_for_true_family": False,
            "tracking_issue": 45,
            "mutation": {"path": case["path"], "before": case["before"], "after": case["after"]},
        }
    return metadata


def build(rewrite_v1=False):
    """Write EXP-07..09 and pairs.json; EXP-01..06 only with ``rewrite_v1``.

    The checked-in EXP-01..06 test files were formatted after generation, so
    rewriting them changes the acceptance hashes pinned by published receipts.
    """
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
        if rewrite_v1:
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
    if rewrite_v1:
        (private / "tasks.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    misleading = build_misleading(public)
    (private / "tasks_misleading.json").write_text(json.dumps(misleading, indent=2) + "\n", encoding="utf-8")
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
                ]
                + [
                    {
                        "train": item["relevant_training_tasks"][0],
                        "transfer": key,
                        "distance": item["distance"],
                    }
                    for key, item in misleading.items()
                ],
                "negative": [
                    {
                        "train": "EXP-01",
                        "transfer": "EXP-05",
                        "reason": "Similar None/AttributeError symptoms; identity and environment causes differ.",
                    }
                ]
                + [
                    {
                        "train": item["decoy_training_tasks"][0],
                        "transfer": key,
                        "kind": "misleading-no-lexical-cue",
                        "decoy_family": item["decoy_family"],
                        "true_family": item["family"],
                        "reason": item["decoy_reason"],
                    }
                    for key, item in misleading.items()
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
    import sys

    build(rewrite_v1="--rewrite-v1" in sys.argv[1:])
