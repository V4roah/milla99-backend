from fastapi.testclient import TestClient
from app.main import app
from app.test.test_drivers import create_and_approve_driver
from app.models.client_request import StatusEnum
from datetime import datetime, timezone, timedelta
from app.models.project_settings import ProjectSettings
from sqlmodel import Session
from app.core.db import engine
from uuid import UUID

client = TestClient(app)


def test_create_client_request():
    # Datos del cliente
    phone_number = "3004444456"
    country_code = "+57"

    # Enviar código de verificación
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]

    # Verificar el código y obtener el token
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Datos de la solicitud
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
    response = client.post(
        "/client-request/", json=request_data, headers=headers)
    assert response.status_code == 201
    assert "id" in response.json()


def test_assign_driver_to_client_request():
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)

    # Asignar el conductor a la solicitud
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True


def test_driver_changes_status_to_ontheway():
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Asignar el conductor a la solicitud
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # Cambiar el estado a ON_THE_WAY
    status_data = {
        "id_client_request": client_request_id,
        "status": "ON_THE_WAY"
    }
    status_resp = client.patch(
        "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["success"] is True

    # Consultar el detalle de la solicitud y verificar el estado
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=driver_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == str(StatusEnum.ON_THE_WAY)


def test_driver_changes_status_to_arrived():
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Asignar el conductor a la solicitud
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # Cambiar el estado a ON_THE_WAY
    status_data_ontheway = {
        "id_client_request": client_request_id,
        "status": "ON_THE_WAY"
    }
    status_resp_ontheway = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_ontheway, headers=driver_headers)
    assert status_resp_ontheway.status_code == 200
    assert status_resp_ontheway.json()["success"] is True

    # Cambiar el estado a ARRIVED
    status_data_arrived = {
        "id_client_request": client_request_id,
        "status": "ARRIVED"
    }
    status_resp_arrived = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_arrived, headers=driver_headers)
    assert status_resp_arrived.status_code == 200
    assert status_resp_arrived.json()["success"] is True

    # Consultar el detalle de la solicitud y verificar el estado
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=driver_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == str(StatusEnum.ARRIVED)


def test_driver_changes_status_to_travelling():
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Asignar el conductor a la solicitud
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # Cambiar el estado a ON_THE_WAY
    status_data_ontheway = {
        "id_client_request": client_request_id,
        "status": "ON_THE_WAY"
    }
    status_resp_ontheway = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_ontheway, headers=driver_headers)
    assert status_resp_ontheway.status_code == 200
    assert status_resp_ontheway.json()["success"] is True

    # Cambiar el estado a ARRIVED
    status_data_arrived = {
        "id_client_request": client_request_id,
        "status": "ARRIVED"
    }
    status_resp_arrived = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_arrived, headers=driver_headers)
    assert status_resp_arrived.status_code == 200
    assert status_resp_arrived.json()["success"] is True

    # Cambiar el estado a TRAVELLING
    status_data_travelling = {
        "id_client_request": client_request_id,
        "status": "TRAVELLING"
    }
    status_resp_travelling = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_travelling, headers=driver_headers)
    assert status_resp_travelling.status_code == 200
    assert status_resp_travelling.json()["success"] is True

    # Consultar el detalle de la solicitud y verificar el estado
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=driver_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == str(StatusEnum.TRAVELLING)


def test_driver_changes_status_to_finished():
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Asignar el conductor a la solicitud
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # Cambiar el estado a ON_THE_WAY
    status_data_ontheway = {
        "id_client_request": client_request_id,
        "status": "ON_THE_WAY"
    }
    status_resp_ontheway = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_ontheway, headers=driver_headers)
    assert status_resp_ontheway.status_code == 200
    assert status_resp_ontheway.json()["success"] is True

    # Cambiar el estado a ARRIVED
    status_data_arrived = {
        "id_client_request": client_request_id,
        "status": "ARRIVED"
    }
    status_resp_arrived = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_arrived, headers=driver_headers)
    assert status_resp_arrived.status_code == 200
    assert status_resp_arrived.json()["success"] is True

    # Cambiar el estado a TRAVELLING
    status_data_travelling = {
        "id_client_request": client_request_id,
        "status": "TRAVELLING"
    }
    status_resp_travelling = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_travelling, headers=driver_headers)
    assert status_resp_travelling.status_code == 200
    assert status_resp_travelling.json()["success"] is True

    # Cambiar el estado a FINISHED
    status_data_finished = {
        "id_client_request": client_request_id,
        "status": "FINISHED"
    }
    status_resp_finished = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_finished, headers=driver_headers)
    assert status_resp_finished.status_code == 200
    assert status_resp_finished.json()["success"] is True

    # Consultar el detalle de la solicitud y verificar el estado
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=driver_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == str(StatusEnum.FINISHED)


def test_driver_changes_status_to_paid():
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Asignar el conductor a la solicitud
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # Cambiar el estado a ON_THE_WAY
    status_data_ontheway = {
        "id_client_request": client_request_id,
        "status": "ON_THE_WAY"
    }
    status_resp_ontheway = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_ontheway, headers=driver_headers)
    assert status_resp_ontheway.status_code == 200
    assert status_resp_ontheway.json()["success"] is True

    # Cambiar el estado a ARRIVED
    status_data_arrived = {
        "id_client_request": client_request_id,
        "status": "ARRIVED"
    }
    status_resp_arrived = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_arrived, headers=driver_headers)
    assert status_resp_arrived.status_code == 200
    assert status_resp_arrived.json()["success"] is True

    # Cambiar el estado a TRAVELLING
    status_data_travelling = {
        "id_client_request": client_request_id,
        "status": "TRAVELLING"
    }
    status_resp_travelling = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_travelling, headers=driver_headers)
    assert status_resp_travelling.status_code == 200
    assert status_resp_travelling.json()["success"] is True

    # Cambiar el estado a FINISHED
    status_data_finished = {
        "id_client_request": client_request_id,
        "status": "FINISHED"
    }
    status_resp_finished = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_finished, headers=driver_headers)
    assert status_resp_finished.status_code == 200
    assert status_resp_finished.json()["success"] is True

    # Cambiar el estado a PAID
    status_data_paid = {
        "id_client_request": client_request_id,
        "status": "PAID"
    }
    status_resp_paid = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_paid, headers=driver_headers)
    assert status_resp_paid.status_code == 200
    assert status_resp_paid.json()["success"] is True

    # Consultar el detalle de la solicitud y verificar el estado
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=driver_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == str(StatusEnum.PAID)


def test_driver_cannot_skip_states_to_finished():
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Crear y aprobar conductor
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # Asignar el conductor a la solicitud
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # Intentar saltar de ACCEPTED a FINISHED
    status_data_finished = {
        "id_client_request": client_request_id,
        "status": "FINISHED"
    }
    status_resp_finished = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_finished, headers=driver_headers)
    assert status_resp_finished.status_code == 400
    assert "Transición de estado no permitida" in status_resp_finished.json()[
        "detail"]


