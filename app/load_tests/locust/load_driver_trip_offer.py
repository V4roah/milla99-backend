import random
import time
from locust import HttpUser, task, between, events
from typing import Dict, List, Optional
import json
from datetime import datetime, date
from uuid import UUID
import io


class DriverTripOfferLoadTest(HttpUser):
    """
    Usuario virtual que simula el comportamiento de un Conductor (Driver)
    enfocado específicamente en la creación de ofertas de viaje (DriverTripOffer).

    **Flujo de simulación:**
    1.  **Creación y Autenticación:** Al iniciar, crea un conductor de prueba completo y lo autentica.
    2.  **Búsqueda de viajes:** Busca solicitudes de viaje cercanas.
    3.  **Creación de oferta:** Envía una oferta para un viaje encontrado.

    **Dependencia:** Este test requiere que existan `ClientRequest` con estado 'CREATED'
    en la base de datos.
    """

    wait_time = between(1, 4)  # Espera entre 1 y 4 segundos entre tareas

    # Datos del conductor virtual
    auth_token: Optional[str] = None
    user_data: Optional[Dict] = None
    offered_requests: set = set()  # Trackear solicitudes ya ofertadas por este conductor

    def on_start(self):
        """
        Se ejecuta al iniciar cada usuario virtual.
        Crea un conductor de prueba completo, lo aprueba y lo autentica.
        """
        print("Iniciando un conductor virtual para ofertar...")
        self.create_test_driver()
        if self.user_data and self.user_data.get("user", {}).get("id"):
            self.authenticate_driver()
            # Crear algunas solicitudes de clientes para que los conductores tengan ofertas
            self.create_test_client_requests()
        else:
            print(
                "[ERROR] No se pudo crear el conductor de prueba. Saltando autenticación.")

    def create_test_driver(self):
        """Crea un conductor de prueba completo usando el patrón de los otros tests."""
        # Generar número de teléfono único con prefijo 301 para conductores
        phone_number = f"301{random.randint(1000000, 9999999)}"

        nombres = ["Pedro", "Carmen", "Roberto", "Isabel", "Miguel",
                   "Patricia", "Fernando", "Lucía", "Ricardo", "Elena"]
        apellidos = ["Herrera", "Morales", "Castro", "Reyes",
                     "Jiménez", "Moreno", "Romero", "Alvarez", "Torres", "Ruiz"]
        nombre = random.choice(nombres)
        apellido = random.choice(apellidos)

        user_data = {
            "full_name": f"{nombre} {apellido}",
            "country_code": "+57",
            "phone_number": phone_number
        }
        driver_info_data = {
            "first_name": nombre, "last_name": apellido, "birth_date": str(date(1990, 1, 1)),
            "email": f"{nombre.lower()}.{phone_number}@test.com"
        }

        # Generar datos aleatorios del vehículo
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
            "vehicle_type_id": 1
        }
        driver_documents_data = {
            "license_expiration_date": str(date(2028, 1, 1)),
            "soat_expiration_date": str(date(2026, 1, 1)),
            "vehicle_technical_inspection_expiration_date": str(date(2026, 1, 1))
        }
        self.user_data = {
            "user": user_data, "driver_info": driver_info_data,
            "vehicle_info": vehicle_info_data, "documents": driver_documents_data
        }
        print(
            f"Intentando crear conductor: {user_data['full_name']} - {user_data['phone_number']}")

        try:
            files = {
                "selfie": ("selfie.jpg", io.BytesIO(b"s"), "image/jpeg"),
                "property_card_front": ("pcf.jpg", io.BytesIO(b"pcf"), "image/jpeg"),
                "property_card_back": ("pcb.jpg", io.BytesIO(b"pcb"), "image/jpeg"),
                "license_front": ("lf.jpg", io.BytesIO(b"lf"), "image/jpeg"),
                "license_back": ("lb.jpg", io.BytesIO(b"lb"), "image/jpeg"),
                "soat": ("soat.jpg", io.BytesIO(b"s"), "image/jpeg"),
                "vehicle_technical_inspection": ("vti.jpg", io.BytesIO(b"vti"), "image/jpeg"),
            }
            data_payload = {
                "user": json.dumps(user_data),
                "driver_info": json.dumps(driver_info_data),
                "vehicle_info": json.dumps(vehicle_info_data),
                "driver_documents": json.dumps(driver_documents_data),
            }
            response = self.client.post(
                "/drivers/", data=data_payload, files=files, name="[Setup] Create Driver")

            if response.status_code == 201:
                response_data = response.json()
                user_id = response_data.get("user", {}).get("id")
                self.user_data['user']['id'] = user_id
                print(f"[SUCCESS] Conductor creado con ID: {user_id}")
                self.approve_driver_role()
            elif response.status_code == 409:
                print(
                    f"[INFO] El conductor {phone_number} ya existe, intentando autenticar.")
                # Si ya existe, necesitamos su ID para aprobarlo y autenticarlo
                # Esta parte es compleja sin una consulta a la BD, por ahora asumimos la creación.
            else:
                print(
                    f"[ERROR] Creando conductor: {response.status_code} - {response.text}")
                self.user_data = None
        except Exception as e:
            print(f"[EXCEPTION] Creando conductor: {e}")
            self.user_data = None

    def approve_driver_role(self):
        """Aprueba el rol del conductor para que pueda operar y crea su posición."""
        if not self.user_data or not self.user_data.get("user", {}).get("id"):
            return
        try:
            from app.core.db import engine
            from sqlmodel import Session, select
            from app.models.user_has_roles import UserHasRole, RoleStatus
            from app.models.driver_position import DriverPosition
            from sqlalchemy import func

            with Session(engine) as session:
                user_id_uuid = UUID(self.user_data['user']['id'])

                # 1. Aprobar el rol de conductor
                user_role = session.exec(select(UserHasRole).where(
                    UserHasRole.id_user == user_id_uuid, UserHasRole.id_rol == "DRIVER")).first()
                if user_role:
                    user_role.status = RoleStatus.APPROVED
                    user_role.is_verified = True
                    user_role.verified_at = datetime.now()
                    print(
                        f"[SUCCESS] Rol de conductor aprobado para {self.user_data['user']['phone_number']}")
                else:
                    print(
                        f"[WARNING] No se encontró el rol a aprobar para el conductor.")

                # 2. Crear posición aleatoria del conductor
                # Coordenadas aproximadas de Bogotá: lat 4.6-4.8, lng -74.0 a -74.2
                # Centrado alrededor del punto donde se crean las solicitudes (4.71, -74.07)
                driver_lat = round(random.uniform(
                    4.69, 4.73), 6)  # ±2km del centro
                # ±2km del centro
                driver_lng = round(random.uniform(-74.09, -74.05), 6)

                # Verificar si ya existe una posición para este conductor
                existing_position = session.exec(select(DriverPosition).where(
                    DriverPosition.id_driver == user_id_uuid)).first()

                if existing_position:
                    # Actualizar posición existente
                    existing_position.position = func.ST_GeomFromText(
                        f'POINT({driver_lng} {driver_lat})', 4326)
                    existing_position.updated_at = datetime.now()
                    print(
                        f"[INFO] Posición actualizada para conductor: ({driver_lat}, {driver_lng})")
                else:
                    # Crear nueva posición
                    new_position = DriverPosition(
                        id_driver=user_id_uuid,
                        position=func.ST_GeomFromText(
                            f'POINT({driver_lng} {driver_lat})', 4326),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    session.add(new_position)
                    print(
                        f"[SUCCESS] Nueva posición creada para conductor: ({driver_lat}, {driver_lng})")

                session.commit()

        except Exception as e:
            print(
                f"[WARNING] No se pudo aprobar el rol del conductor en DB: {str(e)}")

    def authenticate_driver(self):
        """Autentica al conductor recién creado para obtener un token JWT."""
        country_code = self.user_data['user']['country_code']
        phone_number = self.user_data['user']['phone_number']
        try:
            send_code_response = self.client.post(
                f"/auth/verify/{country_code}/{phone_number}/send", name="[Auth] Send Verification Code")
            if send_code_response.status_code != 201:
                print(
                    f"[ERROR] No se pudo enviar código a {phone_number}: {send_code_response.status_code}")
                return

            message = send_code_response.json().get("message", "")
            verification_code = message.split()[-1]

            verify_response = self.client.post(f"/auth/verify/{country_code}/{phone_number}/code", json={
                                               "code": verification_code}, name="[Auth] Verify Code")
            if verify_response.status_code == 200:
                self.auth_token = verify_response.json().get("access_token")
                print(f"[SUCCESS] Conductor {phone_number} autenticado.")
            else:
                print(
                    f"[ERROR] Falló la verificación para {phone_number}: {verify_response.status_code} - {verify_response.text}")
        except Exception as e:
            print(f"[EXCEPTION] Durante la autenticación: {e}")

    def create_test_client_requests(self):
        """Crea algunas solicitudes de clientes dentro del rango de 4km para testing."""
        try:
            # Crear 3-5 solicitudes de clientes en diferentes ubicaciones dentro del rango
            for i in range(random.randint(3, 5)):
                self.create_single_client_request(i)
        except Exception as e:
            print(
                f"[WARNING] No se pudieron crear solicitudes de clientes: {e}")

    def create_single_client_request(self, index):
        """Crea una solicitud de cliente individual."""
        try:
            # Generar número de teléfono único con prefijo 300 para clientes
            phone_number = f"300{random.randint(1000000, 9999999)}"

            nombres = ["Ana", "Carlos", "María", "Luis", "Sofia",
                       "Diego", "Camila", "Andrés", "Valentina", "Juan"]
            apellidos = ["García", "Rodríguez", "López", "Martínez", "González",
                         "Pérez", "Sánchez", "Ramírez", "Torres", "Flores"]
            nombre = random.choice(nombres)
            apellido = random.choice(apellidos)

            # Crear cliente
            client_data = {
                "full_name": f"{nombre} {apellido}",
                "country_code": "+57",
                "phone_number": phone_number
            }

            # Crear cliente primero
            client_response = self.client.post(
                "/users/", json=client_data, name="[Setup] Create Client")

            if client_response.status_code != 201:
                print(f"[WARNING] No se pudo crear cliente {phone_number}")
                return

            client_id = client_response.json().get("id")

            # Autenticar cliente
            auth_response = self.client.post(
                f"/auth/verify/+57/{phone_number}/send", name="[Setup] Send Client Code")
            if auth_response.status_code != 201:
                return

            message = auth_response.json().get("message", "")
            verification_code = message.split()[-1]

            verify_response = self.client.post(
                f"/auth/verify/+57/{phone_number}/code",
                json={"code": verification_code},
                name="[Setup] Verify Client Code"
            )

            if verify_response.status_code != 200:
                return

            client_token = verify_response.json().get("access_token")
            client_headers = {"Authorization": f"Bearer {client_token}"}

            # Generar ubicaciones dentro del rango de 4km (aproximadamente 0.036 grados)
            # Centro de Bogotá: lat=4.71, lng=-74.07
            center_lat = 4.71
            center_lng = -74.07

            # Generar posición aleatoria dentro del rango de 4km
            # 0.036 grados ≈ 4km en latitud
            pickup_lat = center_lat + \
                random.uniform(-0.018, 0.018)  # ±2km en latitud
            pickup_lng = center_lng + \
                random.uniform(-0.018, 0.018)  # ±2km en longitud

            # Destino aleatorio también dentro del rango
            destination_lat = center_lat + random.uniform(-0.025, 0.025)
            destination_lng = center_lng + random.uniform(-0.025, 0.025)

            # Crear solicitud de viaje
            request_data = {
                "fare_offered": random.randint(15000, 30000),
                "pickup_description": f"Ubicación de prueba {index + 1}",
                "destination_description": f"Destino de prueba {index + 1}",
                "pickup_lat": round(pickup_lat, 6),
                "pickup_lng": round(pickup_lng, 6),
                "destination_lat": round(destination_lat, 6),
                "destination_lng": round(destination_lng, 6),
                "type_service_id": 1,  # Car
                "payment_method_id": 1  # Cash
            }

            request_response = self.client.post(
                "/client-request/",
                json=request_data,
                headers=client_headers,
                name="[Setup] Create Client Request"
            )

            if request_response.status_code == 201:
                request_id = request_response.json().get("id")
                print(
                    f"[SUCCESS] Solicitud de cliente creada: {request_id} en ({pickup_lat:.6f}, {pickup_lng:.6f})")
            else:
                print(
                    f"[WARNING] No se pudo crear solicitud de cliente: {request_response.status_code}")

        except Exception as e:
            print(f"[WARNING] Error creando solicitud de cliente: {e}")

    @task
    def make_trip_offer(self):
        """
        Busca solicitudes cercanas y crea una oferta de viaje.
        """
        if not self.auth_token:
            print("[WARNING] No hay token de autenticación, saltando oferta")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Generar posición aleatoria del conductor
        # Centrado alrededor del punto donde se crean las solicitudes (4.71, -74.07)
        driver_lat = round(random.uniform(4.69, 4.73), 6)  # ±2km del centro
        driver_lng = round(random.uniform(-74.09, -74.05),
                           6)  # ±2km del centro

        try:
            # Buscar solicitudes cercanas
            response = self.client.get(
                f"/client-request/nearby?driver_lat={driver_lat}&driver_lng={driver_lng}",
                headers=headers,
                name="[Offer] Get Nearby Requests"
            )

            if response.status_code == 200:
                requests_data = response.json()

                if not requests_data:
                    print(
                        f"[INFO] No hay solicitudes cercanas en ({driver_lat}, {driver_lng})")
                    return

                # Filtrar solicitudes que no hemos ofertado aún
                available_requests = [
                    req for req in requests_data
                    if req.get('id') not in self.offered_requests
                ]

                if not available_requests:
                    print(
                        f"[INFO] Todas las solicitudes cercanas ya fueron ofertadas")
                    return

                # Seleccionar una solicitud aleatoria de las disponibles
                selected_request = random.choice(available_requests)
                request_id = selected_request.get('id')

                print(f"[INFO] Creando oferta para solicitud {request_id}")

                # Calcular tarifa con margen aleatorio
                base_fare = selected_request.get('fare_offered', 20000)
                margin = random.uniform(1.05, 1.15)  # 5% a 15% de margen
                fare_offer = round(base_fare * margin, 0)

                # Generar datos de tiempo y distancia aleatorios
                time_estimate = round(random.uniform(5, 30), 2)
                distance_estimate = round(random.uniform(2, 15), 2)

                offer_data = {
                    "id_client_request": request_id,
                    "fare_offer": fare_offer,
                    "time": time_estimate,
                    "distance": distance_estimate,
                    "id_driver": self.user_data['user']['id']
                }

                # Crear la oferta
                offer_response = self.client.post(
                    "/driver-trip-offers/",
                    json=offer_data,
                    headers=headers,
                    name="[Offer] Create Trip Offer"
                )

                if offer_response.status_code == 201:
                    print(
                        f"[SUCCESS] Oferta creada exitosamente para solicitud {request_id}")
                    # Agregar la solicitud al set de ofertadas
                    self.offered_requests.add(request_id)
                elif offer_response.status_code == 400:
                    error_detail = offer_response.json().get('detail', '')
                    if 'Ya existe una oferta' in error_detail:
                        print(
                            f"[INFO] Oferta duplicada para solicitud {request_id}, agregando al set")
                        # Agregar al set aunque falle para evitar reintentos
                        self.offered_requests.add(request_id)
                    else:
                        print(
                            f"[ERROR] Error 400 creando oferta: {error_detail}")
                else:
                    print(
                        f"[ERROR] Error creando oferta: {offer_response.status_code} - {offer_response.text}")

            else:
                print(
                    f"[ERROR] Error buscando solicitudes: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"[ERROR] Exception en make_trip_offer: {e}")


class LoadTestConfig:
    """
    Configuración para el test de carga de ofertas de viaje.
    """
    USERS = 10
    SPAWN_RATE = 2  # Nuevos conductores virtuales por segundo
    RUN_TIME = "30s"
    HOST = "http://localhost:8000"
    HTML_REPORT = "driver_trip_offer_report.html"
