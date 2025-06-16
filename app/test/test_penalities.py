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
from app.models.transaction import Transaction, TransactionType
from app.services.transaction_service import TransactionService

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
    session.refresh(user)

    # Asignar rol CLIENT aprobado
    role = UserHasRole(
        id_user=user.id,
        id_rol="CLIENT",
        status=RoleStatus.APPROVED,
        is_verified=True,
        verified_at=datetime.now(timezone.utc)
    )
    session.add(role)
    session.commit()

    # Agregar saldo inicial al usuario
    transaction_service = TransactionService(session)
    transaction_service.create_transaction(
        user_id=user.id,
        income=50000,  # Saldo inicial de 50,000
        type=TransactionType.RECHARGE,
        description="Saldo inicial para pruebas"
    )
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


def test_client_cancellation_penalty_on_the_way(session, client_user, driver_user):
    """
    Caso de prueba para verificar la penalización al cliente cuando cancela una solicitud
    en estado ON_THE_WAY.

    Verifica:
    1. Penalización de fine_one (1000) cuando cancela en ON_THE_WAY
    2. Que se registre la penalización en la tabla penality_user
    3. Que se registre la transacción de penalización
    4. Que se actualice el saldo del cliente
    """
    print("\n=== DEBUG INFO ===")
    print(f"Client User ID: {client_user.id}")
    print(f"Driver User ID: {driver_user.id}")

    # Obtener configuración existente
    config = session.query(ProjectSettings).first()
    assert config is not None, "No se encontró la configuración del proyecto"
    assert config.fine_one == "1000", "El valor de fine_one debe ser 1000"
    print(f"Fine One: {config.fine_one}")

    # Obtener el balance inicial del cliente usando TransactionService
    transaction_service = TransactionService(session)
    initial_balance = transaction_service.get_user_balance(client_user.id)
    print(f"Initial Balance: {initial_balance}")
    assert initial_balance["available"] >= int(
        config.fine_one), "El cliente debe tener saldo suficiente para la penalización"

    # Crear y cancelar solicitud en ON_THE_WAY
    request = create_test_request(
        session, client_user.id, StatusEnum.ON_THE_WAY, driver_user.id)
    print(f"Request ID: {request.id}")
    print(f"Request Status: {request.status}")

    try:
        result = client_canceled_service(session, request.id, client_user.id)
        print(f"Cancel Result: {result}")
    except Exception as e:
        print(f"Error en client_canceled_service: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise

    assert result["success"] is True
    assert "penalización" in result["message"].lower(
    ), f"El mensaje no contiene 'penalización': {result['message']}"
    assert config.fine_one in result[
        "message"], f"El mensaje no contiene el monto de la penalización: {result['message']}"

    # Verificar que se registró la penalización en penality_user
    penality = session.query(PenalityUser).filter(
        PenalityUser.id_user == client_user.id,
        PenalityUser.id_client_request == request.id,
        PenalityUser.amount == float(config.fine_one),
        PenalityUser.status == statusEnum.PENDING
    ).first()
    print(f"Penality Record: {penality}")
    assert penality is not None, "No se registró la penalización en penality_user"

    # Verificar que se registró la transacción de penalización
    transaction = session.query(Transaction).filter(
        Transaction.user_id == client_user.id,
        Transaction.type == TransactionType.PENALITY_DEDUCTION,
        Transaction.expense == int(config.fine_one)
    ).first()
    print(f"Penalty Transaction: {transaction}")
    assert transaction is not None, "No se registró la transacción de penalización"

    # Verificar saldo después de la penalización
    final_balance = transaction_service.get_user_balance(client_user.id)
    print(f"Final Balance: {final_balance}")
    assert final_balance["available"] == initial_balance["available"] - \
        int(config.fine_one), "El saldo no se actualizó correctamente"


def test_client_cancellation_penalty_arrived(session, client_user, driver_user):
    """
    Caso de prueba para verificar la penalización al cliente cuando cancela una solicitud
    en estado ARRIVED.

    Verifica:
    1. Penalización de fine_two (2000) cuando cancela en ARRIVED
    2. Que se registre la penalización en la tabla penality_user
    3. Que se registre la transacción de penalización
    4. Que se actualice el saldo del cliente
    """
    print("\n=== DEBUG INFO ===")
    print(f"Client User ID: {client_user.id}")
    print(f"Driver User ID: {driver_user.id}")

    # Obtener configuración existente
    config = session.query(ProjectSettings).first()
    assert config is not None, "No se encontró la configuración del proyecto"
    assert config.fine_two == "2000", "El valor de fine_two debe ser 2000"
    print(f"Fine Two: {config.fine_two}")

    # Obtener el balance inicial del cliente usando TransactionService
    transaction_service = TransactionService(session)
    initial_balance = transaction_service.get_user_balance(client_user.id)
    print(f"Initial Balance: {initial_balance}")
    assert initial_balance["available"] >= int(
        config.fine_two), "El cliente debe tener saldo suficiente para la penalización"

    # Crear y cancelar solicitud en ARRIVED
    request = create_test_request(
        session, client_user.id, StatusEnum.ARRIVED, driver_user.id)
    print(f"Request ID: {request.id}")
    print(f"Request Status: {request.status}")

    try:
        result = client_canceled_service(session, request.id, client_user.id)
        print(f"Cancel Result: {result}")
    except Exception as e:
        print(f"Error en client_canceled_service: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise

    assert result["success"] is True
    assert "penalización" in result["message"].lower()
    assert config.fine_two in result["message"]

    # Verificar que se registró la penalización en penality_user
    penality = session.query(PenalityUser).filter(
        PenalityUser.id_user == client_user.id,
        PenalityUser.id_client_request == request.id,
        PenalityUser.amount == float(config.fine_two),
        PenalityUser.status == statusEnum.PENDING
    ).first()
    print(f"Penality Record: {penality}")
    assert penality is not None, "No se registró la penalización en penality_user"

    # Verificar que se registró la transacción de penalización
    transaction = session.query(Transaction).filter(
        Transaction.user_id == client_user.id,
        Transaction.type == TransactionType.PENALITY_DEDUCTION,
        Transaction.expense == int(config.fine_two)
    ).first()
    print(f"Penalty Transaction: {transaction}")
    assert transaction is not None, "No se registró la transacción de penalización"

    # Verificar saldo después de la penalización
    final_balance = transaction_service.get_user_balance(client_user.id)
    print(f"Final Balance: {final_balance}")
    assert final_balance["available"] == initial_balance["available"] - \
        int(config.fine_two), "El saldo no se actualizó correctamente"
