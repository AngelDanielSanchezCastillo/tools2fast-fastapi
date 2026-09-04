"""Pruebas independientes del paquete tools2fast-fastapi: query_filters.

Validan:
  - apply_filters: DSL de filtros (igualdad exacta + sufijos __contains/__in/__gte/__lte),
    booleans/FKs como igualdad, whitelist por modelo y campo desconocido -> HTTP 422.
  - build_count: COUNT que reutiliza los WHERE filtrados y excluye offset/limit.
  - list_with_total: dos queries (count + items paginados), acepta statements base
    pre-construidos (caso cotizaciones => latest revision) y respeta el join.

Estas pruebas NO importan routers de Metal-ERP: son autocontenidas (pytest + aiosqlite)
y portables al repo de tools2fast-fastapi.
"""

from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import BigInteger, Column, Integer, func
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# PK BigInteger que, en SQLite (test), delega a Integer para conservar el
# autoincrement; en Postgres/SQLAlchemy mantiene BigInteger real.
BigIntPk = BigInteger().with_variant(Integer, "sqlite")

# Import del modulo en desarrollo: falla en RED porque query_filters no existe aun.
from tools2fast_fastapi.services.query_filters import (
    apply_filters,
    build_count,
    list_with_total,
)


class ProductFilterModel(SQLModel, table=True):
    """Modelo de prueba: replica columnas tipicas (familia/FK, stock, is_active)."""

    __tablename__ = "tf_query_filter_product"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigIntPk, primary_key=True, autoincrement=True),
    )
    code: str = Field(index=True)
    family_id: int | None = Field(default=None, index=True)
    stock: int = Field(default=0)
    is_active: bool = Field(default=True)


class FilterJoinModel(SQLModel, table=True):
    """Modelo auxiliar para probar counts con statements base que traen JOINs."""

    __tablename__ = "tf_query_filter_join"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigIntPk, primary_key=True, autoincrement=True),
    )
    product_id: int = Field(index=True)


