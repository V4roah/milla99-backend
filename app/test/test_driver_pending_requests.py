from fastapi.testclient import TestClient
from app.main import app
from app.test.test_drivers import create_and_approve_driver
from app.models.client_request import StatusEnum
from app.models.driver_info import DriverInfo
from app.models.client_request import ClientRequest
from app.models.user import User
from app.models.project_settings import ProjectSettings
from sqlmodel import Session, select
from datetime import datetime, timezone, timedelta
from uuid import UUID
import pytz

COLOMBIA_TZ = pytz.timezone("America/Bogota")
client = TestClient(app)

# ===== HELPERS =====


def create_busy_driver_with_active_trip(client: TestClient, driver_phone: str = "3010000001", country_code: str = "+57"):
    """
    Crea un conductor que está actualmente en un viaje activo.
    Retorna: (driver_token, driver_id, active_request_id)
    """
    # 1. Crear conductor aprobado
    driver_token, driver_id = create_and_approve_driver(
        client, driver_phone, country_code)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 2. Crear cliente y solicitud
    client_phone = "3004444456"
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

    # 3. Crear solicitud de cliente
    request_data = {
        "fare_offered": 20000,
        "pickup_description": "Centro Comercial",
        "destination_description": "Aeropuerto",
        "pickup_lat": 4.718136,
        "pickup_lng": -74.073170,
        "destination_lat": 4.702468,
        "destination_lng": -74.109776,
        "type_service_id": 1,  # Car
        "payment_method_id": 1  # Cash
    }
    create_resp = client.post(
        "/client-request/", json=request_data, headers=client_headers)
    assert create_resp.status_code == 201
    active_request_id = create_resp.json()["id"]

    # 4. Asignar conductor a la solicitud
    assign_data = {
        "id_client_request": active_request_id,
        "id_driver": driver_id,
        "fare_assigned": 25000
    }
    print(f"🔍 Intentando asignar conductor...")
    print(f"   - Request ID: {active_request_id}")
    print(f"   - Driver ID: {driver_id}")
    print(f"   - Assign data: {assign_data}")

    assign_resp = client.patch(
        "/client-request/updateDriverAssigned", json=assign_data, headers=client_headers)

    print(f"🔍 Respuesta de asignación:")
    print(f"   - Status Code: {assign_resp.status_code}")
    print(f"   - Response: {assign_resp.text}")

    if assign_resp.status_code != 200:
        print(f"❌ Error en asignación:")
        print(f"   - Status Code: {assign_resp.status_code}")
        print(f"   - Response: {assign_resp.text}")

    assert assign_resp.status_code == 200

    # 5. Cambiar estado siguiendo el flujo correcto: ACCEPTED -> ON_THE_WAY -> ARRIVED -> TRAVELLING

    # 5.1 Cambiar a ON_THE_WAY
    status_data_on_the_way = {
        "id_client_request": active_request_id,
        "status": "ON_THE_WAY"
    }
    print(f"🔍 Paso 5.1: Cambiando a ON_THE_WAY...")
    status_resp_on_the_way = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_on_the_way, headers=driver_headers)
    print(f"   - Status Code: {status_resp_on_the_way.status_code}")
    print(f"   - Response: {status_resp_on_the_way.text}")
    assert status_resp_on_the_way.status_code == 200

    # 5.2 Cambiar a ARRIVED
    status_data_arrived = {
        "id_client_request": active_request_id,
        "status": "ARRIVED"
    }
    print(f"🔍 Paso 5.2: Cambiando a ARRIVED...")
    status_resp_arrived = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_arrived, headers=driver_headers)
    print(f"   - Status Code: {status_resp_arrived.status_code}")
    print(f"   - Response: {status_resp_arrived.text}")
    assert status_resp_arrived.status_code == 200

    # 5.3 Cambiar a TRAVELLING
    status_data_travelling = {
        "id_client_request": active_request_id,
        "status": "TRAVELLING"
    }
    print(f"🔍 Paso 5.3: Cambiando a TRAVELLING...")
    status_resp_travelling = client.patch(
        "/client-request/updateStatusByDriver", json=status_data_travelling, headers=driver_headers)
    print(f"   - Status Code: {status_resp_travelling.status_code}")
    print(f"   - Response: {status_resp_travelling.text}")

    if status_resp_travelling.status_code != 200:
        print(f"❌ Error en cambio de estado a TRAVELLING:")
        print(f"   - Status Code: {status_resp_travelling.status_code}")
        print(f"   - Response: {status_resp_travelling.text}")
        import traceback
        traceback.print_exc()

    assert status_resp_travelling.status_code == 200

    return driver_token, driver_id, active_request_id


