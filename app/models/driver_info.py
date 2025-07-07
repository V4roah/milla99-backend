from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String
from typing import Optional, TYPE_CHECKING, List
from datetime import date, datetime
from uuid import UUID, uuid4
import pytz

if TYPE_CHECKING:
    from .user import User
    from .vehicle_info import VehicleInfo
    from .driver_documents import DriverDocuments
    from .client_request import ClientRequest


class DriverInfoBase(SQLModel):
    first_name: str
    last_name: str
    birth_date: date
    email: Optional[str] = None
    # selfie_url: Optional[str] = None  # Eliminado, ahora está en User


class DriverInfo(DriverInfoBase, table=True):
    __tablename__ = "driver_info"
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    user_id: UUID = Field(foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="driver_info")
    vehicle_info: Optional["VehicleInfo"] = Relationship(
        back_populates="driver_info")
    documents: List["DriverDocuments"] = Relationship(
        back_populates="driver_info")

    # Campos para gestión de solicitudes pendientes
    pending_request_id: Optional[UUID] = Field(
        default=None,
        foreign_key="client_request.id",
        description="ID de la solicitud pendiente aceptada por el conductor"
    )
    pending_request_accepted_at: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora cuando el conductor aceptó la solicitud pendiente"
    )

    # Relación con la solicitud pendiente
    pending_request: Optional["ClientRequest"] = Relationship(
        back_populates="driver_pending_request"
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(
        pytz.timezone("America/Bogota")), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("America/Bogota")),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(
            pytz.timezone("America/Bogota"))}
    )


class DriverInfoCreate(DriverInfoBase):
    pass


class DriverInfoUpdate(SQLModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    # selfie_url: Optional[str] = None  # Eliminado
    pending_request_id: Optional[UUID] = None
    pending_request_accepted_at: Optional[datetime] = None
