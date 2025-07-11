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
from app.test.test_drivers import create_and_approve_driver


def test_pending_request_price_negotiation_success(client: TestClient):
    """Verificar que un conductor puede hacer oferta de precio en solicitud pendiente"""
    import traceback

    print("\n🔍 DEBUG: Iniciando test_pending_request_price_negotiation_success")

    # Crear conductor completo usando la función helper
    driver_phone = "3001234570"
    driver_country_code = "+57"
    print(f"🔍 DEBUG: Creando conductor con phone={driver_phone}")

    try:
        driver_token, driver_id = create_and_approve_driver(
            client, driver_phone, driver_country_code)
        print(f"✅ DEBUG: Conductor creado - driver_id={driver_id}")
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Crear cliente
        client_data = {
            "full_name": "Test Client Price",
            "country_code": "+57",
            "phone_number": "3001234571"
        }
        print(f"🔍 DEBUG: Creando cliente...")
        response = client.post("/users/", json=client_data)
        print(f"   - Status: {response.status_code}")
        print(f"   - Response: {response.text}")
        assert response.status_code == 201

        # Autenticar cliente
        print(f"🔍 DEBUG: Autenticando cliente...")
        send_resp = client.post("/auth/verify/+57/3001234571/send")
        print(f"   - Send Status: {send_resp.status_code}")
        print(f"   - Send Response: {send_resp.text}")
        assert send_resp.status_code == 201
        code = send_resp.json()["message"].split()[-1]
        print(f"   - Code: {code}")

        verify_resp = client.post(
            "/auth/verify/+57/3001234571/code",
            json={"code": code}
        )
        print(f"   - Verify Status: {verify_resp.status_code}")
        print(f"   - Verify Response: {verify_resp.text}")
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
        print(f"🔍 DEBUG: Creando solicitud de cliente...")
        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        print(f"   - Create Status: {create_resp.status_code}")
        print(f"   - Create Response: {create_resp.text}")
        assert create_resp.status_code == 201
        request_id = create_resp.json()["id"]
        print(f"   - Request ID: {request_id}")

        # Asignar la solicitud pendiente al conductor
        print(f"🔍 DEBUG: Intentando aceptar solicitud pendiente...")
        print(
            f"   - URL: /drivers/pending-request/accept?client_request_id={request_id}")
        print(f"   - Driver Headers: {driver_headers}")

        accept_resp = client.post(f"/drivers/pending-request/accept?client_request_id={request_id}",
                                  headers=driver_headers)
        print(f"   - Accept Status: {accept_resp.status_code}")
        print(f"   - Accept Response: {accept_resp.text}")

        if accept_resp.status_code != 200:
            print(f"❌ ERROR: Falló al aceptar solicitud pendiente")
            print(f"   - Status Code: {accept_resp.status_code}")
            print(f"   - Response Body: {accept_resp.text}")
            print(f"   - Traceback completo:")
            traceback.print_exc()

        assert accept_resp.status_code == 200

        # Ahora el conductor puede hacer una oferta de precio
        print(f"🔍 DEBUG: Intentando hacer oferta de precio...")
        offer_resp = client.post("/drivers/pending-request/offer?fare_offer=25000",
                                 headers=driver_headers)
        print(f"   - Offer Status: {offer_resp.status_code}")
        print(f"   - Offer Response: {offer_resp.text}")

        # La oferta debería crearse exitosamente
        assert offer_resp.status_code == 200
        offer_data = offer_resp.json()
        assert "message" in offer_data
        assert "offer_id" in offer_data
        assert offer_data["fare_offer"] == 25000

        print("✅ Test completado: Validación de ofertas en solicitudes pendientes funciona correctamente")

    except Exception as e:
        print(f"❌ ERROR en test: {e}")
        print(f"   - Traceback completo:")
        traceback.print_exc()
        raise


