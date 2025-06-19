import random
import time
from locust import HttpUser, task, between, events
from typing import Dict, List
import json
from datetime import datetime, date
from uuid import UUID
import io


class ClientRequestLoadTest(HttpUser):
    """
    Usuario virtual que simula el flujo completo de client request
    Incluye: creación de solicitudes, asignación de conductor, cambio de estados
    """

    # Tiempo de espera entre tareas (1-3 segundos para simular comportamiento real)
    wait_time = between(1, 3)

    # Token de autenticación
    auth_token: str = None

    # Datos del usuario (puede ser cliente o conductor)
    user_data: Dict = None

    # Contador de requests
    request_count: int = 0

    # Estado del usuario (CLIENT o DRIVER)
    user_role: str = "CLIENT"

    # Solicitudes creadas por este usuario
    created_requests: List[str] = []

    # Métricas de performance por endpoint
    endpoint_metrics: Dict = {}

    def on_start(self):
        """Se ejecuta al iniciar cada usuario virtual"""
        print("Iniciando usuario virtual para flujo completo")
        self.request_count = 0
        self.created_requests = []
        self.initialize_metrics()

        # Usar el ID del usuario virtual para determinar el rol
        # Usuarios pares serán conductores, impares serán clientes
        user_id = getattr(self, 'user_id', random.randint(1, 1000))
        self.user_role = "DRIVER" if user_id % 2 == 0 else "CLIENT"

        if self.user_role == "CLIENT":
            self.create_test_client()
        else:
            self.create_test_driver()

        self.authenticate_user()
        print(f"Usuario {self.user_role} inicializado completamente")

    def initialize_metrics(self):
        """Inicializa las métricas por endpoint"""
        self.endpoint_metrics = {
            "create_user": {"requests": 0, "total_duration": 0, "errors": 0},
            "send_verification": {"requests": 0, "total_duration": 0, "errors": 0},
            "verify_code": {"requests": 0, "total_duration": 0, "errors": 0},
            "create_request": {"requests": 0, "total_duration": 0, "errors": 0},
            "assign_driver": {"requests": 0, "total_duration": 0, "errors": 0},
            "update_status": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_requests_by_status": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_trip_detail": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_nearby_requests": {"requests": 0, "total_duration": 0, "errors": 0},
            "update_position": {"requests": 0, "total_duration": 0, "errors": 0}
        }

    def create_test_client(self):
        """Crea un cliente de prueba único"""
        start_time = time.time()

        # Generar número de teléfono colombiano válido
        prefix = 300
        suffix = random.randint(1000000, 9999999)
        phone_number = f"{prefix}{suffix}"

        # Generar nombre real (sin números)
        nombres = ["Juan", "María", "Carlos", "Ana", "Luis",
                   "Sofia", "Diego", "Valentina", "Andrés", "Camila"]
        apellidos = ["García", "Rodríguez", "López", "Martínez",
                     "González", "Pérez", "Sánchez", "Ramírez", "Torres", "Flores"]

        nombre = random.choice(nombres)
        apellido = random.choice(apellidos)
        full_name = f"{nombre} {apellido}"

        # Datos del cliente
        self.user_data = {
            "full_name": full_name,
            "country_code": "+57",
            "phone_number": phone_number,
            "referral_phone": None
        }

        print(f"Creando cliente: {full_name} - {phone_number}")

        try:
            response = self.client.post(
                "/users/",
                json=self.user_data,
                name="Create Client"
            )

            duration = time.time() - start_time
            success = response.status_code in [
                201, 409]  # 201 = creado, 409 = ya existe
            self.record_metric("create_user", duration, success)

            if response.status_code == 201:
                data = response.json()
                self.user_data["id"] = data.get("id")
                print(
                    f"[SUCCESS] Cliente creado: {phone_number} ({duration:.2f}s)")
            elif response.status_code == 409:
                print(
                    f"[INFO] Cliente ya existe: {phone_number} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error creando cliente: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("create_user", duration, False)
            print(f"[ERROR] Exception creando cliente: {e} ({duration:.2f}s)")

    def create_test_driver(self):
        """Crea un conductor de prueba completo usando el patrón que funciona"""
        start_time = time.time()

        # Generar número de teléfono colombiano válido
        prefix = 301
        suffix = random.randint(1000000, 9999999)
        phone_number = f"{prefix}{suffix}"

        # Generar nombre real
        nombres = ["Pedro", "Carmen", "Roberto", "Isabel", "Miguel",
                   "Patricia", "Fernando", "Lucía", "Ricardo", "Elena"]
        apellidos = ["Herrera", "Morales", "Castro", "Reyes", "Jiménez",
                     "Moreno", "Romero", "Alvarez", "Torres", "Ruiz"]

        nombre = random.choice(nombres)
        apellido = random.choice(apellidos)
        full_name = f"{nombre} {apellido}"

        # Datos del usuario
        user_data = {
            "full_name": full_name,
            "country_code": "+57",
            "phone_number": phone_number
        }

        # Datos del conductor
        driver_info_data = {
            "first_name": nombre,
            "last_name": apellido,
            "birth_date": str(date(1990, 1, 1)),
            "email": f"{nombre.lower()}.{apellido.lower()}@example.com"
        }

        # Datos del vehículo
        marcas = ["Toyota", "Honda", "Mazda", "Kia",
                  "Hyundai", "Ford", "Chevrolet", "Nissan"]
        modelos = ["Corolla", "Civic", "3", "Rio",
                   "Accent", "Focus", "Spark", "Sentra"]
        colores = ["Blanco", "Negro", "Rojo", "Azul", "Gris", "Plateado"]

        vehicle_info_data = {
            "brand": random.choice(marcas),
            "model": random.choice(modelos),
            "model_year": random.randint(2018, 2024),
            "color": random.choice(colores),
            "plate": f"ABC{random.randint(100, 999)}",
            "vehicle_type_id": 1  # Car
        }

        # Datos de documentos
        driver_documents_data = {
            "license_expiration_date": str(date(2026, 1, 1)),
            "soat_expiration_date": str(date(2025, 12, 31)),
            "vehicle_technical_inspection_expiration_date": str(date(2025, 12, 31))
        }

        # Guardar datos para uso posterior
        self.user_data = {
            "user": user_data,
            "driver_info": driver_info_data,
            "vehicle_info": vehicle_info_data,
            "documents": driver_documents_data
        }

        print(f"Creando conductor: {full_name} - {phone_number}")

        try:
            # Crear archivos simulados
            selfie = ("selfie.jpg", io.BytesIO(
                b"fake-selfie-data"), "image/jpeg")
            property_card_front = ("property_front.jpg", io.BytesIO(
                b"fake-property-front"), "image/jpeg")
            property_card_back = ("property_back.jpg", io.BytesIO(
                b"fake-property-back"), "image/jpeg")
            license_front = ("license_front.jpg", io.BytesIO(
                b"fake-license-front"), "image/jpeg")
            license_back = ("license_back.jpg", io.BytesIO(
                b"fake-license-back"), "image/jpeg")
            soat = ("soat.jpg", io.BytesIO(b"fake-soat"), "image/jpeg")
            vehicle_technical_inspection = (
                "tech.jpg", io.BytesIO(b"fake-tech"), "image/jpeg")

            # Construir el payload multipart/form-data
            data = {
                "user": (None, json.dumps(user_data), "application/json"),
                "driver_info": (None, json.dumps(driver_info_data), "application/json"),
                "vehicle_info": (None, json.dumps(vehicle_info_data), "application/json"),
                "driver_documents": (None, json.dumps(driver_documents_data), "application/json"),
                "selfie": selfie,
                "property_card_front": property_card_front,
                "property_card_back": property_card_back,
                "license_front": license_front,
                "license_back": license_back,
                "soat": soat,
                "vehicle_technical_inspection": vehicle_technical_inspection,
            }

            response = self.client.post(
                "/drivers/",
                files=data,
                name="Create Driver"
            )

            duration = time.time() - start_time
            success = response.status_code in [201, 409]
            self.record_metric("create_user", duration, success)

            if response.status_code == 201:
                print(
                    f"[SUCCESS] Conductor creado: {phone_number} ({duration:.2f}s)")

                # Extraer user_id de la respuesta
                try:
                    response_data = response.json()
                    user_id = response_data.get("user", {}).get("id")
                    if user_id:
                        self.user_data['user']['id'] = user_id
                        print(f"[DEBUG] User ID extraído: {user_id}")
                    else:
                        print(
                            f"[WARNING] No se pudo extraer user_id de la respuesta")
                except Exception as e:
                    print(f"[WARNING] Error extrayendo user_id: {e}")

                # Aprobar rol de conductor directamente en DB
                self.approve_driver_role()

            elif response.status_code == 409:
                print(
                    f"[INFO] Conductor ya existe: {phone_number} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error creando conductor: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("create_user", duration, False)
            print(
                f"[ERROR] Exception creando conductor: {e} ({duration:.2f}s)")

    def approve_driver_role(self):
        """Aprueba el rol del conductor directamente en la base de datos"""
        try:
            from app.core.db import engine
            from sqlmodel import Session
            from app.models.user_has_roles import UserHasRole, RoleStatus
            from sqlmodel import select

            with Session(engine) as session:
                # Buscar el UserHasRole del conductor
                user_id_str = self.user_data['user']['id']
                user_id_uuid = UUID(user_id_str)

                user_role = session.exec(
                    select(UserHasRole).where(
                        UserHasRole.id_user == user_id_uuid,
                        UserHasRole.id_rol == "DRIVER"
                    )
                ).first()

                if user_role:
                    # Aprobar el rol
                    user_role.status = RoleStatus.APPROVED
                    user_role.is_verified = True
                    user_role.verified_at = datetime.now()

                    session.commit()
                    print(
                        f"[SUCCESS] Rol de conductor aprobado para {self.user_data['user']['phone_number']}")
                    return True
                else:
                    print(
                        f"[WARNING] No se encontró UserHasRole para user_id: {user_id_str}")
                    return False

        except Exception as e:
            print(
                f"[WARNING] Error aprobando rol del conductor en DB: {str(e)}")
            return False

    def authenticate_user(self):
        """Autentica al usuario y obtiene token"""
        try:
            phone_number = self.user_data['phone_number'] if self.user_role == "CLIENT" else self.user_data['user']['phone_number']
            country_code = self.user_data['country_code'] if self.user_role == "CLIENT" else self.user_data['user']['country_code']

            print(
                f"Iniciando autenticación para {phone_number}")

            # Enviar código de verificación
            start_time = time.time()

            response = self.client.post(
                f"/auth/verify/{country_code}/{phone_number}/send",
                name="Send Verification Code"
            )

            duration = time.time() - start_time
            success = response.status_code == 201
            self.record_metric("send_verification", duration, success)

            if success:
                print(f"Código enviado exitosamente ({duration:.2f}s)")

                # Extraer código del mensaje
                response_data = response.json()
                message = response_data.get("message", "")
                if "successfully" in message:
                    code = message.split()[-1]

                    # Verificar código
                    verify_start = time.time()
                    verify_response = self.client.post(
                        f"/auth/verify/{country_code}/{phone_number}/code",
                        json={"code": code},
                        name="Verify Code"
                    )

                    verify_duration = time.time() - verify_start
                    verify_success = verify_response.status_code == 200
                    self.record_metric(
                        "verify_code", verify_duration, verify_success)

                    if verify_success:
                        verify_data = verify_response.json()
                        self.auth_token = verify_data.get("access_token")
                        total_duration = time.time() - start_time
                        print(
                            f"[SUCCESS] Usuario autenticado: {phone_number} ({total_duration:.2f}s)")
                        print(f"Token obtenido: {self.auth_token[:20]}...")
                    else:
                        print(
                            f"[ERROR] Error verificando código: {verify_response.status_code} - {verify_response.text}")
                else:
                    print(f"[ERROR] No se pudo extraer código de: {message}")
            else:
                print(
                    f"[ERROR] Error enviando código: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"[ERROR] Exception en autenticación: {e}")

    def record_metric(self, endpoint: str, duration: float, success: bool):
        """Registra métricas de performance por endpoint"""
        if endpoint in self.endpoint_metrics:
            self.endpoint_metrics[endpoint]["requests"] += 1
            self.endpoint_metrics[endpoint]["total_duration"] += duration
            if not success:
                self.endpoint_metrics[endpoint]["errors"] += 1

    def on_stop(self):
        """Se ejecuta al finalizar cada usuario virtual"""
        phone_number = self.user_data['phone_number'] if self.user_role == "CLIENT" else self.user_data['user']['phone_number']
        print(
            f"\n[METRICS] Métricas finales del {self.user_role} {phone_number}:")
        print(f"Total de requests procesados: {self.request_count}")
        print(f"Solicitudes creadas: {len(self.created_requests)}")

        for endpoint, metrics in self.endpoint_metrics.items():
            if metrics["requests"] > 0:
                avg_duration = metrics["total_duration"] / metrics["requests"]
                error_rate = (metrics["errors"] / metrics["requests"]) * 100
                print(
                    f"  {endpoint}: {metrics['requests']} requests, {avg_duration:.3f}s avg, {error_rate:.1f}% errors")

    @task(4)
    def create_trip_request(self):
        """Crear solicitud de viaje (solo para clientes)"""
        if self.user_role != "CLIENT" or not self.auth_token:
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Creando solicitud de viaje (request #{self.request_count})")

        # Generar coordenadas aleatorias en Bogotá
        pickup_lat = 4.710989 + random.uniform(-0.01, 0.01)
        pickup_lng = -74.072092 + random.uniform(-0.01, 0.01)
        destination_lat = 4.702468 + random.uniform(-0.01, 0.01)
        destination_lng = -74.109776 + random.uniform(-0.01, 0.01)

        # Datos de la solicitud
        trip_data = {
            "fare_offered": random.randint(15000, 50000),
            "pickup_description": f"Punto de recogida {self.request_count}",
            "destination_description": f"Destino {self.request_count}",
            "pickup_lat": pickup_lat,
            "pickup_lng": pickup_lng,
            "destination_lat": destination_lat,
            "destination_lng": destination_lng,
            "type_service_id": random.choice([1, 2]),  # 1=Car, 2=Motorcycle
            # 1=cash, 2=nequi, 3=daviplata
            "payment_method_id": random.choice([1, 2, 3])
        }

        try:
            response = self.client.post(
                "/client-request/",
                json=trip_data,
                headers=headers,
                name="Create Trip Request"
            )

            duration = time.time() - start_time
            success = response.status_code == 201
            self.record_metric("create_request", duration, success)

            if success:
                data = response.json()
                trip_id = data.get("id", "N/A")
                self.created_requests.append(trip_id)
                print(
                    f"[SUCCESS] Solicitud creada: {trip_id} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error creando solicitud: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("create_request", duration, False)
            print(f"[ERROR] Exception creando solicitud: {e}")

    @task(3)
    def get_nearby_requests(self):
        """Buscar solicitudes cercanas (solo para conductores)"""
        if self.user_role != "DRIVER" or not self.auth_token:
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Buscando solicitudes cercanas (request #{self.request_count})")

        # Generar coordenadas aleatorias en Bogotá
        driver_lat = 4.710989 + random.uniform(-0.01, 0.01)
        driver_lng = -74.072092 + random.uniform(-0.01, 0.01)

        try:
            response = self.client.get(
                f"/client-request/nearby?driver_lat={driver_lat}&driver_lng={driver_lng}",
                headers=headers,
                name="Get Nearby Requests"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_nearby_requests", duration, success)

            if success:
                data = response.json()
                requests_count = len(data) if isinstance(data, list) else 0
                print(
                    f"[SUCCESS] Solicitudes cercanas encontradas: {requests_count} ({duration:.2f}s)")

                # Si hay solicitudes, intentar asignarse a una
                if requests_count > 0:
                    self.assign_to_request(data[0].get("id"))
            else:
                print(
                    f"[ERROR] Error buscando solicitudes: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_nearby_requests", duration, False)
            print(f"[ERROR] Exception buscando solicitudes: {e}")

    def assign_to_request(self, request_id: str):
        """Asignarse a una solicitud (solo para conductores)"""
        if not self.auth_token:
            return

        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Asignándose a solicitud: {request_id}")

        assign_data = {
            "id_client_request": request_id,
            "id_driver": self.user_data['user']['id'],
            "fare_assigned": random.randint(20000, 60000)
        }

        try:
            response = self.client.patch(
                "/client-request/updateDriverAssigned",
                json=assign_data,
                headers=headers,
                name="Assign Driver"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("assign_driver", duration, success)

            if success:
                print(
                    f"[SUCCESS] Conductor asignado a solicitud: {request_id} ({duration:.2f}s)")
                # Iniciar flujo de cambio de estados
                self.simulate_trip_flow(request_id)
            else:
                print(
                    f"[ERROR] Error asignando conductor: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("assign_driver", duration, False)
            print(f"[ERROR] Exception asignando conductor: {e}")

    def simulate_trip_flow(self, request_id: str):
        """Simula el flujo completo de un viaje"""
        if not self.auth_token:
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Estados del viaje en orden
        states = ["ON_THE_WAY", "ARRIVED", "TRAVELLING", "FINISHED", "PAID"]

        for state in states:
            try:
                # Actualizar posición si es necesario
                if state in ["ON_THE_WAY", "ARRIVED"]:
                    self.update_driver_position()

                # Cambiar estado
                status_data = {
                    "id_client_request": request_id,
                    "status": state
                }

                response = self.client.patch(
                    "/client-request/updateStatusByDriver",
                    json=status_data,
                    headers=headers,
                    name=f"Update Status to {state}"
                )

                if response.status_code == 200:
                    print(f"[SUCCESS] Estado cambiado a {state}")
                    time.sleep(0.5)  # Pequeña pausa entre estados
                else:
                    print(
                        f"[ERROR] Error cambiando estado a {state}: {response.status_code}")
                    break

            except Exception as e:
                print(f"[ERROR] Exception en flujo de viaje: {e}")
                break

    @task(2)
    def update_driver_position(self):
        """Actualizar posición GPS (solo para conductores)"""
        if self.user_role != "DRIVER" or not self.auth_token:
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Actualizando posición GPS (request #{self.request_count})")

        # Generar coordenadas aleatorias en Bogotá
        lat = 4.710989 + random.uniform(-0.01, 0.01)
        lng = -74.072092 + random.uniform(-0.01, 0.01)

        position_data = {
            "lat": lat,
            "lng": lng
        }

        try:
            response = self.client.post(
                "/drivers-position/",
                json=position_data,
                headers=headers,
                name="Update Driver Position"
            )

            duration = time.time() - start_time
            success = response.status_code in [200, 201]
            self.record_metric("update_position", duration, success)

            if success:
                print(
                    f"[SUCCESS] Posición actualizada: {lat:.6f}, {lng:.6f} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error actualizando posición: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("update_position", duration, False)
            print(f"[ERROR] Exception actualizando posición: {e}")

    @task(2)
    def get_requests_by_status(self):
        """Consultar solicitudes por estado"""
        if not self.auth_token:
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(
            f"Consultando solicitudes por estado (request #{self.request_count})")

        # Estados comunes para consultar
        statuses = ["CREATED", "ACCEPTED", "ON_THE_WAY",
                    "ARRIVED", "TRAVELLING", "FINISHED", "PAID"]
        selected_status = random.choice(statuses)

        try:
            response = self.client.get(
                f"/client-request/by-status/{selected_status}",
                headers=headers,
                name="Get Requests By Status"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_requests_by_status", duration, success)

            if success:
                data = response.json()
                requests_count = len(data) if isinstance(data, list) else 0
                print(
                    f"[SUCCESS] Solicitudes en estado {selected_status}: {requests_count} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error consultando solicitudes: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_requests_by_status", duration, False)
            print(f"[ERROR] Exception consultando solicitudes: {e}")

    @task(1)
    def get_trip_detail(self):
        """Obtener detalle de una solicitud específica"""
        if not self.auth_token:
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(
            f"Consultando detalle de solicitud (request #{self.request_count})")

        # Intentar obtener una solicitud válida del usuario
        try:
            # Primero intentar con solicitudes CREATED del usuario
            response = self.client.get(
                "/client-request/by-status/CREATED",
                headers=headers,
                name="Get User Requests"
            )

            trip_id = None
            if response.status_code == 200:
                requests_data = response.json()
                if requests_data and len(requests_data) > 0:
                    trip_id = requests_data[0].get("id")
                    print(f"Usando solicitud CREATED: {trip_id}")
                else:
                    # Si no hay solicitudes CREATED, intentar con otros estados
                    other_statuses = ["ACCEPTED", "ON_THE_WAY",
                                      "ARRIVED", "TRAVELLING", "FINISHED", "PAID"]
                    for status in other_statuses:
                        status_response = self.client.get(
                            f"/client-request/by-status/{status}",
                            headers=headers,
                            name=f"Get User Requests {status}"
                        )
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            if status_data and len(status_data) > 0:
                                trip_id = status_data[0].get("id")
                                print(f"Usando solicitud {status}: {trip_id}")
                                break

            if trip_id:
                # Obtener el detalle de esa solicitud
                detail_response = self.client.get(
                    f"/client-request/{trip_id}",
                    headers=headers,
                    name="Get Trip Detail"
                )

                duration = time.time() - start_time
                success = detail_response.status_code == 200
                self.record_metric("get_trip_detail", duration, success)

                if success:
                    data = detail_response.json()
                    status = data.get("status", "N/A")
                    print(
                        f"[SUCCESS] Detalle obtenido: {trip_id} - {status} ({duration:.2f}s)")
                else:
                    print(
                        f"[INFO] No se pudo obtener detalle: {detail_response.status_code}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_trip_detail", duration, False)
            print(f"[ERROR] Exception consultando detalle: {e}")


@events.request.add_listener
def my_request_handler(request_type, name, response_time, response_length, response, context, exception, start_time, url, **kwargs):
    """Manejador de eventos para requests fallidos"""
    if exception:
        print(f"[ERROR] Request failed: {name} - {exception}")
    elif response and response.status_code >= 400:
        print(
            f"[ERROR] Request failed: {name} - Status: {response.status_code}")


class ClientRequestLoadTestConfig:
    """
    Configuración para el test de carga completo de client request
    """

    # Configuración de usuarios
    USERS = 10
    SPAWN_RATE = 2  # Usuarios por segundo

    # Configuración de tiempo
    RUN_TIME = "2m"  # 2 minutos para pruebas completas

    # Configuración de host
    HOST = "http://localhost:8000"

    # Configuración de reportes
    HTML_REPORT = "client_request_load_test_report.html"
    CSV_REPORT = "client_request_load_test_results.csv"

    # Configuración de métricas
    FOCUS_METRICS = [
        "response_time_p95",
        "response_time_p99",
        "requests_per_sec",
        "failure_rate"
    ]

    # Umbrales de performance específicos para flujo completo
    PERFORMANCE_THRESHOLDS = {
        "response_time_p95": 2000,  # 2 segundos
        "response_time_p99": 5000,  # 5 segundos
        "failure_rate": 5.0,  # 5%
        "requests_per_sec": 20  # 20 requests por segundo
    }


if __name__ == "__main__":
    """
    Para ejecutar directamente con Python:
    python -m locust -f app/load_tests/locust/load_client_request.py --host=http://localhost:8000
    """
    print("Test de carga para client request")
    print(f"Usuarios: {ClientRequestLoadTestConfig.USERS}")
    print(f"Tiempo: {ClientRequestLoadTestConfig.RUN_TIME}")
    print(f"Enfoque: Operaciones básicas de client request sin cancelación")
    print(f"Métricas: {', '.join(ClientRequestLoadTestConfig.FOCUS_METRICS)}")
    print("\nPara ejecutar:")
    print("locust -f app/load_tests/locust/load_client_request.py --host=http://localhost:8000")
