from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlmodel import SQLModel, Field
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Relationship, Column, Integer, ForeignKey
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class ConfigServiceValue(SQLModel, table=True):
    __tablename__ = "config_service_value"
    id: Optional[int] = Field(default=None, primary_key=True)
    km_value: float = Field(..., nullable=False)
    min_value: float = Field(..., nullable=False)
    tarifa_value: float = Field(..., nullable=True)
    weight_value: float = Field(..., nullable=True)
    # Llave foránea única a TypeService
    service_type_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("type_service.id", ondelete="CASCADE"),
            unique=True,
            nullable=False
        )
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )

    # Relaciones
    type_service: Optional["TypeService"] = Relationship(
        back_populates="config_service_value")


class CalculateFareRequest(BaseModel):
    type_vehicle_id: int
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float

# Modelo para la respuesta


class FareCalculationResponse(BaseModel):
    recommended_value: float
    destination_addresses: str
    origin_addresses: str
    distance: str
    duration: str


class VehicleTypeConfigurationCreate(BaseModel):
    km_value: float
    min_value: float
    tarifa_value: Optional[float] = None
    weight_value: Optional[float] = None


class VehicleTypeConfigurationUpdate(BaseModel):
    km_value: Optional[float] = None
    min_value: Optional[float] = None
    tarifa_value: Optional[float] = None
    weight_value: Optional[float] = None


class VehicleTypeConfigurationResponse(BaseModel):
    id: int
    km_value: float
    min_value: float
    tarifa_value: Optional[float]
    weight_value: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
