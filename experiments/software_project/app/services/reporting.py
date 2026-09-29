import os

DEFAULT_LABEL = "Open tasks"


def report(database):
    value = os.getenv("LEDGER_REPORT_LABEL") or DEFAULT_LABEL
    return {
        "label": value.strip(),
        "count": database.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
    }
