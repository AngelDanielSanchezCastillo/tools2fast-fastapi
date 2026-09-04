"""Filtros de consulta genericos reutilizables para listados paginados.

Provee un mini-DSL de filtros (igualdad exacta + sufijos), un constructor de
COUNT que reutiliza los WHERE filtrados y un helper que ejecuta las dos
consultas (total + items paginados) en una sola llamada.
"""

from typing import Any, TypeVar, cast

from fastapi import HTTPException
from sqlalchemy import Select, func
from sqlalchemy.engine import Row
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel.ext.asyncio.session import AsyncSession

ModelT = TypeVar("ModelT", bound=Any)

# Sufijos soportados por el DSL: <campo>__<sufijo>
_FILTER_SUFFIXES = ("__contains", "__in", "__gte", "__lte")


def _split_suffix(key: str) -> tuple[str, str]:
    """Separa el campo del sufijo DSL (ej. 'code__contains' -> ('code', '__contains'))."""
    for suffix in _FILTER_SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix):
            return key[: -len(suffix)], suffix
    return key, ""


def apply_filters(stmt: Select, model: type[ModelT], filters: dict) -> Select:
    """Aplica filtros con whitelist sobre el statement.

    Nombres planos = igualdad exacta (incluye booleanos y FKs). Sufijos:
    - ``__contains``: contiene el texto (LIKE %valor%).
    - ``__in``: pertenece a una lista de valores.
    - ``__gte`` / ``__lte``: mayor/igual o menor/igual.
    Los valores llegan tipados por FastAPI (no se coercionan aqui). Un campo
    fuera de la whitelist del modelo lanza HTTPException 422 en espanol.
    """
    whitelist = {column.name for column in cast(Any, model).__table__.columns}
    for key, value in filters.items():
        # Parametros opcionales no enviados (None) se ignoran
        if value is None:
            continue
        field, suffix = _split_suffix(key)
        if field not in whitelist:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Campo de filtro '{field}' no permitido para "
                    f"el modelo {model.__name__}."
                ),
            )
        column = getattr(model, field)
        column = cast(Any, column)
        if suffix == "__contains":
            stmt = stmt.where(column.contains(str(value)))
        elif suffix == "__in":
            stmt = stmt.where(column.in_(value))
        elif suffix == "__gte":
            stmt = stmt.where(column >= value)
        elif suffix == "__lte":
            stmt = stmt.where(column <= value)
        else:
            stmt = stmt.where(column == value)
    return stmt


def build_count(stmt: Select, model: type[ModelT]) -> Select:
    """Construye un ``select(func.count(model.id))`` con los WHERE filtrados.

    Reutiliza las condiciones WHERE y los FROM/JOIN del statement (necesario
    para statements base pre-construidos como el de latest-revision de
    cotizaciones) pero excluye offset/limit, order_by y group_by: el total
    siempre refleja el universo filtrado, no la pagina.
    """
    inner = stmt.order_by(None).group_by(None).offset(None).limit(None)
    return inner.with_only_columns(func.count(cast(Any, model).id))


def _scalar_count(result: Any) -> int:
    """Normaliza el valor del COUNT sin importar el tipo de statement.

    ``session.exec`` devuelve un escalar puro cuando el statement es un
    ``SelectOfScalar`` (sqlmodel.select) y un ``Row`` cuando es un ``Select``
    plano de SQLAlchemy. Ambos representan el mismo valor.
    """
    first = result.one()
    if isinstance(first, Row):
        return int(first[0])
    return int(first)


async def list_with_total(
    session: AsyncSession,
    stmt: Select,
    model: type[ModelT],
    filters: dict,
    skip: int = 0,
    limit: int = 50,
    order_by: ColumnElement | None = None,
) -> tuple[list, int]:
    """Ejecuta las dos consultas de un listado paginado: total + items.

    - ``count``: sin paginacion, reutilizando los mismos filtros (build_count).
    - ``items``: con offset/limit y un order_by opcional.

    Acepta un statement base pre-construido (p. ej. el de latest-revision de
    cotizaciones) al que se le aplican los filtros encima. Devuelve
    ``(items, total)`` donde total es el universo filtrado completo.
    """
    filtered = apply_filters(stmt, model, filters)
    count_stmt = build_count(filtered, model)

    total = _scalar_count(await session.exec(count_stmt))

    items_stmt = filtered.offset(skip).limit(limit)
    if order_by is not None:
        items_stmt = items_stmt.order_by(order_by)

    result = await session.exec(items_stmt)
    return list(result.all()), total