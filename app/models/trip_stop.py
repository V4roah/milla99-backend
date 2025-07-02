from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Enum
from geoalchemy2 import Geometry
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
import pytz
import enum


class StopType(str, enum.Enum):
    PICKUP = "PICKUP"           # Punto de recogida
    INTERMEDIATE = "INTERMEDIATE"  # Parada intermedia
    DESTINATION = "DESTINATION"    # Destino final


class StopStatus(str, enum.Enum):
    PENDING = "PENDING"         # Pendiente de llegar
    ARRIVED = "ARRIVED"         # Conductor llegó
    COMPLETED = "COMPLETED"     # Parada completada (cliente subió/bajó)


class TripStop(SQLModel, table=True):
    __tablename__ = "trip_stop"

    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)

    # Relación con la solicitud de viaje
    client_request_id: UUID = Field(foreign_key="client_request.id")

    # Información de la parada
    stop_order: int = Field(description="Orden de la parada (1, 2, 3, etc.)")
    stop_type: StopType = Field(
        sa_column=Column(Enum(StopType)),
        description="Tipo de parada: PICKUP, INTERMEDIATE, DESTINATION"
    )
    status: StopStatus = Field(
        default=StopStatus.PENDING,
        sa_column=Column(Enum(StopStatus)),
        description="Estado de la parada"
    )

    # Información geográfica
    latitude: float = Field(description="Latitud de la parada")
    longitude: float = Field(description="Longitud de la parada")
    position: Optional[object] = Field(
        sa_column=Column(Geometry(geometry_type="POINT", srid=4326)),
        description="Posición geoespacial de la parada"
    )

    # Información descriptiva
    description: Optional[str] = Field(
        default=None, max_length=255,
        description="Descripción de la parada (ej: 'Casa de Juan', 'Centro Comercial')"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("America/Bogota")),
        nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("America/Bogota")),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(
            pytz.timezone("America/Bogota"))}
    )

    # Relaciones
    client_request: Optional["ClientRequest"] = Relationship(
        back_populates="trip_stops"
    )


class TripStopCreate(SQLModel):
    """Modelo para crear una nueva parada"""
    stop_order: int = Field(description="Orden de la parada")
    stop_type: StopType = Field(description="Tipo de parada")
    latitude: float = Field(description="Latitud de la parada")
    longitude: float = Field(description="Longitud de la parada")
    description: Optional[str] = Field(
        default=None, description="Descripción de la parada"
    )


class TripStopUpdate(SQLModel):
    """Modelo para actualizar una parada"""
    status: Optional[StopStatus] = None
    description: Optional[str] = None


class TripStopRead(SQLModel):
    """Modelo para leer una parada"""
    id: UUID
    stop_order: int
    stop_type: StopType
    status: StopStatus
    latitude: float
    longitude: float
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
