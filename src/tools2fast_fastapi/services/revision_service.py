"""
RevisionService — utilidades genéricas de versionado.

Compatible con CUALQUIER modelo que herede RevisionMixin.

Flujo:
  - La "revisión actual" es siempre la de mayor `revision`.
  - Crear una nueva revisión no toca el registro anterior (solo clona con revision+1).
  - Eliminar la revisión más reciente restaura automáticamente la anterior como vigente.

Casos de uso:
  Caso 1 — Solo versionado de cabecera:
      new_record = await create_revision(session, current, changes)

  Caso 2 — Versionado de cabecera con ítems:
      new_header = await create_revision(session, current_header, changes)
      new_items  = await clone_children(
          session, ChildModel, "parent_fk_field",
          old_parent=current_header, new_parent=new_header,
      )
"""

from typing import Any, TypeVar

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T")

# Campos que nunca se copian al clonar (los genera la BD o el ORM automáticamente)
_EXCLUDED_ON_CLONE = {"id", "created_at", "updated_at"}


# ─────────────────────────────────────────────────────────────
# Lectura genérica
# ─────────────────────────────────────────────────────────────


async def get_latest_revision(
    session: AsyncSession,
    model_class: type[T],
    number: int,
) -> T | None:
    """
    Devuelve el registro con la revisión más alta para un `number` dado.
    Compatible con cualquier modelo que tenga RevisionMixin.
    """
    stmt = (
        select(model_class)
        .where(model_class.number == number)  # type: ignore[attr-defined]
        .order_by(model_class.revision.desc())  # type: ignore[attr-defined]
        .limit(1)
    )
    result = await session.exec(stmt)
    return result.first()


async def list_revisions(
    session: AsyncSession,
    model_class: type[T],
    number: int,
) -> list[T]:
    """
    Lista todas las revisiones de un registro por su `number`, de mayor a menor revisión.
    Compatible con cualquier modelo que tenga RevisionMixin.
    """
    stmt = (
        select(model_class)
        .where(model_class.number == number)  # type: ignore[attr-defined]
        .order_by(model_class.revision.desc())  # type: ignore[attr-defined]
    )
    result = await session.exec(stmt)
    return list(result.all())


# ─────────────────────────────────────────────────────────────
# Escritura genérica
# ─────────────────────────────────────────────────────────────


async def create_revision(
    session: AsyncSession,
    current: T,
    changes: dict[str, Any] | None = None,
) -> T:
    """
    Crea una nueva revisión de cualquier modelo con RevisionMixin.

    Clona todos los campos del registro actual, aplica `changes` y sube `revision` en 1.
    El registro anterior queda intacto — la nueva revisión es la vigente por tener mayor número.

    Args:
        session: Sesión async activa.
        current: Registro actual (cualquier modelo con RevisionMixin).
        changes: Campos a cambiar en la nueva revisión. Si es None, clona sin cambios.

    Returns:
        La nueva instancia creada (ya con flush aplicado, id disponible).
    """
    changes = changes or {}
    model_class: type[T] = type(current)

    # Clonar todos los campos del registro actual, excluyendo los auto-generados
    field_values: dict[str, Any] = current.model_dump(exclude=_EXCLUDED_ON_CLONE)

    # Aplicar cambios y subir revisión
    field_values.update(changes)
    field_values["revision"] = current.revision + 1  # type: ignore[attr-defined]

    new_record = model_class(**field_values)
    session.add(new_record)
    await session.flush()  # Obtener id antes de que el caller use new_record.id
    return new_record


async def clone_children(
    session: AsyncSession,
    item_model: type[T],
    parent_fk_field: str,
    old_parent: Any,
    new_parent: Any,
    overrides: dict[int, dict[str, Any]] | None = None,
) -> list[T]:
    """
    Clona todos los registros hijo de `old_parent` hacia `new_parent`.

    Funciona con cualquier modelo de ítems, sin importar sus campos específicos.
    Usa model_dump() para copiar genéricamente y luego reasigna el FK al nuevo padre.

    Args:
        session: Sesión async activa.
        item_model: Clase del modelo hijo (e.g. QuotationItem, OrderItem).
        parent_fk_field: Nombre del campo FK al padre (e.g. "quotation_header_id").
        old_parent: Instancia del padre anterior (se extrae .id internamente).
        new_parent: Instancia del nuevo padre (se extrae .id internamente).
        overrides: Cambios a aplicar a ítems específicos { item.number -> {campo: valor} }.

    Returns:
        Lista de nuevos ítems creados (pendientes de commit).
    """
    overrides = overrides or {}

    # Filtrar ítems del padre anterior por su FK
    fk_col = getattr(item_model, parent_fk_field)
    stmt = select(item_model).where(fk_col == old_parent.id)
    result = await session.exec(stmt)
    old_items = list(result.all())

    new_items: list[T] = []
    for item in old_items:
        # Clonar todos los campos excepto los auto-generados
        item_values: dict[str, Any] = item.model_dump(exclude=_EXCLUDED_ON_CLONE)

        # Aplicar overrides específicos del ítem (buscado por número)
        item_number = item_values.get("number")
        if item_number in overrides:
            item_values.update(overrides[item_number])

        # Reasignar FK al nuevo padre
        item_values[parent_fk_field] = new_parent.id

        new_item = item_model(**item_values)
        session.add(new_item)
        new_items.append(new_item)

    return new_items
