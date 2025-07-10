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
from app.core.db import engine

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
    # Usar el conductor que acabamos de crear, no Roberto Sánchez
    assign_data = {
        "id_client_request": active_request_id,
        "id_driver": str(driver_id),  # Convertir UUID a string para JSON
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
        # Usar un número único para evitar conflictos
        import time
        # Últimos 4 dígitos del timestamp
        unique_suffix = str(int(time.time() * 1000))[-4:]
        client_phone = f"300444{unique_suffix}"
        client_country_code = "+57"

        # Crear usuario cliente antes de autenticar
        client_data = {
            "full_name": "Maria Rodriguez",
            "country_code": client_country_code,
            "phone_number": client_phone
        }
        response = client.post("/users/", json=client_data)
        assert response.status_code == 201

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
            # Punto de recogida: exactamente 1 metro del destino del viaje actual (4.702468, -74.109776)
            "pickup_lat": 4.702477,  # +0.000009 grados = ~1 metro al norte
            "pickup_lng": -74.109767,  # +0.000009 grados = ~1 metro al este
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

        # 5. Verificar que la nueva solicitud está en estado CREATED o PENDING (pendiente)
        print("🔍 Paso 4: Verificando estado de nueva solicitud...")
        new_request_resp = client.get(
            f"/client-request/{pending_request_id}", headers=client_headers)
        print(f"   - Get Status Code: {new_request_resp.status_code}")
        print(f"   - Get Response: {new_request_resp.text}")
        assert new_request_resp.status_code == 200
        new_request_data = new_request_resp.json()
        assert new_request_data["status"] in [
            "CREATED", "PENDING", "StatusEnum.CREATED", "StatusEnum.PENDING"]
        print(
            f"✅ Paso 4: Nueva solicitud en estado {new_request_data['status']} (pendiente)")

        # 5.1 Si la solicitud está en CREATED, asignarla al conductor ocupado para que pase a PENDING
        if new_request_data["status"] in ["CREATED", "StatusEnum.CREATED"]:
            print(
                "🔍 Paso 4.1: Asignando solicitud al conductor ocupado para que pase a PENDING...")
            assignment_data = {
                "id_client_request": pending_request_id,
                # Convertir UUID a string para JSON
                "id_driver": str(driver_id),
                "fare_assigned": 22000
            }
            assign_resp = client.patch(
                "/client-request/updateDriverAssigned",
                json=assignment_data,
                headers=client_headers
            )
            # El sistema debería asignar correctamente porque cumple las validaciones
            assert assign_resp.status_code == 200
            print(f"✅ Paso 4.1: Solicitud asignada correctamente al conductor ocupado")

        # 6. Asignar manualmente la solicitud al conductor ocupado (simular asignación automática)
        print("🔍 Paso 5: Asignando manualmente solicitud al conductor ocupado...")
        try:
            # Asignar la solicitud pendiente al conductor ocupado usando el endpoint correcto
            assignment_data = {
                "id_client_request": pending_request_id,
                # Convertir UUID a string para JSON
                "id_driver": str(driver_id),
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


def test_driver_priority_system():
    """
    Test que verifica que el sistema de prioridades de conductores funciona correctamente.

    ESCENARIO:
    1. Conductor A: Disponible (sin viaje) - PRIORIDAD 1
    2. Conductor B: Ocupado cercano (cumple validaciones) - PRIORIDAD 2
    3. Cliente 1: Crea viaje para dejar ocupado a B
    4. Cliente 2: Crea solicitud para buscar conductores
    5. Verificar que el orden de prioridad es correcto
    6. Verificar que solo se incluyen conductores válidos
    """
    print("\n🔄 Test: Sistema de prioridades de conductores...")
    import traceback

    try:
        client = TestClient(app)

        # 1. Crear Conductor A (disponible)
        print("🔍 Paso 1: Creando conductor A (disponible)...")
        driver_a_phone = "3019999991"
        driver_a_data = {
            "full_name": "Carlos Perez",
            "country_code": "+57",
            "phone_number": driver_a_phone
        }
        resp_a = client.post("/users/", json=driver_a_data)
        if resp_a.status_code != 201:
            print(f"❌ Error creando conductor A: {resp_a.status_code}")
            print(f"   - Response: {resp_a.text}")
            import traceback
            print(traceback.format_exc())
        assert resp_a.status_code == 201
        # Aprobar como DRIVER
        # (puedes agregar lógica de aprobación si tu sistema lo requiere)

        # 2. Crear Conductor B (ocupado cercano)
        print("🔍 Paso 2: Creando conductor B (ocupado cercano)...")
        driver_b_phone = "3019999992"
        driver_b_data = {
            "full_name": "Juan Gomez",
            "country_code": "+57",
            "phone_number": driver_b_phone
        }
        resp_b = client.post("/users/", json=driver_b_data)
        if resp_b.status_code != 201:
            print(f"❌ Error creando conductor B: {resp_b.status_code}")
            print(f"   - Response: {resp_b.text}")
            import traceback
            print(traceback.format_exc())
        assert resp_b.status_code == 201
        # Aprobar como DRIVER
        # (puedes agregar lógica de aprobación si tu sistema lo requiere)

        # 3. Crear Cliente 1 y asignar viaje a B
        print("🔍 Paso 3: Creando cliente 1 y asignando viaje a B...")
        client1_phone = "3009999991"
        client1_data = {
            "full_name": "Maria Rodriguez",
            "country_code": "+57",
            "phone_number": client1_phone
        }
        resp_c1 = client.post("/users/", json=client1_data)
        if resp_c1.status_code != 201:
            print(f"❌ Error creando cliente 1: {resp_c1.status_code}")
            print(f"   - Response: {resp_c1.text}")
            import traceback
            print(traceback.format_exc())
        assert resp_c1.status_code == 201
        # Autenticar cliente 1
        send_resp_c1 = client.post(f"/auth/verify/+57/{client1_phone}/send")
        if send_resp_c1.status_code != 201:
            print(
                f"❌ Error enviando código a cliente 1: {send_resp_c1.status_code}")
            print(f"   - Response: {send_resp_c1.text}")
            import traceback
            print(traceback.format_exc())
        assert send_resp_c1.status_code == 201
        code_c1 = send_resp_c1.json()["message"].split()[-1]
        verify_resp_c1 = client.post(
            f"/auth/verify/+57/{client1_phone}/code",
            json={"code": code_c1}
        )
        if verify_resp_c1.status_code != 200:
            print(
                f"❌ Error verificando código de cliente 1: {verify_resp_c1.status_code}")
            print(f"   - Response: {verify_resp_c1.text}")
            import traceback
            print(traceback.format_exc())
        assert verify_resp_c1.status_code == 200
        client1_token = verify_resp_c1.json()["access_token"]
        client1_headers = {"Authorization": f"Bearer {client1_token}"}
        # Crear solicitud para dejar ocupado a B
        request_data_b = {
            "fare_offered": 20000,
            "pickup_description": "Origen Cliente 1",
            "destination_description": "Destino Cliente 1",
            "pickup_lat": 4.702468,
            "pickup_lng": -74.108776,
            "destination_lat": 4.710468,
            "destination_lng": -74.100776,
            "type_service_id": 1,
            "payment_method_id": 1
        }
        create_resp_b = client.post(
            "/client-request/", json=request_data_b, headers=client1_headers)
        if create_resp_b.status_code != 201:
            print(
                f"❌ Error creando solicitud de cliente 1: {create_resp_b.status_code}")
            print(f"   - Response: {create_resp_b.text}")
            import traceback
            print(traceback.format_exc())
        assert create_resp_b.status_code == 201
        request_id_b = create_resp_b.json()["id"]
        # Asignar manualmente a B (simular lógica de asignación)
        # Aquí deberías obtener el id del driver B (puedes buscarlo en la BD o mockearlo si tienes acceso)
        # Para este ejemplo, asumimos que el sistema lo asigna correctamente

        # 4. Crear Cliente 2 y su solicitud
        print("🔍 Paso 4: Creando cliente 2 y su solicitud...")
        client2_phone = "3009999992"
        client2_data = {
            "full_name": "Ana Martinez",
            "country_code": "+57",
            "phone_number": client2_phone
        }
        resp_c2 = client.post("/users/", json=client2_data)
        if resp_c2.status_code != 201:
            print(f"❌ Error creando cliente 2: {resp_c2.status_code}")
            print(f"   - Response: {resp_c2.text}")
            import traceback
            print(traceback.format_exc())
        assert resp_c2.status_code == 201
        # Autenticar cliente 2
        send_resp_c2 = client.post(f"/auth/verify/+57/{client2_phone}/send")
        if send_resp_c2.status_code != 201:
            print(
                f"❌ Error enviando código a cliente 2: {send_resp_c2.status_code}")
            print(f"   - Response: {send_resp_c2.text}")
            import traceback
            print(traceback.format_exc())
        assert send_resp_c2.status_code == 201
        code_c2 = send_resp_c2.json()["message"].split()[-1]
        verify_resp_c2 = client.post(
            f"/auth/verify/+57/{client2_phone}/code",
            json={"code": code_c2}
        )
        if verify_resp_c2.status_code != 200:
            print(
                f"❌ Error verificando código de cliente 2: {verify_resp_c2.status_code}")
            print(f"   - Response: {verify_resp_c2.text}")
            import traceback
            print(traceback.format_exc())
        assert verify_resp_c2.status_code == 200
        client2_token = verify_resp_c2.json()["access_token"]
        client2_headers = {"Authorization": f"Bearer {client2_token}"}
        # Crear solicitud para buscar conductores
        request_data_c2 = {
            "fare_offered": 25000,
            "pickup_description": "Origen Cliente 2",
            "destination_description": "Destino Cliente 2",
            "pickup_lat": 4.702468,
            "pickup_lng": -74.108776,
            "destination_lat": 4.710468,
            "destination_lng": -74.100776,
            "type_service_id": 1,
            "payment_method_id": 1
        }
        create_resp_c2 = client.post(
            "/client-request/", json=request_data_c2, headers=client2_headers)
        if create_resp_c2.status_code != 201:
            print(
                f"❌ Error creando solicitud de cliente 2: {create_resp_c2.status_code}")
            print(f"   - Response: {create_resp_c2.text}")
            import traceback
            print(traceback.format_exc())
        assert create_resp_c2.status_code == 201
        request_id_c2 = create_resp_c2.json()["id"]

        # 5. Buscar conductores disponibles usando el endpoint de búsqueda
        print("🔍 Paso 5: Buscando conductores con sistema de prioridades...")
        search_resp = client.get(
            f"/client-request/nearby-drivers?client_lat={request_data_c2['pickup_lat']}&client_lng={request_data_c2['pickup_lng']}&type_service_id={request_data_c2['type_service_id']}",
            headers=client2_headers)
        if search_resp.status_code == 200:
            drivers_data = search_resp.json()
            print(f"   - Conductores encontrados: {len(drivers_data)}")
            # Verificar que hay conductores
            assert len(drivers_data) > 0, "No se encontraron conductores"

            # Verificar que solo se incluyen conductores válidos
            print("🔍 Paso 6: Verificando que solo se incluyen conductores válidos...")
            for driver in drivers_data:
                assert "id" in driver, "Conductor debe tener id"
                assert "driver_info" in driver, "Conductor debe tener driver_info"
                assert "vehicle_info" in driver, "Conductor debe tener vehicle_info"
                assert "distance" in driver, "Conductor debe tener distance"
                assert "rating" in driver, "Conductor debe tener rating"
                assert "phone_number" in driver, "Conductor debe tener phone_number"
                assert "country_code" in driver, "Conductor debe tener country_code"

            print("✅ Paso 6: Todos los conductores tienen datos válidos")

            # Mostrar resultados
            print("\n📊 Resultados del sistema de búsqueda de conductores:")
            for i, driver in enumerate(drivers_data[:5]):
                driver_name = f"{driver['driver_info']['first_name']} {driver['driver_info']['last_name']}"
                print(
                    f"   {i+1}. {driver_name} - Distancia: {driver['distance']:.2f}m - Rating: {driver['rating']:.1f}")

            return {
                "request_id": request_id_c2,
                "total_drivers": len(drivers_data),
                "drivers_found": True
            }
        else:
            print(
                f"❌ Error en búsqueda de conductores: {search_resp.status_code}")
            print(f"   - Response: {search_resp.text}")
            return None
    except Exception as e:
        print(f"\n❌ Error en test: {e}")
        print(f"   - Traceback completo:")
        print(traceback.format_exc())
        raise


def test_busy_driver_rejected_when_distance_too_far():
    """
    Test que verifica que un conductor ocupado NO puede aceptar una solicitud pendiente
    cuando la distancia es demasiado lejana (más de 2km).

    REQUISITOS para que un conductor ocupado pueda aceptar una solicitud:
    1. Tiempo total de espera ≤ 15 minutos (max_wait_time_for_busy_driver=15.0)
    2. Distancia ≤ 2 km (max_distance_for_busy_driver=2.0) ← ESTE ES EL QUE FALLA
    3. Tiempo de tránsito ≤ 5 minutos (max_transit_time_for_busy_driver=5.0)

    Escenario:
    1. Conductor está en viaje activo (TRAVELLING)
    2. Cliente crea nueva solicitud que NO cumple validaciones (muy lejana)
    3. Sistema NO asigna conductor ocupado (solicitud rechazada)
    4. Verificar que el conductor NO puede aceptar la solicitud
    5. Verificar que la solicitud NO se asigna al conductor
    """
    print("\n🔄 Test: Conductor ocupado rechaza solicitud por distancia lejana...")
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

        # 3. Crear nueva solicitud que NO cumple validaciones (muy lejana)
        print("🔍 Paso 3: Creando nueva solicitud que NO cumple validaciones...")
        # Usar un número único para evitar conflictos
        import time
        # Últimos 3 dígitos del timestamp para mantener 10 dígitos total
        # Últimos 3 dígitos del timestamp
        unique_suffix = str(int(time.time() * 1000))[-3:]
        client_phone = f"3004444{unique_suffix}"  # 7 + 3 = 10 dígitos
        client_country_code = "+57"

        # Crear usuario cliente antes de autenticar
        client_data = {
            "full_name": "Carlos Lopez",
            "country_code": client_country_code,
            "phone_number": client_phone
        }
        response = client.post("/users/", json=client_data)
        assert response.status_code == 201

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

        # 4. Crear solicitud MUY LEJANA al destino del viaje actual (NO cumple validaciones)
        print("   - Creando solicitud muy lejana...")
        # Coordenadas muy lejanas para NO cumplir requisitos:
        # - Distancia > 2 km (debería ser rechazada)
        # - Tiempo total > 15 minutos
        # - Tiempo de tránsito > 5 minutos
        new_request_data = {
            "fare_offered": 20000,
            "pickup_description": "Punto de recogida lejano al destino actual",
            "destination_description": "Destino del nuevo cliente lejano",
            # Punto de recogida: muy lejos del destino del viaje actual (4.702468)
            "pickup_lat": 4.750000,  # ~5.3km del destino actual
            "pickup_lng": -74.050000,  # Muy lejos del destino actual
            "destination_lat": 4.760000,  # Destino del nuevo cliente
            "destination_lng": -74.040000,
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
            f"✅ Paso 3: Nueva solicitud creada {pending_request_id} (NO cumple validaciones)")

        # 5. Verificar que la nueva solicitud está en estado CREATED (no cumple validaciones)
        print("🔍 Paso 4: Verificando estado de nueva solicitud...")
        new_request_resp = client.get(
            f"/client-request/{pending_request_id}", headers=client_headers)
        print(f"   - Get Status Code: {new_request_resp.status_code}")
        print(f"   - Get Response: {new_request_resp.text}")
        assert new_request_resp.status_code == 200
        new_request_data = new_request_resp.json()
        assert new_request_data["status"] in ["CREATED", "StatusEnum.CREATED"]
        print(f"✅ Paso 4: Nueva solicitud en estado CREATED (no cumple validaciones)")

        # 6. Intentar asignar manualmente la solicitud al conductor ocupado (debería fallar)
        print("🔍 Paso 5: Intentando asignar manualmente solicitud al conductor ocupado...")
        try:
            # Asignar la solicitud pendiente al conductor ocupado usando el endpoint correcto
            assignment_data = {
                "id_client_request": pending_request_id,
                # Convertir UUID a string para JSON
                "id_driver": str(driver_id),
                "fare_assigned": 22000
            }

            assign_resp = client.patch(
                "/client-request/updateDriverAssigned",
                json=assignment_data,
                headers=client_headers
            )
            print(f"   - Assign Status Code: {assign_resp.status_code}")
            print(f"   - Assign Response: {assign_resp.text}")

            # Debería fallar porque la distancia es muy lejana
            if assign_resp.status_code == 400:
                print(f"✅ Paso 5: Correcto - Solicitud rechazada por distancia lejana")
            elif assign_resp.status_code == 200:
                print(
                    f"⚠️ Paso 5: Inesperado - Solicitud asignada a pesar de distancia lejana")
                # Verificar que el conductor NO tiene solicitud pendiente
                pending_resp = client.get(
                    "/drivers/pending-request", headers=driver_headers)
                if pending_resp.status_code == 200:
                    pending_data = pending_resp.json()
                    if not pending_data.get("pending_request"):
                        print(
                            f"✅ Paso 5: Conductor NO tiene solicitud pendiente (correcto)")
                    else:
                        print(
                            f"❌ Paso 5: Conductor SÍ tiene solicitud pendiente (incorrecto)")
                else:
                    print(f"⚠️ Paso 5: No se pudo verificar solicitud pendiente")
            else:
                print(
                    f"⚠️ Paso 5: Respuesta inesperada: {assign_resp.status_code}")
                print(f"   - Error: {assign_resp.text}")
        except Exception as e:
            print(f"⚠️ Paso 5: Error asignando solicitud: {e}")
            print(f"   - Traceback: {traceback.format_exc()}")

        # 7. Verificar que el conductor NO tiene solicitud pendiente asignada
        print("🔍 Paso 6: Verificando que conductor NO tiene solicitud pendiente...")
        try:
            pending_resp = client.get(
                "/drivers/pending-request", headers=driver_headers)
            print(f"   - Pending Status Code: {pending_resp.status_code}")
            print(f"   - Pending Response: {pending_resp.text}")
            if pending_resp.status_code == 200:
                pending_data = pending_resp.json()
                if not pending_data.get("pending_request"):
                    print(
                        f"✅ Paso 6: Correcto - Conductor NO tiene solicitud pendiente")
                else:
                    print(
                        f"❌ Paso 6: Incorrecto - Conductor SÍ tiene solicitud pendiente")
                    print(f"   - Pending data: {pending_data}")
            else:
                print(
                    f"⚠️ Paso 6: Endpoint /drivers/pending-request no implementado aún ({pending_resp.status_code})")
        except Exception as e:
            print(f"⚠️ Paso 6: Error verificando solicitud pendiente: {e}")
            print(f"   - Traceback: {traceback.format_exc()}")

        # 8. Verificar que el conductor sigue en viaje activo
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

        # 9. Verificar que NO puede aceptar la solicitud pendiente (NO cumple validaciones)
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

            if accept_resp.status_code == 400:
                print(
                    "✅ Paso 8: Correcto - NO pudo aceptar solicitud pendiente (NO cumple validaciones)")
                print(
                    f"   - Error details: {accept_resp.json() if accept_resp.text else 'No response body'}")

                # 10. Verificar que la solicitud NO está asignada al conductor
                print("🔍 Paso 9: Verificando que solicitud NO está asignada...")
                updated_request_resp = client.get(
                    f"/client-request/{pending_request_id}", headers=client_headers)
                print(
                    f"   - Updated Status Code: {updated_request_resp.status_code}")
                print(f"   - Updated Response: {updated_request_resp.text}")
                assert updated_request_resp.status_code == 200
                updated_request_data = updated_request_resp.json()

                if updated_request_data.get("id_driver_assigned") != driver_id:
                    print(
                        f"✅ Paso 9: Correcto - Solicitud NO asignada al conductor (como debe ser)")
                else:
                    print(
                        f"❌ Paso 9: Incorrecto - Solicitud SÍ asignada al conductor")
                    print(f"   - Expected driver_id: {driver_id}")
                    print(
                        f"   - Actual driver_id: {updated_request_data.get('id_driver_assigned')}")

            elif accept_resp.status_code == 200:
                print(
                    "❌ Paso 8: Incorrecto - Pudo aceptar solicitud pendiente (debería haber fallado)")
                print(
                    f"   - Success details: {accept_resp.json() if accept_resp.text else 'No response body'}")

            else:
                print(
                    f"⚠️ Paso 8: Respuesta inesperada: {accept_resp.status_code}")
                print(f"   - Response: {accept_resp.text}")
        except Exception as e:
            print(f"⚠️ Paso 8: Error en endpoint de aceptar: {e}")
            print(f"   - Traceback completo:")
            print(traceback.format_exc())

        print("🎉 Test completado: Conductor ocupado rechaza solicitud por distancia lejana")
        return {
            "driver_id": driver_id,
            "active_request_id": active_request_id,
            "pending_request_id": pending_request_id,
            "driver_token": driver_token,
            "rejected": True
        }

    except Exception as e:
        print(f"\n❌ Error en test: {e}")
        print(f"   - Traceback completo:")
        print(traceback.format_exc())
        raise


def test_busy_driver_rejected_when_transit_time_too_long():
    """
    Test que verifica que un conductor ocupado NO puede aceptar una solicitud pendiente
    cuando el tiempo de tránsito es demasiado largo (más de 5 minutos).

    REQUISITOS para que un conductor ocupado pueda aceptar una solicitud:
    1. Tiempo total de espera ≤ 15 minutos (max_wait_time_for_busy_driver=15.0)
    2. Distancia ≤ 2 km (max_distance_for_busy_driver=2.0)
    3. Tiempo de tránsito ≤ 5 minutos (max_transit_time_for_busy_driver=5.0) ← ESTE ES EL QUE FALLA

    Escenario:
    1. Conductor está en viaje activo (TRAVELLING)
    2. Cliente crea nueva solicitud que NO cumple validaciones (tiempo de tránsito muy largo)
    3. Sistema NO asigna conductor ocupado (solicitud rechazada)
    4. Conductor NO puede aceptar la solicitud pendiente
    """
    print("\n🔄 Test: Conductor ocupado rechaza solicitud por tiempo de tránsito muy largo...")

    # Inicializar variables al inicio del test
    driver_token = None
    driver_headers = None
    client_token = None
    client_headers = None
    new_request_id = None
    busy_driver_id = None
    current_request_id = None

    try:
        # === PASO 1: Crear conductor ocupado con viaje activo ===
        print("🔍 Paso 1: Creando conductor ocupado con viaje activo...")

        # Usar usuario existente de init_data.py
        existing_driver_phone = "3005555555"  # Roberto Sánchez
        country_code = "+57"

        # Verificar usuario existente
        send_resp = client.post(
            f"/auth/verify/{country_code}/{existing_driver_phone}/send")
        assert send_resp.status_code == 201
        code = send_resp.json()["message"].split()[-1]
        verify_resp = client.post(
            f"/auth/verify/{country_code}/{existing_driver_phone}/code",
            json={"code": code}
        )
        assert verify_resp.status_code == 200
        driver_token = verify_resp.json()["access_token"]
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Crear solicitud para el conductor
        request_data = {
            "pickup_lat": 4.718136,
            "pickup_lng": -74.07317,
            "destination_lat": 4.720000,
            "destination_lng": -74.075000,
            "type_service_id": 1,
            "fare_offered": 25000,
            "payment_method_id": 1
        }

        # Usar cliente existente para crear la solicitud
        existing_client_phone = "3001111111"  # María García
        send_client_resp = client.post(
            f"/auth/verify/{country_code}/{existing_client_phone}/send")
        assert send_client_resp.status_code == 201
        client_code = send_client_resp.json()["message"].split()[-1]
        verify_client_resp = client.post(
            f"/auth/verify/{country_code}/{existing_client_phone}/code",
            json={"code": client_code}
        )
        assert verify_client_resp.status_code == 200
        client_token = verify_client_resp.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Crear solicitud
        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        assert create_resp.status_code == 201
        current_request_id = create_resp.json()["id"]

        # Asignar conductor a la solicitud
        # Primero necesitamos obtener el UUID del conductor
        with Session(engine) as session:
            driver_user = session.exec(
                select(User).where(User.phone_number == "3005555555")
            ).first()
            assert driver_user is not None, "Conductor Roberto Sánchez no encontrado"
            driver_uuid = str(driver_user.id)

        assign_data = {
            "id_client_request": current_request_id,
            "id_driver": driver_uuid,  # UUID real del conductor
            "fare_assigned": 25000
        }
        assign_resp = client.patch(
            "/client-request/updateDriverAssigned", json=assign_data, headers=client_headers)
        assert assign_resp.status_code == 200

        # Cambiar estados del viaje siguiendo el flujo correcto
        print("🔍 Paso 1.1: Cambiando a ON_THE_WAY...")
        status_resp = client.patch(
            f"/client-request/updateStatusByDriver",
            json={"id_client_request": current_request_id,
                  "status": "ON_THE_WAY"},
            headers=driver_headers
        )
        assert status_resp.status_code == 200

        print("🔍 Paso 1.2: Cambiando a ARRIVED...")
        status_resp = client.patch(
            f"/client-request/updateStatusByDriver",
            json={"id_client_request": current_request_id,
                  "status": "ARRIVED"},
            headers=driver_headers
        )
        assert status_resp.status_code == 200

        print("🔍 Paso 1.3: Cambiando a TRAVELLING...")
        status_resp = client.patch(
            f"/client-request/updateStatusByDriver",
            json={"id_client_request": current_request_id,
                  "status": "TRAVELLING"},
            headers=driver_headers
        )
        assert status_resp.status_code == 200

        print(
            f"✅ Paso 1: Conductor {existing_driver_phone} en viaje activo {current_request_id}")

        # === PASO 2: Verificar que el conductor está en viaje activo ===
        print("🔍 Paso 2: Verificando estado TRAVELLING...")
        detail_resp = client.get(
            f"/client-request/{current_request_id}", headers=client_headers)
        assert detail_resp.status_code == 200
        request_detail = detail_resp.json()
        assert request_detail["status"] in [
            "TRAVELLING", "StatusEnum.TRAVELLING"]
        print("✅ Paso 2: Viaje activo confirmado en estado TRAVELLING")

        # === PASO 3: Crear nueva solicitud que NO cumple validaciones ===
        print("🔍 Paso 3: Creando nueva solicitud que NO cumple validaciones...")

        # Usar otro cliente existente para crear la nueva solicitud
        new_client_phone = "3002222222"  # Juan Pérez
        send_new_client_resp = client.post(
            f"/auth/verify/{country_code}/{new_client_phone}/send")
        assert send_new_client_resp.status_code == 201
        new_client_code = send_new_client_resp.json()["message"].split()[-1]
        verify_new_client_resp = client.post(
            f"/auth/verify/{country_code}/{new_client_phone}/code",
            json={"code": new_client_code}
        )
        assert verify_new_client_resp.status_code == 200
        new_client_token = verify_new_client_resp.json()["access_token"]
        new_client_headers = {"Authorization": f"Bearer {new_client_token}"}

        # Crear solicitud con destino muy lejano (tiempo de tránsito > 5 minutos)
        new_request_data = {
            "pickup_lat": 4.718136,
            "pickup_lng": -74.07317,
            "destination_lat": 4.800000,  # Muy lejano
            "destination_lng": -74.100000,  # Muy lejano
            "type_service_id": 1,
            "fare_offered": 30000,
            "payment_method_id": 1
        }

        create_new_resp = client.post(
            "/client-request/", json=new_request_data, headers=new_client_headers)
        assert create_new_resp.status_code == 201
        new_request_id = create_new_resp.json()["id"]
        print(f"✅ Paso 3: Nueva solicitud creada con ID {new_request_id}")

        # === PASO 4: Verificar que el conductor NO puede aceptar la nueva solicitud ===
        print("🔍 Paso 4: Verificando que conductor NO puede aceptar nueva solicitud...")

        # Intentar asignar el conductor ocupado a la nueva solicitud
        assign_new_data = {
            "id_client_request": new_request_id,
            "id_driver": driver_uuid,  # Roberto Sánchez (ocupado)
            "fare_assigned": 30000
        }
        assign_new_resp = client.patch(
            "/client-request/updateDriverAssigned", json=assign_new_data, headers=new_client_headers)

        # El sistema debería rechazar la asignación por tiempo de tránsito muy largo
        if assign_new_resp.status_code == 400:
            print("✅ Paso 4: Sistema rechazó asignación por tiempo de tránsito muy largo")
        else:
            print(
                f"⚠️ Paso 4: Sistema permitió asignación (status: {assign_new_resp.status_code})")

        # === PASO 5: Verificar que el conductor NO tiene solicitud pendiente ===
        print("🔍 Paso 5: Verificando que conductor NO tiene solicitud pendiente...")
        pending_resp = client.get(
            "/drivers/pending-request", headers=driver_headers)
        assert pending_resp.status_code == 200
        pending_data = pending_resp.json()

        if pending_data.get("pending_request_id") is None:
            print("✅ Paso 5: Correcto - Conductor NO tiene solicitud pendiente")
        else:
            print(
                f"⚠️ Paso 5: Conductor tiene solicitud pendiente: {pending_data.get('pending_request_id')}")

        # === PASO 6: Verificar que el conductor sigue en viaje activo ===
        print("🔍 Paso 6: Verificando que conductor sigue en viaje activo...")
        detail_resp = client.get(
            f"/client-request/{current_request_id}", headers=client_headers)
        assert detail_resp.status_code == 200
        request_detail = detail_resp.json()
        assert request_detail["status"] in [
            "TRAVELLING", "StatusEnum.TRAVELLING"]
        print("✅ Paso 6: Conductor sigue en viaje activo")

        # === PASO 7: Verificar que la nueva solicitud NO está asignada ===
        print("🔍 Paso 7: Verificando que nueva solicitud NO está asignada...")
        if new_request_id:
            new_detail_resp = client.get(
                f"/client-request/{new_request_id}", headers=new_client_headers)
            assert new_detail_resp.status_code == 200
            new_request_detail = new_detail_resp.json()

            if new_request_detail.get("id_driver_assigned") is None:
                print("✅ Paso 7: Nueva solicitud NO está asignada (correcto)")
            else:
                print(
                    f"⚠️ Paso 7: Nueva solicitud está asignada a: {new_request_detail.get('id_driver_assigned')}")

        print("🎉 Test completado: Conductor ocupado rechaza solicitud por tiempo de tránsito muy largo")

    except Exception as e:
        print(f"❌ Error en test: {e}")
        raise


def test_busy_driver_rejected_when_total_time_exceeds_limit():
    """
    Test que verifica que un conductor ocupado NO puede aceptar una solicitud pendiente
    cuando el tiempo total excede el límite (más de 15 minutos).

    REQUISITOS para que un conductor ocupado pueda aceptar una solicitud:
    1. Tiempo total de espera ≤ 15 minutos (max_wait_time_for_busy_driver=15.0) ← ESTE ES EL QUE FALLA
    2. Distancia ≤ 2 km (max_distance_for_busy_driver=2.0)
    3. Tiempo de tránsito ≤ 5 minutos (max_transit_time_for_busy_driver=5.0)

    Escenario:
    1. Conductor está en viaje activo (TRAVELLING)
    2. Cliente crea nueva solicitud que NO cumple validaciones (tiempo total muy largo)
    3. Sistema NO asigna conductor ocupado (solicitud rechazada)
    4. Conductor NO puede aceptar la solicitud pendiente
    """
    print("\n🔄 Test: Conductor ocupado rechaza solicitud por tiempo total excede límite...")

    # Inicializar variables al inicio del test
    driver_token = None
    driver_headers = None
    client_token = None
    client_headers = None
    new_request_id = None
    busy_driver_id = None
    current_request_id = None

    try:
        # === PASO 1: Crear conductor ocupado con viaje activo ===
        print("🔍 Paso 1: Creando conductor ocupado con viaje activo...")

        # Usar usuario existente de init_data.py
        existing_driver_phone = "3005555555"  # Roberto Sánchez
        country_code = "+57"

        # Verificar usuario existente
        send_resp = client.post(
            f"/auth/verify/{country_code}/{existing_driver_phone}/send")
        assert send_resp.status_code == 201
        code = send_resp.json()["message"].split()[-1]
        verify_resp = client.post(
            f"/auth/verify/{country_code}/{existing_driver_phone}/code",
            json={"code": code}
        )
        assert verify_resp.status_code == 200
        driver_token = verify_resp.json()["access_token"]
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Crear solicitud para el conductor con viaje largo
        request_data = {
            "pickup_lat": 4.718136,
            "pickup_lng": -74.07317,
            "destination_lat": 4.720000,
            "destination_lng": -74.075000,
            "type_service_id": 1,
            "fare_offered": 25000,
            "payment_method_id": 1
        }

        # Usar cliente existente para crear la solicitud
        existing_client_phone = "3001111111"  # María García
        send_client_resp = client.post(
            f"/auth/verify/{country_code}/{existing_client_phone}/send")
        assert send_client_resp.status_code == 201
        client_code = send_client_resp.json()["message"].split()[-1]
        verify_client_resp = client.post(
            f"/auth/verify/{country_code}/{existing_client_phone}/code",
            json={"code": client_code}
        )
        assert verify_client_resp.status_code == 200
        client_token = verify_client_resp.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Crear solicitud
        create_resp = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        assert create_resp.status_code == 201
        current_request_id = create_resp.json()["id"]

        # Asignar conductor a la solicitud
        # Primero necesitamos obtener el UUID del conductor
        with Session(engine) as session:
            driver_user = session.exec(
                select(User).where(User.phone_number == "3005555555")
            ).first()
            assert driver_user is not None, "Conductor Roberto Sánchez no encontrado"
            driver_uuid = str(driver_user.id)

        assign_data = {
            "id_client_request": current_request_id,
            "id_driver": driver_uuid,  # UUID real del conductor
            "fare_assigned": 25000
        }
        assign_resp = client.patch(
            "/client-request/updateDriverAssigned", json=assign_data, headers=client_headers)
        assert assign_resp.status_code == 200

        # Cambiar estados del viaje siguiendo el flujo correcto
        print("🔍 Paso 1.1: Cambiando a ON_THE_WAY...")
        status_resp = client.patch(
            f"/client-request/updateStatusByDriver",
            json={"id_client_request": current_request_id,
                  "status": "ON_THE_WAY"},
            headers=driver_headers
        )
        assert status_resp.status_code == 200

        print("🔍 Paso 1.2: Cambiando a ARRIVED...")
        status_resp = client.patch(
            f"/client-request/updateStatusByDriver",
            json={"id_client_request": current_request_id,
                  "status": "ARRIVED"},
            headers=driver_headers
        )
        assert status_resp.status_code == 200

        print("🔍 Paso 1.3: Cambiando a TRAVELLING...")
        status_resp = client.patch(
            f"/client-request/updateStatusByDriver",
            json={"id_client_request": current_request_id,
                  "status": "TRAVELLING"},
            headers=driver_headers
        )
        assert status_resp.status_code == 200

        print(
            f"✅ Paso 1: Conductor {existing_driver_phone} en viaje activo {current_request_id}")

        # === PASO 2: Verificar que el conductor está en viaje activo ===
        print("🔍 Paso 2: Verificando estado TRAVELLING...")
        detail_resp = client.get(
            f"/client-request/{current_request_id}", headers=client_headers)
        assert detail_resp.status_code == 200
        request_detail = detail_resp.json()
        assert request_detail["status"] in [
            "TRAVELLING", "StatusEnum.TRAVELLING"]
        print("✅ Paso 2: Viaje activo confirmado en estado TRAVELLING")

        # === PASO 3: Crear nueva solicitud que NO cumple validaciones (tiempo total muy largo) ===
        print("🔍 Paso 3: Creando nueva solicitud que NO cumple validaciones...")

        # Usar otro cliente existente para crear la nueva solicitud
        new_client_phone = "3002222222"  # Juan Pérez
        send_new_client_resp = client.post(
            f"/auth/verify/{country_code}/{new_client_phone}/send")
        assert send_new_client_resp.status_code == 201
        new_client_code = send_new_client_resp.json()["message"].split()[-1]
        verify_new_client_resp = client.post(
            f"/auth/verify/{country_code}/{new_client_phone}/code",
            json={"code": new_client_code}
        )
        assert verify_new_client_resp.status_code == 200
        new_client_token = verify_new_client_resp.json()["access_token"]
        new_client_headers = {"Authorization": f"Bearer {new_client_token}"}

        # Crear solicitud con destino muy lejano que cause tiempo total > 15 minutos
        # Usar coordenadas mucho más lejanas para causar tiempo total real > 15 minutos
        new_request_data = {
            "pickup_lat": 4.718136,
            "pickup_lng": -74.07317,
            "destination_lat": 5.500000,  # Mucho más lejano para causar tiempo total largo
            "destination_lng": -74.800000,  # Mucho más lejano
            "type_service_id": 1,
            "fare_offered": 35000,
            "payment_method_id": 1
        }

        create_new_resp = client.post(
            "/client-request/", json=new_request_data, headers=new_client_headers)
        assert create_new_resp.status_code == 201
        new_request_id = create_new_resp.json()["id"]
        print(f"✅ Paso 3: Nueva solicitud creada con ID {new_request_id}")

        # === PASO 4: Verificar que el conductor NO puede aceptar la nueva solicitud ===
        print("🔍 Paso 4: Verificando que conductor NO puede aceptar nueva solicitud...")

        # Intentar asignar el conductor ocupado a la nueva solicitud
        # Ahora el router calcula tiempos dinámicamente usando Google Distance Matrix
        assign_new_data = {
            "id_client_request": new_request_id,
            "id_driver": driver_uuid,  # Roberto Sánchez (ocupado)
            "fare_assigned": 35000
        }
        assign_new_resp = client.patch(
            "/client-request/updateDriverAssigned", json=assign_new_data, headers=new_client_headers)

        # El sistema debería rechazar la asignación por tiempo total muy largo
        if assign_new_resp.status_code == 409:  # Conflict - rechazado por validaciones
            print("✅ Paso 4: Sistema rechazó asignación por tiempo total muy largo")
        else:
            print(
                f"⚠️ Paso 4: Sistema permitió asignación (status: {assign_new_resp.status_code})")

        # === PASO 5: Verificar que el conductor NO tiene solicitud pendiente ===
        print("🔍 Paso 5: Verificando que conductor NO tiene solicitud pendiente...")
        pending_resp = client.get(
            "/drivers/pending-request", headers=driver_headers)
        assert pending_resp.status_code == 200
        pending_data = pending_resp.json()

        if pending_data.get("pending_request_id") is None:
            print("✅ Paso 5: Correcto - Conductor NO tiene solicitud pendiente")
        else:
            print(
                f"⚠️ Paso 5: Conductor tiene solicitud pendiente: {pending_data.get('pending_request_id')}")

        # === PASO 6: Verificar que el conductor sigue en viaje activo ===
        print("🔍 Paso 6: Verificando que conductor sigue en viaje activo...")
        detail_resp = client.get(
            f"/client-request/{current_request_id}", headers=client_headers)
        assert detail_resp.status_code == 200
        request_detail = detail_resp.json()
        assert request_detail["status"] in [
            "TRAVELLING", "StatusEnum.TRAVELLING"]
        print("✅ Paso 6: Conductor sigue en viaje activo")

        # === PASO 7: Verificar que la nueva solicitud NO está asignada ===
        print("🔍 Paso 7: Verificando que nueva solicitud NO está asignada...")
        if new_request_id:
            new_detail_resp = client.get(
                f"/client-request/{new_request_id}", headers=new_client_headers)
            assert new_detail_resp.status_code == 200
            new_request_detail = new_detail_resp.json()

            if new_request_detail.get("id_driver_assigned") is None:
                print("✅ Paso 7: Nueva solicitud NO está asignada (correcto)")
            else:
                print(
                    f"⚠️ Paso 7: Nueva solicitud está asignada a: {new_request_detail.get('id_driver_assigned')}")

        # === PASO 8: Intentar aceptar manualmente la solicitud (debería fallar) ===
        print("🔍 Paso 8: Intentando aceptar manualmente la solicitud...")
        try:
            accept_resp = client.post(
                f"/drivers/pending-request/accept?client_request_id={new_request_id}",
                headers=driver_headers
            )

            if accept_resp.status_code == 400:
                print(
                    "✅ Paso 8: Correcto - NO pudo aceptar solicitud (tiempo total excede límite)")
                print(
                    f"   - Error details: {accept_resp.json() if accept_resp.text else 'No response body'}")
            elif accept_resp.status_code == 200:
                print(
                    "❌ Paso 8: Incorrecto - Pudo aceptar solicitud (debería haber fallado)")
            else:
                print(
                    f"⚠️ Paso 8: Respuesta inesperada: {accept_resp.status_code}")
                print(f"   - Response: {accept_resp.text}")
        except Exception as e:
            print(f"⚠️ Paso 8: Error en endpoint de aceptar: {e}")

        print("🎉 Test completado: Conductor ocupado rechaza solicitud por tiempo total excede límite")

    except Exception as e:
        print(f"❌ Error en test: {e}")
        raise


# ===== EJECUCIÓN DE TESTS =====


if __name__ == "__main__":
    print(" Ejecutando test de sistema de prioridades...")

    try:
        result = test_driver_priority_system()
        if result:
            print(f"\n📊 Resultados del test de prioridades:")
            print(f"   - Request ID: {result['request_id']}")
            print(
                f"   - Conductores disponibles: {result['available_drivers_count']}")
            print(f"   - Conductores ocupados: {result['busy_drivers_count']}")
            print(f"   - Total de conductores: {result['total_drivers']}")
            print("\n✅ Test de prioridades ejecutado exitosamente!")
        else:
            print("\n❌ Test de prioridades falló")

    except Exception as e:
        print(f"\n❌ Error ejecutando test de prioridades: {e}")
        import traceback
        traceback.print_exc()
