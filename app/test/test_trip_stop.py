from fastapi.testclient import TestClient
from app.main import app
from app.test.test_drivers import create_and_approve_driver
from app.models.client_request import StatusEnum
from app.core.db import engine
from sqlmodel import Session, select
from app.models.user import User
from app.models.user_has_roles import UserHasRole, RoleStatus
import traceback

client = TestClient(app)


def test_trip_with_multiple_stops():
    # 1. Crear y autenticar cliente
    phone_number = "3005555555"
    country_code = "+57"
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

    # Asegurar que el usuario tiene el rol CLIENT aprobado
    with Session(engine) as session:
        user = session.exec(select(User).where(
            User.phone_number == phone_number)).first()
        if user:
            client_role = session.exec(select(UserHasRole).where(
                UserHasRole.id_user == user.id, UserHasRole.id_rol == "CLIENT")).first()
            if client_role is None:
                client_role = UserHasRole(
                    id_user=user.id,
                    id_rol="CLIENT",
                    status=RoleStatus.APPROVED
                )
                session.add(client_role)
                session.commit()
            elif client_role.status != RoleStatus.APPROVED:
                client_role.status = RoleStatus.APPROVED
                session.add(client_role)
                session.commit()

    try:
        # 2. Crear solicitud de viaje con 2 paradas intermedias
        request_data = {
            "fare_offered": 30000,
            "pickup_description": "Origen (pickup)",
            "destination_description": "Destino (casa)",
            "pickup_lat": 4.700000,
            "pickup_lng": -74.100000,
            "destination_lat": 4.710000,
            "destination_lng": -74.110000,
            "type_service_id": 1,
            "payment_method_id": 1,
            "intermediate_stops": [
                {"latitude": 4.705000, "longitude": -74.105000,
                    "description": "Parada 1 (banco)"},
                {"latitude": 4.707000, "longitude": -74.108000,
                    "description": "Parada 2 (paquetería)"}
            ]
        }
        create_resp = client.post(
            "/client-request/", json=request_data, headers=headers)
        print("[DEBUG] Crear solicitud:",
              create_resp.status_code, create_resp.text)
        assert create_resp.status_code == 201, f"Error al crear solicitud: {create_resp.text}"
        client_request_id = create_resp.json()["id"]

        # 3. Crear y aprobar conductor
        driver_phone = "3015555555"
        driver_country_code = "+57"
        driver_token, driver_id = create_and_approve_driver(
            client, driver_phone, driver_country_code)
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # 4. Asignar conductor
        assign_data = {
            "id_client_request": client_request_id,
            "id_driver": str(driver_id),  # Convertir UUID a string para JSON
            "fare_assigned": 35000
        }
        assign_resp = client.patch(
            "/client-request/updateDriverAssigned", json=assign_data, headers=headers)
        print("[DEBUG] Asignar conductor:",
              assign_resp.status_code, assign_resp.text)
        assert assign_resp.status_code == 200, f"Error al asignar conductor: {assign_resp.text}"
        assert assign_resp.json()["success"] is True

        # 5. Cambiar estado a ON_THE_WAY
        status_data = {"id_client_request": client_request_id,
                       "status": "ON_THE_WAY"}
        status_resp = client.patch(
            "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
        print("[DEBUG] Estado ON_THE_WAY:",
              status_resp.status_code, status_resp.text)
        assert status_resp.status_code == 200, f"Error ON_THE_WAY: {status_resp.text}"
        assert status_resp.json()["success"] is True

        # 6. Cambiar estado a ARRIVED
        status_data = {
            "id_client_request": client_request_id, "status": "ARRIVED"}
        status_resp = client.patch(
            "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
        print("[DEBUG] Estado ARRIVED:",
              status_resp.status_code, status_resp.text)
        assert status_resp.status_code == 200, f"Error ARRIVED: {status_resp.text}"
        assert status_resp.json()["success"] is True

        # 7. Cambiar estado a TRAVELLING
        status_data = {"id_client_request": client_request_id,
                       "status": "TRAVELLING"}
        status_resp = client.patch(
            "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
        print("[DEBUG] Estado TRAVELLING:",
              status_resp.status_code, status_resp.text)
        assert status_resp.status_code == 200, f"Error TRAVELLING: {status_resp.text}"
        assert status_resp.json()["success"] is True

        # 8. Consultar detalle del viaje antes de pedir paradas
        detail_resp = client.get(
            f"/client-request/{client_request_id}", headers=driver_headers)
        print("[DEBUG] Detalle del viaje:",
              detail_resp.status_code, detail_resp.text)
        assert detail_resp.status_code == 200, f"Detalle no encontrado: {detail_resp.text}"
        print("[DEBUG] trip_stops en detalle:",
              detail_resp.json().get("trip_stops"))

        # 9. Obtener las paradas del viaje
        stops_resp = client.get(
            f"/trip-stops/{client_request_id}/stops", headers=driver_headers)
        print("[DEBUG] Paradas del viaje:",
              stops_resp.status_code, stops_resp.text)
        assert stops_resp.status_code == 200, f"No se encontraron paradas: {stops_resp.text}"
        stops = stops_resp.json()
        assert len(stops) == 4, f"Cantidad de paradas inesperada: {len(stops)}"

        # 10. Marcar cada parada como completed en orden
        for stop in stops:
            complete_resp = client.patch(
                f"/trip-stops/{stop['id']}/status",
                json={"status": "COMPLETED"},
                headers=driver_headers)
            print(f"[DEBUG] Completar parada {stop['id']}:",
                  complete_resp.status_code, complete_resp.text)
            assert complete_resp.status_code == 200, f"Error al completar parada: {complete_resp.text}"
            assert complete_resp.json()["stop"]["status"] == "COMPLETED"

        # 11. Cambiar estado a FINISHED
        status_data = {"id_client_request": client_request_id,
                       "status": "FINISHED"}
        status_resp = client.patch(
            "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
        print("[DEBUG] Estado FINISHED:",
              status_resp.status_code, status_resp.text)
        assert status_resp.status_code == 200, f"Error FINISHED: {status_resp.text}"
        assert status_resp.json()["success"] is True

        # 12. Cambiar estado a PAID
        status_data = {
            "id_client_request": client_request_id, "status": "PAID"}
        status_resp = client.patch(
            "/client-request/updateStatusByDriver", json=status_data, headers=driver_headers)
        print("[DEBUG] Estado PAID:", status_resp.status_code, status_resp.text)
        assert status_resp.status_code == 200, f"Error PAID: {status_resp.text}"
        assert status_resp.json()["success"] is True

        # 13. Verificar que todas las paradas están completed y el viaje está PAID
        stops_resp = client.get(
            f"/trip-stops/{client_request_id}/stops", headers=driver_headers)
        print("[DEBUG] Paradas finales:",
              stops_resp.status_code, stops_resp.text)
        assert stops_resp.status_code == 200, f"No se encontraron paradas finales: {stops_resp.text}"
        stops = stops_resp.json()
        for stop in stops:
            assert stop["status"] == "COMPLETED", f"Parada no completada: {stop}"
        detail_resp = client.get(
            f"/client-request/{client_request_id}", headers=driver_headers)
        print("[DEBUG] Estado final del viaje:",
              detail_resp.status_code, detail_resp.text)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["status"] == str(StatusEnum.PAID)
    except Exception as e:
        print("[TRACEBACK] Error en el test:")
        traceback.print_exc()
        raise
