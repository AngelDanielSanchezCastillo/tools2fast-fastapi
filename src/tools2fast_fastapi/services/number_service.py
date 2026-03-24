"""
NumberService — utilidades para manejar secuencias continuas de campos 'number'.

Provee funciones param obtener el siguiente número disponible en modelos que
hereden de NumberMixin. Al consultar el máximo actual en la base de datos
y sumar 1, garantizamos que si se borra el registro más reciente y se crea
uno nuevo, el nuevo tomará su lugar (max + 1).
"""

from typing import TypeVar

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T")


async def get_next_number(
    session: AsyncSession,
    model_class: type[T],
) -> int:
    """
    Devuelve el siguiente `number` disponible para un modelo con NumberMixin.
    Busca el valor máximo actual y le suma 1. Si no hay registros, inicia en 1.

    Args:
        session: Sesión async activa.
        model_class: Clase del modelo (debe tener el campo `number`).

    Returns:
        El siguiente número a utilizar (int).
    """
    stmt = select(func.max(model_class.number))  # type: ignore[attr-defined]
    result = await session.exec(stmt)
    max_number = result.first()
    
    return (max_number or 0) + 1
