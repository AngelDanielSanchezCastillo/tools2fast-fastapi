"""
Utilidades compartidas para los routers de tenant.
"""

import functools
import inspect
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fastapi.types import DecoratedCallable
from .. import APIResponse


def handle_exceptions(func: Callable) -> Callable:
    """
    Decorator que envuelve un endpoint (sync o async) y convierte cualquier
    excepción inesperada en una ``JSONResponse`` estándar usando
    ``APIResponse.from_exception``.

    - Soportar endpoints ``def`` (sync) además de ``async def``: sólo se hace
      ``await`` cuando el resultado es awaitable.
    - ``HTTPException`` se re-lanza tal cual para que FastAPI preserve su
      código de estado (401/403/404/...) en lugar de convertirlo en 500.

    Uso::

        @router.get("/items/")
        @handle_exceptions
        async def list_items(session: AsyncSession = Depends(get_tenant_session)):
            items = await service.list(session)
            return APIResponse.ok(items)
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result
        except HTTPException:
            raise
        except Exception as exc:
            error_response, http_status = APIResponse.from_exception(exc)
            return JSONResponse(status_code=http_status, content=error_response.model_dump())

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
