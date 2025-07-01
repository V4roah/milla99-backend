import pytest
from fastapi.testclient import TestClient
from app.main import app
from sqlmodel import Session, select
from uuid import UUID
from app.models.user import User
from app.models.client_request import ClientRequest, StatusEnum
from app.models.chat_message import ChatMessage, MessageStatus
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.core.db import engine
from datetime import datetime, timedelta
import pytz
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
import time

client = TestClient(app)

COLOMBIA_TZ = pytz.timezone("America/Bogota")


class TestChatSystem:
    """Tests para el sistema de chat"""

    def test_send_message_success(self, client: TestClient):
        """Test para enviar un mensaje exitosamente"""
        # Crear usuarios de prueba
        client_user, driver_user = self._create_test_users()

        # Crear solicitud de viaje
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Enviar mensaje
        message_data = {
            "receiver_id": str(driver_user.id),
            "client_request_id": str(client_request.id),
            "message": "Hola conductor, ¿dónde estás?"
        }

        response = client.post(
            "/chat/send", json=message_data, headers=client_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Hola conductor, ¿dónde estás?"
        assert data["sender_id"] == str(client_user.id)
        assert data["receiver_id"] == str(driver_user.id)
        assert data["client_request_id"] == str(client_request.id)
        assert data["status"] == "SENT"
        assert data["is_read"] == False

    def test_send_message_unauthorized(self, client: TestClient):
        """Test para enviar mensaje sin autenticación"""
        message_data = {
            "receiver_id": "123e4567-e89b-12d3-a456-426614174000",
            "client_request_id": "123e4567-e89b-12d3-a456-426614174001",
            "message": "Mensaje sin autorización"
        }

        response = client.post("/chat/send", json=message_data)
        assert response.status_code == 401

    def test_get_conversation_success(self, client: TestClient):
        """Test para obtener conversación exitosamente"""
        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Crear algunos mensajes en la BD directamente
        self._create_test_messages(
            client_user.id, driver_user.id, client_request.id)

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Obtener conversación
        response = client.get(
            f"/chat/conversation/{client_request.id}", headers=client_headers)

        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 2  # Deberían ser 2 mensajes
        assert messages[0]["message"] == "Hola cliente"
        assert messages[1]["message"] == "Hola conductor"

    def test_get_conversation_unauthorized_access(self, client: TestClient):
        """Test para acceder a conversación sin autorización"""
        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Crear un tercer usuario
        third_user = self._create_user("3009999999", "Usuario Tercero")

        # Autenticar como tercer usuario
        third_token = self._authenticate_user(client, third_user.phone_number)
        third_headers = {"Authorization": f"Bearer {third_token}"}

        # Intentar acceder a conversación que no le pertenece
        response = client.get(
            f"/chat/conversation/{client_request.id}", headers=third_headers)

        assert response.status_code == 400  # Debería fallar por no tener acceso

    def test_mark_messages_as_read(self, client: TestClient):
        """Test para marcar mensajes como leídos"""
        print(f"\n🧪 INICIANDO TEST: test_mark_messages_as_read")

        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Crear mensajes no leídos
        self._create_test_messages(
            client_user.id, driver_user.id, client_request.id)

        # Autenticar como conductor (receptor de mensajes)
        driver_token = self._authenticate_user(
            client, driver_user.phone_number)
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Verificar mensajes antes de marcar como leído
        print(f"\n🔍 DEBUG: Verificando mensajes antes de marcar como leído")
        try:
            with Session(engine) as session:
                unread_messages = session.exec(
                    select(ChatMessage).where(
                        ChatMessage.client_request_id == client_request.id,
                        ChatMessage.receiver_id == driver_user.id,
                        ChatMessage.is_read == False
                    )
                ).all()

                print(
                    f"📊 Mensajes no leídos para el conductor: {len(unread_messages)}")
                for msg in unread_messages:
                    print(
                        f"   - ID: {msg.id}, Sender: {msg.sender_id}, Message: '{msg.message}', Read: {msg.is_read}")
        except Exception as e:
            print(f"💥 EXCEPCIÓN al verificar mensajes: {str(e)}")
            import traceback
            print(f"💥 TRACEBACK: {traceback.format_exc()}")

        # Marcar como leído
        print(f"\n🔍 DEBUG: Llamando endpoint para marcar como leído")
        print(f"📤 URL: /chat/mark-read/{client_request.id}")
        print(f"📤 Headers: {driver_headers}")

        try:
            response = client.patch(
                f"/chat/mark-read/{client_request.id}", headers=driver_headers)

            print(f"📥 Response status: {response.status_code}")
            print(f"📥 Response headers: {dict(response.headers)}")
            print(f"📥 Response text: {response.text}")

            assert response.status_code == 200
            data = response.json()
            print(f"📥 Response data: {data}")

            # Debería haber 1 mensaje marcado como leído
            assert data["count"] == 1

        except Exception as e:
            print(f"💥 EXCEPCIÓN al marcar como leído: {str(e)}")
            import traceback
            print(f"💥 TRACEBACK: {traceback.format_exc()}")
            raise

    def test_get_unread_count(self, client: TestClient):
        """Test para obtener conteo de mensajes no leídos"""
        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Crear mensajes no leídos
        self._create_test_messages(
            client_user.id, driver_user.id, client_request.id)

        # Autenticar como conductor
        driver_token = self._authenticate_user(
            client, driver_user.phone_number)
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Obtener conteo general
        response = client.get("/chat/unread-count", headers=driver_headers)

        assert response.status_code == 200
        unread_counts = response.json()
        # Debería tener 1 conversación con mensajes no leídos
        assert len(unread_counts) == 1
        assert unread_counts[0]["unread_count"] == 1
        assert unread_counts[0]["conversation_id"] == str(client_request.id)

    def test_get_conversation_unread_count(self, client: TestClient):
        """Test para obtener conteo de mensajes no leídos de una conversación específica"""
        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Crear mensajes no leídos
        self._create_test_messages(
            client_user.id, driver_user.id, client_request.id)

        # Autenticar como conductor
        driver_token = self._authenticate_user(
            client, driver_user.phone_number)
        driver_headers = {"Authorization": f"Bearer {driver_token}"}

        # Obtener conteo específico
        response = client.get(
            f"/chat/unread-count/{client_request.id}", headers=driver_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 1
        assert data["client_request_id"] == str(client_request.id)

    def test_message_retention_policy(self, client: TestClient):
        """Test para verificar que los mensajes tienen fecha de expiración"""
        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Enviar mensaje
        message_data = {
            "receiver_id": str(driver_user.id),
            "client_request_id": str(client_request.id),
            "message": "Mensaje de prueba"
        }

        response = client.post(
            "/chat/send", json=message_data, headers=client_headers)
        assert response.status_code == 201

        # Verificar que el mensaje tiene fecha de expiración en la BD
        with Session(engine) as session:
            message = session.exec(
                select(ChatMessage).where(
                    ChatMessage.message == "Mensaje de prueba")
            ).first()

            assert message is not None
            assert message.expires_at > datetime.now(COLOMBIA_TZ)
            # Debería expirar en aproximadamente 30 días
            expected_expiry = datetime.now(COLOMBIA_TZ) + timedelta(days=30)
            assert abs((message.expires_at - expected_expiry).days) <= 1

    # Métodos auxiliares para crear datos de prueba
    def _create_test_users(self):
        """Crea un cliente y un conductor para las pruebas"""
        # Usar timestamps para hacer números únicos
        timestamp = int(time.time()) % 10000000  # 7 dígitos del timestamp

        # Cliente: 300 + 7 dígitos = 10 dígitos total
        client_phone = f"300{timestamp:07d}"
        # Conductor: 301 + 7 dígitos = 10 dígitos total (diferente prefijo)
        driver_phone = f"301{timestamp:07d}"

        print(f"📱 Creando cliente con teléfono: {client_phone}")
        print(f"📱 Creando conductor con teléfono: {driver_phone}")

        client_user = self._create_user(client_phone, "Cliente Test")
        driver_user = self._create_user(driver_phone, "Conductor Test")

        # Asignar roles
        self._assign_role(client_user.id, "CLIENT")
        self._assign_role(driver_user.id, "DRIVER")

        return client_user, driver_user

    def _create_user(self, phone_number: str, full_name: str) -> User:
        """Crea un usuario de prueba directamente en la BD"""
        print(f"\n🔍 DEBUG: Creando usuario {phone_number} directamente en BD")

        try:
            with Session(engine) as session:
                # Verificar si el usuario ya existe
                existing_user = session.exec(
                    select(User).where(User.phone_number == phone_number)
                ).first()

                if existing_user:
                    print(f"✅ Usuario ya existe en BD: {existing_user.id}")
                    return existing_user

                # Crear usuario directamente en la BD
                user = User(
                    full_name=full_name,
                    country_code="+57",
                    phone_number=phone_number,
                    is_verified_phone=True,
                    is_active=True
                )
                session.add(user)
                session.commit()
                session.refresh(user)

                print(f"✅ Usuario creado exitosamente en BD: {user.id}")
                return user

        except Exception as e:
            print(f"💥 EXCEPCIÓN al crear usuario en BD: {str(e)}")
            import traceback
            print(f"💥 TRACEBACK: {traceback.format_exc()}")
            raise

    def _assign_role(self, user_id: UUID, role_name: str):
        """Asigna un rol a un usuario"""
        with Session(engine) as session:
            role = session.exec(
                select(UserHasRole).where(UserHasRole.id_user == user_id)
            ).first()

            if not role:
                role = UserHasRole(
                    id_user=user_id,
                    id_rol=role_name,
                    status=RoleStatus.APPROVED
                )
                session.add(role)
                session.commit()

    def _create_test_client_request(self, client_id: UUID, driver_id: UUID) -> ClientRequest:
        """Crea una solicitud de viaje de prueba"""
        # Obtener el usuario cliente para autenticarlo
        with Session(engine) as session:
            client_user = session.exec(
                select(User).where(User.id == client_id)
            ).first()

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Crear solicitud usando el endpoint de la API
        request_data = {
            "fare_offered": 20000,
            "pickup_description": "Test pickup",
            "destination_description": "Test destination",
            "pickup_lat": 4.718136,
            "pickup_lng": -74.07317,
            "destination_lat": 4.702468,
            "destination_lng": -74.076542,
            "type_service_id": 1,  # Car
            "payment_method_id": 1  # Cash
        }

        response = client.post(
            "/client-request/", json=request_data, headers=client_headers)
        assert response.status_code == 201
        client_request_data = response.json()

        # Obtener la solicitud de la base de datos
        with Session(engine) as session:
            client_request = session.exec(
                select(ClientRequest).where(
                    ClientRequest.id == UUID(client_request_data["id"]))
            ).first()

            # Asignar el conductor manualmente
            client_request.id_driver_assigned = driver_id
            client_request.status = "ACCEPTED"
            session.add(client_request)
            session.commit()
            session.refresh(client_request)

            return client_request

    def _create_test_messages(self, client_id: UUID, driver_id: UUID, client_request_id: UUID):
        """Crea mensajes de prueba"""
        print(f"\n🔍 DEBUG: Creando mensajes de prueba")
        print(f"📤 Cliente ID: {client_id}")
        print(f"🚗 Conductor ID: {driver_id}")
        print(f"📋 Client Request ID: {client_request_id}")

        try:
            with Session(engine) as session:
                # Mensaje del cliente al conductor (NO LEÍDO - el conductor debe marcarlo como leído)
                message1 = ChatMessage(
                    sender_id=client_id,
                    receiver_id=driver_id,
                    client_request_id=client_request_id,
                    message="Hola conductor, ¿dónde estás?",
                    status=MessageStatus.SENT,
                    is_read=False  # NO LEÍDO - el conductor debe marcarlo
                )

                # Mensaje del conductor al cliente (NO LEÍDO - el cliente debe marcarlo como leído)
                message2 = ChatMessage(
                    sender_id=driver_id,
                    receiver_id=client_id,
                    client_request_id=client_request_id,
                    message="Hola cliente, estoy llegando",
                    status=MessageStatus.SENT,
                    is_read=False  # NO LEÍDO - el cliente debe marcarlo
                )

                session.add(message1)
                session.add(message2)
                session.commit()

                print(
                    f"✅ Mensaje 1 creado: {message1.id} (cliente → conductor, no leído)")
                print(
                    f"✅ Mensaje 2 creado: {message2.id} (conductor → cliente, no leído)")

                # Verificar que se crearon correctamente
                messages = session.exec(
                    select(ChatMessage).where(
                        ChatMessage.client_request_id == client_request_id
                    )
                ).all()

                print(
                    f"📊 Total mensajes en BD para esta conversación: {len(messages)}")
                for msg in messages:
                    print(
                        f"   - ID: {msg.id}, Sender: {msg.sender_id}, Receiver: {msg.receiver_id}, Read: {msg.is_read}")

        except Exception as e:
            print(f"💥 EXCEPCIÓN al crear mensajes de prueba: {str(e)}")
            import traceback
            print(f"💥 TRACEBACK: {traceback.format_exc()}")
            raise

    def _authenticate_user(self, client: TestClient, phone_number: str) -> str:
        """Autentica un usuario y retorna el token"""
        # Enviar código de verificación
        response = client.post(f"/auth/verify/+57/{phone_number}/send")
        assert response.status_code == 201

        # Extraer código del mensaje
        message = response.json()["message"]
        code = message.split()[-1]

        # Verificar código
        response = client.post(
            f"/auth/verify/+57/{phone_number}/code",
            json={"code": code}
        )
        assert response.status_code == 200

        return response.json()["access_token"]

    def test_chat_messages_deleted_when_request_paid(self, client: TestClient):
        """Test que verifica que los mensajes de chat se eliminan automáticamente cuando un ClientRequest cambia a estado PAID"""
        print(f"\n🧪 INICIANDO TEST: test_chat_messages_deleted_when_request_paid")

        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Guardar el ID para usarlo después
        client_request_id = client_request.id

        # Crear algunos mensajes de chat
        self._create_test_messages(
            client_user.id, driver_user.id, client_request_id)

        # Verificar que los mensajes existen
        with Session(engine) as session:
            messages = session.exec(
                select(ChatMessage).where(
                    ChatMessage.client_request_id == client_request_id)
            ).all()
            assert len(messages) == 2
            print(f"✅ Mensajes creados: {len(messages)}")

        # Cambiar el estado a PAID (esto debería activar la limpieza automática)
        with Session(engine) as session:
            client_request = session.exec(
                select(ClientRequest).where(
                    ClientRequest.id == client_request_id)
            ).first()
            client_request.status = "PAID"
            session.add(client_request)
            session.commit()
            print(f"✅ Estado cambiado a PAID")

        # Verificar que los mensajes fueron eliminados automáticamente
        with Session(engine) as session:
            remaining_messages = session.exec(
                select(ChatMessage).where(
                    ChatMessage.client_request_id == client_request_id)
            ).all()
            assert len(remaining_messages) == 0
            print(
                f"✅ Mensajes eliminados automáticamente: {len(remaining_messages)}")

    def test_cannot_send_messages_to_paid_request(self, client: TestClient):
        """Test que verifica que no se pueden enviar mensajes a un ClientRequest en estado PAID"""
        print(f"\n🧪 INICIANDO TEST: test_cannot_send_messages_to_paid_request")

        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Cambiar el estado a PAID
        with Session(engine) as session:
            client_request = session.exec(
                select(ClientRequest).where(
                    ClientRequest.id == client_request.id)
            ).first()
            client_request.status = "PAID"
            session.add(client_request)
            session.commit()
            print(f"✅ Estado cambiado a PAID")

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Intentar enviar mensaje (debería fallar)
        message_data = {
            "receiver_id": str(driver_user.id),
            "client_request_id": str(client_request.id),
            "message": "Este mensaje no debería enviarse"
        }

        response = client.post(
            "/chat/send", json=message_data, headers=client_headers)
        assert response.status_code == 400
        assert "No se pueden enviar mensajes en un viaje completado" in response.json()[
            "detail"]
        print(f"✅ Mensaje rechazado correctamente para viaje completado")

    def test_cannot_send_messages_to_cancelled_request(self, client: TestClient):
        """Test que verifica que no se pueden enviar mensajes a un ClientRequest cancelado"""
        print(f"\n🧪 INICIANDO TEST: test_cannot_send_messages_to_cancelled_request")

        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Cambiar el estado a CANCELLED
        with Session(engine) as session:
            client_request = session.exec(
                select(ClientRequest).where(
                    ClientRequest.id == client_request.id)
            ).first()
            client_request.status = "CANCELLED"
            session.add(client_request)
            session.commit()
            print(f"✅ Estado cambiado a CANCELLED")

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Intentar enviar mensaje (debería fallar)
        message_data = {
            "receiver_id": str(driver_user.id),
            "client_request_id": str(client_request.id),
            "message": "Este mensaje no debería enviarse"
        }

        response = client.post(
            "/chat/send", json=message_data, headers=client_headers)
        assert response.status_code == 400
        assert "No se pueden enviar mensajes en un viaje cancelado" in response.json()[
            "detail"]
        print(f"✅ Mensaje rechazado correctamente para viaje cancelado")

    def test_get_conversation_returns_empty_for_paid_request(self, client: TestClient):
        """Test que verifica que get_conversation_messages retorna lista vacía para ClientRequest en estado PAID"""
        print(f"\n🧪 INICIANDO TEST: test_get_conversation_returns_empty_for_paid_request")

        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Crear algunos mensajes
        self._create_test_messages(
            client_user.id, driver_user.id, client_request.id)

        # Cambiar el estado a PAID
        with Session(engine) as session:
            client_request = session.exec(
                select(ClientRequest).where(
                    ClientRequest.id == client_request.id)
            ).first()
            client_request.status = "PAID"
            session.add(client_request)
            session.commit()
            print(f"✅ Estado cambiado a PAID")

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Intentar obtener mensajes (debería retornar lista vacía)
        response = client.get(
            f"/chat/conversation/{client_request.id}", headers=client_headers)
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 0
        print(f"✅ Conversación retorna lista vacía para viaje completado")

    def test_chat_active_during_active_request(self, client: TestClient):
        """Test que verifica que el chat funciona normalmente durante un ClientRequest activo"""
        print(f"\n🧪 INICIANDO TEST: test_chat_active_during_active_request")

        # Crear usuarios y solicitud
        client_user, driver_user = self._create_test_users()
        client_request = self._create_test_client_request(
            client_user.id, driver_user.id)

        # Verificar que el estado es activo
        with Session(engine) as session:
            client_request = session.exec(
                select(ClientRequest).where(
                    ClientRequest.id == client_request.id)
            ).first()
            assert client_request.status in [
                "ACCEPTED", "ON_THE_WAY", "ARRIVED", "TRAVELLING", "FINISHED"]
            print(f"✅ Estado activo: {client_request.status}")

        # Autenticar como cliente
        client_token = self._authenticate_user(
            client, client_user.phone_number)
        client_headers = {"Authorization": f"Bearer {client_token}"}

        # Enviar mensaje (debería funcionar)
        message_data = {
            "receiver_id": str(driver_user.id),
            "client_request_id": str(client_request.id),
            "message": "Mensaje durante viaje activo"
        }

        response = client.post(
            "/chat/send", json=message_data, headers=client_headers)
        assert response.status_code == 201
        print(f"✅ Mensaje enviado correctamente durante viaje activo")

        # Obtener conversación (debería funcionar)
        response = client.get(
            f"/chat/conversation/{client_request.id}", headers=client_headers)
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) > 0
        print(f"✅ Conversación accesible durante viaje activo")
