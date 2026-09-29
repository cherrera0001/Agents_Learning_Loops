from .database import Database
from .services.reporting import report


def summarize():
    database = Database()
    database.initialize()
    try:
        return report(database)
    finally:
        database.close()
