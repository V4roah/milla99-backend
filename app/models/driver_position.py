from typing import Optional, Any
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column
from geoalchemy2 import Geometry
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
import pytz


COLOMBIA_TZ = pytz.timezone("America/Bogota")


class DriverPosition(SQLModel, table=True):
    __tablename__ = "driver_position"
    id_driver: UUID = Field(foreign_key="user.id", primary_key=True)
    position: Optional[Any] = Field(
        sa_column=Column(
            Geometry(geometry_type="POINT", srid=4326),  # Agregado SRID 4326
            nullable=False
        )
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(
        COLOMBIA_TZ), nullable=False, sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)})
    user: Optional["User"] = Relationship(back_populates="driver_position")


class DriverPositionCreate(BaseModel):
    lat: float = Field(...,
                       description="Latitud donde se encuentra el conductor. Ejemplo: 4.710989")
    lng: float = Field(...,
                       description="Longitud donde se encuentra el conductor. Ejemplo: -74.072092")


class DriverPositionRead(BaseModel):
    id_driver: UUID = Field(...,
                            description="ID único del conductor. Ejemplo: 123")
    lat: float = Field(...,
                       description="Latitud de la posición del conductor. Ejemplo: 4.710989")
    lng: float = Field(...,
                       description="Longitud de la posición del conductor. Ejemplo: -74.072092")
    distance_km: Optional[float] = Field(
        None, description="Distancia al punto de búsqueda en kilómetros. Ejemplo: 2.35")

    @classmethod
    def from_orm_with_point(cls, obj):
        from geoalchemy2.shape import to_shape
        point = to_shape(obj.position)
        return cls(
            id_driver=obj.id_driver,
            lat=point.y,
            lng=point.x
        )

# Recuerda registrar la relación en el modelo User agregando:
# driver_position: Optional["DriverPosition"] = Relationship(back_populates="user")