def test_pending_request_price_validation(client: TestClient):
    """Verificar que no se puede ofrecer un precio menor al precio base"""
    import traceback

    print("\n🔍 DEBUG: Iniciando test_pending_request_price_validation")

    try:
        # Crear conductor completo usando la función helper
        driver_phone = "3001234572"
        driver_country_code = "+57"
        print(f"🔍 DEBUG: Creando conductor con phone={driver_phone}")

        driver_token, driver_id = create_and_approve_driver(
            client, driver_phone, driver_country_code)
        print(f"✅ DEBUG: Conductor creado - driver_id={driver_id}")
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Crear cliente
        client_data = {
            "full_name": "Test Client Validation",
            "country_code": "+57",
            "phone_number": "3001234573"
        }
        print(f"🔍 DEBUG: Creando cliente...")
        response = client.post("/users/", json=client_data)
        print(f"   - Status: {response.status_code}")
        assert response.status_code == 201

        # Autenticar cliente
        print(f"🔍 DEBUG: Autenticando cliente...")
        send_resp = client.post("/auth/verify/+57/3001234573/send")
        print(f"   - Send Status: {send_resp.status_code}")
        assert send_resp.status_code == 201
        code = send_resp.json()["message"].split()[-1]
        print(f"   - Code: {code}")

        verify_resp = client.post(
            "/auth/verify/+57/3001234573/code",
            json={"code": code}
        )
        print(f"   - Verify Status: {verify_resp.status_code}")
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
        print(f"🔍 DEBUG: Creando solicitud de cliente...")
        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        print(f"   - Create Status: {create_resp.status_code}")
        print(f"   - Create Response: {create_resp.text}")
        assert create_resp.status_code == 201
        request_id = create_resp.json()["id"]
        print(f"   - Request ID: {request_id}")

        # Asignar la solicitud pendiente al conductor
        print(f"🔍 DEBUG: Intentando aceptar solicitud pendiente...")
        accept_resp = client.post(f"/drivers/pending-request/accept?client_request_id={request_id}",
                                  headers=driver_headers)
        print(f"   - Accept Status: {accept_resp.status_code}")
        print(f"   - Accept Response: {accept_resp.text}")
        assert accept_resp.status_code == 200

        # Intentar hacer oferta con precio menor al base
        print(f"🔍 DEBUG: Intentando hacer oferta con precio menor al base...")
        offer_resp = client.post("/drivers/pending-request/offer?fare_offer=25000",
                                 # Menor al precio base (30000)
                                 headers=driver_headers)
        print(f"   - Offer Status: {offer_resp.status_code}")
        print(f"   - Offer Response: {offer_resp.text}")

        # Debería fallar por validación de precio
        assert offer_resp.status_code == 400
        assert "no puede ser menor al precio base" in offer_resp.json()[
            "detail"]

        print("✅ Test completado: Validación de precios funciona correctamente")

    except Exception as e:
        print(f"❌ ERROR en test: {e}")
        print(f"   - Traceback completo:")
        traceback.print_exc()
        raise


def test_complete_pending_request_with_price_negotiation(client: TestClient):
    """Verificar que se puede completar una solicitud pendiente con precio negociado"""
    import traceback

    print("\n🔍 DEBUG: Iniciando test_complete_pending_request_with_price_negotiation")

    try:
        # Crear conductor completo usando la función helper
        driver_phone = "3001234574"
        driver_country_code = "+57"
        print(f"🔍 DEBUG: Creando conductor con phone={driver_phone}")

        driver_token, driver_id = create_and_approve_driver(
            client, driver_phone, driver_country_code)
        print(f"✅ DEBUG: Conductor creado - driver_id={driver_id}")
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Crear cliente
        client_data = {
            "full_name": "Test Client Complete",
            "country_code": "+57",
            "phone_number": "3001234575"
        }
        print(f"🔍 DEBUG: Creando cliente...")
        response = client.post("/users/", json=client_data)
        print(f"   - Status: {response.status_code}")
        assert response.status_code == 201

        # Autenticar cliente
        print(f"🔍 DEBUG: Autenticando cliente...")
        send_resp = client.post("/auth/verify/+57/3001234575/send")
        print(f"   - Send Status: {send_resp.status_code}")
        assert send_resp.status_code == 201
        code = send_resp.json()["message"].split()[-1]
        print(f"   - Code: {code}")

        verify_resp = client.post(
            "/auth/verify/+57/3001234575/code",
            json={"code": code}
        )
        print(f"   - Verify Status: {verify_resp.status_code}")
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
        print(f"🔍 DEBUG: Creando solicitud de cliente...")
        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        print(f"   - Create Status: {create_resp.status_code}")
        print(f"   - Create Response: {create_resp.text}")
        assert create_resp.status_code == 201
        request_id = create_resp.json()["id"]
        print(f"   - Request ID: {request_id}")

        # Asignar la solicitud pendiente al conductor
        print(f"🔍 DEBUG: Intentando aceptar solicitud pendiente...")
        accept_resp = client.post(f"/drivers/pending-request/accept?client_request_id={request_id}",
                                  headers=driver_headers)
        print(f"   - Accept Status: {accept_resp.status_code}")
        print(f"   - Accept Response: {accept_resp.text}")
        assert accept_resp.status_code == 200

        # Hacer oferta de precio
        print(f"🔍 DEBUG: Haciendo oferta de precio...")
        offer_resp = client.post("/drivers/pending-request/offer?fare_offer=25000",
                                 headers=driver_headers)
        print(f"   - Offer Status: {offer_resp.status_code}")
        print(f"   - Offer Response: {offer_resp.text}")
        assert offer_resp.status_code == 200

        # Completar solicitud pendiente
        print(f"🔍 DEBUG: Completando solicitud pendiente...")
        complete_resp = client.post("/drivers/pending-request/complete",
                                    headers=driver_headers)
        print(f"   - Complete Status: {complete_resp.status_code}")
        print(f"   - Complete Response: {complete_resp.text}")

        # Debería completarse exitosamente
        assert complete_resp.status_code == 200

        print("✅ Test completado: Completar solicitud con precio negociado funciona correctamente")

    except Exception as e:
        print(f"❌ ERROR en test: {e}")
        print(f"   - Traceback completo:")
        traceback.print_exc()
        raise