@pytest_asyncio.fixture
async def db_engine() -> AsyncEngine:
    """Engine SQLite in-memory compartido (StaticPool) para las pruebas."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        # Solo creamos nuestras tablas; el metadata global puede contener otras.
        await conn.run_sync(
            SQLModel.metadata.create_all,
            tables=[ProductFilterModel.__table__, FilterJoinModel.__table__],
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(db_engine: AsyncEngine) -> AsyncSession:
    async with AsyncSession(db_engine, expire_on_commit=False) as s:
        yield s


async def _seed_products(session: AsyncSession, rows: list[dict]) -> list[int]:
    """Crea productos y devuelve sus IDs en orden de insercion."""
    ids: list[int] = []
    for data in rows:
        product = ProductFilterModel(**data)
        session.add(product)
        await session.flush()
        ids.append(int(product.id))
    await session.commit()
    return ids


async def _fetch_count(session: AsyncSession, stmt: Any) -> int:
    """Extrae el valor del COUNT sin importar si exec devuelve Row o escalar."""
    first = (await session.exec(stmt)).one()
    if isinstance(first, Row):
        return int(first[0])
    return int(first)


# ─────────────────────────────────────────────────────────────────────────────
# apply_filters
# ─────────────────────────────────────────────────────────────────────────────


async def test_apply_filters_exact_and_suffix_dsl(session: AsyncSession) -> None:
    """Igualdad exacta + __contains + __gte combinados filtran en AND."""
    ids = await _seed_products(
        session,
        [
            {"code": "A1-X", "family_id": 3, "stock": 10},  # cumple todo
            {"code": "A1-X", "family_id": 3, "stock": 2},  # stock < 5 -> afuera
            {"code": "B2-X", "family_id": 3, "stock": 10},  # code sin "A1" -> afuera
            {"code": "A1-X", "family_id": 4, "stock": 10},  # otra familia -> afuera
        ],
    )

    stmt = apply_filters(
        select(ProductFilterModel),
        ProductFilterModel,
        {"family_id": 3, "code__contains": "A1", "stock__gte": 5},
    )
    result = await session.exec(stmt)
    products = list(result.all())

    assert [p.id for p in products] == [ids[0]]
    assert products[0].code == "A1-X"
    assert products[0].stock == 10


async def test_apply_filters_in_and_lte(session: AsyncSession) -> None:
    """Sufijos __in y __lte generan IN (...) y <=."""
    ids = await _seed_products(
        session,
        [
            {"code": "P1", "family_id": 3, "stock": 4},  # in(3,4) y <=5
            {"code": "P2", "family_id": 4, "stock": 5},  # in(3,4) y <=5
            {"code": "P3", "family_id": 4, "stock": 9},  # stock muy alto -> afuera
            {"code": "P4", "family_id": 9, "stock": 1},  # familia fuera -> afuera
        ],
    )

    stmt = apply_filters(
        select(ProductFilterModel),
        ProductFilterModel,
        {"family_id__in": [3, 4], "stock__lte": 5},
    )
    result = await session.exec(stmt)
    products = list(result.all())

    assert sorted(p.id for p in products) == sorted(ids[:2])


async def test_apply_filters_boolean_and_fk_equality(session: AsyncSession) -> None:
    """Booleans y FK se tratan como igualdad exacta."""
    ids = await _seed_products(
        session,
        [
            {"code": "F4-A", "family_id": 4, "is_active": True},  # cumple
            {"code": "F4-B", "family_id": 4, "is_active": False},  # inactivo -> afuera
            {
                "code": "F9-A",
                "family_id": 9,
                "is_active": True,
            },  # otra familia -> afuera
        ],
    )

    stmt = apply_filters(
        select(ProductFilterModel),
        ProductFilterModel,
        {"is_active": True, "family_id": 4},
    )
    result = await session.exec(stmt)
    products = list(result.all())

    assert [p.id for p in products] == [ids[0]]


async def test_apply_filters_unknown_field_raises_422_spanish(
    session: AsyncSession,
) -> None:
    """Campo fuera de la whitelist -> HTTPException 422 con mensaje en espanol."""
    await _seed_products(session, [{"code": "X1", "family_id": 1, "stock": 1}])

    with pytest.raises(HTTPException) as excinfo:
        apply_filters(
            select(ProductFilterModel),
            ProductFilterModel,
            {"impostor_field": 1},
        )

    assert excinfo.value.status_code == 422
    assert "impostor_field" in str(excinfo.value.detail)


async def test_apply_filters_empty_filters_returns_all_rows(
    session: AsyncSession,
) -> None:
    """Sin filtros el statement queda intacto (todos los registros)."""
    ids = await _seed_products(
        session,
        [
            {"code": c, "family_id": 1, "stock": i}
            for i, c in enumerate(["A", "B", "C"])
        ],
    )

    stmt = apply_filters(select(ProductFilterModel), ProductFilterModel, {})
    result = await session.exec(stmt)
    products = list(result.all())

    assert sorted(p.id for p in products) == sorted(ids)


# ─────────────────────────────────────────────────────────────────────────────
# build_count
# ─────────────────────────────────────────────────────────────────────────────


async def test_build_count_ignores_paging(session: AsyncSession) -> None:
    """Count usa los WHERE filtrados pero ignora offset/limit."""
    await _seed_products(
        session,
        [{"code": f"F3-{i}", "family_id": 3, "stock": i} for i in range(25)]
        + [{"code": f"F4-{i}", "family_id": 4, "stock": i} for i in range(5)],
    )

    # Statement filtrado por familia 3 con paginacion aplicada
    filtered = select(ProductFilterModel).where(ProductFilterModel.family_id == 3)
    paged = filtered.offset(10).limit(10)
    count_stmt = build_count(paged, ProductFilterModel)

    assert (
        int(await _fetch_count(session, count_stmt)) == 25
    )  # no 10 (limit) ni 30 (sin filtro)


async def test_build_count_empty_filters_counts_dataset(session: AsyncSession) -> None:
    """Sin filtro, count = tamano total del dataset (aunque haya offset/limit)."""
    await _seed_products(
        session,
        [{"code": f"P-{i}", "family_id": 1, "stock": i} for i in range(60)],
    )

    paged = select(ProductFilterModel).offset(20).limit(10)
    count_stmt = build_count(paged, ProductFilterModel)

    assert int(await _fetch_count(session, count_stmt)) == 60


async def test_build_count_excludes_aggregate_columns(session: AsyncSession) -> None:
    """El count no incluye funciones agregadas del statement original."""
    await _seed_products(
        session,
        [{"code": f"P-{i}", "family_id": 1, "stock": i} for i in range(5)],
    )

    # Simula un statement con group_by (como el COUNT(DISTINCT number) de cotizaciones)
    grouped = select(
        ProductFilterModel.family_id, func.count(ProductFilterModel.id)
    ).group_by(ProductFilterModel.family_id)
    count_stmt = build_count(grouped, ProductFilterModel)

    assert (
        int(await _fetch_count(session, count_stmt)) == 5
    )  # filas base, no la agregacion


# ─────────────────────────────────────────────────────────────────────────────
# list_with_total
# ─────────────────────────────────────────────────────────────────────────────


async def test_list_with_total_filtered_across_pages(session: AsyncSession) -> None:
    """25 filas que matchean: skip=10/limit=10 => 10 items y total=25 (no page length)."""
    ids = await _seed_products(
        session,
        [{"code": f"F3-{i}", "family_id": 3, "stock": i} for i in range(25)]
        + [{"code": f"F4-{i}", "family_id": 4, "stock": i} for i in range(7)],
    )

    items, total = await list_with_total(
        session,
        select(ProductFilterModel),
        ProductFilterModel,
        {"family_id": 3},
        skip=10,
        limit=10,
        order_by=ProductFilterModel.id,
    )

    assert len(items) == 10
    assert total == 25
    # Pagina 2 (items 11..20): los 25 de la familia 3 son los primeros 25 ids
    assert [p.id for p in items] == ids[10:20]


async def test_list_with_total_empty_filters_and_bounds(session: AsyncSession) -> None:
    """Sin filtros: primeros N rows (skip=0, limit=50) y total = tamano del dataset."""
    ids = await _seed_products(
        session,
        [{"code": f"P-{i}", "family_id": 1, "stock": i} for i in range(80)],
    )

    items, total = await list_with_total(
        session,
        select(ProductFilterModel),
        ProductFilterModel,
        {},
        skip=0,
        limit=50,
        order_by=ProductFilterModel.id,
    )

    assert len(items) == 50
    assert total == 80
    assert [p.id for p in items] == ids[:50]


async def test_list_with_total_accepts_prebuilt_base_statement(
    session: AsyncSession,
) -> None:
    """Acepta un statement base pre-filtrado (caso cotizaciones latest-revision)."""
    await _seed_products(
        session,
        [
            {"code": f"F3H-{i}", "family_id": 3, "stock": 10} for i in range(8)
        ]  # cumple base (stock>=5) y filtro extra (familia 3)
        + [
            {"code": f"F3L-{i}", "family_id": 3, "stock": 1} for i in range(4)
        ]  # base lo excluye (stock<5)
        + [
            {"code": f"F4H-{i}", "family_id": 4, "stock": 10} for i in range(3)
        ],  # pasa base pero filtro extra (familia 3) lo excluye
    )

    base_stmt = select(ProductFilterModel).where(ProductFilterModel.stock >= 5)

    items, total = await list_with_total(
        session,
        base_stmt,
        ProductFilterModel,
        {"family_id": 3},
        skip=2,
        limit=4,
    )

    assert len(items) == 4  # paginacion respetada sobre el base + filtros
    assert total == 8  # solo los F3H: base (stock>=5) AND familia 3


async def test_list_with_total_preserves_join_in_count(session: AsyncSession) -> None:
    """El total de un statement base con JOIN cuenta SOLO las filas del join."""
    await _seed_products(
        session,
        [{"code": f"P-{i}", "family_id": 1, "stock": i} for i in range(3)],
    )
    # Solo los productos 1 y 2 tienen fila en el join
    session.add_all(
        [
            FilterJoinModel(product_id=1, id=1),
            FilterJoinModel(product_id=2, id=2),
        ]
    )
    await session.commit()

    base_stmt = select(ProductFilterModel).join(
        FilterJoinModel,
        FilterJoinModel.product_id == ProductFilterModel.id,
    )

    items, total = await list_with_total(
        session,
        base_stmt,
        ProductFilterModel,
        {},
        skip=0,
        limit=50,
    )

    assert total == 2  # el count NO debe ignorar el join (seria 3)
    assert sorted(int(p.id) for p in items) == [1, 2]
