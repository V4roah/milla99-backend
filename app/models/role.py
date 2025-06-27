from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from app.models.user_has_roles import UserHasRole
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class Role(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True, max_length=36)
    name: str = Field(index=True, max_length=36, unique=True)
    route: str = Field(max_length=255)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )
    # Relaciones
    users: List["User"] = Relationship(
        back_populates="roles", link_model=UserHasRole)