def test_complete_pending_request_without_price_negotiation(client: TestClient):
    """Verificar que se puede completar una solicitud pendiente sin precio negociado (usar precio del cliente)"""
    import traceback

    print("\n🔍 DEBUG: Iniciando test_complete_pending_request_without_price_negotiation")

    try:
        # Crear conductor completo usando la función helper
        driver_phone = "3001234576"
        driver_country_code = "+57"
        print(f"🔍 DEBUG: Creando conductor con phone={driver_phone}")

        driver_token, driver_id = create_and_approve_driver(
            client, driver_phone, driver_country_code)
        print(f"✅ DEBUG: Conductor creado - driver_id={driver_id}")
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Crear cliente
        client_data = {
            "full_name": "Test Client No Price",
            "country_code": "+57",
            "phone_number": "3001234577"
        }
        print(f"🔍 DEBUG: Creando cliente...")
        response = client.post("/users/", json=client_data)
        print(f"   - Status: {response.status_code}")
        assert response.status_code == 201

        # Autenticar cliente
        print(f"🔍 DEBUG: Autenticando cliente...")
        send_resp = client.post("/auth/verify/+57/3001234577/send")
        print(f"   - Send Status: {send_resp.status_code}")
        assert send_resp.status_code == 201
        code = send_resp.json()["message"].split()[-1]
        print(f"   - Code: {code}")

        verify_resp = client.post(
            "/auth/verify/+57/3001234577/code",
            json={"code": code}
        )
        print(f"   - Verify Status: {verify_resp.status_code}")
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
        print(f"🔍 DEBUG: Creando solicitud de cliente...")
        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        print(f"   - Create Status: {create_resp.status_code}")
        print(f"   - Create Response: {create_resp.text}")
        assert create_resp.status_code == 201
        request_id = create_resp.json()["id"]
        print(f"   - Request ID: {request_id}")

        # Asignar la solicitud pendiente al conductor
        print(f"🔍 DEBUG: Intentando aceptar solicitud pendiente...")
        accept_resp = client.post(f"/drivers/pending-request/accept?client_request_id={request_id}",
                                  headers=driver_headers)
        print(f"   - Accept Status: {accept_resp.status_code}")
        print(f"   - Accept Response: {accept_resp.text}")
        assert accept_resp.status_code == 200

        # Completar solicitud pendiente sin precio negociado
        print(f"🔍 DEBUG: Completando solicitud pendiente sin precio negociado...")
        complete_resp = client.post("/drivers/pending-request/complete",
                                    headers=driver_headers)
        print(f"   - Complete Status: {complete_resp.status_code}")
        print(f"   - Complete Response: {complete_resp.text}")

        # Debería completarse exitosamente usando el precio del cliente
        assert complete_resp.status_code == 200

        print("✅ Test completado: Completar solicitud sin precio negociado funciona correctamente")

    except Exception as e:
        print(f"❌ ERROR en test: {e}")
        print(f"   - Traceback completo:")
        traceback.print_exc()
        raise