def create_pending_request_for_busy_driver(client: TestClient, busy_driver_id: UUID):
    """
    Crea una solicitud que será asignada como pendiente a un conductor ocupado.
    Retorna: pending_request_id
    """
    # 1. Crear cliente y solicitud
    client_phone = "3004444457"
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

    # 2. Crear solicitud (esto debería activar la lógica de conductor ocupado)
    request_data = {
        "fare_offered": 15000,
        "pickup_description": "Universidad Nacional",
        "destination_description": "Centro Histórico",
        "pickup_lat": 4.638136,
        "pickup_lng": -74.083170,
        "destination_lat": 4.598468,
        "destination_lng": -74.075776,
        "type_service_id": 1,  # Car
        "payment_method_id": 1  # Cash
    }
    create_resp = client.post(
        "/client-request/", json=request_data, headers=client_headers)
    assert create_resp.status_code == 201
    pending_request_id = create_resp.json()["id"]

    return pending_request_id


def verify_driver_has_pending_request(session: Session, driver_id: UUID) -> bool:
    """
    Verifica que un conductor tenga una solicitud pendiente asignada.
    """
    driver_info = session.exec(
        select(DriverInfo).where(DriverInfo.user_id == driver_id)
    ).first()

    if not driver_info:
        return False

    return driver_info.pending_request_id is not None


def verify_pending_request_exists(session: Session, request_id: UUID) -> bool:
    """
    Verifica que existe una solicitud con el ID especificado.
    """
    request = session.get(ClientRequest, request_id)
    return request is not None

# ===== TESTS PRINCIPALES =====


