"""
Utilidades compartidas para los routers de tenant.
"""

import functools
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.types import DecoratedCallable
from .. import APIResponse


def handle_exceptions(func: Callable) -> Callable:
    """
    Decorator que envuelve un endpoint async y convierte cualquier excepción
    en una ``JSONResponse`` estándar usando ``APIResponse.from_exception``.

    Uso::

        @router.get("/items/")
        @handle_exceptions
        async def list_items(session: AsyncSession = Depends(get_tenant_session)):
            items = await service.list(session)
            return APIResponse.ok(items)
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> JSONResponse:
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            return APIResponse.from_exception(exc)

    return wrapper


class SafeRouter(APIRouter):
    """
    ``APIRouter`` que aplica ``handle_exceptions`` automáticamente a todos
    los endpoints registrados, sin necesidad de decorar cada función.

    Uso::

        router = SafeRouter(prefix="/tenant/quotations", tags=["Quotations"])

        @router.get("/items/")
        async def list_items(...):
            ...  # sin try/except, sin @handle_exceptions
    """

    def add_api_route(
        self, path: str, endpoint: DecoratedCallable, **kwargs: Any
    ) -> None:
        super().add_api_route(path, handle_exceptions(endpoint), **kwargs)
