from fastapi.testclient import TestClient
from app.main import app
from app.test.test_drivers import create_and_approve_driver
from app.models.client_request import StatusEnum
from app.models.penality_user import statusEnum, PenalityUser
from app.models.project_settings import ProjectSettings
from app.models.driver_cancellation import DriverCancellation
from app.models.user_has_roles import UserHasRole, RoleStatus
from decimal import Decimal
from uuid import UUID
import pytest
from sqlmodel import Session
from uuid import uuid4
from datetime import datetime, timezone
from app.services.client_requests_service import client_canceled_service, driver_canceled_service
from app.models.user import User
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

client = TestClient(app)


@pytest.fixture
def client_user(session):
    """Fixture para crear un usuario cliente"""
    user = User(
        id=uuid4(),
        full_name="Test Client",
        email="client@test.com",
        phone_number="3004444456",
        country_code="+57"
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def driver_user(session):
    """Fixture para crear un usuario conductor"""
    user = User(
        id=uuid4(),
        full_name="Test Driver",
        email="driver@test.com",
        phone_number="3010000005",
        country_code="+57"
    )
    session.add(user)

    role = UserHasRole(
        id_user=user.id,
        id_rol="DRIVER",
        status=RoleStatus.APPROVED
    )
    session.add(role)
    session.commit()
    return user


def create_test_request(session, client_id, status, driver_id=None):
    """Función auxiliar para crear una solicitud de prueba"""
    from app.models.client_request import ClientRequest
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point
    from uuid import uuid4

    # Crear puntos de posición usando geoalchemy2
    pickup_point = from_shape(Point(-74.073170, 4.718136), srid=4326)
    destination_point = from_shape(Point(-74.109776, 4.702468), srid=4326)

    request = ClientRequest(
        id=uuid4(),
        id_client=client_id,
        id_driver_assigned=driver_id,
        fare_offered=20000,
        fare_assigned=25000 if driver_id else None,
        pickup_description="Test Pickup",
        destination_description="Test Destination",
        pickup_position=pickup_point,
        destination_position=destination_point,
        type_service_id=1,
        payment_method_id=1,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def test_driver_cancellation_suspension_on_the_way(session, client_user, driver_user):
    """
    Caso de prueba para cancelación del conductor en estado ON_THE_WAY.
    Verifica:
    1. Registro de cancelación
    2. Conteo de cancelaciones diarias/semanales
    3. Aplicación de suspensión al exceder límites
    4. Estado del conductor después de la suspensión
    """
    # Obtener configuración existente
    config = session.query(ProjectSettings).first()
    assert config is not None, "No se encontró la configuración del proyecto"
    assert config.cancel_max_days == 3, "Límite diario incorrecto"
    assert config.cancel_max_weeks == 10, "Límite semanal incorrecto"
    assert config.day_suspension == 7, "Días de suspensión incorrectos"

    # Verificar estado inicial del conductor
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role is not None, "No se encontró el rol del conductor"
    assert driver_role.suspension is False, "El conductor no debería estar suspendido inicialmente"
    assert driver_role.status == RoleStatus.APPROVED, "El conductor debería estar aprobado inicialmente"

    # Primera cancelación (no debería suspender)
    client_request_1 = create_test_request(
        session, client_user.id, StatusEnum.ON_THE_WAY, driver_user.id)
    result_1 = driver_canceled_service(
        session, client_request_1.id, driver_user.id, "Primera cancelación")
    assert result_1["success"] is True
    assert "registrado" in result_1["message"]
    assert result_1["daily_cancellation_count"] == 1
    assert result_1["weekly_cancellation_count"] == 1

    # Verificar que no se suspendió después de la primera cancelación
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role.suspension is False, "No debería estar suspendido después de una cancelación"
    assert driver_role.status == RoleStatus.APPROVED, "Debería mantener estado APPROVED"

    # Segunda cancelación (no debería suspender)
    client_request_2 = create_test_request(
        session, client_user.id, StatusEnum.ON_THE_WAY, driver_user.id)
    result_2 = driver_canceled_service(
        session, client_request_2.id, driver_user.id, "Segunda cancelación")
    assert result_2["success"] is True
    assert "registrado" in result_2["message"]
    assert result_2["daily_cancellation_count"] == 2
    assert result_2["weekly_cancellation_count"] == 2

    # Verificar que no se suspendió después de la segunda cancelación
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role.suspension is False, "No debería estar suspendido después de dos cancelaciones"
    assert driver_role.status == RoleStatus.APPROVED, "Debería mantener estado APPROVED"

    # Tercera cancelación (DEBERÍA suspender por alcanzar el límite diario)
    client_request_3 = create_test_request(
        session, client_user.id, StatusEnum.ON_THE_WAY, driver_user.id)
    result_3 = driver_canceled_service(
        session, client_request_3.id, driver_user.id, "Tercera cancelación")
    assert result_3["success"] is True
    assert "suspendido" in result_3["message"]
    assert "7 días" in result_3["message"]
    assert result_3["daily_cancellation_count"] == 3
    assert result_3["weekly_cancellation_count"] == 3

    # Verificar que se suspendió después de la tercera cancelación
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role.suspension is True, "Debería estar suspendido después de alcanzar el límite diario"
    assert driver_role.status == RoleStatus.PENDING, "Debería cambiar a estado PENDING"

    # Verificar que se registraron todas las cancelaciones
    cancellations = session.query(DriverCancellation).filter(
        DriverCancellation.id_driver == driver_user.id
    ).all()
    assert len(cancellations) == 3, "Deberían haberse registrado 3 cancelaciones"


def test_driver_cancellation_suspension_accepted(session, client_user, driver_user):
    """
    Caso de prueba para cancelación del conductor en estado ACCEPTED.
    Verifica:
    1. Registro de cancelación
    2. Conteo de cancelaciones diarias/semanales
    3. Aplicación de suspensión al exceder límites
    4. Estado del conductor después de la suspensión

    Este test verifica el mismo comportamiento que test_driver_cancellation_suspension_on_the_way
    pero en el estado ACCEPTED, ya que ambos estados tienen las mismas reglas de cancelación.
    """
    # Obtener configuración existente
    config = session.query(ProjectSettings).first()
    assert config is not None, "No se encontró la configuración del proyecto"
    assert config.cancel_max_days == 3, "Límite diario incorrecto"
    assert config.cancel_max_weeks == 10, "Límite semanal incorrecto"
    assert config.day_suspension == 7, "Días de suspensión incorrectos"

    # Verificar estado inicial del conductor
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role is not None, "No se encontró el rol del conductor"
    assert driver_role.suspension is False, "El conductor no debería estar suspendido inicialmente"
    assert driver_role.status == RoleStatus.APPROVED, "El conductor debería estar aprobado inicialmente"

    # Primera cancelación (no debería suspender)
    client_request_1 = create_test_request(
        session, client_user.id, StatusEnum.ACCEPTED, driver_user.id)
    result_1 = driver_canceled_service(
        session, client_request_1.id, driver_user.id, "Primera cancelación")
    assert result_1["success"] is True
    assert "registrado" in result_1["message"]
    assert result_1["daily_cancellation_count"] == 1
    assert result_1["weekly_cancellation_count"] == 1

    # Verificar que no se suspendió después de la primera cancelación
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role.suspension is False, "No debería estar suspendido después de una cancelación"
    assert driver_role.status == RoleStatus.APPROVED, "Debería mantener estado APPROVED"

    # Segunda cancelación (no debería suspender)
    client_request_2 = create_test_request(
        session, client_user.id, StatusEnum.ACCEPTED, driver_user.id)
    result_2 = driver_canceled_service(
        session, client_request_2.id, driver_user.id, "Segunda cancelación")
    assert result_2["success"] is True
    assert "registrado" in result_2["message"]
    assert result_2["daily_cancellation_count"] == 2
    assert result_2["weekly_cancellation_count"] == 2

    # Verificar que no se suspendió después de la segunda cancelación
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role.suspension is False, "No debería estar suspendido después de dos cancelaciones"
    assert driver_role.status == RoleStatus.APPROVED, "Debería mantener estado APPROVED"

    # Tercera cancelación (DEBERÍA suspender por alcanzar el límite diario)
    client_request_3 = create_test_request(
        session, client_user.id, StatusEnum.ACCEPTED, driver_user.id)
    result_3 = driver_canceled_service(
        session, client_request_3.id, driver_user.id, "Tercera cancelación")
    assert result_3["success"] is True
    assert "suspendido" in result_3["message"]
    assert "7 días" in result_3["message"]
    assert result_3["daily_cancellation_count"] == 3
    assert result_3["weekly_cancellation_count"] == 3

    # Verificar que se suspendió después de la tercera cancelación
    driver_role = session.query(UserHasRole).filter(
        UserHasRole.id_user == driver_user.id,
        UserHasRole.id_rol == "DRIVER"
    ).first()
    assert driver_role.suspension is True, "Debería estar suspendido después de alcanzar el límite diario"
    assert driver_role.status == RoleStatus.PENDING, "Debería cambiar a estado PENDING"

    # Verificar que se registraron todas las cancelaciones
    cancellations = session.query(DriverCancellation).filter(
        DriverCancellation.id_driver == driver_user.id
    ).all()
    assert len(cancellations) == 3, "Deberían haberse registrado 3 cancelaciones"
