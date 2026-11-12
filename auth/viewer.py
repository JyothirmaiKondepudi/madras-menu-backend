"""Who is making the current request, for response schemas that show different
data to different viewers (ProjectOut hides other clients from a client).

main.py's middleware stores the request here; get_current_user records the
user on request.state. Outside a request (scripts, a schema used directly)
there is no viewer, and schemas show everything."""

from contextvars import ContextVar, Token
from uuid import UUID

from starlette.requests import Request

_current_request: ContextVar[Request | None] = ContextVar("current_request", default=None)


def set_current_request(request: Request) -> Token:
    return _current_request.set(request)


def reset_current_request(token: Token) -> None:
    _current_request.reset(token)


def current_viewer() -> tuple[UUID, str] | None:
    """(user id, role) of the signed-in caller, or None if there isn't one."""
    request = _current_request.get()
    if request is None:
        return None
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "user_role", None)
    if user_id is None or role is None:
        return None
    return user_id, role
