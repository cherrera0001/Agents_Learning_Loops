import sqlite3


class Database:
    def __init__(self):
        self.connection = None

    def initialize(self):
        if self.connection is None:
            self.connection = sqlite3.connect(":memory:")
            self.connection.execute(
                "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, done INTEGER NOT NULL)"
            )

    def execute(self, query, parameters=()):
        if self.connection is None:
            raise ConnectionError("database connection refused")
        return self.connection.execute(query, parameters)

    def close(self):
        if self.connection is not None:
            self.connection.close()
