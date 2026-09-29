class Unauthorized(Exception):
    pass


USERS = {"demo-token": {"name": "Ada", "role": "editor"}}


def profile(token):
    user = USERS.get(token)
    if user is None:
        raise Unauthorized("authentication required")
    return {"name": user.get("name")}
