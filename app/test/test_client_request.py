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
