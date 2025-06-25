import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.user_fcm_token import UserFCMToken
from app.models.user import User
from app.models.client_request import ClientRequest, StatusEnum
from app.models.driver_trip_offer import DriverTripOffer
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.services.notification_service import NotificationService
from app.utils.notification_templates import NotificationTemplates
from uuid import UUID
import json
from app.models.vehicle_type import VehicleType


class TestFCMTokens:
    """Tests para el sistema de notificaciones FCM de Milla99"""

    def test_register_fcm_token(self, client: TestClient, session: Session):
        """Test para registrar un token FCM"""
        # Crear y autenticar un usuario
        user_data = {
            "full_name": "Test User",
            "country_code": "+57",
            "phone_number": "3009876543"
        }
        print(f"Intentando crear usuario con datos: {user_data}")
        user_response = client.post("/users/", json=user_data)
        print(
            f"Respuesta creación usuario - Status: {user_response.status_code}")
        print(f"Respuesta creación usuario - Body: {user_response.text}")

        if user_response.status_code != 201:
            print(f"Error en creación de usuario: {user_response.status_code}")
            print(f"Detalle del error: {user_response.json()}")
            assert user_response.status_code == 201

        # Enviar código de verificación
        print("Enviando código de verificación...")
        send_response = client.post("/auth/verify/+57/3009876543/send")
        print(f"Respuesta envío código - Status: {send_response.status_code}")
        print(f"Respuesta envío código - Body: {send_response.text}")
        assert send_response.status_code == 201
        code = send_response.json()["message"].split()[-1]
        print(f"Código obtenido: {code}")

        # Verificar código y obtener token
        print("Verificando código...")
        verify_response = client.post(
            "/auth/verify/+57/3009876543/code",
            json={"code": code}
        )
        print(
            f"Respuesta verificación - Status: {verify_response.status_code}")
        print(f"Respuesta verificación - Body: {verify_response.text}")
        assert verify_response.status_code == 200
        token = verify_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Token obtenido: {token[:20]}...")

        # Registrar token FCM
        fcm_data = {
            "fcm_token": "test_fcm_token_12345",
            "device_type": "android",
            "device_name": "Test Device"
        }
        print(f"Registrando token FCM: {fcm_data}")
        response = client.post("/fcm-token/register",
                               json=fcm_data, headers=headers)
        print(f"Respuesta registro FCM - Status: {response.status_code}")
        print(f"Respuesta registro FCM - Body: {response.text}")

        assert response.status_code == 201
        data = response.json()
        assert data["fcm_token"] == "test_fcm_token_12345"
        assert data["device_type"] == "android"
        assert data["device_name"] == "Test Device"
        assert data["is_active"] is True
        print("Test completado exitosamente")

    def test_deactivate_fcm_token(self, client: TestClient, session: Session):
        """Test para desactivar un token FCM"""
        # Crear y autenticar usuario
        user_data = {
            "full_name": "Test User Deactivate",
            "country_code": "+57",
            "phone_number": "3001234568"
        }
        print(f"Intentando crear usuario con datos: {user_data}")
        user_response = client.post("/users/", json=user_data)
        print(
            f"Respuesta creación usuario - Status: {user_response.status_code}")
        print(f"Respuesta creación usuario - Body: {user_response.text}")
        assert user_response.status_code == 201

        # Enviar código de verificación
        print("Enviando código de verificación...")
        send_response = client.post("/auth/verify/+57/3001234568/send")
        print(f"Respuesta envío código - Status: {send_response.status_code}")
        print(f"Respuesta envío código - Body: {send_response.text}")
        assert send_response.status_code == 201
        code = send_response.json()["message"].split()[-1]
        print(f"Código obtenido: {code}")

        # Verificar código y obtener token
        print("Verificando código...")
        verify_response = client.post(
            "/auth/verify/+57/3001234568/code",
            json={"code": code}
        )
        print(
            f"Respuesta verificación - Status: {verify_response.status_code}")
        print(f"Respuesta verificación - Body: {verify_response.text}")
        assert verify_response.status_code == 200
        token = verify_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Token obtenido: {token[:20]}...")

        # Registrar token FCM
        fcm_data = {
            "fcm_token": "test_fcm_token_deactivate",
            "device_type": "ios",
            "device_name": "iPhone Test"
        }
        print(f"Registrando token FCM: {fcm_data}")
        register_response = client.post(
            "/fcm-token/register", json=fcm_data, headers=headers)
        print(
            f"Respuesta registro FCM - Status: {register_response.status_code}")
        print(f"Respuesta registro FCM - Body: {register_response.text}")
        assert register_response.status_code == 201

        # Desactivar token
        print("Desactivando token FCM...")
        response = client.delete(
            f"/fcm-token/deactivate?fcm_token=test_fcm_token_deactivate",
            headers=headers
        )
        print(f"Respuesta desactivación - Status: {response.status_code}")
        print(f"Respuesta desactivación - Body: {response.text}")
        assert response.status_code == 200
        assert response.json()[
            "detail"] == "Token FCM desactivado exitosamente"
        print("Test de desactivación completado exitosamente")

    def test_get_my_fcm_tokens(self, client: TestClient, session: Session):
        """Test para obtener tokens FCM del usuario"""
        # Crear y autenticar usuario
        user_data = {
            "full_name": "Test User",
            "country_code": "+57",
            "phone_number": "3001234569"
        }
        user_response = client.post("/users/", json=user_data)
        assert user_response.status_code == 201

        # Autenticar
        send_response = client.post("/auth/verify/+57/3001234569/send")
        assert send_response.status_code == 201
        code = send_response.json()["message"].split()[-1]
        verify_response = client.post(
            "/auth/verify/+57/3001234569/code",
            json={"code": code}
        )
        assert verify_response.status_code == 200
        token = verify_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Registrar múltiples tokens
        tokens_data = [
            {"fcm_token": "token1", "device_type": "android",
                "device_name": "Phone 1"},
            {"fcm_token": "token2", "device_type": "ios", "device_name": "Phone 2"}
        ]

        for token_data in tokens_data:
            response = client.post("/fcm-token/register",
                                   json=token_data, headers=headers)
            assert response.status_code == 201

        # Obtener todos los tokens
        response = client.get("/fcm-token/my-tokens", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tokens"]) == 2
        assert any(t["fcm_token"] == "token1" for t in data["tokens"])
        assert any(t["fcm_token"] == "token2" for t in data["tokens"])

    def test_test_notification_endpoint(self, client: TestClient, session: Session):
        """Test para el endpoint de notificación de prueba básica"""
        # Crear y autenticar usuario
        user_data = {
            "full_name": "Test User",
            "country_code": "+57",
            "phone_number": "3001234570"
        }
        user_response = client.post("/users/", json=user_data)
        assert user_response.status_code == 201

        # Autenticar
        send_response = client.post("/auth/verify/+57/3001234570/send")
        assert send_response.status_code == 201
        code = send_response.json()["message"].split()[-1]
        verify_response = client.post(
            "/auth/verify/+57/3001234570/code",
            json={"code": code}
        )
        assert verify_response.status_code == 200
        token = verify_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Probar notificación sin token FCM (debería fallar pero no dar error)
        response = client.post("/fcm-token/test-notification", headers=headers)
        assert response.status_code == 404
        assert "No hay tokens FCM activos" in response.json()["detail"]

        # Registrar token y probar de nuevo
        fcm_data = {
            "fcm_token": "test_fcm_token_notification",
            "device_type": "android",
            "device_name": "Test Device"
        }
        register_response = client.post(
            "/fcm-token/register", json=fcm_data, headers=headers)
        assert register_response.status_code == 201

        # Ahora debería funcionar (aunque Firebase no esté configurado)
        response = client.post("/fcm-token/test-notification", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "Notificación enviada" in data["detail"]

    def test_business_notification_endpoint(self, client: TestClient, session: Session):
        """Test para el endpoint de notificaciones de negocio"""
        # Crear y autenticar usuario
        user_data = {
            "full_name": "Test User",
            "country_code": "+57",
            "phone_number": "3001234571"
        }
        user_response = client.post("/users/", json=user_data)
        assert user_response.status_code == 201

        # Autenticar
        send_response = client.post("/auth/verify/+57/3001234571/send")
        assert send_response.status_code == 201
        code = send_response.json()["message"].split()[-1]
        verify_response = client.post(
            "/auth/verify/+57/3001234571/code",
            json={"code": code}
        )
        assert verify_response.status_code == 200
        token = verify_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Probar diferentes tipos de notificaciones de negocio
        notification_types = [
            {"type": "driver_offer", "data": {"fare": 25000}},
            {"type": "driver_assigned", "data": {}},
            {"type": "driver_on_the_way", "data": {"estimated_time": 15}},
            {"type": "driver_arrived", "data": {}},
            {"type": "trip_started", "data": {}},
            {"type": "trip_finished", "data": {"fare": 30000}},
            {"type": "trip_cancelled_by_driver", "data": {
                "reason": "Vehículo en mal estado"}},
            {"type": "trip_assigned", "data": {}},
            {"type": "trip_cancelled_by_client", "data": {}},
            {"type": "payment_received", "data": {"fare": 25000}}
        ]

        for notification in notification_types:
            test_data = {
                "notification_type": notification["type"],
                **notification["data"]
            }
            response = client.post(
                "/fcm-token/test-business-notification",
                json=test_data,
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["notification_type"] == notification["type"]
            assert "enviada" in data["detail"]

    def test_invalid_notification_type(self, client: TestClient, session: Session):
        """Test para tipo de notificación inválido"""
        # Crear y autenticar usuario
        user_data = {
            "full_name": "Test User",
            "country_code": "+57",
            "phone_number": "3001234572"
        }
        user_response = client.post("/users/", json=user_data)
        assert user_response.status_code == 201

        # Autenticar
        send_response = client.post("/auth/verify/+57/3001234572/send")
        assert send_response.status_code == 201
        code = send_response.json()["message"].split()[-1]
        verify_response = client.post(
            "/auth/verify/+57/3001234572/code",
            json={"code": code}
        )
        assert verify_response.status_code == 200
        token = verify_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Probar tipo inválido
        test_data = {
            "notification_type": "invalid_type"
        }
        response = client.post(
            "/fcm-token/test-business-notification",
            json=test_data,
            headers=headers
        )
        assert response.status_code == 400
        assert "no válido" in response.json()["detail"]

    def test_notification_templates(self):
        """Test para las plantillas de notificaciones"""
        # Test plantilla de oferta de conductor
        template = NotificationTemplates.driver_offer_received(
            request_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            driver_name="Juan Pérez",
            fare=25000.0
        )
        assert template["title"] == "¡Nueva oferta de viaje!"
        assert "Juan Pérez ha hecho una oferta de $25,000" in template["body"]
        assert template["data"]["type"] == "driver_offer"
        assert template["data"]["action"] == "view_offers"

        # Test plantilla de conductor asignado
        template = NotificationTemplates.driver_assigned(
            request_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            driver_name="María García",
            vehicle_info="Toyota Corolla - ABC123"
        )
        assert template["title"] == "¡Conductor asignado!"
        assert "María García con Toyota Corolla - ABC123 está en camino" in template["body"]
        assert template["data"]["type"] == "driver_assigned"

        # Test plantilla de conductor en camino
        template = NotificationTemplates.driver_on_the_way(
            request_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            estimated_time=15
        )
        assert template["title"] == "Conductor en camino"
        assert "llegará en aproximadamente 15 minutos" in template["body"]
        assert template["data"]["action"] == "track_driver"

    def test_notification_service_integration(self, session: Session):
        """Test para la integración del servicio de notificaciones"""
        # Crear usuario de prueba
        user = User(
            full_name="Test User",
            country_code="+57",
            phone_number="3001234573"
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Crear token FCM de prueba
        fcm_token = UserFCMToken(
            user_id=user.id,
            fcm_token="test_service_token",
            device_type="android",
            device_name="Test Device",
            is_active=True
        )
        session.add(fcm_token)
        session.commit()

        # Crear solicitud de cliente
        client_request = ClientRequest(
            id_client=user.id,
            type_service_id=1,
            fare_offered=20000.0,
            pickup_description="Test Pickup",
            destination_description="Test Destination",
            status=StatusEnum.CREATED,
            pickup_position="POINT(4.718136 -74.073170)",
            destination_position="POINT(4.702468 -74.109776)"
        )
        session.add(client_request)
        session.commit()
        session.refresh(client_request)

        # Test servicio de notificaciones
        notification_service = NotificationService(session)

        # Test notificación de oferta (debería funcionar aunque no haya conductor)
        result = notification_service.notify_driver_offer(
            request_id=client_request.id,
            driver_id=user.id,
            fare=25000.0
        )
        # La notificación debería enviarse exitosamente
        assert result["success"] >= 0
        assert "error" not in result or result["error"] is None

    def test_notification_service_with_driver_info(self, session: Session):
        """Test para el servicio de notificaciones con información completa de conductor"""
        # Crear usuario conductor
        driver = User(
            full_name="Test Driver",
            country_code="+57",
            phone_number="3001234574"
        )
        session.add(driver)
        session.commit()
        session.refresh(driver)

        # Asignar rol de conductor
        driver_role = UserHasRole(
            id_user=driver.id,
            id_rol="DRIVER",
            status=RoleStatus.APPROVED
        )
        session.add(driver_role)
        session.commit()

        # Crear información del conductor
        from app.models.driver_info import DriverInfo
        from app.models.vehicle_info import VehicleInfo
        from app.models.vehicle_type import VehicleType

        driver_info = DriverInfo(
            user_id=driver.id,
            first_name="Test",
            last_name="Driver",
            email="driver@test.com",
            birth_date="1990-01-01"
        )
        session.add(driver_info)
        session.commit()

        # Obtener tipo de vehículo (Car)
        car_type = session.exec(select(VehicleType).where(
            VehicleType.name == "Car")).first()
        if not car_type:
            # Si no existe, crear uno
            car_type = VehicleType(
                name="Car",
                description="Four-wheeled vehicle for passenger transportation",
                capacity=4
            )
            session.add(car_type)
            session.commit()
            session.refresh(car_type)

        vehicle_info = VehicleInfo(
            brand="Toyota",
            model="Corolla",
            model_year=2020,
            color="Blanco",
            plate="ABC123",
            vehicle_type_id=car_type.id,  # Agregar el campo obligatorio
            driver_info_id=driver_info.id  # Cambiar user_id por driver_info_id
        )
        session.add(vehicle_info)
        session.commit()

        # Crear usuario cliente
        client = User(
            full_name="Test Client",
            country_code="+57",
            phone_number="3001234575"
        )
        session.add(client)
        session.commit()
        session.refresh(client)

        # Crear token FCM para el cliente
        fcm_token = UserFCMToken(
            user_id=client.id,
            fcm_token="test_client_token",
            device_type="android",
            device_name="Client Device",
            is_active=True
        )
        session.add(fcm_token)
        session.commit()

        # Crear solicitud de cliente
        client_request = ClientRequest(
            id_client=client.id,
            type_service_id=1,
            fare_offered=20000.0,
            pickup_description="Test Pickup",
            destination_description="Test Destination",
            status=StatusEnum.CREATED,
            pickup_position="POINT(4.718136 -74.073170)",
            destination_position="POINT(4.702468 -74.109776)"
        )
        session.add(client_request)
        session.commit()
        session.refresh(client_request)

        # Test notificación de oferta (ahora debería funcionar)
        notification_service = NotificationService(session)
        result = notification_service.notify_driver_offer(
            request_id=client_request.id,
            driver_id=driver.id,
            fare=25000.0
        )

        # Debería tener éxito aunque Firebase no esté configurado
        assert "success" in result
        assert "failed" in result

    # def test_multiple_tokens_per_user(self, client: TestClient, session: Session):
    #     """Test para múltiples tokens por usuario"""
    #     # Crear y autenticar usuario
    #     user_data = {
    #         "full_name": "Test User",
    #         "country_code": "+57",
    #         "phone_number": "3001234576"
    #     }
    #     user_response = client.post("/users/", json=user_data)
    #     assert user_response.status_code == 201

    #     # Autenticar
    #     send_response = client.post("/auth/verify/+57/3001234576/send")
    #     assert send_response.status_code == 201
    #     code = send_response.json()["message"].split()[-1]
    #     verify_response = client.post(
    #         "/auth/verify/+57/3001234576/code",
    #         json={"code": code}
    #     )
    #     assert verify_response.status_code == 200
    #     token = verify_response.json()["access_token"]
    #     headers = {"Authorization": f"Bearer {token}"}

    #     # Registrar múltiples tokens
    #     tokens = [
    #         {"fcm_token": "token_android", "device_type": "android",
    #             "device_name": "Android Phone"},
    #         {"fcm_token": "token_ios", "device_type": "ios", "device_name": "iPhone"},
    #         {"fcm_token": "token_web", "device_type": "web",
    #             "device_name": "Web Browser"}
    #     ]

    #     for token_data in tokens:
    #         response = client.post("/fcm-token/register",
    #                                json=token_data, headers=headers)
    #         assert response.status_code == 201

    #     # Obtener todos los tokens
    #     response = client.get("/fcm-token/my-tokens", headers=headers)
    #     assert response.status_code == 200
    #     data = response.json()
    #     assert len(data["tokens"]) == 3

    #     # Verificar que todos están activos
    #     for token_info in data["tokens"]:
    #         assert token_info["is_active"] is True

    #     # Desactivar uno y verificar
    #     response = client.delete(
    #         "/fcm-token/deactivate?fcm_token=token_android",
    #         headers=headers
    #     )
    #     assert response.status_code == 200

    #     # Obtener tokens de nuevo y verificar que uno está inactivo
    #     response = client.get("/fcm-token/my-tokens", headers=headers)
    #     assert response.status_code == 200
    #     data = response.json()

    #     android_token = next(
    #         t for t in data["tokens"] if t["fcm_token"] == "token_android")
    #     assert android_token["is_active"] is False
