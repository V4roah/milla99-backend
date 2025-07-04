from fastapi import FastAPI
from typing import Annotated
from fastapi import Depends
from sqlmodel import Session, create_engine, SQLModel
from .config import settings
import os

# ✅ IMPORTAR TODOS LOS MODELOS
from app.models import (
    Role, UserHasRole, DocumentType, DriverInfo, VehicleInfo,
    VehicleType, User, DriverDocuments, ClientRequest, DriverPosition,
    DriverTripOffer, ProjectSettings, Referral, CompanyAccount,
    DriverSavings, Transaction, VerifyMount, TypeService, ConfigServiceValue,
    AdminLog, Administrador
)

# ============================================================================
# CONFIGURACIÓN DE BASE DE DATOS DINÁMICA
# ============================================================================


def get_database_url() -> str:
    """Obtiene la URL de base de datos según el entorno actual"""
    return settings.current_database_url


def validate_database_environment():
    """Valida que la configuración de base de datos sea segura para el entorno"""
    environment = settings.environment_name

    # Validaciones específicas por entorno
    if environment == "production":
        # En producción, asegurar que no estamos usando bases de datos de desarrollo
        if "localhost" in get_database_url() or "127.0.0.1" in get_database_url():
            raise ValueError(
                " ERROR: No se puede usar localhost en entorno de producción")

        if "test" in get_database_url().lower():
            raise ValueError(
                " ERROR: No se puede usar base de datos de test en producción")

    elif environment == "qa":
        # En QA, asegurar que no estamos usando la base de datos de desarrollo
        if settings.is_development and get_database_url() == settings.DATABASE_URL:
            raise ValueError(
                " ERROR: QA no puede usar la base de datos de desarrollo")

    print(f" Conectando a base de datos para entorno: {environment}")
    print(f" URL de base de datos: {get_database_url()}")


# Crear el engine con la URL dinámica
engine = create_engine(get_database_url(), echo=False)


def create_all_tables():
    """Crea todas las tablas en la base de datos"""
    validate_database_environment()
    SQLModel.metadata.create_all(engine)
    print(f" Tablas creadas en entorno: {settings.environment_name}")


def get_session():
    """Obtiene una sesión de base de datos con validación de entorno"""
    validate_database_environment()
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

# ============================================================================
# FUNCIONES DE VALIDACIÓN ADICIONALES
# ============================================================================


def is_safe_for_data_initialization() -> bool:
    """Verifica si es seguro inicializar datos en el entorno actual"""
    environment = settings.environment_name

    # Solo permitir inicialización en desarrollo
    if environment == "development":
        return True

    # En QA y producción, solo permitir si se especifica explícitamente
    force_init = os.getenv("FORCE_INIT_DATA", "false").lower() == "true"

    if environment == "qa" and force_init:
        print("  ADVERTENCIA: Inicializando datos en QA con FORCE_INIT_DATA=true")
        return True

    if environment == "production" and force_init:
        print("  ADVERTENCIA: Inicializando datos en producción con FORCE_INIT_DATA=true")
        return True

    return False


def get_environment_info() -> dict:
    """Retorna información del entorno actual"""
    return {
        "environment": settings.environment_name,
        "database_url": get_database_url(),
        "is_development": settings.is_development,
        "is_qa": settings.is_qa,
        "is_production": settings.is_production,
        "safe_for_init": is_safe_for_data_initialization()
    }
