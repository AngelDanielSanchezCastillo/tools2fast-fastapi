from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

ModelT = TypeVar("ModelT")

class DocumentSimpleRevisionService(Generic[ModelT]):
    """
    Servicio genérico para manejar documentos que tienen control de revisiones 
    (RevisionMixin y NumberMixin) pero NO tienen partidas (ítems) asociadas.
    
    Abstrae la creación, obtención, versionado y eliminación de la cabecera 
    de forma eficiente.
    """

    def __init__(self, model_class: type[ModelT]):
        self.model_class = model_class
        # Se excluyen los campos internos auto-generados típicamente por SQLAlchemy/Pydantic
        self._excluded_on_clone = {"id", "created_at", "updated_at"}

    # ═══════════════════════════════════════════════════════
    # LECTURA
    # ═══════════════════════════════════════════════════════

    async def get_latest_document(self, session: AsyncSession, number: int) -> ModelT:
        """Devuelve la revisión más reciente (mayor revision) de un documento."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.number == number)  # type: ignore
            .order_by(self.model_class.revision.desc())  # type: ignore
            .limit(1)
        )
        result = await session.exec(stmt)
        document = result.first()
        if not document:
            raise HTTPException(status_code=404, detail=f"Documento número {number} no encontrado.")
        return document

    async def list_latest_documents(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> list[ModelT]:
        """Devuelve únicamente la revisión más reciente de CADA documento."""
        subq = (
            select(
                self.model_class.number,  # type: ignore
                func.max(self.model_class.revision).label("max_rev"),  # type: ignore
            )
            .group_by(self.model_class.number)  # type: ignore
            .subquery()
        )
        stmt = (
            select(self.model_class)
            .join(
                subq,
                (self.model_class.number == subq.c.number)  # type: ignore
                & (self.model_class.revision == subq.c.max_rev),  # type: ignore
            )
            .order_by(self.model_class.number)  # type: ignore
            .offset(skip)
            .limit(limit)
        )
        result = await session.exec(stmt)
        return list(result.all())

    async def list_document_revisions(self, session: AsyncSession, number: int) -> list[ModelT]:
        """Lista todo el historial de revisiones de un documento específico."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.number == number)  # type: ignore
            .order_by(self.model_class.revision.desc())  # type: ignore
        )
        result = await session.exec(stmt)
        revisions = list(result.all())
        if not revisions:
            raise HTTPException(status_code=404, detail=f"Documento número {number} no encontrado.")
        return revisions

    # ═══════════════════════════════════════════════════════
    # ESCRITURA
    # ═══════════════════════════════════════════════════════

    async def create_document(self, session: AsyncSession, create_kwargs: dict[str, Any]) -> ModelT:
        """Crea un documento nuevo, inicializado siempre en la versión 1."""
        document = self.model_class(**create_kwargs, revision=1)
        session.add(document)
        await session.flush()
        return document

    async def revise_document(self, session: AsyncSession, number: int, changes: dict[str, Any]) -> ModelT:
        """
        Crea la nueva versión del documento preservando campos internos ocultos e inyectándole 
        los nuevos valores desde `changes`. Todo el historial previo queda intacto.
        """
        current_document = await self.get_latest_document(session, number)
        
        # Filtramos los campos prohibidos de la clonación
        field_values: dict[str, Any] = current_document.model_dump(exclude=self._excluded_on_clone) # type: ignore
        
        # Aplicamos inyección/overrides provenientes del Payload JSON y subimos +1 a la revisión
        field_values.update(changes)
        field_values["revision"] = getattr(current_document, "revision") + 1
        
        new_document = self.model_class(**field_values)
        session.add(new_document)
        await session.flush()
        
        return new_document

    async def delete_latest_revision(self, session: AsyncSession, number: int) -> None:
        """Elimina físicamente la revisión más reciente (Hard delete)."""
        latest = await self.get_latest_document(session, number)
        await session.delete(latest)
        await session.commit()
