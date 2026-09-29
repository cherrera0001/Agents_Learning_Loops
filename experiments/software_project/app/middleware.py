from .auth import USERS, Unauthorized


def authorize(token):
    principal = USERS.get(token)
    if principal is None:
        raise Unauthorized("authentication required")
    return principal["role"] == "editor"
