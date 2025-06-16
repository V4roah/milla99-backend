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
    Verifica que el filtrado por distancia de las solicitudes cercanas funciona correctamente.

    Flujo del test:
    1. Crear múltiples solicitudes en diferentes ubicaciones:
       - Solicitud 1: Cerca del conductor (dentro del radio)
       - Solicitud 2: Lejos del conductor (fuera del radio)
       - Solicitud 3: En el límite del radio

    2. Verificar que:
       - Solo aparecen las solicitudes dentro del radio configurado
       - Las solicitudes fuera del radio no aparecen
       - La distancia se calcula correctamente
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