def test_client_cancel_request():
    """
    Test básico para verificar que el endpoint de cancelación del cliente funciona.
    """
    # Datos del cliente
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

    # Crear solicitud de cliente
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

    # Intentar cancelar la solicitud
    cancel_data = {
        "id_client_request": client_request_id
    }
    cancel_resp = client.patch(
        "/client-request/clientCanceled", json=cancel_data, headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["success"] is True
    assert "Solicitud cancelada" in cancel_resp.json()["message"]

    # Verificar que el estado de la solicitud cambió a CANCELLED
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=headers)
    assert detail_resp.status_code == 200

    # Imprimir información para debug
    print("\n=== DEBUG INFO ===")
    print(f"Status from API: {detail_resp.json()['status']}")
    print(f"Type of status: {type(detail_resp.json()['status'])}")
    print(f"StatusEnum.CANCELLED value: {StatusEnum.CANCELLED}")
    print(f"StatusEnum.CANCELLED type: {type(StatusEnum.CANCELLED)}")
    print("=================\n")

    # Comparar con el valor del enum
    assert detail_resp.json()["status"] == str(StatusEnum.CANCELLED)


def test_client_request_timeout():
    """
    Verifica que las solicitudes expiren después del tiempo configurado en project_settings.

    Flujo del test:
    1. Preparación del Cliente:
       - Se usa un número de teléfono específico (3004444456)
       - Se envía código de verificación
       - Se verifica el código para obtener el token de autenticación
       - Se guardan los headers con el token para futuras peticiones

    2. Creación de la Solicitud:
       - Se crea una solicitud de viaje con datos específicos:
         * Tarifa ofrecida: 20000
         * Origen: Suba Bogotá (lat: 4.718136, lng: -74.073170)
         * Destino: Santa Rosita Engativa (lat: 4.702468, lng: -74.109776)
         * Tipo de servicio: Car (id: 1)
         * Método de pago: Cash (id: 1)

    3. Preparación del Conductor:
       - Se crea y aprueba un conductor con:
         * Teléfono: 3010000005
         * Se procesa su selfie
         * Se crean sus documentos
         * Se obtiene su token de autenticación

    4. Creación y Verificación Inicial:
       - Se crea la solicitud de viaje
       - Se obtiene el ID de la solicitud y se convierte a UUID
       - Se verifica que la solicitud se creó exitosamente (status 201)

    5. Simulación del Timeout:
       - Se obtiene el timeout configurado en project_settings
       - Se actualiza manualmente el created_at de la solicitud en la base de datos
       - Se establece la fecha a (timeout_minutes + 1) minutos en el pasado

    6. Verificación del Timeout:
       - Se verifica que la solicitud ya no aparece en las solicitudes cercanas
       - Se hace una petición a /client-request/nearby con la posición del conductor
       - Se verifica que la solicitud no está en la respuesta

    7. Verificación del Estado:
       - Se verifica que la solicitud sigue existiendo en la base de datos
       - Se obtiene el detalle de la solicitud
       - Se verifica que:
         * El ID coincide
         * El estado sigue siendo CREATED
         * El tiempo transcurrido es mayor al timeout configurado

    Este test es importante porque asegura que el sistema maneja correctamente el timeout de las solicitudes, lo cual es crucial para:
    - No mostrar solicitudes antiguas a los conductores
    - Mantener un registro de todas las solicitudes
    - Permitir que los clientes puedan crear nuevas solicitudes si la anterior expiró
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

    # 2. Crear solicitud de cliente
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

    # 3. Crear y aprobar conductor para verificar nearby requests
    driver_phone = "3010000005"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 4. Crear la solicitud y verificar que está disponible
    create_resp = client.post(
        "/client-request/", json=request_data, headers=headers)
    assert create_resp.status_code == 201
    client_request_id = UUID(create_resp.json()["id"])  # Convertir a UUID

    # Actualizar manualmente el created_at en la base de datos
    with Session(engine) as session:
        from app.models.client_request import ClientRequest

        # Obtener el timeout configurado
        project_settings = session.query(ProjectSettings).first()
        assert project_settings is not None
        timeout_minutes = project_settings.request_timeout_minutes

        # Actualizar el created_at a hace más del timeout
        old_created_at = datetime.now(
            timezone.utc) - timedelta(minutes=timeout_minutes + 1)
        client_request = session.query(ClientRequest).filter(
            ClientRequest.id == client_request_id).first()
        assert client_request is not None
        client_request.created_at = old_created_at
        session.commit()

    # Verificar que la solicitud ya no aparece en nearby requests
    nearby_resp = client.get(
        "/client-request/nearby?driver_lat=4.718136&driver_lng=-74.073170",
        headers=driver_headers
    )
    assert nearby_resp.status_code == 200
    nearby_data = nearby_resp.json()
    assert len(nearby_data) == 0 or not any(
        req["id"] == str(client_request_id) for req in nearby_data)

    # Verificar que la solicitud sigue existiendo en la base de datos
    with Session(engine) as session:
        # Verificar que la solicitud existe pero está expirada
        detail_resp = client.get(
            f"/client-request/{client_request_id}", headers=headers)
        assert detail_resp.status_code == 200
        request_detail = detail_resp.json()
        assert request_detail["id"] == str(client_request_id)
        assert request_detail["status"] == str(StatusEnum.CREATED)

        # Verificar que el tiempo transcurrido es mayor al timeout
        created_at_str = request_detail["created_at"].replace("Z", "+00:00")
        created_at = datetime.fromisoformat(
            created_at_str).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = now - created_at
        assert time_diff.total_seconds() > timeout_minutes * 60


def test_nearby_requests_distance_filter():
    """
    Verifica que el filtrado por distancia de las solicitudes cercanas funciona correctamente y que cada solicitud contiene el campo fair_price con un valor válido.

    Flujo del test:
    1. Crear múltiples solicitudes en diferentes ubicaciones:
       - Solicitud 1: Cerca del conductor (dentro del radio)
       - Solicitud 2: Lejos del conductor (fuera del radio)
       - Solicitud 3: En el límite del radio

    2. Verificar que:
       - Solo aparecen las solicitudes dentro del radio configurado
       - Las solicitudes fuera del radio no aparecen
       - La distancia se calcula correctamente
       - Cada solicitud retornada contiene el campo fair_price y su valor es None o un número positivo
    """
    print("\n=== INICIANDO TEST DE FILTRADO POR DISTANCIA ===")

    # 1. Crear y autenticar conductor (será nuestro punto de referencia)
    driver_phone = "3010000005"
    driver_country_code = "+57"
    print(f"\n1. Creando conductor con teléfono {driver_phone}")
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}
    print(f"Conductor creado con ID: {driver_id}")

    # Posición del conductor (centro de Bogotá)
    driver_lat = 4.60971
    driver_lng = -74.08175
    print(f"Posición del conductor: lat={driver_lat}, lng={driver_lng}")

    # 2. Crear múltiples clientes y solicitudes en diferentes ubicaciones
    # Usamos teléfonos que no están en init_data.py
    requests_data = [
        {
            "phone": "3011111111",  # Cliente nuevo
            "name": "Juan Pérez",  # Nombre válido
            "location": {
                "pickup_lat": 4.60971,  # Mismo punto que el conductor
                "pickup_lng": -74.08175,
                "destination_lat": 4.702468,
                "destination_lng": -74.109776
            }
        },
        {
            "phone": "3011111112",  # Cliente nuevo
            "name": "María García",  # Nombre válido
            "location": {
                # Aproximadamente 15km al sur (fuera del radio)
                "pickup_lat": 4.45971,  # Cambiado de 4.50971 a 4.45971
                "pickup_lng": -74.08175,
                "destination_lat": 4.702468,
                "destination_lng": -74.109776
            }
        },
        {
            "phone": "3011111113",  # Cliente nuevo
            "name": "Carlos López",  # Nombre válido
            "location": {
                "pickup_lat": 4.65971,  # Aproximadamente 5km al norte
                "pickup_lng": -74.08175,
                "destination_lat": 4.702468,
                "destination_lng": -74.109776
            }
        }
    ]

    created_requests = []

    # Crear los clientes primero
    print("\n2. Creando clientes")
    for req_data in requests_data:
        print(f"\nCreando cliente con teléfono {req_data['phone']}")
        # Crear cliente usando el endpoint correcto
        client_data = {
            "full_name": req_data["name"],
            "country_code": driver_country_code,
            "phone_number": req_data["phone"]
        }
        create_resp = client.post("/users/", json=client_data)
        assert create_resp.status_code == 201, f"Error al crear cliente: {create_resp.text}"
        print(f"Cliente creado exitosamente")

    # Crear las solicitudes
    print("\n3. Creando solicitudes de clientes")
    for req_data in requests_data:
        print(f"\nCreando solicitud para cliente {req_data['phone']}")
        # Autenticar cliente
        send_resp = client.post(
            f"/auth/verify/{driver_country_code}/{req_data['phone']}/send")
        assert send_resp.status_code == 201, f"Error al enviar código: {send_resp.text}"
        # Obtener el código real del mensaje
        code = send_resp.json()["message"].split()[-1]

        # Verificar código usando el código real
        verify_resp = client.post(
            f"/auth/verify/{driver_country_code}/{req_data['phone']}/code",
            json={"code": code})
        assert verify_resp.status_code == 200, f"Error al verificar código: {verify_resp.text}"
        client_token = verify_resp.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Crear solicitud
        request_data = {
            "fare_offered": 20000,
            "pickup_description": "Test Location",
            "destination_description": "Test Destination",
            "pickup_lat": req_data["location"]["pickup_lat"],
            "pickup_lng": req_data["location"]["pickup_lng"],
            "destination_lat": req_data["location"]["destination_lat"],
            "destination_lng": req_data["location"]["destination_lng"],
            "type_service_id": 1,  # Car
            "payment_method_id": 1  # Cash
        }

        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        assert create_resp.status_code == 201, f"Error al crear solicitud: {create_resp.text}"
        request_id = create_resp.json()["id"]
        print(f"Solicitud creada con ID: {request_id}")

        created_requests.append({
            "id": request_id,
            "location": req_data["location"],
            "phone": req_data["phone"]
        })

    print(f"\nSolicitudes creadas: {len(created_requests)}")
    for req in created_requests:
        print(
            f"- ID: {req['id']}, Teléfono: {req['phone']}, Lat: {req['location']['pickup_lat']}")

    # 3. Verificar las solicitudes cercanas
    print("\n3. Consultando solicitudes cercanas")
    nearby_resp = client.get(
        f"/client-request/nearby?driver_lat={driver_lat}&driver_lng={driver_lng}",
        headers=driver_headers
    )
    assert nearby_resp.status_code == 200, f"Error al consultar nearby: {nearby_resp.text}"
    nearby_data = nearby_resp.json()

    print(f"\nSolicitudes cercanas encontradas: {len(nearby_data)}")
    for req in nearby_data:
        print(
            f"- ID: {req['id']}, Distancia: {req.get('distance', 'N/A')} metros")
        if req.get('distance') is not None:
            print(
                f"  Coordenadas: {req.get('pickup_position', {}).get('lat')}, {req.get('pickup_position', {}).get('lng')}")

    # 4. Verificar que solo aparecen las solicitudes dentro del radio
    print("\n4. Verificando filtrado por distancia")
    print(f"Radio máximo configurado: 5000 metros")

    # Filtrar solo las solicitudes que creamos en este test
    test_requests = [req for req in nearby_data if any(
        str(req["id"]) == str(created["id"]) for created in created_requests)]
    print(f"\nSolicitudes de test encontradas: {len(test_requests)}")
    for req in test_requests:
        print(
            f"- ID: {req['id']}, Distancia: {req.get('distance', 'N/A')} metros")
        if req.get('distance') is not None:
            print(
                f"  Coordenadas: {req.get('pickup_position', {}).get('lat')}, {req.get('pickup_position', {}).get('lng')}")
            print(
                f"  Diferencia de latitud con conductor: {abs(float(req.get('pickup_position', {}).get('lat', 0)) - driver_lat)} grados")

    # Verificar que tenemos al menos 2 solicitudes de test
    assert len(
        test_requests) >= 2, f"Se esperaban al menos 2 solicitudes de test, se encontraron {len(test_requests)}"

    # Verificar que las solicitudes que aparecen están dentro del radio
    for request in test_requests:
        print(f"\nVerificando solicitud {request['id']}")
        # Encontrar la solicitud original para comparar ubicaciones
        original_request = next(
            (r for r in created_requests if str(r["id"]) == str(request["id"])), None)
        assert original_request is not None, f"No se encontró la solicitud original para {request['id']}"

        # Verificar que la distancia es correcta
        distance = request.get("distance", 0)
        print(f"Distancia verificada: {distance} metros")
        assert distance >= 0, f"La distancia debe ser positiva, se obtuvo {distance}"
        assert distance <= 5000, f"La distancia debe ser menor a 5000 metros, se obtuvo {distance}"

        # Verificar que la solicitud que está en el mismo punto tiene distancia cercana a 0
        if original_request["location"]["pickup_lat"] == driver_lat and original_request["location"]["pickup_lng"] == driver_lng:
            assert distance < 1, f"La solicitud en el mismo punto debe tener distancia cercana a 0, se obtuvo {distance}"

    # 5. Verificar que la solicitud lejana no aparece
    print("\n5. Verificando que la solicitud lejana no aparece")
    far_request = next(
        (r for r in created_requests if r["location"]["pickup_lat"] == 4.45971), None)
    assert far_request is not None, "No se encontró la solicitud lejana"
    print(f"Solicitud lejana encontrada con ID: {far_request['id']}")
    print(
        f"Coordenadas de la solicitud lejana: {far_request['location']['pickup_lat']}, {far_request['location']['pickup_lng']}")
    print(
        f"Diferencia de latitud con conductor: {abs(far_request['location']['pickup_lat'] - driver_lat)} grados")
    assert not any(str(req["id"]) == str(far_request["id"]) for req in nearby_data), \
        f"La solicitud lejana {far_request['id']} apareció en nearby"
    print("Solicitud lejana correctamente filtrada")

    # 6. Verificar que las distancias son consistentes
    print("\n6. Verificando consistencia de distancias")
    same_point_request = next(
        (r for r in created_requests if r["location"]["pickup_lat"] == driver_lat), None)
    assert same_point_request is not None, "No se encontró la solicitud en el mismo punto"
    same_point_nearby = next(
        (req for req in nearby_data if str(req["id"]) == str(same_point_request["id"])), None)
    assert same_point_nearby is not None, "No se encontró la solicitud en nearby"
    assert same_point_nearby["distance"] < 100, \
        f"La distancia debería ser menor a 100m, es {same_point_nearby['distance']}"
    print(
        f"Distancia de solicitud en mismo punto: {same_point_nearby['distance']} metros")

    print("\n=== TEST DE FILTRADO POR DISTANCIA COMPLETADO EXITOSAMENTE ===")

    # Verificar que cada solicitud tiene el campo fair_price y que es válido
    for req in nearby_data:
        print("FAIR PRICE:", req["fair_price"])
        assert "fair_price" in req, "No se encontró el campo fair_price en la respuesta de nearby"
        # El precio justo debe ser None o un número positivo si se pudo calcular
        assert req["fair_price"] is None or req[
            "fair_price"] > 0, f"El fair_price no es válido: {req['fair_price']}"


def test_nearby_requests_service_type_filter():
    """
    Verifica que el filtrado por tipo de servicio de las solicitudes cercanas funciona correctamente.

    Flujo del test:
    1. Crear múltiples solicitudes con diferentes tipos de servicio:
       - Solicitud 1: Tipo Car (id: 1)
       - Solicitud 2: Tipo Motorcycle (id: 2)
       - Solicitud 3: Tipo Car (id: 1)

    2. Verificar que:
       - Solo aparecen las solicitudes del tipo de servicio que el conductor puede manejar
       - Las solicitudes de otros tipos de servicio no aparecen
       - El filtrado funciona correctamente junto con el filtrado por distancia
    """
    print("\n=== INICIANDO TEST DE FILTRADO POR TIPO DE SERVICIO ===")

    # 1. Crear y autenticar conductor (será nuestro punto de referencia)
    driver_phone = "3010000005"
    driver_country_code = "+57"
    print(f"\n1. Creando conductor con teléfono {driver_phone}")
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}
    print(f"Conductor creado con ID: {driver_id}")

    # Posición del conductor (centro de Bogotá)
    driver_lat = 4.60971
    driver_lng = -74.08175
    print(f"Posición del conductor: lat={driver_lat}, lng={driver_lng}")

    # 2. Crear múltiples clientes y solicitudes con diferentes tipos de servicio
    requests_data = [
        {
            "phone": "3011111114",  # Cliente nuevo
            "name": "Ana Martínez",
            "location": {
                "pickup_lat": 4.60971,  # Mismo punto que el conductor
                "pickup_lng": -74.08175,
                "destination_lat": 4.702468,
                "destination_lng": -74.109776
            },
            "type_service_id": 1  # Car
        },
        {
            "phone": "3011111115",  # Cliente nuevo
            "name": "Pedro Rodríguez",
            "location": {
                "pickup_lat": 4.61971,  # Cerca del conductor
                "pickup_lng": -74.08175,
                "destination_lat": 4.702468,
                "destination_lng": -74.109776
            },
            "type_service_id": 2  # Motorcycle
        },
        {
            "phone": "3011111116",  # Cliente nuevo
            "name": "Laura Sánchez",
            "location": {
                "pickup_lat": 4.62971,  # Cerca del conductor
                "pickup_lng": -74.08175,
                "destination_lat": 4.702468,
                "destination_lng": -74.109776
            },
            "type_service_id": 1  # Car
        }
    ]

    created_requests = []

    # Crear los clientes primero
    print("\n2. Creando clientes")
    for req_data in requests_data:
        print(f"\nCreando cliente con teléfono {req_data['phone']}")
        client_data = {
            "full_name": req_data["name"],
            "country_code": driver_country_code,
            "phone_number": req_data["phone"]
        }
        create_resp = client.post("/users/", json=client_data)
        assert create_resp.status_code == 201, f"Error al crear cliente: {create_resp.text}"
        print(f"Cliente creado exitosamente")

    # Crear las solicitudes
    print("\n3. Creando solicitudes de clientes")
    for req_data in requests_data:
        print(f"\nCreando solicitud para cliente {req_data['phone']}")
        # Autenticar cliente
        send_resp = client.post(
            f"/auth/verify/{driver_country_code}/{req_data['phone']}/send")
        assert send_resp.status_code == 201, f"Error al enviar código: {send_resp.text}"
        code = send_resp.json()["message"].split()[-1]

        verify_resp = client.post(
            f"/auth/verify/{driver_country_code}/{req_data['phone']}/code",
            json={"code": code})
        assert verify_resp.status_code == 200, f"Error al verificar código: {verify_resp.text}"
        client_token = verify_resp.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Crear solicitud
        request_data = {
            "fare_offered": 20000,
            "pickup_description": "Test Location",
            "destination_description": "Test Destination",
            "pickup_lat": req_data["location"]["pickup_lat"],
            "pickup_lng": req_data["location"]["pickup_lng"],
            "destination_lat": req_data["location"]["destination_lat"],
            "destination_lng": req_data["location"]["destination_lng"],
            "type_service_id": req_data["type_service_id"],
            "payment_method_id": 1  # Cash
        }

        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        assert create_resp.status_code == 201, f"Error al crear solicitud: {create_resp.text}"
        request_id = create_resp.json()["id"]
        print(
            f"Solicitud creada con ID: {request_id}, Tipo de servicio: {req_data['type_service_id']}")

        created_requests.append({
            "id": request_id,
            "location": req_data["location"],
            "phone": req_data["phone"],
            "type_service_id": req_data["type_service_id"]
        })

    print(f"\nSolicitudes creadas: {len(created_requests)}")
    for req in created_requests:
        print(
            f"- ID: {req['id']}, Teléfono: {req['phone']}, Tipo de servicio: {req['type_service_id']}")

    # 3. Verificar las solicitudes cercanas
    print("\n3. Consultando solicitudes cercanas")
    nearby_resp = client.get(
        f"/client-request/nearby?driver_lat={driver_lat}&driver_lng={driver_lng}",
        headers=driver_headers
    )
    assert nearby_resp.status_code == 200, f"Error al consultar nearby: {nearby_resp.text}"
    nearby_data = nearby_resp.json()

    print(f"\nSolicitudes cercanas encontradas: {len(nearby_data)}")
    for req in nearby_data:
        print(
            f"- ID: {req['id']}, Tipo de servicio: {req.get('type_service', {}).get('id')}, Distancia: {req.get('distance', 'N/A')} metros")

    # 4. Verificar que solo aparecen las solicitudes del tipo de servicio correcto
    print("\n4. Verificando filtrado por tipo de servicio")

    # Filtrar solo las solicitudes que creamos en este test
    test_requests = [req for req in nearby_data if any(
        str(req["id"]) == str(created["id"]) for created in created_requests)]
    print(f"\nSolicitudes de test encontradas: {len(test_requests)}")

    # Verificar que solo aparecen solicitudes de tipo Car (id: 1)
    car_requests = [req for req in test_requests if req.get(
        'type_service', {}).get('id') == 1]
    motorcycle_requests = [req for req in test_requests if req.get(
        'type_service', {}).get('id') == 2]

    print(f"Solicitudes de tipo Car encontradas: {len(car_requests)}")
    print(
        f"Solicitudes de tipo Motorcycle encontradas: {len(motorcycle_requests)}")

    # Verificar que solo hay solicitudes de tipo Car
    assert len(
        motorcycle_requests) == 0, "Se encontraron solicitudes de tipo Motorcycle cuando no deberían aparecer"
    assert len(
        car_requests) == 2, f"Se esperaban 2 solicitudes de tipo Car, se encontraron {len(car_requests)}"

    # 5. Verificar que las solicitudes que aparecen están dentro del radio y son del tipo correcto
    for request in test_requests:
        print(f"\nVerificando solicitud {request['id']}")
        # Encontrar la solicitud original para comparar
        original_request = next(
            (r for r in created_requests if str(r["id"]) == str(request["id"])), None)
        assert original_request is not None, f"No se encontró la solicitud original para {request['id']}"

        # Verificar que es del tipo correcto
        assert request.get('type_service', {}).get('id') == 1, \
            f"La solicitud {request['id']} es de tipo {request.get('type_service', {}).get('id')}, debería ser tipo 1 (Car)"

        # Verificar que la distancia es correcta
        distance = request.get("distance", 0)
        print(f"Distancia verificada: {distance} metros")
        assert distance >= 0, f"La distancia debe ser positiva, se obtuvo {distance}"
        assert distance <= 5000, f"La distancia debe ser menor a 5000 metros, se obtuvo {distance}"

    print("\n=== TEST DE FILTRADO POR TIPO DE SERVICIO COMPLETADO EXITOSAMENTE ===")


def test_client_request_ratings():
    """
    Test case para verificar el sistema de calificaciones entre cliente y conductor.
    Verifica:
    1. Calificación del cliente al conductor
    2. Calificación del conductor al cliente
    3. Cálculo del promedio de calificaciones
    4. Validación de estados para calificar
    """
    print("\n=== INICIANDO TEST DE CALIFICACIONES ===")

    # 1. Crear y autenticar cliente
    phone_number = "3011111117"
    country_code = "+57"

    print("\n1. Creando y autenticando cliente")
    # Crear usuario
    user_data = {
        "full_name": "Usuario de Prueba",
        "country_code": country_code,
        "phone_number": phone_number
    }
    create_user_resp = client.post("/users/", json=user_data)
    assert create_user_resp.status_code == 201
    print("Usuario creado exitosamente")

    # Enviar código de verificación
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

    # 2. Crear solicitud de cliente
    print("\n2. Creando solicitud de cliente")
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
    print(f"Solicitud creada con ID: {client_request_id}")

    # 3. Crear y aprobar conductor
    print("\n3. Creando y aprobando conductor")
    driver_phone = "3010000007"
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 4. Asignar conductor a la solicitud
    print("\n4. Asignando conductor a la solicitud")
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned",
        json=assign_data,
        headers=headers
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # 5. Intentar calificar antes de que el viaje esté terminado (debe fallar)
    print("\n5. Intentando calificar antes de terminar el viaje")
    # Intentar calificar como cliente
    client_rating_data = {
        "id_client_request": client_request_id,
        "driver_rating": 5
    }
    client_rating_resp = client.patch(
        "/client-request/updateDriverRating",
        json=client_rating_data,
        headers=headers
    )
    assert client_rating_resp.status_code == 400
    mensaje_error = "Solo se puede calificar cuando el viaje está PAID"
    assert mensaje_error in client_rating_resp.json()["detail"]

    # Intentar calificar como conductor
    driver_rating_data = {
        "id_client_request": client_request_id,
        "client_rating": 4
    }
    driver_rating_resp = client.patch(
        "/client-request/updateClientRating",
        json=driver_rating_data,
        headers=driver_headers
    )
    assert driver_rating_resp.status_code == 400
    assert mensaje_error in driver_rating_resp.json()["detail"]

    # 6. Completar el viaje
    print("\n6. Completando el viaje")
    # Cambiar estado a ON_THE_WAY
    status_resp = client.patch(
        "/client-request/updateStatusByDriver",
        json={
            "id_client_request": client_request_id,
            "status": "ON_THE_WAY"
        },
        headers=driver_headers
    )
    assert status_resp.status_code == 200

    # Cambiar estado a ARRIVED
    status_resp = client.patch(
        "/client-request/updateStatusByDriver",
        json={
            "id_client_request": client_request_id,
            "status": "ARRIVED"
        },
        headers=driver_headers
    )
    assert status_resp.status_code == 200

    # Cambiar estado a TRAVELLING
    status_resp = client.patch(
        "/client-request/updateStatusByDriver",
        json={
            "id_client_request": client_request_id,
            "status": "TRAVELLING"
        },
        headers=driver_headers
    )
    assert status_resp.status_code == 200

    # Cambiar estado a FINISHED
    status_resp = client.patch(
        "/client-request/updateStatusByDriver",
        json={
            "id_client_request": client_request_id,
            "status": "FINISHED"
        },
        headers=driver_headers
    )
    assert status_resp.status_code == 200

    # Cambiar estado a PAID
    status_resp = client.patch(
        "/client-request/updateStatusByDriver",
        json={
            "id_client_request": client_request_id,
            "status": "PAID"
        },
        headers=driver_headers
    )
    assert status_resp.status_code == 200

    # 7. Calificar el viaje
    print("\n7. Calificando el viaje")
    # Cliente califica al conductor
    client_rating_data = {
        "id_client_request": client_request_id,
        "driver_rating": 5
    }
    client_rating_resp = client.patch(
        "/client-request/updateDriverRating",
        json=client_rating_data,
        headers=headers
    )
    assert client_rating_resp.status_code == 200
    assert client_rating_resp.json()["success"] is True

    # Conductor califica al cliente
    driver_rating_data = {
        "id_client_request": client_request_id,
        "client_rating": 4
    }
    driver_rating_resp = client.patch(
        "/client-request/updateClientRating",
        json=driver_rating_data,
        headers=driver_headers
    )
    assert driver_rating_resp.status_code == 200
    assert driver_rating_resp.json()["success"] is True

    # 8. Verificar que no se puede calificar dos veces
    print("\n8. Verificando que no se puede calificar dos veces")
    # Intentar calificar de nuevo como cliente
    duplicate_client_rating_resp = client.patch(
        "/client-request/updateDriverRating",
        json=client_rating_data,
        headers=headers
    )
    assert duplicate_client_rating_resp.status_code == 400
    mensaje_duplicado = "Ya existe una calificación para este viaje"
    assert mensaje_duplicado in duplicate_client_rating_resp.json()["detail"]

    # Intentar calificar de nuevo como conductor
    duplicate_driver_rating_resp = client.patch(
        "/client-request/updateClientRating",
        json=driver_rating_data,
        headers=driver_headers
    )
    assert duplicate_driver_rating_resp.status_code == 400
    assert mensaje_duplicado in duplicate_driver_rating_resp.json()["detail"]

    # 9. Verificar que las calificaciones se guardaron correctamente
    print("\n9. Verificando calificaciones guardadas")
    request_details = client.get(
        f"/client-request/{client_request_id}",
        headers=headers
    )
    assert request_details.status_code == 200
    details = request_details.json()
    assert details["client_rating"] == 4
    assert details["driver_rating"] == 5

    print("\n=== TEST DE CALIFICACIONES COMPLETADO EXITOSAMENTE ===")


def test_driver_trip_offer_flow():
    """
    Test que verifica el flujo completo de ofertas de viaje:
    1. Cliente crea solicitud
    2. Conductor hace oferta
    3. Cliente acepta oferta
    4. Verificación de estados y precios
    """
    print("\n=== INICIANDO TEST DE OFERTAS DE VIAJE ===")

    # 1. Crear y autenticar cliente
    phone_number = "3011111118"  # Nuevo número para evitar conflictos
    country_code = "+57"

    print("\n1. Creando y autenticando cliente")
    # Crear usuario
    user_data = {
        "full_name": "Usuario de Prueba Ofertas",
        "country_code": country_code,
        "phone_number": phone_number
    }
    create_user_resp = client.post("/users/", json=user_data)
    assert create_user_resp.status_code == 201
    print("Usuario creado exitosamente")

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

    # 2. Crear solicitud de cliente
    print("\n2. Creando solicitud de cliente")
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
    print(f"Solicitud creada con ID: {client_request_id}")

    # 3. Crear y aprobar conductor
    print("\n3. Creando y aprobando conductor")
    driver_phone = "3010000008"  # Nuevo número para evitar conflictos
    driver_country_code = "+57"
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 4. Conductor hace oferta
    print("\n4. Conductor haciendo oferta")
    offer_data = {
        "id_client_request": client_request_id,
        "fare_offer": 25000,  # Oferta mayor que la del cliente
        "time": 15,  # minutos estimados
        "distance": 5.5  # km estimados
    }
    offer_resp = client.post("/driver-trip-offers/",
                             json=offer_data, headers=driver_headers)
    assert offer_resp.status_code == 201
    offer_id = offer_resp.json()["id"]
    print(f"Oferta creada con ID: {offer_id}")

    # 5. Verificar que la oferta se creó correctamente
    print("\n5. Verificando detalles de la oferta")
    offers_resp = client.get(
        f"/driver-trip-offers/by-client-request/{client_request_id}", headers=headers)
    assert offers_resp.status_code == 200
    offers = offers_resp.json()
    assert len(offers) == 1
    assert offers[0]["fare_offer"] == 25000
    assert offers[0]["time"] == 15
    assert offers[0]["distance"] == 5.5
    print("Detalles de la oferta verificados correctamente")

    # 6. Cliente acepta la oferta
    print("\n6. Cliente aceptando la oferta")
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000  # Usar el precio de la oferta
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True
    print("Oferta aceptada correctamente")

    # 7. Verificar estado final
    print("\n7. Verificando estado final de la solicitud")
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=headers)
    assert detail_resp.status_code == 200
    request_detail = detail_resp.json()
    assert request_detail["status"] == str(StatusEnum.ACCEPTED)
    assert request_detail["fare_assigned"] == 25000
    assert request_detail["id_driver_assigned"] == str(driver_id)
    print("Estado final verificado correctamente")

    print("\n=== TEST DE OFERTAS DE VIAJE COMPLETADO EXITOSAMENTE ===")


def test_multiple_driver_offers():
    """
    Test que verifica el comportamiento cuando múltiples conductores hacen ofertas
    para la misma solicitud.
    """
    print("\n=== INICIANDO TEST DE MÚLTIPLES OFERTAS ===")

    # 1. Crear y autenticar cliente
    phone_number = "3011111119"  # Nuevo número para evitar conflictos
    country_code = "+57"

    print("\n1. Creando y autenticando cliente")
    user_data = {
        "full_name": "Usuario de Prueba Múltiples Ofertas",
        "country_code": country_code,
        "phone_number": phone_number
    }
    create_user_resp = client.post("/users/", json=user_data)
    assert create_user_resp.status_code == 201

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

    # 2. Crear solicitud de cliente
    print("\n2. Creando solicitud de cliente")
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

    # 3. Crear múltiples conductores
    print("\n3. Creando múltiples conductores")
    drivers = []
    for i in range(3):  # Crear 3 conductores
        driver_phone = f"30100000{10+i}"  # Números únicos para cada conductor
        driver_token, driver_id = create_and_approve_driver(
            client, driver_phone, country_code)
        drivers.append({
            "token": driver_token,
            "id": driver_id,
            "headers": {"Authorization": f"Bearer {driver_token}"}
        })

    # 4. Cada conductor hace una oferta
    print("\n4. Conductores haciendo ofertas")
    offers = []
    for i, driver in enumerate(drivers):
        offer_data = {
            "id_client_request": client_request_id,
            "fare_offer": 20000 + (i + 1) * 1000,  # Ofertas incrementales
            "time": 15 + i,  # Tiempos diferentes
            "distance": 5.5 + (i * 0.5)  # Distancias diferentes
        }
        offer_resp = client.post(
            "/driver-trip-offers/", json=offer_data, headers=driver["headers"])
        assert offer_resp.status_code == 201
        offers.append(offer_resp.json())
        print(f"Oferta {i+1} creada con ID: {offer_resp.json()['id']}")

    # 5. Verificar todas las ofertas
    print("\n5. Verificando todas las ofertas")
    offers_resp = client.get(
        f"/driver-trip-offers/by-client-request/{client_request_id}", headers=headers)
    assert offers_resp.status_code == 200
    all_offers = offers_resp.json()
    assert len(
        all_offers) == 3, f"Se esperaban 3 ofertas, se encontraron {len(all_offers)}"

    # 6. Cliente acepta una oferta específica
    print("\n6. Cliente aceptando una oferta específica")
    selected_offer = offers[1]  # Seleccionar la segunda oferta
    selected_driver = drivers[1]
    assign_data = {
        "id_client_request": client_request_id,
        "id_driver": selected_driver["id"],
        "fare_assigned": selected_offer["fare_offer"]
    }
    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["success"] is True

    # 7. Verificar estado final
    print("\n7. Verificando estado final")
    detail_resp = client.get(
        f"/client-request/{client_request_id}", headers=headers)
    assert detail_resp.status_code == 200
    request_detail = detail_resp.json()
    assert request_detail["status"] == str(StatusEnum.ACCEPTED)
    assert request_detail["fare_assigned"] == selected_offer["fare_offer"]
    assert request_detail["id_driver_assigned"] == str(selected_driver["id"])

    print("\n=== TEST DE MÚLTIPLES OFERTAS COMPLETADO EXITOSAMENTE ===")


def test_offer_validation():
    """
    Test que verifica las validaciones de las ofertas:
    1. Oferta menor que el precio base
    2. Oferta en solicitud no válida
    3. Conductor no aprobado
    4. Oferta duplicada
    """
    print("\n=== INICIANDO TEST DE VALIDACIONES DE OFERTAS ===")

    # 1. Crear y autenticar cliente
    phone_number = "3011111120"  # Nuevo número para evitar conflictos
    country_code = "+57"

    print("\n1. Creando y autenticando cliente")
    user_data = {
        "full_name": "Usuario de Prueba Validaciones",
        "country_code": country_code,
        "phone_number": phone_number
    }
    create_user_resp = client.post("/users/", json=user_data)
    assert create_user_resp.status_code == 201

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

    # 2. Crear solicitud de cliente
    print("\n2. Creando solicitud de cliente")
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

    # 3. Crear conductor aprobado
    print("\n3. Creando conductor aprobado")
    driver_phone = "3010000013"  # Nuevo número para evitar conflictos
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 4. Intentar oferta menor que el precio base
    print("\n4. Probando oferta menor que el precio base")
    low_offer_data = {
        "id_client_request": client_request_id,
        "fare_offer": 15000,  # Menor que fare_offered
        "time": 15,
        "distance": 5.5
    }
    low_offer_resp = client.post(
        "/driver-trip-offers/", json=low_offer_data, headers=driver_headers)
    assert low_offer_resp.status_code == 400
    assert "La oferta debe ser mayor o igual al precio base" in low_offer_resp.json()[
        "detail"]

    # 5. Intentar oferta en solicitud no válida
    print("\n5. Probando oferta en solicitud no válida")
    invalid_request_id = "00000000-0000-0000-0000-000000000000"
    invalid_offer_data = {
        "id_client_request": invalid_request_id,
        "fare_offer": 25000,
        "time": 15,
        "distance": 5.5
    }
    invalid_offer_resp = client.post(
        "/driver-trip-offers/", json=invalid_offer_data, headers=driver_headers)
    assert invalid_offer_resp.status_code == 404
    assert "Solicitud de cliente no encontrada" in invalid_offer_resp.json()[
        "detail"]

    # 6. Crear conductor no aprobado
    print("\n6. Probando con conductor no aprobado")
    unapproved_phone = "3010000014"  # Nuevo número para evitar conflictos
    unapproved_data = {
        "full_name": "Conductor No Aprobado",
        "country_code": country_code,
        "phone_number": unapproved_phone
    }
    create_unapproved_resp = client.post("/users/", json=unapproved_data)
    assert create_unapproved_resp.status_code == 201

    # Autenticar conductor no aprobado
    send_unapproved_resp = client.post(
        f"/auth/verify/{country_code}/{unapproved_phone}/send")
    assert send_unapproved_resp.status_code == 201
    unapproved_code = send_unapproved_resp.json()["message"].split()[-1]

    verify_unapproved_resp = client.post(
        f"/auth/verify/{country_code}/{unapproved_phone}/code",
        json={"code": unapproved_code}
    )
    assert verify_unapproved_resp.status_code == 200
    unapproved_token = verify_unapproved_resp.json()["access_token"]
    unapproved_headers = {"Authorization": f"Bearer {unapproved_token}"}

    # Intentar oferta con conductor no aprobado
    unapproved_offer_data = {
        "id_client_request": client_request_id,
        "fare_offer": 25000,
        "time": 15,
        "distance": 5.5
    }
    unapproved_offer_resp = client.post(
        "/driver-trip-offers/", json=unapproved_offer_data, headers=unapproved_headers)
    assert unapproved_offer_resp.status_code == 403
    assert "El usuario no tiene el rol de conductor" in unapproved_offer_resp.json()[
        "detail"]

    # 7. Intentar oferta duplicada
    print("\n7. Probando oferta duplicada")
    # Primera oferta válida
    valid_offer_data = {
        "id_client_request": client_request_id,
        "fare_offer": 25000,
        "time": 15,
        "distance": 5.5
    }
    first_offer_resp = client.post(
        "/driver-trip-offers/", json=valid_offer_data, headers=driver_headers)
    assert first_offer_resp.status_code == 201

    # Intentar oferta duplicada
    duplicate_offer_resp = client.post(
        "/driver-trip-offers/", json=valid_offer_data, headers=driver_headers)
    assert duplicate_offer_resp.status_code == 400
    assert "Ya existe una oferta para esta solicitud" in duplicate_offer_resp.json()[
        "detail"]

    print("\n=== TEST DE VALIDACIONES DE OFERTAS COMPLETADO EXITOSAMENTE ===")


def test_get_offers_with_calculated_time_and_distance(client):
    """
    Prueba el flujo completo:
    1. Cliente crea una solicitud de viaje.
    2. Conductor crea una oferta para esa solicitud.
    3. Cliente consulta las ofertas y verifica que time y distance se calculan.
    """
    # === PASO 1: Usar un cliente existente de init_data y autenticarlo ===
    client_phone = "3004444456"  # Usar un número de init_data.py
    client_country_code = "+57"
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
    assert client_token

    # === PASO 2: Cliente crea una solicitud de viaje ===
    request_payload = {
        "fare_offered": 20000,  # Agregar el precio base
        "pickup_lat": 4.6587,
        "pickup_lng": -74.0538,
        "destination_lat": 4.6739,
        "destination_lng": -74.053,
        "type_service_id": 1,
        "payment_method_id": 1
    }
    response = client.post(
        "/client-request/",
        headers=client_headers,
        json=request_payload
    )
    assert response.status_code == 201
    client_request_data = response.json()
    client_request_id = client_request_data["id"]
    assert client_request_id

    # === PASO 3: Usar un conductor existente y aprobado de init_data.py ===
    driver_phone = "3009999999"  # Conductor existente y aprobado en init_data
    driver_country_code = "+57"
    driver_token, _ = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}
    assert driver_token

    # === PASO 4: Conductor crea una oferta para el viaje ===
    offer_payload = {
        "id_client_request": client_request_id,
        "fare_offer": 20000,
        "time": 0,  # Enviamos 0 para forzar el cálculo en el backend
        "distance": 0
    }
    response = client.post(
        "/driver-trip-offers/",
        headers=driver_headers,
        json=offer_payload
    )
    assert response.status_code == 201

    # === PASO 5: Cliente consulta las ofertas del viaje ===
    response = client.get(
        f"/driver-trip-offers/by-client-request/{client_request_id}",
        headers=client_headers
    )
    assert response.status_code == 200

    # === PASO 6: Verificar que 'time' y 'distance' son mayores a 0 ===
    offers = response.json()
    assert isinstance(offers, list)
    assert len(offers) > 0

    first_offer = offers[0]
    assert "time" in first_offer
    assert "distance" in first_offer
    assert first_offer["time"] > 0
    assert first_offer["distance"] > 0

    print(
        f"\n[SUCCESS] Test exitoso: La oferta devolvió time={first_offer['time']} y distance={first_offer['distance']}")


def test_nearby_requests_with_addresses():
    """
    Verifica que el endpoint /client-request/nearby devuelve pickup_address y destination_address
    en el response, usando la función get_address_from_coords para convertir coordenadas a nombres legibles.
    """
    print("\n=== INICIANDO TEST DE DIRECCIONES EN NEARBY ===")

    # 1. Crear y autenticar conductor
    driver_phone = "3010000015"  # Nuevo número para evitar conflictos
    driver_country_code = "+57"
    print(f"\n1. Creando conductor con teléfono {driver_phone}")
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, driver_country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}
    print(f"Conductor creado con ID: {driver_id}")

    # Posición del conductor (centro de Bogotá)
    driver_lat = 4.60971
    driver_lng = -74.08175
    print(f"Posición del conductor: lat={driver_lat}, lng={driver_lng}")

    # 2. Crear cliente y solicitud
    print("\n2. Creando cliente y solicitud")
    client_phone = "3011111121"  # Nuevo número para evitar conflictos
    client_data = {
        "full_name": "Cliente Test Direcciones",
        "country_code": driver_country_code,
        "phone_number": client_phone
    }
    create_resp = client.post("/users/", json=client_data)
    assert create_resp.status_code == 201, f"Error al crear cliente: {create_resp.text}"

    # Autenticar cliente
    send_resp = client.post(
        f"/auth/verify/{driver_country_code}/{client_phone}/send")
    assert send_resp.status_code == 201, f"Error al enviar código: {send_resp.text}"
    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        f"/auth/verify/{driver_country_code}/{client_phone}/code",
        json={"code": code})
    assert verify_resp.status_code == 200, f"Error al verificar código: {verify_resp.text}"
    client_token = verify_resp.json()["access_token"]
    client_headers = {"Authorization": f"Bearer {client_token}"}

    # Crear solicitud con coordenadas conocidas
    request_data = {
        "fare_offered": 20000,
        "pickup_description": "Test Pickup",
        "destination_description": "Test Destination",
        "pickup_lat": 4.60971,  # Mismo punto que el conductor
        "pickup_lng": -74.08175,
        "destination_lat": 4.702468,  # Coordenadas de destino
        "destination_lng": -74.109776,
        "type_service_id": 1,  # Car
        "payment_method_id": 1  # Cash
    }

    create_resp = client.post(
        "/client-request/", json=request_data, headers=client_headers)
    assert create_resp.status_code == 201, f"Error al crear solicitud: {create_resp.text}"
    request_id = create_resp.json()["id"]
    print(f"Solicitud creada con ID: {request_id}")

    # 3. Consultar solicitudes cercanas
    print("\n3. Consultando solicitudes cercanas")
    nearby_resp = client.get(
        f"/client-request/nearby?driver_lat={driver_lat}&driver_lng={driver_lng}",
        headers=driver_headers
    )
    assert nearby_resp.status_code == 200, f"Error al consultar nearby: {nearby_resp.text}"
    nearby_data = nearby_resp.json()

    print(f"\nSolicitudes cercanas encontradas: {len(nearby_data)}")

    # 4. Verificar que la solicitud aparece y tiene los nuevos campos
    print("\n4. Verificando campos de direcciones")
    test_request = next(
        (req for req in nearby_data if str(req["id"]) == str(request_id)), None)
    assert test_request is not None, f"No se encontró la solicitud {request_id} en nearby"

    # Verificar que existen los nuevos campos
    assert "pickup_address" in test_request, "El campo pickup_address no está presente"
    assert "destination_address" in test_request, "El campo destination_address no está presente"

    # Verificar que los campos no están vacíos
    assert test_request["pickup_address"] is not None, "pickup_address no puede ser None"
    assert test_request["destination_address"] is not None, "destination_address no puede ser None"
    assert test_request["pickup_address"] != "", "pickup_address no puede estar vacío"
    assert test_request["destination_address"] != "", "destination_address no puede estar vacío"

    # Verificar que las direcciones son strings legibles
    assert isinstance(test_request["pickup_address"],
                      str), "pickup_address debe ser un string"
    assert isinstance(test_request["destination_address"],
                      str), "destination_address debe ser un string"

    # Verificar que las direcciones contienen información útil (no "Error al obtener dirección")
    assert "Error al obtener dirección" not in test_request["pickup_address"], \
        f"pickup_address contiene error: {test_request['pickup_address']}"
    assert "Error al obtener dirección" not in test_request["destination_address"], \
        f"destination_address contiene error: {test_request['destination_address']}"

    # Verificar que las direcciones no son "No disponible" (a menos que las coordenadas sean inválidas)
    if test_request["pickup_address"] != "No disponible":
        assert len(test_request["pickup_address"]) > 10, \
            f"pickup_address parece muy corto: {test_request['pickup_address']}"
    if test_request["destination_address"] != "No disponible":
        assert len(test_request["destination_address"]) > 10, \
            f"destination_address parece muy corto: {test_request['destination_address']}"

    # 5. Verificar que los campos de posición siguen existiendo
    print("\n5. Verificando campos de posición existentes")
    assert "pickup_position" in test_request, "El campo pickup_position debe seguir existiendo"
    assert "destination_position" in test_request, "El campo destination_position debe seguir existiendo"
    assert test_request["pickup_position"] is not None, "pickup_position no puede ser None"
    assert test_request["destination_position"] is not None, "destination_position no puede ser None"

    # Verificar estructura de las posiciones
    assert "lat" in test_request["pickup_position"], "pickup_position debe tener campo lat"
    assert "lng" in test_request["pickup_position"], "pickup_position debe tener campo lng"
    assert "lat" in test_request["destination_position"], "destination_position debe tener campo lat"
    assert "lng" in test_request["destination_position"], "destination_position debe tener campo lng"

    # 6. Imprimir información para verificación manual
    print("\n6. Información de la solicitud:")
    print(f"ID: {test_request['id']}")
    print(f"Pickup Position: {test_request['pickup_position']}")
    print(f"Pickup Address: {test_request['pickup_address']}")
    print(f"Destination Position: {test_request['destination_position']}")
    print(f"Destination Address: {test_request['destination_address']}")
    print(f"Distance: {test_request.get('distance', 'N/A')} metros")

    # 7. Verificar que la dirección coincide con las coordenadas (validación básica)
    print("\n7. Verificando consistencia entre coordenadas y direcciones")
    pickup_lat = test_request["pickup_position"]["lat"]
    pickup_lng = test_request["pickup_position"]["lng"]
    dest_lat = test_request["destination_position"]["lat"]
    dest_lng = test_request["destination_position"]["lng"]

    # Las coordenadas deben coincidir con las que enviamos
    assert abs(
        pickup_lat - 4.60971) < 0.001, f"Latitud de pickup no coincide: {pickup_lat}"
    assert abs(pickup_lng - (-74.08175)
               ) < 0.001, f"Longitud de pickup no coincide: {pickup_lng}"
    assert abs(
        dest_lat - 4.702468) < 0.001, f"Latitud de destino no coincide: {dest_lat}"
    assert abs(dest_lng - (-74.109776)
               ) < 0.001, f"Longitud de destino no coincide: {dest_lng}"

    print("\n=== TEST DE DIRECCIONES EN NEARBY COMPLETADO EXITOSAMENTE ===")
