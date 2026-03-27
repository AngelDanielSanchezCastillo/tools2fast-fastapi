"""
TransactionService

Servicio genérico que centraliza el manejo de transacciones de base de datos
(commit / rollback automático).

Para el manejo de respuestas HTTP usa :class:`~tenant.schemas.response_schema.APIResponse`.
"""

from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T")


class TransactionService:
    """Servicio genérico de transacciones para routers FastAPI."""

    @staticmethod
    async def run(
        session: AsyncSession,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        """Ejecuta ``operation`` y confirma la transacción.

        Si ``operation`` lanza una excepción se hace rollback automático y se
        re-lanza el error para que el llamador lo maneje con
        :meth:`~tenant.schemas.response_schema.APIResponse.from_exception`.

        Args:
            session:   Sesión asíncrona de SQLModel / SQLAlchemy.
            operation: Coroutine factory sin argumentos que realiza las
                       operaciones de base de datos deseadas.

        Returns:
            El valor que devuelva ``operation``.

        Raises:
            Exception: La misma excepción lanzada dentro de ``operation``
                       tras ejecutar el rollback.

        Example::

            from tenant.schemas.response_schema import APIResponse
            from tenant.services import TransactionService

            @router.post("/")
            async def create(data: MySchema, session: AsyncSession = Depends(...)):
                try:
                    result = await TransactionService.run(
                        session,
                        lambda: my_db_function(session, data),
                    )
                    return APIResponse.created(result)
                except Exception as exc:
                    return APIResponse.from_exception(exc)
        """
        try:
            result = await operation()
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
