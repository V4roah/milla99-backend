from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import field_validator
from uuid import UUID, uuid4
import pytz

# Definimos el enum para el status


class DriverStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class DriverDocumentsBase(SQLModel):
    document_type_id: int = Field(
        foreign_key="document_type.id", nullable=False)
    document_front_url: Optional[str] = Field(default=None, nullable=True)
    document_back_url: Optional[str] = Field(default=None, nullable=True)
    status: DriverStatus = Field(default=DriverStatus.PENDING, nullable=False)
    expiration_date: Optional[datetime] = Field(default=None, nullable=True)


class DriverDocuments(DriverDocumentsBase, table=True):
    __tablename__ = "driver_documents"
    id: Optional[UUID] = Field(
        default_factory=uuid4, primary_key=True, unique=True)
    driver_info_id: UUID = Field(foreign_key="driver_info.id", nullable=False)
    vehicle_info_id: Optional[UUID] = Field(
        default=None, foreign_key="vehicle_info.id", nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(
        pytz.timezone("America/Bogota")), nullable=False)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("America/Bogota")),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(
            pytz.timezone("America/Bogota"))}
    )
    # Relaciones
    driver_info: "DriverInfo" = Relationship(back_populates="documents")
    documenttype: "DocumentType" = Relationship(
        back_populates="driver_documents")
    vehicle_info: Optional["VehicleInfo"] = Relationship(
        back_populates="driver_documents")


class DriverDocumentsCreate(DriverDocumentsBase):
    pass


class DriverDocumentsRead(SQLModel):
    id: UUID
    user_id: UUID
    driver_info_id: UUID
    document_type_id: int
    vehicle_info_id: Optional[UUID]
    soat_id: Optional[int]
    technomechanics_id: Optional[int]
    drivers_license_id: Optional[int]
    status: DriverStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DriverDocumentsUpdate(SQLModel):
    document_type_id: Optional[int] = None
    vehicle_info_id: Optional[UUID] = None
    soat_id: Optional[int] = None
    technomechanics_id: Optional[int] = None
    drivers_license_id: Optional[int] = None
    document_front_url: Optional[str] = None
    document_back_url: Optional[str] = None
    status: Optional[DriverStatus] = None
    expiration_date: Optional[datetime] = None


class DocumentsUpdate (SQLModel):
    id: UUID
    status: Optional[DriverStatus] = None
    expiration_date: Optional[datetime] = None
    document_front_url: Optional[str] = None
    document_back_url: Optional[str] = None


class DriverDocumentsCreateRequest(SQLModel):
    user_id: UUID
    driver_info_id: UUID
    document_type_id: int
    document_front_url: str
    document_back_url: Optional[str] = None
    expiration_date: Optional[datetime] = None
    # vehicle_info_id: Optional[UUID] = None
