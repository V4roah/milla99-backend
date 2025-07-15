from fastapi.testclient import TestClient
from app.main import app
from app.models.client_request import StatusEnum, ClientRequest
from app.models.transaction import Transaction, TransactionType
from app.models.verify_mount import VerifyMount
from app.models.driver_savings import DriverSavings
from app.models.company_account import CompanyAccount
from decimal import Decimal
from sqlmodel import Session, select
from app.core.db import engine
from app.services.earnings_service import distribute_earnings
from uuid import UUID
from datetime import date
import json
import io
from fastapi import status as http_status
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.test.test_drivers import create_and_approve_driver

client = TestClient(app)


def test_cash_payment_transaction_flow():
    """
    Prueba el flujo completo de pago en efectivo y verifica todas las transacciones:
    1. Verifica que el conductor recibe el 85% del valor del viaje
    2. Verifica que se descuenta el 10% de comisión
    3. Verifica que se guarda el 1% en ahorros
    4. Verifica que la empresa recibe su comisión
    """
    # 1. Crear y autenticar cliente
    phone_number = "3004444456"
    country_code = "+57"

    # Autenticar cliente
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Crear solicitud con pago en efectivo
    request_data = {
        "fare_offered": 20000,
        "pickup_description": "Suba Bogotá",
        "destination_description": "Santa Rosita Engativa",
        "pickup_lat": 4.718136,
        "pickup_lng": -74.073170,
        "destination_lat": 4.702468,
        "destination_lng": -74.109776,
        "type_service_id": 1,  # Car
        "payment_method_id": 1  # Cash
    }
    create_resp = client.post(
        "/client-request/", json=request_data, headers=headers)
    assert create_resp.status_code == 201
    client_request_id = create_resp.json()["id"]

    # 3. Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 4. Asignar conductor y completar viaje
    fare_assigned = 25000  # Valor final del viaje

    # Asignar conductor
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": str(driver_id),  # Convertir UUID a string para JSON
        "fare_assigned": fare_assigned
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned",
        json=assign_data,
        headers=headers
    )
    assert assign_resp.status_code == 200

    # Completar flujo del viaje
    status_flow = ["ON_THE_WAY", "ARRIVED", "TRAVELLING", "FINISHED", "PAID"]
    for status in status_flow:
        status_data = {
            "id_client_request": client_request_id,
            "status": status
        }
        status_resp = client.patch(
            "/client-request/updateStatusByDriver",
            json=status_data,
            headers=driver_headers
        )
        assert status_resp.status_code == 200

    # 5. Verificar todas las transacciones
    with Session(engine) as session:
        # Verificar transacción de ingreso del conductor (85%)
        driver_income = session.exec(
            select(Transaction).where(
                Transaction.client_request_id == UUID(str(client_request_id)),
                Transaction.user_id == UUID(str(driver_id)),
                Transaction.type == TransactionType.SERVICE,
                Transaction.income != None
            )
        ).first()
        assert driver_income is not None
        expected_income = int(fare_assigned * Decimal('0.85'))
        assert driver_income.income == expected_income

        # Verificar transacción de comisión del conductor (10%)
        driver_commission = session.exec(
            select(Transaction).where(
                Transaction.client_request_id == UUID(str(client_request_id)),
                Transaction.user_id == UUID(str(driver_id)),
                Transaction.type == TransactionType.COMMISSION,
                Transaction.expense != None
            )
        ).first()
        assert driver_commission is not None
        expected_commission = int(fare_assigned * Decimal('0.10'))
        assert driver_commission.expense == expected_commission

        # Verificar ahorros del conductor (1%)
        driver_savings = session.exec(
            select(DriverSavings).where(
                DriverSavings.user_id == UUID(str(driver_id))
            )
        ).first()
        assert driver_savings is not None
        expected_savings = int(fare_assigned * Decimal('0.01'))
        assert driver_savings.mount == expected_savings

        # Verificar comisión de la empresa (4%)
        company_account = session.exec(
            select(CompanyAccount).where(
                CompanyAccount.client_request_id == UUID(
                    str(client_request_id)),
                CompanyAccount.type == "SERVICE"
            )
        ).first()
        assert company_account is not None
        expected_company_commission = int(fare_assigned * Decimal('0.04'))
        assert company_account.income == expected_company_commission


