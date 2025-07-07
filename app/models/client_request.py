from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Enum, event, String
from app.models.chat_message import ChatMessage
import enum
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import Field as PydanticField  # Renombrar para evitar conflictos
from geoalchemy2 import Geometry
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import inspect
import pytz

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
    # Nuevo campo para múltiples paradas
    intermediate_stops: Optional[List[dict]] = Field(
        default=None,
        description="Lista de paradas intermedias. Cada parada debe tener: latitude, longitude, description"
    )


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

    # Campos para gestión de conductores ocupados
    assigned_busy_driver_id: Optional[UUID] = Field(
        default=None,
        foreign_key="user.id",
        description="ID del conductor ocupado asignado a esta solicitud"
    )
    estimated_pickup_time: Optional[datetime] = Field(
        default=None,
        description="Tiempo estimado de recogida cuando el conductor está ocupado"
    )
    driver_current_trip_remaining_time: Optional[float] = Field(
        default=None,
        description="Tiempo restante del viaje actual del conductor en minutos"
    )
    driver_transit_time: Optional[float] = Field(
        default=None,
        description="Tiempo de tránsito desde el destino actual hasta el cliente en minutos"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("America/Bogota")), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("America/Bogota")),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(
            pytz.timezone("America/Bogota"))}
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
        sa_relationship_kwargs={
            "foreign_keys": "PenalityUser.id_client_request"}
    )
    chat_messages: List["ChatMessage"] = Relationship(
        back_populates="client_request")
    trip_stops: List["TripStop"] = Relationship(
        back_populates="client_request"
    )

    # Relación con conductor ocupado asignado
    assigned_busy_driver: Optional["User"] = Relationship(
        back_populates="busy_driver_requests",
        sa_relationship_kwargs={
            "foreign_keys": "[ClientRequest.assigned_busy_driver_id]"}
    )

    # Relación con DriverInfo para solicitudes pendientes
    driver_pending_request: Optional["DriverInfo"] = Relationship(
        back_populates="pending_request"
    )

# Definir el listener para el evento after_update


def after_update_listener(mapper, connection, target):
    from app.services.earnings_service import distribute_earnings  # Import aquí, no arriba
    # Import aquí, no arriba
    from app.services.chat_service import cleanup_chat_messages_for_request
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
                # Distribuir ganancias
                distribute_earnings(session, target)
                # Limpiar mensajes de chat automáticamente
                cleanup_chat_messages_for_request(session, target.id)
                print(
                    f"✅ Chat messages eliminados automáticamente para ClientRequest {target.id} (status: PAID)")
            except Exception as e:
                print(f"Error en after_update_listener: {e}")
                raise


# Registrar el evento después de definir la clase
event.listen(ClientRequest, 'after_update', after_update_listener)
