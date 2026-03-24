"""
Tests genéricos para RevisionMixin y NumberMixin.

Utiliza una base de datos SQLite en memoria (configurada en conftest.py) para
validar el funcionamiento agnóstico y genérico del versionado de documentos.

Ejecutar con:
    uv run --group test pytest tests/test_revision_service.py -v
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlmodel import Field, SQLModel
from tools2fast_fastapi.models.mixins import NumberMixin, RevisionMixin
from tools2fast_fastapi.services.revision_service import (
    clone_children,
    create_revision,
    get_latest_revision,
    list_revisions,
)


class DocumentHeader(RevisionMixin, SQLModel, table=True):
    """Modelo dummy de Header para pruebas"""

    __tablename__ = "test_document_headers"
    id: int | None = Field(default=None, primary_key=True)
    client_id: int
    currency_id: int


class DocumentItem(NumberMixin, SQLModel, table=True):
    """Modelo dummy de Item para pruebas"""

    __tablename__ = "test_document_items"
    id: int | None = Field(default=None, primary_key=True)
    document_header_id: int = Field(index=True)
    material_id: int | None = None
    quantity: float
    unit_price: float | None = None


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


async def _create_header(session: AsyncSession, number: int = 1001) -> DocumentHeader:
    """Crea un DocumentHeader de revisión 1."""
    header = DocumentHeader(
        number=number,
        client_id=1,
        currency_id=1,
        revision=1,
    )
    session.add(header)
    await session.flush()
    return header


async def _add_item(
    session: AsyncSession,
    header_id: int,
    number: int = 1,
    material_id: int = 10,
    qty: float = 5.0,
    price: float = 100.0,
) -> DocumentItem:
    """Agrega una partida a un header."""
    item = DocumentItem(
        document_header_id=header_id,
        number=number,
        material_id=material_id,
        quantity=qty,
        unit_price=price,
    )
    session.add(item)
    await session.flush()
    return item


# ─────────────────────────────────────────────────────────────
# Tests: RevisionMixin
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_header_default_revision(session: AsyncSession):
    """Un header nuevo debe tener revision=1."""
    header = await _create_header(session)
    await session.commit()
    await session.refresh(header)

    assert header.revision == 1


@pytest.mark.asyncio
async def test_item_links_to_header(session: AsyncSession):
    """Una partida nueva debe estar vinculada a su header correctamente."""
    header = await _create_header(session)
    item = await _add_item(session, header.id, number=1, qty=7.0)
    await session.commit()
    await session.refresh(item)

    assert item.document_header_id == header.id
    assert item.quantity == 7.0


# ─────────────────────────────────────────────────────────────
# Tests: create_revision (genérico)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_revision_increments(session: AsyncSession):
    """create_revision debe incrementar revision en 1."""
    header = await _create_header(session)
    await session.commit()

    new_header = await create_revision(session, header)
    await session.commit()

    assert new_header.revision == 2


@pytest.mark.asyncio
async def test_create_revision_old_record_unchanged(session: AsyncSession):
    """El registro original debe quedar intacto con revision=1."""
    header = await _create_header(session)
    original_id = header.id
    await session.commit()

    await create_revision(session, header)
    await session.commit()

    old = await session.get(DocumentHeader, original_id)
    assert old is not None
    assert old.revision == 1


@pytest.mark.asyncio
async def test_create_revision_applies_changes(session: AsyncSession):
    """Los cambios deben reflejarse en la nueva revisión."""
    header = await _create_header(session)
    await session.commit()

    new_header = await create_revision(session, header, {"client_id": 99})
    await session.commit()

    assert new_header.client_id == 99
    assert new_header.number == header.number  # El number no cambia


@pytest.mark.asyncio
async def test_create_revision_same_type(session: AsyncSession):
    """create_revision debe devolver el mismo tipo que el original."""
    header = await _create_header(session)
    await session.commit()

    new_header = await create_revision(session, header)
    await session.commit()

    assert type(new_header) is DocumentHeader


# ─────────────────────────────────────────────────────────────
# Tests: clone_children (genérico)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clone_children_copies_all_items(session: AsyncSession):
    """clone_children debe crear copias de todos los ítems en el nuevo padre."""
    header = await _create_header(session)
    await _add_item(session, header.id, number=1)
    await _add_item(session, header.id, number=2, material_id=20)

    new_header = await _create_header(session, number=1002)
    await session.commit()

    new_items = await clone_children(
        session, DocumentItem, "document_header_id",
        old_parent=header, new_parent=new_header,
    )
    await session.commit()

    assert len(new_items) == 2
    assert all(it.document_header_id == new_header.id for it in new_items)


@pytest.mark.asyncio
async def test_clone_children_applies_override(session: AsyncSession):
    """El override debe modificar únicamente el ítem indicado."""
    header = await _create_header(session)
    await _add_item(session, header.id, number=1, qty=5.0)
    await _add_item(session, header.id, number=2, qty=10.0)

    new_header = await _create_header(session, number=1002)
    await session.commit()

    new_items = await clone_children(
        session, DocumentItem, "document_header_id",
        old_parent=header, new_parent=new_header,
        overrides={1: {"quantity": 99.0}},
    )
    await session.commit()

    item_1 = next(it for it in new_items if it.number == 1)
    item_2 = next(it for it in new_items if it.number == 2)

    assert item_1.quantity == 99.0  # Modificado
    assert item_2.quantity == 10.0  # Intacto


# ─────────────────────────────────────────────────────────────
# Tests: get_latest_revision y list_revisions
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_latest_revision(session: AsyncSession):
    """get_latest_revision debe devolver la revisión más alta."""
    header = await _create_header(session, number=2001)
    await session.commit()

    rev2 = await create_revision(session, header)
    await session.commit()

    latest = await get_latest_revision(session, DocumentHeader, 2001)
    assert latest is not None
    assert latest.revision == 2
    assert latest.id == rev2.id


@pytest.mark.asyncio
async def test_list_revisions_returns_all_ordered(session: AsyncSession):
    """list_revisions debe devolver todas las revisiones en orden descendente."""
    header = await _create_header(session, number=3001)
    await session.commit()

    rev2 = await create_revision(session, header)
    await session.commit()

    await create_revision(session, rev2)
    await session.commit()

    revisions = await list_revisions(session, DocumentHeader, 3001)
    assert len(revisions) == 3
    assert revisions[0].revision == 3
    assert revisions[1].revision == 2
    assert revisions[2].revision == 1


# ─────────────────────────────────────────────────────────────
# Tests: flujo completo cabecera + ítems (Caso 2)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_revision_with_items_creates_new_header(session: AsyncSession):
    """Crear una revisión con ítems debe generar un nuevo header con revision=2."""
    header = await _create_header(session, number=4001)
    await _add_item(session, header.id, number=1, qty=5.0)
    await _add_item(session, header.id, number=2, qty=3.0)
    await session.commit()

    new_header = await create_revision(session, header)
    await clone_children(
        session, DocumentItem, "document_header_id",
        old_parent=header, new_parent=new_header,
        overrides={1: {"quantity": 20.0}},
    )
    await session.commit()

    assert new_header.revision == 2
    assert new_header.number == 4001

    # Header original intacto
    old = await session.get(DocumentHeader, header.id)
    assert old.revision == 1


@pytest.mark.asyncio
async def test_full_revision_override_applies_to_correct_item(session: AsyncSession):
    """Solo el ítem con override debe cambiar; los demás quedan iguales."""
    header = await _create_header(session, number=5001)
    await _add_item(session, header.id, number=1, qty=5.0, price=100.0)
    await _add_item(session, header.id, number=2, qty=3.0, price=200.0)
    await session.commit()

    new_header = await create_revision(session, header)
    new_items = await clone_children(
        session, DocumentItem, "document_header_id",
        old_parent=header, new_parent=new_header,
        overrides={2: {"unit_price": 999.0}},
    )
    await session.commit()

    item_1 = next(it for it in new_items if it.number == 1)
    item_2 = next(it for it in new_items if it.number == 2)

    assert item_1.unit_price == 100.0   # Sin cambio
    assert item_2.unit_price == 999.0   # Modificado


@pytest.mark.asyncio
async def test_full_revision_preserves_item_count(session: AsyncSession):
    """La nueva revisión debe tener el mismo número de ítems que la anterior."""
    header = await _create_header(session, number=6001)
    for i in range(1, 5):
        await _add_item(session, header.id, number=i)
    await session.commit()

    new_header = await create_revision(session, header)
    new_items = await clone_children(
        session, DocumentItem, "document_header_id",
        old_parent=header, new_parent=new_header,
    )
    await session.commit()

    assert len(new_items) == 4