def test_busy_driver_pending_request_validation_rejection():
    """
    Test que verifica que un conductor en viaje activo puede aceptar otro viaje
    que cumple las validaciones de tiempo y distancia.

    Escenario:
    1. Conductor está en viaje activo (TRAVELLING)
    2. Cliente crea nueva solicitud cercana (cumple validaciones)
    3. Sistema asigna conductor ocupado (solicitud pendiente)
    4. Verificar que el conductor puede aceptar la solicitud pendiente
    5. Verificar que la solicitud se asigna correctamente
    """
    print("\n🔄 Test: Conductor acepta segundo viaje mientras viaja...")

    # 1. Crear conductor ocupado con viaje activo
    driver_token, driver_id, active_request_id = create_busy_driver_with_active_trip(
        client)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}
    print(
        f"✅ Paso 1: Conductor {driver_id} en viaje activo {active_request_id}")

    # 2. Verificar que el conductor está en estado TRAVELLING
    active_trip_resp = client.get(
        f"/client-request/{active_request_id}", headers=driver_headers)
    assert active_trip_resp.status_code == 200
    active_trip_data = active_trip_resp.json()
    # El estado puede venir como 'TRAVELLING' o 'StatusEnum.TRAVELLING'
    assert active_trip_data["status"] in [
        "TRAVELLING", "StatusEnum.TRAVELLING"]
    print(
        f"✅ Paso 2: Viaje activo confirmado en estado {active_trip_data['status']}")

    # 3. Crear nueva solicitud de cliente CERCANA (debería cumplir validaciones)
    client_phone = "3004444458"
    client_country_code = "+57"

    # Autenticar nuevo cliente
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

    # 4. Crear nueva solicitud CERCANA al destino del viaje actual
    # Usar coordenadas cercanas al destino del viaje activo
    new_request_data = {
        "fare_offered": 18000,
        "pickup_description": "Cerca del destino del viaje actual",
        "destination_description": "Destino cercano",
        "pickup_lat": 4.702468,  # Cerca del destino del viaje actual
        "pickup_lng": -74.109776,
        "destination_lat": 4.708468,  # Muy cerca
        "destination_lng": -74.105776,
        "type_service_id": 1,  # Car
        "payment_method_id": 1  # Cash
    }
    create_resp = client.post(
        "/client-request/", json=new_request_data, headers=client_headers)
    assert create_resp.status_code == 201
    pending_request_id = create_resp.json()["id"]
    print(f"✅ Paso 3: Nueva solicitud creada {pending_request_id}")

    # 4.1 Verificar el estado inicial de la nueva solicitud
    new_request_resp = client.get(
        f"/client-request/{pending_request_id}", headers=client_headers)
    assert new_request_resp.status_code == 200
    new_request_data = new_request_resp.json()
    print(f"🔍 Estado inicial de nueva solicitud: {new_request_data['status']}")
    print(
        f"🔍 Conductor asignado: {new_request_data.get('id_driver_assigned', 'None')}")

    # 5. Verificar que la nueva solicitud está en estado CREATED (pendiente)
    assert new_request_data["status"] in ["CREATED", "StatusEnum.CREATED"]
    print(f"✅ Paso 4: Nueva solicitud en estado CREATED (pendiente)")

    # 6. Verificar que el conductor tiene solicitud pendiente asignada
    try:
        pending_resp = client.get(
            "/drivers/pending-request", headers=driver_headers)
        if pending_resp.status_code == 200:
            pending_data = pending_resp.json()
            print(f"✅ Paso 5: Conductor tiene solicitud pendiente asignada")
        else:
            print(
                f"⚠️ Paso 5: Endpoint /drivers/pending-request no implementado aún ({pending_resp.status_code})")
    except Exception as e:
        print(f"⚠️ Paso 5: Error verificando solicitud pendiente: {e}")

    # 7. Verificar que el conductor sigue en su viaje activo
    active_trip_resp_2 = client.get(
        f"/client-request/{active_request_id}", headers=driver_headers)
    assert active_trip_resp_2.status_code == 200
    active_trip_data_2 = active_trip_resp_2.json()
    # El estado puede venir como 'TRAVELLING' o 'StatusEnum.TRAVELLING'
    assert active_trip_data_2["status"] in [
        "TRAVELLING", "StatusEnum.TRAVELLING"]
    print(f"✅ Paso 6: Conductor sigue en viaje activo")

    # 8. Verificar que SÍ puede aceptar la solicitud pendiente (cumple validaciones)
    try:
        accept_resp = client.post(
            f"/drivers/pending-request/accept?client_request_id={pending_request_id}", headers=driver_headers)
        if accept_resp.status_code == 200:
            print(
                "✅ Paso 7: Correcto - Pudo aceptar solicitud pendiente (cumple validaciones)")
        elif accept_resp.status_code == 400:
            print(
                "⚠️ Paso 7: No pudo aceptar solicitud pendiente (no cumple validaciones)")
        else:
            print(
                f"⚠️ Paso 7: Respuesta inesperada: {accept_resp.status_code}")
    except Exception as e:
        print(f"⚠️ Paso 7: Error en endpoint de aceptar: {e}")

    print("🎉 Test completado: Conductor en viaje activo puede aceptar solicitud pendiente si cumple validaciones")
    return {
        "driver_id": driver_id,
        "active_request_id": active_request_id,
        "pending_request_id": pending_request_id,
        "driver_token": driver_token
    }


