from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class DocumentTypeBase(SQLModel):
    name: str = Field(unique=True)


class DocumentType(DocumentTypeBase, table=True):
    __tablename__ = "document_type"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )
    # Relaciones
    driver_documents: List["DriverDocuments"] = Relationship(
        back_populates="documenttype")


class DocumentTypeCreate(DocumentTypeBase):
    pass


class DocumentTypeUpdate(SQLModel):
    name: Optional[str] = None
