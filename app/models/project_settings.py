from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class ProjectSettingsBase(SQLModel):
    driver_dist: str
    referral_1: str
    referral_2: str
    referral_3: str
    referral_4: str
    referral_5: str
    driver_saving: str
    company: str
    bonus: str
    amount: str  # Monto mínimo para retiro de ahorros
    fine_one: Optional[str] = None  # Multa por cancelación en on the way 
    fine_two: Optional[str] = None  # Multa por cancelación en arrived
    cancel_max_days: Optional[int] = None  # maximas cancelaciones por dias
    cancel_max_weeks: Optional[int] = None  # maximas cancelaciones por semanas
    day_suspension: Optional[int] = None  # Dias de suspension por multa

class ProjectSettings(ProjectSettingsBase, table=True):
    __tablename__ = "project_settings"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )


class ProjectSettingsCreate(ProjectSettingsBase):
    pass

class ProjectSettingsUpdate(SQLModel):
    driver_dist: Optional[str] = None
    referral_1: Optional[str] = None
    referral_2: Optional[str] = None
    referral_3: Optional[str] = None
    referral_4: Optional[str] = None
    referral_5: Optional[str] = None
    driver_saving: Optional[str] = None
    company: Optional[str] = None
    bonus: Optional[str] = None
    amount: Optional[str] = None