def test_pending_request_transaction_flow():
    """
    Prueba el flujo de transacciones para solicitudes en estado PENDING
    con precio negociado.
    """
    # 1. Crear conductor ocupado con viaje activo
    driver_phone = "3010000011"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 2. Crear solicitud para ocupar al conductor
    client_phone = "3004444466"
    client_country_code = "+57"

    # Crear y autenticar cliente
    user_data = {
        "full_name": "Cliente Ocupado",
        "country_code": client_country_code,
        "phone_number": client_phone
    }
    create_resp = client.post("/users/", json=user_data)
    assert create_resp.status_code == 201, f"Error creando usuario: {create_resp.text}"

    # Autenticar cliente
    send_resp = client.post(
        f"/auth/verify/{client_country_code}/{client_phone}/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        f"/auth/verify/{client_country_code}/{client_phone}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    client_token = verify_resp.json()["access_token"]
    client_headers = {"Authorization": f"Bearer {client_token}"}

    # Crear solicitud para ocupar al conductor
    busy_request_data = {
        "fare_offered": 15000,
        "pickup_description": "Chapinero",
        "destination_description": "Usaquén",
        "pickup_lat": 4.650000,
        "pickup_lng": -74.050000,
        "destination_lat": 4.700000,
        "destination_lng": -74.100000,
        "type_service_id": 1,
        "payment_method_id": 1
    }
    busy_response = client.post(
        "/client-request/", json=busy_request_data, headers=client_headers)
    assert busy_response.status_code == 201
    busy_request_id = busy_response.json()["id"]

    # Asignar conductor y poner en TRAVELLING
    assign_busy_data = {
        "id_client_request": busy_request_id,
        "id_driver": str(driver_id),  # Convertir UUID a string
        "fare_assigned": 15000
    }
    assign_busy_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_busy_data, headers=client_headers)
    assert assign_busy_resp.status_code == 200

    # Seguir el flujo correcto de estados
    status_flow = ["ON_THE_WAY", "ARRIVED", "TRAVELLING"]
    for status in status_flow:
        status_data = {
            "id_client_request": busy_request_id,
            "status": status
        }
        status_resp = client.patch(
            "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
        assert status_resp.status_code == 200, f"Error cambiando estado a {status}: {status_resp.text}"

    # 3. Crear solicitud pendiente con precio negociado
    client2_phone = "3004444467"
    client2_country_code = "+57"

    # Crear y autenticar segundo cliente
    user_data2 = {
        "full_name": "Cliente Pendiente",
        "country_code": client2_country_code,
        "phone_number": client2_phone
    }
    create_resp2 = client.post("/users/", json=user_data2)
    assert create_resp2.status_code == 201, f"Error creando segundo usuario: {create_resp2.text}"

    # Autenticar segundo cliente
    send_resp2 = client.post(
        f"/auth/verify/{client2_country_code}/{client2_phone}/send")
    assert send_resp2.status_code == 201
    code2 = send_resp2.json()["message"].split()[-1]

    verify_resp2 = client.post(
        f"/auth/verify/{client2_country_code}/{client2_phone}/code",
        json={"code": code2}
    )
    assert verify_resp2.status_code == 200
    client2_token = verify_resp2.json()["access_token"]
    client2_headers = {"Authorization": f"Bearer {client2_token}"}

    # Crear solicitud pendiente
    pending_request_data = {
        "fare_offered": 20000,  # Precio base
        "pickup_description": "Cerca del destino del viaje actual",
        "destination_description": "Destino cercano",
        # Más cerca del destino del viaje actual (4.700000, -74.100000)
        "pickup_lat": 4.700500,
        "pickup_lng": -74.100500,
        "destination_lat": 4.708468,
        "destination_lng": -74.105776,
        "type_service_id": 1,
        "payment_method_id": 1
    }
    pending_response = client.post(
        "/client-request/", json=pending_request_data, headers=client2_headers)
    assert pending_response.status_code == 201
    pending_request_id = pending_response.json()["id"]

    # 4. Asignar conductor ocupado a la solicitud pendiente
    assign_pending_data = {
        "id_client_request": pending_request_id,
        "id_driver": str(driver_id),  # Convertir UUID a string
        "fare_assigned": 20000
    }
    assign_pending_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_pending_data, headers=client2_headers)
    assert assign_pending_resp.status_code == 200

    # Verificar que está en estado PENDING
    detail_resp = client.get(
        f"/client-request/{pending_request_id}", headers=client2_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["status"] == str(StatusEnum.PENDING)

    # 5. Conductor hace oferta de precio
    offer_resp = client.post(
        f"/drivers/pending-request/offer?fare_offer=25000", headers=driver_headers)
    assert offer_resp.status_code == 200

    # 6. Completar solicitud pendiente con precio negociado
    complete_resp = client.post(
        "/drivers/pending-request/complete", headers=driver_headers)
    assert complete_resp.status_code == 200

    # 7. Completar flujo del viaje pendiente
    status_flow = ["ON_THE_WAY", "ARRIVED", "TRAVELLING", "FINISHED", "PAID"]
    for status in status_flow:
        status_data = {
            "id_client_request": pending_request_id,
            "status": status
        }
        status_resp = client.patch(
            "/client-request/updateStatusByDriver",
            json=status_data,
            headers=driver_headers
        )
        assert status_resp.status_code == 200

    # 8. Verificar transacciones con precio negociado
    negotiated_price = 25000
    with Session(engine) as session:
        # Verificar transacción de ingreso del conductor (85% del precio negociado)
        driver_income = session.exec(
            select(Transaction).where(
                Transaction.client_request_id == UUID(str(pending_request_id)),
                Transaction.user_id == UUID(str(driver_id)),
                Transaction.type == TransactionType.SERVICE,
                Transaction.income != None
            )
        ).first()
        assert driver_income is not None
        expected_income = int(negotiated_price * Decimal('0.85'))
        assert driver_income.income == expected_income

        # Verificar transacción de comisión del conductor (10% del precio negociado)
        driver_commission = session.exec(
            select(Transaction).where(
                Transaction.client_request_id == UUID(str(pending_request_id)),
                Transaction.user_id == UUID(str(driver_id)),
                Transaction.type == TransactionType.COMMISSION,
                Transaction.expense != None
            )
        ).first()
        assert driver_commission is not None
        expected_commission = int(negotiated_price * Decimal('0.10'))
        assert driver_commission.expense == expected_commission

        # Verificar ahorros del conductor (1% del precio negociado)
        driver_savings = session.exec(
            select(DriverSavings).where(
                DriverSavings.user_id == UUID(str(driver_id))
            )
        ).first()
        assert driver_savings is not None
        expected_savings = int(negotiated_price * Decimal('0.01'))
        assert driver_savings.mount == expected_savings

        # Verificar comisión de la empresa (4% del precio negociado)
        company_account = session.exec(
            select(CompanyAccount).where(
                CompanyAccount.client_request_id == UUID(
                    str(pending_request_id)),
                CompanyAccount.type == "SERVICE"
            )
        ).first()
        assert company_account is not None
        expected_company_commission = int(negotiated_price * Decimal('0.04'))
        assert company_account.income == expected_company_commission

    print("✅ Test completado: Transacciones con precio negociado en solicitudes PENDING")


def test_recharge_flow():
    """
    Test del flujo completo de recarga:
    1. Usuario crea recarga
    2. Admin aprueba la recarga
    3. Verificar que se actualiza verify_mount
    """
    print("\n🔄 Iniciando test de flujo de recarga...")

    # 1. Crear usuario y obtener token
    print("\n👤 Paso 1: Usando usuario existente y obteniendo token...")

    # Usar un usuario que ya existe en la inicialización
    phone_number = "3001111111"  # Usar un número que sabemos que existe
    country_code = "+57"

    # Autenticar usuario existente
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200, f"Error en verificación: {verify_resp.text}"

    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Obtener user_id del token
    user_info_resp = client.get("/users/me", headers=headers)
    assert user_info_resp.status_code == 200
    user_id = user_info_resp.json()["id"]

    print(f"✅ Usuario autenticado: {user_id}")

    # 2. Verificar saldo inicial
    print("\n💰 Paso 2: Verificando saldo inicial...")
    balance_resp_before = client.get(
        "/transactions/balance/me", headers=headers)
    assert balance_resp_before.status_code == 200
    balance_data_before = balance_resp_before.json()
    initial_balance = balance_data_before["mount"]
    print(f"💰 Saldo inicial: ${initial_balance:,}")

    # 3. Crear recarga
    print("\n💳 Paso 3: Creando recarga...")
    recharge_amount = 50000
    recharge_data = {
        "amount": recharge_amount,
        "description": "Recarga de prueba"
    }

    recharge_resp = client.post(
        "/transactions/recharge",
        json=recharge_data,
        headers=headers
    )
    assert recharge_resp.status_code == 201, f"Error creando recarga: {recharge_resp.text}"

    recharge_response = recharge_resp.json()
    transaction_id = recharge_response["transaction_id"]
    user_id_from_response = recharge_response["user_id"]

    assert user_id_from_response == user_id
    assert recharge_response["amount_recharged"] == recharge_amount
    assert recharge_response["transaction_type"] == "RECHARGE"
    assert recharge_response["message"] == "Recarga creada exitosamente. Pendiente de aprobación por administrador."

    print(
        f"✅ Recarga creada: ID {transaction_id}, Monto: ${recharge_amount:,}")

    # 4. Verificar que la transacción está pendiente
    print("\n⏳ Paso 4: Verificando que la transacción está pendiente...")
    with Session(engine) as session:
        transaction = session.exec(
            select(Transaction).where(Transaction.id == UUID(transaction_id))
        ).first()
        assert transaction is not None
        assert transaction.is_confirmed == False
        assert transaction.income == recharge_amount
        assert transaction.type == TransactionType.RECHARGE
        print(f"✅ Transacción creada como pendiente: {transaction.id}")

    # 5. Verificar saldo ANTES de la aprobación (debería ser el mismo)
    print("\n💰 Paso 5: Verificando saldo antes de la aprobación...")
    balance_resp_pending = client.get(
        "/transactions/balance/me", headers=headers)
    assert balance_resp_pending.status_code == 200
    balance_data_pending = balance_resp_pending.json()
    balance_before_approval = balance_data_pending["mount"]
    print(f"💰 Saldo antes de aprobación: ${balance_before_approval:,}")
    assert balance_before_approval == initial_balance, f"El saldo no debería haber cambiado aún. Esperado: ${initial_balance}, Actual: ${balance_before_approval}"

    # 6. Autenticar admin
    print("\n👨‍💼 Paso 6: Autenticando admin...")
    admin_login_data = {
        "email": "admin",
        "password": "admin"
    }
    admin_login_resp = client.post(
        "/login-admin/login", json=admin_login_data)
    assert admin_login_resp.status_code == 200, f"Error login admin: {admin_login_resp.text}"
    admin_token = admin_login_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(f"✅ Admin autenticado exitosamente")

    # 7. Admin aprueba la transacción usando el endpoint administrativo
    print("\n✅ Paso 7: Admin aprueba la transacción...")
    approval_data = {
        "transaction_id": transaction_id
    }

    print(f"   🔄 Aprobando transacción {transaction_id}...")
    approval_response = client.post(
        "/admin/transactions/approve",
        headers=admin_headers,
        json=approval_data
    )
    assert approval_response.status_code == 200, f"Error aprobando transacción: {approval_response.text}"

    approval_result = approval_response.json()
    assert approval_result["transaction_id"] == transaction_id
    assert approval_result["amount"] == recharge_amount
    assert approval_result["transaction_type"] == "RECHARGE"
    print(f"✅ Transacción aprobada exitosamente: {approval_result['message']}")

    # 8. Verificar que se refleja en verify_mount DESPUÉS de la aprobación
    print("\n💰 Paso 8: Verificando saldo después de la aprobación...")
    balance_resp_after = client.get(
        "/transactions/balance/me", headers=headers)
    assert balance_resp_after.status_code == 200
    balance_data_after = balance_resp_after.json()
    final_balance = balance_data_after["mount"]

    expected_balance = initial_balance + recharge_amount
    assert final_balance == expected_balance, f"Saldo esperado: ${expected_balance:,}, Saldo actual: ${final_balance:,}"

    print(f"💰 Saldo final: ${final_balance:,}")
    print(
        f"✅ Diferencia: ${final_balance - initial_balance:,} (debería ser ${recharge_amount:,})")
    print(f"✅ Incremento correcto: ${recharge_amount:,}")

    # 9. Verificar que la transacción está confirmada
    print("\n✅ Paso 9: Verificando que la transacción está confirmada...")
    with Session(engine) as session:
        transaction = session.exec(
            select(Transaction).where(Transaction.id == UUID(transaction_id))
        ).first()
        assert transaction.is_confirmed == True
        print(f"✅ Transacción confirmada en BD: {transaction.id}")

    print("\n🎉 Test completado: Flujo completo de recarga")
    print(f"📊 Resumen:")
    print(f"   - Saldo inicial: ${initial_balance:,}")
    print(f"   - Recarga solicitada: ${recharge_amount:,}")
    print(f"   - Saldo después de aprobación: ${final_balance:,}")
    print(f"   - Incremento verificado: ${final_balance - initial_balance:,}")
