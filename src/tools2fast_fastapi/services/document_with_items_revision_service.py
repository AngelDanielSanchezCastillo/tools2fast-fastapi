from typing import Any, Generic, TypeVar, Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

HeaderT = TypeVar("HeaderT")
ItemT = TypeVar("ItemT")

class DocumentWithItemsRevisionService(Generic[HeaderT, ItemT]):
    """
    Servicio genérico que fusiona la lógica de versionado (revision_service)
    y el manejo en bloque de documentos (document_service) en una sola clase 
    altamente optimizada.
    
    Abstrae la creación, obtención, versionado y clonación de partidas.
    """

    def __init__(
        self,
        header_model: type[HeaderT],
        item_model: type[ItemT],
        header_fk_field: str,
    ):
        self.header_model = header_model
        self.item_model = item_model
        self.header_fk_field = header_fk_field
        self._excluded_on_clone = {"id", "created_at", "updated_at"}

    # ═══════════════════════════════════════════════════════
    # LECTURA
    # ═══════════════════════════════════════════════════════

    async def get_latest_header(self, session: AsyncSession, number: int) -> HeaderT:
        """Devuelve la revisión más reciente (mayor revision) de un documento."""
        stmt = (
            select(self.header_model)
            .where(self.header_model.number == number)  # type: ignore
            .order_by(self.header_model.revision.desc())  # type: ignore
            .limit(1)
        )
        result = await session.exec(stmt)
        header = result.first()
        if not header:
            raise HTTPException(status_code=404, detail=f"Documento número {number} no encontrado.")
        return header

    async def get_document_with_items(self, session: AsyncSession, number: int) -> tuple[HeaderT, list[ItemT]]:
        """Devuelve la revisión más reciente junto con sus partidas."""
        header = await self.get_latest_header(session, number)
        items = await self.list_items_by_header(session, getattr(header, "id"))
        return header, items

    async def list_latest_headers(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> list[HeaderT]:
        """Devuelve únicamente la revisión más reciente de CADA documento."""
        subq = (
            select(
                self.header_model.number,  # type: ignore
                func.max(self.header_model.revision).label("max_rev"),  # type: ignore
            )
            .group_by(self.header_model.number)  # type: ignore
            .subquery()
        )
        stmt = (
            select(self.header_model)
            .join(
                subq,
                (self.header_model.number == subq.c.number)  # type: ignore
                & (self.header_model.revision == subq.c.max_rev),  # type: ignore
            )
            .order_by(self.header_model.number)  # type: ignore
            .offset(skip)
            .limit(limit)
        )
        result = await session.exec(stmt)
        return list(result.all())

    async def list_document_revisions(self, session: AsyncSession, number: int) -> list[HeaderT]:
        """Lista todo el historial de revisiones de un documento específico."""
        stmt = (
            select(self.header_model)
            .where(self.header_model.number == number)  # type: ignore
            .order_by(self.header_model.revision.desc())  # type: ignore
        )
        result = await session.exec(stmt)
        revisions = list(result.all())
        if not revisions:
            raise HTTPException(status_code=404, detail=f"Documento número {number} no encontrado.")
        return revisions

    async def list_items_by_header(self, session: AsyncSession, header_id: int) -> list[ItemT]:
        """Devuelve todas las partidas asociadas al ID de una cabecera."""
        fk_col = getattr(self.item_model, self.header_fk_field)
        stmt = select(self.item_model).where(fk_col == header_id)
        result = await session.exec(stmt)
        return list(result.all())

    # ═══════════════════════════════════════════════════════
    # ESCRITURA
    # ═══════════════════════════════════════════════════════

    async def create_document_with_items(
        self,
        session: AsyncSession,
        create_header_kwargs: dict[str, Any],
        create_items_kwargs_list: list[dict[str, Any]],
    ) -> tuple[HeaderT, list[ItemT]]:
        """
        Crea un documento (revisión 1) y sus partidas iniciales.
        """
        header = self.header_model(**create_header_kwargs, revision=1)
        session.add(header)
        await session.flush()

        items: list[ItemT] = []
        for item_kwargs in create_items_kwargs_list:
            item_kwargs[self.header_fk_field] = header.id  # type: ignore
            item = self.item_model(**item_kwargs)
            session.add(item)
            items.append(item)

        return header, items

    async def _create_revision_header(
        self, session: AsyncSession, current_header: HeaderT, changes: dict[str, Any]
    ) -> HeaderT:
        """Crea la nueva versión de la cabecera preservando campos internos."""
        field_values: dict[str, Any] = current_header.model_dump(exclude=self._excluded_on_clone) # type: ignore
        field_values.update(changes)
        field_values["revision"] = getattr(current_header, "revision") + 1
        
        new_header = self.header_model(**field_values)
        session.add(new_header)
        await session.flush()
        return new_header

    async def revise_document_with_items(
        self,
        session: AsyncSession,
        number: int,
        header_changes: dict[str, Any],
        new_items_datas: list[Any],
        extract_item_kwargs: Callable[[Any, int], tuple[int, dict[str, Any]]],
    ) -> tuple[HeaderT, list[ItemT]]:
        """
        Fusión eficiente: Crea la nueva revisión de la cabecera y aplica un 
        reemplazo total de ítems en una sola pasada.
        
        Soporta: Clona campos internos de ítems viejos, ignora eliminados y crea nuevos.
        """
        current_header = await self.get_latest_header(session, number)
        new_header = await self._create_revision_header(session, current_header, header_changes)
        
        # Obtener los ítems de la revisión anterior
        fk_col = getattr(self.item_model, self.header_fk_field)
        stmt = select(self.item_model).where(fk_col == getattr(current_header, "id"))
        result = await session.exec(stmt)
        old_items_by_num = {getattr(it, "number"): it for it in result.all()}
        
        new_items: list[ItemT] = []
        
        for i, item_data in enumerate(new_items_datas, start=1):
            num, kwargs = extract_item_kwargs(item_data, i)
            kwargs[self.header_fk_field] = getattr(new_header, "id")
            
            if num in old_items_by_num:
                # 1. ACTUALIZAR: Clonar el ítem anterior para preservar campos ocultos +OVERRIDES
                old_item = old_items_by_num[num]
                item_values: dict[str, Any] = old_item.model_dump(exclude=self._excluded_on_clone) # type: ignore
                item_values.update(kwargs)
                new_item = self.item_model(**item_values)
            else:
                # 2. CREAR: Es un ítem completamente nuevo
                kwargs["number"] = num
                new_item = self.item_model(**kwargs)
            
            # 3. BORRAR: Implícito. Si un ítem estaba en old_items pero el cliente
            #    no lo mandó en new_items_datas, el ciclo simplemente lo ignora.
            
            session.add(new_item)
            new_items.append(new_item)
            
        new_items.sort(key=lambda x: getattr(x, "number"))
        return new_header, new_items

    async def delete_latest_revision(self, session: AsyncSession, number: int) -> None:
        """Elimina físicamente la revisión más reciente (cabecera + ítems)."""
        latest = await self.get_latest_header(session, number)
        
        fk_col = getattr(self.item_model, self.header_fk_field)
        stmt = select(self.item_model).where(fk_col == getattr(latest, "id"))
        result = await session.exec(stmt)
        for item in result.all():
            await session.delete(item)

        await session.delete(latest)
        await session.commit()
