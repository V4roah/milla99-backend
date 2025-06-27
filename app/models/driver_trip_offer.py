from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.driver_response import DriverInfoResponse, UserResponse, VehicleInfoResponse
from uuid import UUID, uuid4
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class DriverTripOfferCreate(BaseModel):
    id_client_request: UUID = Field(...,
                                    description="ID de la solicitud de viaje del cliente.")
    fare_offer: float = Field(...,
                              description="Tarifa ofrecida por el conductor.")
    time: float = Field(..., description="Tiempo estimado del viaje.")
    distance: float = Field(..., description="Distancia estimada del viaje.")


class DriverTripOffer(SQLModel, table=True):
    __tablename__ = "driver_trip_offer"
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    id_driver: UUID = Field(foreign_key="user.id")
    id_client_request: UUID = Field(foreign_key="client_request.id")
    fare_offer: float
    time: float
    distance: float
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(
        COLOMBIA_TZ), nullable=False, sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)})


class DriverTripOfferResponse(BaseModel):
    id: UUID
    fare_offer: float
    time: float
    distance: float
    created_at: str
    updated_at: str
    user: UserResponse
    driver_info: DriverInfoResponse
    vehicle_info: Optional[VehicleInfoResponse] = None
    average_rating: float
