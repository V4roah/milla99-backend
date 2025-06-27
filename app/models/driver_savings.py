from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING, ClassVar
from sqlalchemy import Column, String, event
from enum import Enum
from datetime import datetime
from sqlalchemy.orm import relationship
from uuid import UUID, uuid4
import pytz

if TYPE_CHECKING:
    from .user import User
    from .client_request import ClientRequest


class SavingsType(str, Enum):
    SAVING = "SAVING"
    APPROVED = "APPROVED"


class DriverSavings(SQLModel, table=True):
    __tablename__ = "driver_savings"
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    mount: Optional[int] = Field(default=0)
    user_id: UUID = Field(foreign_key="user.id")
    status: SavingsType = Field(default="SAVING")
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    # Relación con ClassVar
    user: Optional["User"] = Relationship(back_populates="driver_savings")


# Evento para before_insert - se ejecuta antes de crear un registro
COLOMBIA_TZ = pytz.timezone("America/Bogota")


@event.listens_for(DriverSavings, 'before_insert')
def set_created_at(mapper, connection, target):
    now = datetime.now(COLOMBIA_TZ)
    if target.created_at is None:
        target.created_at = now
    target.updated_at = now


# Evento para before_update - se ejecuta antes de actualizar un registro
@event.listens_for(DriverSavings, 'before_update')
def set_updated_at(mapper, connection, target):
    target.updated_at = datetime.now(COLOMBIA_TZ)
