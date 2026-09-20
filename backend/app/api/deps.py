from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.services.app_context import AppContext


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def get_session(request: Request) -> Iterator[Session]:
    context: AppContext = request.app.state.context
    session = context.session_factory()
    try:
        yield session
    finally:
        session.close()