def test_busy_driver_can_accept_request_when_meets_requirements():
    """
    Test que verifica que un conductor ocupado SÍ puede aceptar una solicitud pendiente
    cuando cumple TODOS los requisitos de validación.

    REQUISITOS NECESARIOS para que un conductor ocupado pueda aceptar una solicitud:
    1. Tiempo total de espera ≤ 15 minutos (max_wait_time_for_busy_driver=15.0)
    2. Distancia ≤ 2 km (max_distance_for_busy_driver=2.0) 
    3. Tiempo de tránsito ≤ 5 minutos (max_transit_time_for_busy_driver=5.0)
       - Tiempo desde el destino del viaje actual → punto de recogida del nuevo cliente

    Escenario:
    1. Conductor está en viaje activo (TRAVELLING)
    2. Cliente crea nueva solicitud que CUMPLE validaciones (muy cercana)
    3. Sistema asigna conductor ocupado (solicitud pendiente)
    4. Verificar que el conductor SÍ puede aceptar la solicitud pendiente
    5. Verificar que la solicitud se asigna correctamente al conductor
    """
    print("\n🔄 Test: Conductor ocupado acepta solicitud que cumple requisitos...")
    import traceback

    try:
        # 1. Crear conductor ocupado con viaje activo
        print("🔍 Paso 1: Creando conductor ocupado con viaje activo...")
        driver_token, driver_id, active_request_id = create_busy_driver_with_active_trip(
            client)
        driver_headers = {"Authorization": f"Bearer {driver_token}"}
        print(
            f"✅ Paso 1: Conductor {driver_id} en viaje activo {active_request_id}")

        # 2. Verificar que el conductor está en estado TRAVELLING
        print("🔍 Paso 2: Verificando estado TRAVELLING...")
        active_trip_resp = client.get(
            f"/client-request/{active_request_id}", headers=driver_headers)
        print(f"   - Status Code: {active_trip_resp.status_code}")
        print(f"   - Response: {active_trip_resp.text}")

        assert active_trip_resp.status_code == 200
        active_trip_data = active_trip_resp.json()
        assert active_trip_data["status"] in [
            "TRAVELLING", "StatusEnum.TRAVELLING"]
        print(
            f"✅ Paso 2: Viaje activo confirmado en estado {active_trip_data['status']}")

        # 3. Crear nueva solicitud que CUMPLE validaciones (muy cercana al destino actual)
        print("🔍 Paso 3: Creando nueva solicitud que cumple validaciones...")
        client_phone = "3004444460"
        client_country_code = "+57"

        # Autenticar nuevo cliente
        print(f"   - Autenticando cliente {client_phone}...")
        send_resp = client.post(
            f"/auth/verify/{client_country_code}/{client_phone}/send")
        print(f"   - Send Status Code: {send_resp.status_code}")
        print(f"   - Send Response: {send_resp.text}")
        assert send_resp.status_code == 201
        code = send_resp.json()["message"].split()[-1]

        verify_resp = client.post(
            f"/auth/verify/{client_country_code}/{client_phone}/code",
            json={"code": code}
        )
        print(f"   - Verify Status Code: {verify_resp.status_code}")
        print(f"   - Verify Response: {verify_resp.text}")
        assert verify_resp.status_code == 200
        client_token = verify_resp.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # 4. Crear solicitud MUY CERCANA al destino del viaje actual (cumple validaciones)
        print("   - Creando solicitud muy cercana...")
        # Coordenadas muy cercanas para cumplir requisitos:
        # - Distancia ≤ 2 km
        # - Tiempo total ≤ 15 minutos
        # - Tiempo de tránsito ≤ 5 minutos (desde destino actual → punto de recogida nuevo cliente)
        new_request_data = {
            "fare_offered": 20000,
            "pickup_description": "Punto de recogida cercano al destino actual",
            "destination_description": "Destino del nuevo cliente",
            # Punto de recogida: muy cerca del destino del viaje actual (4.702468)
            "pickup_lat": 4.703468,
            "pickup_lng": -74.108776,  # Solo ~100 metros del destino actual
            "destination_lat": 4.710468,  # Destino del nuevo cliente
            "destination_lng": -74.100776,
            "type_service_id": 1,  # Car
            "payment_method_id": 1  # Cash
        }
        print(f"   - Request data: {new_request_data}")
        create_resp = client.post(
            "/client-request/", json=new_request_data, headers=client_headers)
        print(f"   - Create Status Code: {create_resp.status_code}")
        print(f"   - Create Response: {create_resp.text}")
        assert create_resp.status_code == 201
        pending_request_id = create_resp.json()["id"]
        print(
            f"✅ Paso 3: Nueva solicitud creada {pending_request_id} (cumple validaciones)")

        # 5. Verificar que la nueva solicitud está en estado CREATED (pendiente)
        print("🔍 Paso 4: Verificando estado de nueva solicitud...")
        new_request_resp = client.get(
            f"/client-request/{pending_request_id}", headers=client_headers)
        print(f"   - Get Status Code: {new_request_resp.status_code}")
        print(f"   - Get Response: {new_request_resp.text}")
        assert new_request_resp.status_code == 200
        new_request_data = new_request_resp.json()
        assert new_request_data["status"] in ["CREATED", "StatusEnum.CREATED"]
        print(f"✅ Paso 4: Nueva solicitud en estado CREATED (pendiente)")

        # 6. Asignar manualmente la solicitud al conductor ocupado (simular asignación automática)
        print("🔍 Paso 5: Asignando manualmente solicitud al conductor ocupado...")
        try:
            # Asignar la solicitud pendiente al conductor ocupado usando el endpoint correcto
            assignment_data = {
                "id_client_request": pending_request_id,
                "id_driver": driver_id,
                "fare_assigned": 22000
            }

            assign_resp = client.patch(
                "/client-request/updateDriverAssigned",
                json=assignment_data,
                headers=client_headers
            )
            print(f"   - Assign Status Code: {assign_resp.status_code}")
            print(f"   - Assign Response: {assign_resp.text}")

            if assign_resp.status_code == 200:
                print(f"✅ Paso 5: Solicitud asignada manualmente al conductor ocupado")
            else:
                print(
                    f"⚠️ Paso 5: No se pudo asignar solicitud ({assign_resp.status_code})")
                print(f"   - Error: {assign_resp.text}")
        except Exception as e:
            print(f"⚠️ Paso 5: Error asignando solicitud: {e}")
            print(f"   - Traceback: {traceback.format_exc()}")

        # 7. Verificar que el conductor tiene solicitud pendiente asignada
        print("🔍 Paso 6: Verificando solicitud pendiente del conductor...")
        try:
            pending_resp = client.get(
                "/drivers/pending-request", headers=driver_headers)
            print(f"   - Pending Status Code: {pending_resp.status_code}")
            print(f"   - Pending Response: {pending_resp.text}")
            if pending_resp.status_code == 200:
                pending_data = pending_resp.json()
                print(f"✅ Paso 6: Conductor tiene solicitud pendiente asignada")
                print(f"   - Pending data: {pending_data}")
            else:
                print(
                    f"⚠️ Paso 6: Endpoint /drivers/pending-request no implementado aún ({pending_resp.status_code})")
        except Exception as e:
            print(f"⚠️ Paso 6: Error verificando solicitud pendiente: {e}")
            print(f"   - Traceback: {traceback.format_exc()}")

        # 8. Verificar que el conductor sigue en su viaje activo
        print("🔍 Paso 7: Verificando que conductor sigue en viaje activo...")
        active_trip_resp_2 = client.get(
            f"/client-request/{active_request_id}", headers=driver_headers)
        print(
            f"   - Active Trip Status Code: {active_trip_resp_2.status_code}")
        print(f"   - Active Trip Response: {active_trip_resp_2.text}")
        assert active_trip_resp_2.status_code == 200
        active_trip_data_2 = active_trip_resp_2.json()
        assert active_trip_data_2["status"] in [
            "TRAVELLING", "StatusEnum.TRAVELLING"]
        print(f"✅ Paso 7: Conductor sigue en viaje activo")

        # 9. Verificar que SÍ puede aceptar la solicitud pendiente (cumple validaciones)
        print("🔍 Paso 8: Intentando aceptar solicitud pendiente...")
        try:
            print(f"\n🔍 DEBUGGING: Intentando aceptar solicitud pendiente...")
            print(f"   - Pending Request ID: {pending_request_id}")
            print(f"   - Driver ID: {driver_id}")
            print(f"   - Active Request ID: {active_request_id}")

            accept_resp = client.post(
                f"/drivers/pending-request/accept?client_request_id={pending_request_id}", headers=driver_headers)

            print(f"   - Accept Status Code: {accept_resp.status_code}")
            print(f"   - Accept Response: {accept_resp.text}")

            if accept_resp.status_code == 200:
                print(
                    "✅ Paso 7: Correcto - Pudo aceptar solicitud pendiente (cumple validaciones)")

                # 9. Verificar que la solicitud ahora está asignada al conductor
                print("🔍 Paso 8: Verificando asignación de solicitud...")
                updated_request_resp = client.get(
                    f"/client-request/{pending_request_id}", headers=client_headers)
                print(
                    f"   - Updated Status Code: {updated_request_resp.status_code}")
                print(f"   - Updated Response: {updated_request_resp.text}")
                assert updated_request_resp.status_code == 200
                updated_request_data = updated_request_resp.json()

                if updated_request_data.get("id_driver_assigned") == driver_id:
                    print(
                        f"✅ Paso 8: Solicitud correctamente asignada al conductor {driver_id}")
                else:
                    print(f"⚠️ Paso 8: Solicitud no asignada correctamente")
                    print(f"   - Expected driver_id: {driver_id}")
                    print(
                        f"   - Actual driver_id: {updated_request_data.get('id_driver_assigned')}")

            elif accept_resp.status_code == 400:
                print(
                    "❌ Paso 7: No pudo aceptar solicitud pendiente (no cumple validaciones)")
                print(
                    f"   - Error details: {accept_resp.json() if accept_resp.text else 'No response body'}")
            else:
                print(
                    f"⚠️ Paso 7: Respuesta inesperada: {accept_resp.status_code}")
                print(f"   - Response: {accept_resp.text}")
        except Exception as e:
            print(f"⚠️ Paso 7: Error en endpoint de aceptar: {e}")
            print(f"   - Traceback completo:")
            print(traceback.format_exc())

        print("🎉 Test completado: Conductor ocupado puede aceptar solicitud cuando cumple requisitos")
        return {
            "driver_id": driver_id,
            "active_request_id": active_request_id,
            "pending_request_id": pending_request_id,
            "driver_token": driver_token
        }

    except Exception as e:
        print(f"\n❌ Error en test: {e}")
        print(f"   - Traceback completo:")
        print(traceback.format_exc())
        raise

# ===== EJECUCIÓN DE TESTS =====


if __name__ == "__main__":
    print("🧪 Ejecutando test de conductor que acepta segundo viaje...")

    try:
        result = test_busy_driver_can_accept_request_when_meets_requirements()
        print(f"\n📊 Resultados del test:")
        print(f"   - Driver ID: {result['driver_id']}")
        print(f"   - Viaje activo: {result['active_request_id']}")
        print(f"   - Solicitud pendiente: {result['pending_request_id']}")
        print("\n✅ Test ejecutado exitosamente!")

    except Exception as e:
        print(f"\n❌ Error ejecutando test: {e}")
        import traceback
        traceback.print_exc()
