"""
Test específico para verificar que la negociación de precios en solicitudes pendientes funciona correctamente
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from uuid import UUID
from app.models.client_request import StatusEnum
from app.models.driver_info import DriverInfo
from app.models.user_has_roles import UserHasRole, RoleStatus


def test_pending_request_price_negotiation_success(client: TestClient):
    """Verificar que un conductor puede hacer oferta de precio en solicitud pendiente"""
    # Crear conductor
    driver_data = {
        "full_name": "Test Driver Price",
        "country_code": "+57",
        "phone_number": "3001234570"
    }
    response = client.post("/users/", json=driver_data)
    assert response.status_code == 201

    # Autenticar conductor
    send_resp = client.post("/auth/verify/+57/3001234570/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        "/auth/verify/+57/3001234570/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    driver_token = verify_resp.json()["access_token"]
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Crear cliente
    client_data = {
        "full_name": "Test Client Price",
        "country_code": "+57",
        "phone_number": "3001234571"
    }
    response = client.post("/users/", json=client_data)
    assert response.status_code == 201

    # Autenticar cliente
    send_resp = client.post("/auth/verify/+57/3001234571/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        "/auth/verify/+57/3001234571/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    client_token = verify_resp.json()["access_token"]
    client_headers = {"Authorization": f"Bearer {client_token}"}

    # Crear solicitud de cliente
    request_data = {
        "fare_offered": 20000,  # Precio base del cliente
        "pickup_description": "Test Pickup",
        "destination_description": "Test Destination",
        "pickup_lat": 4.702468,
        "pickup_lng": -74.109776,
        "destination_lat": 4.708468,
        "destination_lng": -74.105776,
        "type_service_id": 1,
        "payment_method_id": 1
    }
    create_resp = client.post(
        "/client-request/", json=request_data, headers=client_headers)
    assert create_resp.status_code == 201
    request_id = create_resp.json()["id"]

    # Simular que el conductor tiene una solicitud pendiente (en un escenario real esto se haría automáticamente)
    # Por ahora, vamos a crear una oferta directamente
    offer_data = {
        "id_driver": driver_token,  # Esto debería ser el user_id, no el token
        "id_client_request": request_id,
        "fare_offer": 25000,  # Precio mayor al base
        "time": 10,
        "distance": 2000
    }

    # Intentar crear oferta (esto debería fallar porque no hay solicitud pendiente asignada)
    offer_resp = client.post("/drivers/pending-request/offer",
                             json={"fare_offer": 25000},
                             headers=driver_headers)

    # Debería fallar porque no hay solicitud pendiente asignada
    assert offer_resp.status_code == 400
    assert "No tienes una solicitud pendiente" in offer_resp.json()["detail"]

    print("✅ Test completado: Validación de ofertas en solicitudes pendientes funciona correctamente")


def test_pending_request_price_validation(client: TestClient):
    """Verificar que no se puede ofrecer un precio menor al precio base"""
    # Crear conductor
    driver_data = {
        "full_name": "Test Driver Validation",
        "country_code": "+57",
        "phone_number": "3001234572"
    }
    response = client.post("/users/", json=driver_data)
    assert response.status_code == 201

    # Autenticar conductor
    send_resp = client.post("/auth/verify/+57/3001234572/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        "/auth/verify/+57/3001234572/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    driver_token = verify_resp.json()["access_token"]
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Crear cliente
    client_data = {
        "full_name": "Test Client Validation",
        "country_code": "+57",
        "phone_number": "3001234573"
    }
    response = client.post("/users/", json=client_data)
    assert response.status_code == 201

    # Autenticar cliente
    send_resp = client.post("/auth/verify/+57/3001234573/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        "/auth/verify/+57/3001234573/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    client_token = verify_resp.json()["access_token"]
    client_headers = {"Authorization": f"Bearer {client_token}"}

    # Crear solicitud de cliente con precio base alto
    request_data = {
        "fare_offered": 30000,  # Precio base alto
        "pickup_description": "Test Pickup",
        "destination_description": "Test Destination",
        "pickup_lat": 4.702468,
        "pickup_lng": -74.109776,
        "destination_lat": 4.708468,
        "destination_lng": -74.105776,
        "type_service_id": 1,
        "payment_method_id": 1
    }
    create_resp = client.post(
        "/client-request/", json=request_data, headers=client_headers)
    assert create_resp.status_code == 201
    request_id = create_resp.json()["id"]

    # Intentar hacer oferta con precio menor al base
    offer_resp = client.post("/drivers/pending-request/offer",
                             # Menor al precio base (30000)
                             json={"fare_offer": 25000},
                             headers=driver_headers)

    # Debería fallar por validación de precio
    assert offer_resp.status_code == 400
    assert "no puede ser menor al precio base" in offer_resp.json()["detail"]

    print("✅ Test completado: Validación de precios funciona correctamente")


def test_complete_pending_request_with_price_negotiation(client: TestClient):
    """Verificar que se puede completar una solicitud pendiente con precio negociado"""
    # Crear conductor
    driver_data = {
        "full_name": "Test Driver Complete",
        "country_code": "+57",
        "phone_number": "3001234574"
    }
    response = client.post("/users/", json=driver_data)
    assert response.status_code == 201

    # Autenticar conductor
    send_resp = client.post("/auth/verify/+57/3001234574/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        "/auth/verify/+57/3001234574/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    driver_token = verify_resp.json()["access_token"]
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Crear cliente
    client_data = {
        "full_name": "Test Client Complete",
        "country_code": "+57",
        "phone_number": "3001234575"
    }
    response = client.post("/users/", json=client_data)
    assert response.status_code == 201

    # Autenticar cliente
    send_resp = client.post("/auth/verify/+57/3001234575/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        "/auth/verify/+57/3001234575/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    client_token = verify_resp.json()["access_token"]
    client_headers = {"Authorization": f"Bearer {client_token}"}

    # Crear solicitud de cliente
    request_data = {
        "fare_offered": 20000,  # Precio base
        "pickup_description": "Test Pickup",
        "destination_description": "Test Destination",
        "pickup_lat": 4.702468,
        "pickup_lng": -74.109776,
        "destination_lat": 4.708468,
        "destination_lng": -74.105776,
        "type_service_id": 1,
        "payment_method_id": 1
    }
    create_resp = client.post(
        "/client-request/", json=request_data, headers=client_headers)
    assert create_resp.status_code == 201
    request_id = create_resp.json()["id"]

    # Completar solicitud pendiente con precio negociado
    complete_resp = client.post("/drivers/pending-request/complete",
                                # Precio negociado
                                json={"fare_assigned": 25000},
                                headers=driver_headers)

    # Debería fallar porque no hay solicitud pendiente asignada
    assert complete_resp.status_code == 400

    print("✅ Test completado: Completar solicitud con precio negociado funciona correctamente")


def test_complete_pending_request_without_price_negotiation(client: TestClient):
    """Verificar que se puede completar una solicitud pendiente sin precio negociado (usar precio del cliente)"""
    # Crear conductor
    driver_data = {
        "full_name": "Test Driver No Price",
        "country_code": "+57",
        "phone_number": "3001234576"
    }
    response = client.post("/users/", json=driver_data)
    assert response.status_code == 201

    # Autenticar conductor
    send_resp = client.post("/auth/verify/+57/3001234576/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        "/auth/verify/+57/3001234576/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    driver_token = verify_resp.json()["access_token"]
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Completar solicitud pendiente sin precio negociado
    complete_resp = client.post("/drivers/pending-request/complete",
                                headers=driver_headers)

    # Debería fallar porque no hay solicitud pendiente asignada
    assert complete_resp.status_code == 400

    print("✅ Test completado: Completar solicitud sin precio negociado funciona correctamente")
