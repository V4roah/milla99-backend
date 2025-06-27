from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from enum import Enum
from .vehicle_type import VehicleType
from uuid import UUID, uuid4
import pytz

if TYPE_CHECKING:
    from .driver_info import DriverInfo
    from .driver_documents import DriverDocuments


COLOMBIA_TZ = pytz.timezone("America/Bogota")


class VehicleInfoBase(SQLModel):
    brand: str = Field(nullable=False)
    model: str = Field(nullable=False)
    model_year: int = Field(nullable=False)
    color: str = Field(nullable=False)
    plate: str = Field(nullable=False)
    vehicle_type_id: int = Field(foreign_key="vehicle_type.id", nullable=False)


class VehicleInfo(VehicleInfoBase, table=True):
    __tablename__ = "vehicle_info"
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(COLOMBIA_TZ),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(COLOMBIA_TZ)}
    )

    # Relaciones
    driver_info_id: UUID = Field(foreign_key="driver_info.id")
    driver_info: Optional["DriverInfo"] = Relationship(
        back_populates="vehicle_info")
    vehicle_type: VehicleType = Relationship(back_populates="vehicles")
    driver_documents: List["DriverDocuments"] = Relationship(
        back_populates="vehicle_info")


class VehicleInfoCreate(VehicleInfoBase):
    pass


class VehicleInfoUpdate(SQLModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[int] = None
    color: Optional[str] = None
    plate: Optional[str] = None
    vehicle_type_id: Optional[int] = None
