import os

DEFAULT_TITLE = "Task Ledger"


def title():
    value = os.getenv("LEDGER_TITLE") or DEFAULT_TITLE
    return value.strip()
