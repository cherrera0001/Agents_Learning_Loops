import json
from wsgiref.simple_server import make_server

from .auth import Unauthorized, profile
from .config import title
from .database import Database
from .middleware import authorize
from .services.tasks import create, list_tasks


class Application:
    def __init__(self):
        self.database = Database()

    def start(self):
        self.database.initialize()
        self.database.execute("SELECT 1")

    def handle(self, path, token=None, payload=None):
        try:
            if path == "/health":
                self.database.execute("SELECT 1")
                return 200, {"status": "ready", "title": title()}
            if path == "/profile":
                return 200, profile(token)
            if path == "/tasks":
                if not authorize(token):
                    return 403, {"error": "forbidden"}
                if payload is not None:
                    create(self.database, payload["title"])
                return 200, list_tasks(self.database)
            return 404, {"error": "not found"}
        except Unauthorized:
            return 401, {"error": "authentication required"}

    def __call__(self, environ, start_response):
        try:
            status, body = self.handle(environ["PATH_INFO"], environ.get("HTTP_AUTHORIZATION"))
        except Exception:
            status, body = 500, {"error": "internal server error"}
        labels = {
            200: "OK",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
        }
        start_response(f"{status} {labels[status]}", [("Content-Type", "application/json")])
        return [json.dumps(body).encode()]


if __name__ == "__main__":
    app = Application()
    app.start()
    with make_server("127.0.0.1", 8000, app) as server:
        server.serve_forever()
