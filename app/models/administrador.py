from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class Administrador(SQLModel, table=True):
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    email: str = Field(index=True, unique=True, nullable=False)
    password: str = Field(nullable=False)
    role: int = Field(nullable=False, default=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )
