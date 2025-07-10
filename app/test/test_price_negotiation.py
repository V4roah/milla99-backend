from fastapi.testclient import TestClient
from app.main import app
from app.test.test_drivers import create_and_approve_driver
from app.models.client_request import StatusEnum
from app.core.db import engine
from sqlmodel import Session, select
from app.models.user import User
from app.models.user_has_roles import UserHasRole, RoleStatus
from uuid import UUID
import time

client = TestClient(app)


def test_price_negotiation_success():
    """
    Test que verifica la negociación exitosa de precios en solicitudes pendientes.
    """
    print("\n🔄 Test: Negociación exitosa de precios...")

    # 1. Crear conductor ocupado con viaje activo
    driver_phone = "3010000007"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 2. Crear solicitud para ocupar al conductor
    client_phone = "3004444458"
    client_country_code = "+57"

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
        "id_driver": driver_id,
        "fare_assigned": 15000
    }
    assign_busy_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_busy_data, headers=client_headers)
    assert assign_busy_resp.status_code == 200

    status_data = {
        "id_client_request": busy_request_id,
        "status": "TRAVELLING"
    }
    status_resp = client.patch(
        "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
    assert status_resp.status_code == 200

    # 3. Crear solicitud pendiente (otro cliente)
    client2_phone = "3004444459"
    client2_country_code = "+57"

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
        "fare_offered": 20000,  # Precio base ofrecido por el cliente
        "pickup_description": "Cerca del destino del viaje actual",
        "destination_description": "Destino cercano",
        "pickup_lat": 4.702468,  # Cerca del destino del viaje actual
        "pickup_lng": -74.109776,
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
        "id_driver": driver_id,
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

    # 5. Conductor hace oferta de precio (mayor al precio base)
    offer_data = {
        "client_request_id": pending_request_id,
        "offered_price": 25000  # Mayor al precio base de 20000
    }
    offer_resp = client.post(
        "/drivers/pending-request/offer-price", json=offer_data, headers=driver_headers)
    assert offer_resp.status_code == 200
    offer_data_resp = offer_resp.json()
    assert offer_data_resp["success"] is True
    assert offer_data_resp["message"] == "Oferta de precio enviada exitosamente"

    # 6. Verificar que la oferta se guardó
    detail_resp_after_offer = client.get(
        f"/client-request/{pending_request_id}", headers=driver_headers)
    assert detail_resp_after_offer.status_code == 200
    detail_data_after_offer = detail_resp_after_offer.json()
    assert detail_data_after_offer["negotiated_price"] == 25000

    print("✅ Test completado: Negociación exitosa de precios")


def test_price_negotiation_invalid_price():
    """
    Test que verifica que no se puede hacer una oferta menor al precio base.
    """
    print("\n🔄 Test: Validación de precio mínimo en negociación...")

    # 1. Crear conductor ocupado con viaje activo
    driver_phone = "3010000008"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 2. Crear solicitud para ocupar al conductor
    client_phone = "3004444460"
    client_country_code = "+57"

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
        "id_driver": driver_id,
        "fare_assigned": 15000
    }
    assign_busy_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_busy_data, headers=client_headers)
    assert assign_busy_resp.status_code == 200

    status_data = {
        "id_client_request": busy_request_id,
        "status": "TRAVELLING"
    }
    status_resp = client.patch(
        "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
    assert status_resp.status_code == 200

    # 3. Crear solicitud pendiente
    client2_phone = "3004444461"
    client2_country_code = "+57"

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
        "pickup_lat": 4.702468,
        "pickup_lng": -74.109776,
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
        "id_driver": driver_id,
        "fare_assigned": 20000
    }
    assign_pending_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_pending_data, headers=client2_headers)
    assert assign_pending_resp.status_code == 200

    # 5. Intentar hacer oferta con precio menor al base (debería fallar)
    offer_data = {
        "client_request_id": pending_request_id,
        "offered_price": 18000  # Menor al precio base de 20000
    }
    offer_resp = client.post(
        "/drivers/pending-request/offer-price", json=offer_data, headers=driver_headers)
    assert offer_resp.status_code == 400
    offer_data_resp = offer_resp.json()
    assert "precio" in offer_data_resp["detail"].lower()
    assert "menor" in offer_data_resp["detail"].lower()

    print("✅ Test completado: Validación de precio mínimo")


def test_complete_pending_request_with_negotiated_price():
    """
    Test que verifica completar una solicitud pendiente con precio negociado.
    """
    print("\n🔄 Test: Completar solicitud pendiente con precio negociado...")

    # 1. Crear conductor ocupado con viaje activo
    driver_phone = "3010000009"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 2. Crear solicitud para ocupar al conductor
    client_phone = "3004444462"
    client_country_code = "+57"

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
        "id_driver": driver_id,
        "fare_assigned": 15000
    }
    assign_busy_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_busy_data, headers=client_headers)
    assert assign_busy_resp.status_code == 200

    status_data = {
        "id_client_request": busy_request_id,
        "status": "TRAVELLING"
    }
    status_resp = client.patch(
        "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
    assert status_resp.status_code == 200

    # 3. Crear solicitud pendiente
    client2_phone = "3004444463"
    client2_country_code = "+57"

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
        "pickup_lat": 4.702468,
        "pickup_lng": -74.109776,
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
        "id_driver": driver_id,
        "fare_assigned": 20000
    }
    assign_pending_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_pending_data, headers=client2_headers)
    assert assign_pending_resp.status_code == 200

    # 5. Conductor hace oferta de precio
    offer_data = {
        "client_request_id": pending_request_id,
        "offered_price": 25000
    }
    offer_resp = client.post(
        "/drivers/pending-request/offer-price", json=offer_data, headers=driver_headers)
    assert offer_resp.status_code == 200

    # 6. Completar solicitud pendiente con precio negociado
    complete_data = {
        "client_request_id": pending_request_id,
        "negotiated_price": 25000
    }
    complete_resp = client.post(
        "/drivers/pending-request/complete", json=complete_data, headers=driver_headers)
    assert complete_resp.status_code == 200
    complete_data_resp = complete_resp.json()
    assert complete_data_resp["success"] is True

    # 7. Verificar que la solicitud se completó correctamente
    detail_resp = client.get(
        f"/client-request/{pending_request_id}", headers=driver_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["status"] == str(StatusEnum.ACCEPTED)
    assert detail_data["negotiated_price"] == 25000

    print("✅ Test completado: Completar solicitud con precio negociado")


def test_complete_pending_request_without_negotiated_price():
    """
    Test que verifica completar una solicitud pendiente sin precio negociado.
    """
    print("\n🔄 Test: Completar solicitud pendiente sin precio negociado...")

    # 1. Crear conductor ocupado con viaje activo
    driver_phone = "3010000010"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 2. Crear solicitud para ocupar al conductor
    client_phone = "3004444464"
    client_country_code = "+57"

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
        "id_driver": driver_id,
        "fare_assigned": 15000
    }
    assign_busy_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_busy_data, headers=client_headers)
    assert assign_busy_resp.status_code == 200

    status_data = {
        "id_client_request": busy_request_id,
        "status": "TRAVELLING"
    }
    status_resp = client.patch(
        "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
    assert status_resp.status_code == 200

    # 3. Crear solicitud pendiente
    client2_phone = "3004444465"
    client2_country_code = "+57"

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
        "pickup_lat": 4.702468,
        "pickup_lng": -74.109776,
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
        "id_driver": driver_id,
        "fare_assigned": 20000
    }
    assign_pending_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_pending_data, headers=client2_headers)
    assert assign_pending_resp.status_code == 200

    # 5. Completar solicitud pendiente sin precio negociado
    complete_data = {
        "client_request_id": pending_request_id
    }
    complete_resp = client.post(
        "/drivers/pending-request/complete", json=complete_data, headers=driver_headers)
    assert complete_resp.status_code == 200
    complete_data_resp = complete_resp.json()
    assert complete_data_resp["success"] is True

    # 6. Verificar que la solicitud se completó correctamente
    detail_resp = client.get(
        f"/client-request/{pending_request_id}", headers=driver_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["status"] == str(StatusEnum.ACCEPTED)
    assert detail_data["negotiated_price"] is None  # Sin precio negociado

    print("✅ Test completado: Completar solicitud sin precio negociado")
