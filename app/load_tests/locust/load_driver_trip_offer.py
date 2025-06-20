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

    def on_start(self):
        """
        Se ejecuta al iniciar cada usuario virtual.
        Crea un conductor de prueba completo, lo aprueba y lo autentica.
        """
        print("Iniciando un conductor virtual para ofertar...")
        self.create_test_driver()
        if self.user_data and self.user_data.get("user", {}).get("id"):
            self.authenticate_driver()
        else:
            print(
                "[ERROR] No se pudo crear el conductor de prueba. Saltando autenticación.")

    def create_test_driver(self):
        """Crea un conductor de prueba completo usando el patrón de los otros tests."""
        # Generar número de teléfono único
        phone_number = f"323{random.randint(1000000, 9999999)}"

        nombres = ["Pedro", "Carmen", "Roberto", "Isabel", "Miguel"]
        apellidos = ["Herrera", "Morales", "Castro", "Reyes", "Jiménez"]
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
        vehicle_info_data = {
            "brand": "Kia", "model": "Rio", "model_year": 2020,
            "color": "Gris", "plate": f"LCT{random.randint(100, 999)}", "vehicle_type_id": 1
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
        """Aprueba el rol del conductor para que pueda operar."""
        if not self.user_data or not self.user_data.get("user", {}).get("id"):
            return
        try:
            from app.core.db import engine
            from sqlmodel import Session, select
            from app.models.user_has_roles import UserHasRole, RoleStatus
            with Session(engine) as session:
                user_id_uuid = UUID(self.user_data['user']['id'])
                user_role = session.exec(select(UserHasRole).where(
                    UserHasRole.id_user == user_id_uuid, UserHasRole.id_rol == "DRIVER")).first()
                if user_role:
                    user_role.status = RoleStatus.APPROVED
                    user_role.is_verified = True
                    user_role.verified_at = datetime.now()
                    session.commit()
                    print(
                        f"[SUCCESS] Rol de conductor aprobado para {self.user_data['user']['phone_number']}")
                else:
                    print(
                        f"[WARNING] No se encontró el rol a aprobar para el conductor.")
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

    @task
    def make_trip_offer(self):
        """Tarea principal: Busca un viaje cercano y crea una oferta para él."""
        if not self.auth_token or not self.user_data:
            print(
                "[SKIP] Saltando tarea, el conductor no está autenticado o no tiene datos.")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}
        driver_id = self.user_data["user"]["id"]
        driver_lat, driver_lng = 4.708822, -74.076542

        try:
            with self.client.get(f"/client-request/nearby?driver_lat={driver_lat}&driver_lng={driver_lng}", headers=headers, name="[Offer] Get Nearby Requests", catch_response=True) as response:
                if response.status_code == 200:
                    nearby_requests = response.json()
                    if isinstance(nearby_requests, dict) and "data" in nearby_requests:
                        nearby_requests = nearby_requests["data"]

                    if nearby_requests and isinstance(nearby_requests, list):
                        selected_request = random.choice(nearby_requests)
                        client_request_id = selected_request["id"]

                        # Leemos la tarifa base de la solicitud para hacer una oferta válida
                        base_fare = float(
                            selected_request.get("fare_offered", 10000))

                        # 3. Crear y enviar la oferta de viaje
                        offer_payload = {
                            "id_client_request": client_request_id,
                            # Ofrecer un poco más
                            "fare_offer": base_fare + random.randint(500, 2000),
                            "time": random.uniform(5.0, 30.0),
                            "distance": random.uniform(1.0, 15.0)
                        }

                        with self.client.post("/driver-trip-offers/",
                                              json=offer_payload,
                                              headers=headers,
                                              name="[Offer] Create Trip Offer",
                                              catch_response=True) as offer_response:
                            if offer_response.status_code == 201:
                                offer_response.success()
                                print(
                                    f"[SUCCESS] Oferta creada para el viaje {client_request_id}")
                            elif offer_response.status_code == 400:
                                offer_response.failure(
                                    f"Error 400: La oferta es inválida o el viaje ya no está disponible - {offer_response.text}")
                            elif offer_response.status_code == 409:
                                offer_response.failure(
                                    f"Error 409: Ya existe una oferta para este viaje - {offer_response.text}")
                            else:
                                offer_response.failure(
                                    f"Error inesperado al crear oferta: {offer_response.status_code} - {offer_response.text}")
                    else:
                        response.success()
                        print(
                            "[INFO] No se encontraron viajes cercanos para ofertar.")
                else:
                    response.failure(
                        f"Error al buscar viajes cercanos: {response.status_code}")
        except Exception as e:
            print(f"[EXCEPTION] en 'make_trip_offer': {e}")


class LoadTestConfig:
    """
    Configuración para el test de carga de ofertas de viaje.
    """
    USERS = 10
    SPAWN_RATE = 2  # Nuevos conductores virtuales por segundo
    RUN_TIME = "30s"
    HOST = "http://localhost:8000"
    HTML_REPORT = "driver_trip_offer_report.html"
