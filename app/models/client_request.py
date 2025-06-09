from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Enum, event, String
import enum
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import Field as PydanticField  # Renombrar para evitar conflictos
from geoalchemy2 import Geometry
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import inspect

# Modelo de entrada (lo que el usuario envía)


class ClientRequestCreate(SQLModel):
    fare_offered: Optional[float] = None
    fare_assigned: Optional[float] = None
    pickup_description: Optional[str] = None
    destination_description: Optional[str] = None
    client_rating: Optional[float] = None
    driver_rating: Optional[float] = None
    pickup_lat: float
    pickup_lng: float
    destination_lat: float
    destination_lng: float
    type_service_id: int
    payment_method_id: Optional[int] = Field(
        # Nuevo campo con valor por defecto
        default=1, description="ID del método de pago (1=cash, 2=nequi, 3=daviplata). Por defecto es 1 (cash)")


class StatusEnum(str, enum.Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    ON_THE_WAY = "ON_THE_WAY"
    ARRIVED = "ARRIVED"
    TRAVELLING = "TRAVELLING"
    FINISHED = "FINISHED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


# Función para generar UUID


# Modelo de base de datos
class ClientRequest(SQLModel, table=True):
    __tablename__ = "client_request"

    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    id_client: UUID = Field(foreign_key="user.id")
    id_driver_assigned: Optional[UUID] = Field(
        default=None, foreign_key="user.id")
    type_service_id: int = Field(
        foreign_key="type_service.id")  # Nueva relación
    payment_method_id: Optional[int] = Field(
        default=None, foreign_key="payment_method.id")  # Nuevo campo
    fare_offered: Optional[float] = Field(default=None)
    fare_assigned: Optional[float] = Field(default=None)
    penality: Optional[float] = Field(default=0, nullable=True)  # Nuevo campo
    pickup_description: Optional[str] = Field(default=None, max_length=255)
    destination_description: Optional[str] = Field(
        default=None, max_length=255)
    review: Optional[str] = Field(default=None, max_length=255)  # Nuevo campo
    client_rating: Optional[float] = Field(default=None)
    driver_rating: Optional[float] = Field(default=None)
    status: StatusEnum = Field(
        default=StatusEnum.CREATED,
        sa_column=Column(Enum(StatusEnum))
    )

    pickup_position: Optional[object] = Field(
        sa_column=Column(Geometry(geometry_type="POINT", srid=4326)))
    destination_position: Optional[object] = Field(
        sa_column=Column(Geometry(geometry_type="POINT", srid=4326)))
    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relaciones explícitas
    client: Optional["User"] = Relationship(
        back_populates="client_requests",
        sa_relationship_kwargs={"foreign_keys": "[ClientRequest.id_client]"}
    )
    driver_assigned: Optional["User"] = Relationship(
        back_populates="assigned_requests",
        sa_relationship_kwargs={
            "foreign_keys": "[ClientRequest.id_driver_assigned]"}
    )
    transactions: List["Transaction"] = Relationship(
        back_populates="client_request")
    company_accounts: List["CompanyAccount"] = Relationship(
        back_populates="client_request")

    type_service: "TypeService" = Relationship(
        back_populates="client_requests")  # Nueva relación
    payment_method: Optional["PaymentMethod"] = Relationship(
        back_populates="client_requests")  # Nueva relación
    # Nueva relación con PenalityUser
    penalities: List["PenalityUser"] = Relationship(
        back_populates="client_request",
        sa_relationship_kwargs={"foreign_keys": "PenalityUser.id_client_request"}
    )

# Definir el listener para el evento after_update
def after_update_listener(mapper, connection, target):
    from app.services.earnings_service import distribute_earnings  # Import aquí, no arriba
    # Obtener el estado del objeto para verificar cambios
    state = inspect(target)
    attr = state.attrs.status
    # Verificar si el status cambió y si el nuevo valor es PAID
    if attr.history.has_changes():
        old_value = attr.history.deleted[0] if attr.history.deleted else None
        new_value = attr.value
        if new_value == StatusEnum.PAID and old_value != StatusEnum.PAID:
            session = Session(bind=connection)
            try:
                distribute_earnings(session, target)
            except Exception as e:
                print(f"Error en distribute_earnings: {e}")
                raise


# Registrar el evento después de definir la clase
event.listen(ClientRequest, 'after_update', after_update_listener)
