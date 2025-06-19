import random
import time
import io
from locust import HttpUser, task, between, events
from typing import Dict, List
import json
from datetime import datetime, date
from uuid import UUID


class DriverLoadTest(HttpUser):
    """
    Usuario virtual que simula el comportamiento de conductores
    Enfoque: Operaciones completas de conductores (registro, documentos, verificación, posición, ahorros)
    """

    # Tiempo de espera entre tareas (1-3 segundos para simular comportamiento real)
    wait_time = between(1, 3)

    # Token de autenticación
    auth_token: str = None

    # Datos del conductor
    driver_data: Dict = None

    # Contador de requests
    request_count: int = 0

    # Estado de verificación
    is_verified: bool = False

    # Métricas de performance por endpoint
    endpoint_metrics: Dict = {}

    def on_start(self):
        """Se ejecuta al iniciar cada usuario virtual"""
        print("Iniciando conductor virtual")
        self.request_count = 0
        self.initialize_metrics()

        print("1. Creando conductor...")
        self.create_test_driver()

        print("2. Autenticando conductor...")
        self.authenticate_driver()

        print("3. Simulando verificación de documentos...")
        self.simulate_document_verification()

        print("Conductor inicializado completamente")

    def initialize_metrics(self):
        """Inicializa las métricas por endpoint"""
        self.endpoint_metrics = {
            "create_driver": {"requests": 0, "total_duration": 0, "errors": 0},
            "send_verification": {"requests": 0, "total_duration": 0, "errors": 0},
            "verify_code": {"requests": 0, "total_duration": 0, "errors": 0},
            "simulate_document_verification": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_driver_profile": {"requests": 0, "total_duration": 0, "errors": 0},
            "update_driver_position": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_driver_position": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_driver_savings": {"requests": 0, "total_duration": 0, "errors": 0},
            "transfer_savings": {"requests": 0, "total_duration": 0, "errors": 0},
            "create_trip_offer": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_nearby_requests": {"requests": 0, "total_duration": 0, "errors": 0},
            "check_verification_status": {"requests": 0, "total_duration": 0, "errors": 0}
        }

    def create_test_driver(self):
        """Crea un conductor de prueba completo"""
        start_time = time.time()

        # Generar número de teléfono colombiano válido
        prefix = 300
        suffix = random.randint(1000000, 9999999)
        phone_number = f"{prefix}{suffix}"

        # Generar nombre real
        nombres = ["Carlos", "María", "Juan", "Ana", "Luis",
                   "Sofia", "Diego", "Valentina", "Andrés", "Camila"]
        apellidos = ["García", "Rodríguez", "López", "Martínez",
                     "González", "Pérez", "Sánchez", "Ramírez", "Torres", "Flores"]

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
        self.driver_data = {
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
            success = response.status_code in [
                201, 409]  # 201 = creado, 409 = ya existe
            self.record_metric("create_driver", duration, success)

            if response.status_code == 201:
                print(
                    f"[SUCCESS] Conductor creado: {phone_number} ({duration:.2f}s)")

                # Extraer user_id de la respuesta
                try:
                    response_data = response.json()
                    user_id = response_data.get("user", {}).get("id")
                    if user_id:
                        self.driver_data['user']['id'] = user_id
                        print(f"[DEBUG] User ID extraído: {user_id}")
                    else:
                        print(
                            f"[WARNING] No se pudo extraer user_id de la respuesta")
                except Exception as e:
                    print(f"[WARNING] Error extrayendo user_id: {e}")

            elif response.status_code == 409:
                print(
                    f"[INFO] Conductor ya existe: {phone_number} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error creando conductor: {response.status_code} - {response.text} ({duration:.2f}s)")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("create_driver", duration, False)
            print(
                f"[ERROR] Exception creando conductor: {e} ({duration:.2f}s)")

    def authenticate_driver(self):
        """Autentica al conductor y obtiene token"""
        try:
            print(
                f"Iniciando autenticación para {self.driver_data['user']['phone_number']}")

            # Enviar código de verificación
            start_time = time.time()

            response = self.client.post(
                f"/auth/verify/{self.driver_data['user']['country_code']}/{self.driver_data['user']['phone_number']}/send",
                name="Send Verification Code"
            )

            duration = time.time() - start_time
            success = response.status_code == 201
            self.record_metric("send_verification", duration, success)

            if success:
                print(f"Código enviado exitosamente ({duration:.2f}s)")

                # Extraer código del mensaje (para testing)
                response_data = response.json()
                message = response_data.get("message", "")
                if "successfully" in message:
                    code = message.split()[-1]  # Última palabra del mensaje

                    # Verificar código
                    verify_start = time.time()
                    verify_response = self.client.post(
                        f"/auth/verify/{self.driver_data['user']['country_code']}/{self.driver_data['user']['phone_number']}/code",
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
                            f"[SUCCESS] Conductor autenticado: {self.driver_data['user']['phone_number']} ({total_duration:.2f}s)")
                        print(f"Token obtenido: {self.auth_token[:20]}...")
                    else:
                        print(
                            f"[ERROR] Error verificando código: {verify_response.status_code} - {verify_response.text}")
                else:
                    print(
                        f"[ERROR] No se pudo extraer código de: {message} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error enviando código: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"[ERROR] Exception en autenticación: {e}")

    def simulate_savings_deposit(self):
        """Simula un depósito en los ahorros del conductor"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando depósito de ahorros")
            return

        start_time = time.time()
        print(
            f"Simulando depósito en ahorros para {self.driver_data['user']['phone_number']}")

        try:
            from app.core.db import engine
            from sqlmodel import Session
            from app.models.driver_savings import DriverSavings
            from sqlmodel import select
            from uuid import UUID

            with Session(engine) as session:
                # Buscar el DriverSavings del conductor
                user_id = UUID(self.driver_data['user']['id'])
                print(
                    f"[DEBUG] Buscando DriverSavings para user_id: {user_id}")

                driver_savings = session.exec(
                    select(DriverSavings).where(
                        DriverSavings.user_id == user_id
                    )
                ).first()

                if driver_savings:
                    # Simular un depósito de $50,000
                    deposit_amount = 50000
                    driver_savings.mount += deposit_amount
                    session.commit()

                    duration = time.time() - start_time
                    print(
                        f"[SUCCESS] Depósito simulado: ${deposit_amount:,} ({duration:.2f}s)")
                    print(
                        f"[INFO] Saldo total en ahorros: ${driver_savings.mount:,}")
                else:
                    print(
                        f"[WARNING] No se encontró DriverSavings para el conductor")

        except Exception as e:
            duration = time.time() - start_time
            print(
                f"[ERROR] Error simulando depósito: {str(e)} ({duration:.2f}s)")

    def simulate_document_verification(self):
        """Simula la verificación de los 4 documentos requeridos por un admin"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando verificación de documentos")
            return

        start_time = time.time()
        print(
            f"Simulando verificación de documentos para {self.driver_data['user']['phone_number']}")

        try:
            # Los 4 documentos requeridos según el sistema:
            # 1 = Tarjeta de Propiedad
            # 2 = Licencia
            # 3 = SOAT
            # 4 = Tecnomecánica

            # En un test real, esto sería hecho por un admin
            # Aquí simulamos que los documentos fueron aprobados
            self.is_verified = True

            # Aprobar el rol del conductor
            print("  [STEP] Aprobando rol del conductor...")
            role_approved = self.approve_driver_role()
            print(f"  [RESULT] Rol aprobado: {role_approved}")

            # Simular depósito en ahorros (siempre ejecutar)
            print("  [STEP] Simulando depósito en ahorros...")
            self.simulate_savings_deposit()
            print("  [RESULT] Depósito de ahorros completado")

            duration = time.time() - start_time
            success = True  # Simulamos éxito
            self.record_metric(
                "simulate_document_verification", duration, success)

            print(
                f"[SUCCESS] Documentos verificados (simulado): 4/4 aprobados ({duration:.2f}s)")
            print("  [OK] Tarjeta de Propiedad (ID: 1)")
            print("  [OK] Licencia de Conducir (ID: 2)")
            print("  [OK] SOAT (ID: 3)")
            print("  [OK] Revisión Tecnomecánica (ID: 4)")
            print(
                f"  [OK] Rol de conductor aprobado: {'SÍ' if role_approved else 'NO'}")
            print("  [OK] Depósito en ahorros simulado")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric(
                "simulate_document_verification", duration, False)
            print(f"[ERROR] Exception en verificación de documentos: {e}")
            import traceback
            traceback.print_exc()

    def approve_driver_role(self):
        """Aprueba el rol del conductor directamente en la base de datos"""
        try:
            from app.core.db import engine
            from sqlmodel import Session
            from app.models.user_has_roles import UserHasRole, RoleStatus
            from sqlmodel import select

            # Debug: Ver qué datos tenemos disponibles
            print(
                f"[DEBUG] driver_data keys: {list(self.driver_data.keys()) if self.driver_data else 'None'}")
            if self.driver_data and 'user' in self.driver_data:
                print(
                    f"[DEBUG] user keys: {list(self.driver_data['user'].keys())}")
                print(f"[DEBUG] user data: {self.driver_data['user']}")
            else:
                print(f"[ERROR] No hay datos de usuario disponibles")
                return False

            with Session(engine) as session:
                # Buscar el UserHasRole del conductor
                user_id_str = self.driver_data['user']['id']
                print(
                    f"[DEBUG] Buscando UserHasRole para user_id: {user_id_str}")

                # Convertir string a UUID
                try:
                    user_id_uuid = UUID(user_id_str)
                except ValueError as e:
                    print(
                        f"[ERROR] user_id no es un UUID válido: {user_id_str}")
                    return

                user_role = session.exec(
                    select(UserHasRole).where(
                        UserHasRole.id_user == user_id_uuid,
                        UserHasRole.id_rol == "DRIVER"
                    )
                ).first()

                if user_role:
                    print(
                        f"[DEBUG] UserHasRole encontrado: {user_role.id_user} - {user_role.id_rol} - {user_role.status}")

                    # Aprobar el rol
                    user_role.status = RoleStatus.APPROVED
                    user_role.is_verified = True
                    user_role.verified_at = datetime.now()

                    session.commit()
                    print(
                        f"[SUCCESS] Rol de conductor aprobado para {self.driver_data['user']['phone_number']}")
                    return True
                else:
                    print(
                        f"[WARNING] No se encontró UserHasRole para user_id: {user_id_str}")
                    return False

        except Exception as e:
            print(
                f"[WARNING] Error aprobando rol del conductor en DB: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def record_metric(self, endpoint: str, duration: float, success: bool):
        """Registra métricas de performance por endpoint"""
        if endpoint in self.endpoint_metrics:
            self.endpoint_metrics[endpoint]["requests"] += 1
            self.endpoint_metrics[endpoint]["total_duration"] += duration
            if not success:
                self.endpoint_metrics[endpoint]["errors"] += 1

    def on_stop(self):
        """Se ejecuta al finalizar cada usuario virtual"""
        print(
            f"\n[METRICS] Métricas finales del conductor {self.driver_data['user']['phone_number']}:")
        print(f"Total de requests procesados: {self.request_count}")
        print(
            f"Estado de verificación: {'[VERIFICADO]' if self.is_verified else '[PENDIENTE]'}")

        for endpoint, metrics in self.endpoint_metrics.items():
            if metrics["requests"] > 0:
                avg_duration = metrics["total_duration"] / metrics["requests"]
                error_rate = (metrics["errors"] / metrics["requests"]) * 100
                print(
                    f"  {endpoint}: {metrics['requests']} requests, {avg_duration:.3f}s avg, {error_rate:.1f}% errors")

    @task(2)
    def check_verification_status(self):
        """Verificar estado de verificación del conductor"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando check_verification_status")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(
            f"Verificando estado de verificación (request #{self.request_count})")

        try:
            # Simular verificación de estado (usando el endpoint de perfil)
            response = self.client.get(
                "/drivers/me",
                headers=headers,
                name="Check Verification Status"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("check_verification_status", duration, success)

            if success:
                data = response.json()
                driver_name = data.get("driver_info", {}).get(
                    "first_name", "N/A")
                verification_status = "Verificado" if self.is_verified else "Pendiente"
                print(
                    f"[SUCCESS] Estado de verificación: {driver_name} - {verification_status} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error verificando estado: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("check_verification_status", duration, False)
            print(f"[ERROR] Exception verificando estado: {e}")

    @task(3)
    def get_driver_profile(self):
        """Obtener perfil del conductor autenticado"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando get_driver_profile")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(
            f"Obteniendo perfil del conductor (request #{self.request_count})")

        try:
            response = self.client.get(
                "/drivers/me",
                headers=headers,
                name="Get Driver Profile"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_driver_profile", duration, success)

            if success:
                data = response.json()
                driver_name = data.get("driver_info", {}).get(
                    "first_name", "N/A")
                print(
                    f"[SUCCESS] Perfil del conductor obtenido: {driver_name} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error obteniendo perfil del conductor: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_driver_profile", duration, False)
            print(f"[ERROR] Exception obteniendo perfil del conductor: {e}")

    @task(4)
    def update_driver_position(self):
        """Actualizar posición GPS del conductor"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando update_driver_position")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Actualizando posición GPS (request #{self.request_count})")

        # Generar coordenadas aleatorias en Bogotá
        lat = 4.710989 + random.uniform(-0.01, 0.01)  # Bogotá ± ~1km
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
            self.record_metric("update_driver_position", duration, success)

            if success:
                print(
                    f"[SUCCESS] Posición actualizada: {lat:.6f}, {lng:.6f} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error actualizando posición: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("update_driver_position", duration, False)
            print(f"[ERROR] Exception actualizando posición: {e}")

    @task(1)
    def get_driver_position(self):
        """Obtener posición actual del conductor"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando get_driver_position")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Obteniendo posición actual (request #{self.request_count})")

        try:
            # Primero intentar obtener la posición
            response = self.client.get(
                "/drivers-position/me",
                headers=headers,
                name="Get Driver Position"
            )

            duration = time.time() - start_time

            if response.status_code == 200:
                success = True
                self.record_metric("get_driver_position", duration, success)
                print(
                    f"[SUCCESS] Posición obtenida ({duration:.2f}s)")
            elif response.status_code == 404:
                # Si no tiene posición, actualizar primero
                print(f"[INFO] No hay posición registrada, actualizando primero...")

                # Generar posición aleatoria
                lat = 4.710989 + random.uniform(-0.01, 0.01)
                lng = -74.072092 + random.uniform(-0.01, 0.01)

                update_response = self.client.post(
                    "/drivers-position/",
                    json={"lat": lat, "lng": lng},
                    headers=headers,
                    name="Update Driver Position"
                )

                if update_response.status_code == 201:
                    print(
                        f"[SUCCESS] Posición actualizada: lat={lat:.6f}, lng={lng:.6f}")
                    # Ahora intentar obtener la posición nuevamente
                    response = self.client.get(
                        "/drivers-position/me",
                        headers=headers,
                        name="Get Driver Position (After Update)"
                    )

                    if response.status_code == 200:
                        success = True
                        self.record_metric(
                            "get_driver_position", duration, success)
                        print(
                            f"[SUCCESS] Posición obtenida después de actualizar ({duration:.2f}s)")
                    else:
                        success = False
                        self.record_metric(
                            "get_driver_position", duration, success)
                        print(
                            f"[ERROR] Error obteniendo posición después de actualizar: {response.status_code}")
                else:
                    success = False
                    self.record_metric(
                        "get_driver_position", duration, success)
                    print(
                        f"[ERROR] Error actualizando posición: {update_response.status_code}")
            else:
                success = False
                self.record_metric("get_driver_position", duration, success)
                print(
                    f"[ERROR] Error obteniendo posición: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_driver_position", duration, False)
            print(f"[ERROR] Exception obteniendo posición: {e}")

    @task(2)
    def get_driver_savings(self):
        """Obtener estado de ahorros del conductor"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando get_driver_savings")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Consultando ahorros (request #{self.request_count})")

        try:
            response = self.client.get(
                "/driver-savings/me",
                headers=headers,
                name="Get Driver Savings"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_driver_savings", duration, success)

            if success:
                data = response.json()
                mount = data.get("mount", 0)
                can_withdraw = data.get("can_withdraw", False)
                print(
                    f"[SUCCESS] Ahorros: ${mount:,} - Puede retirar: {can_withdraw} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error consultando ahorros: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_driver_savings", duration, False)
            print(f"[ERROR] Exception consultando ahorros: {e}")

    @task(1)
    def transfer_savings(self):
        """Transferir ahorros al balance (solo si tiene suficientes)"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando transfer_savings")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Intentando transferir ahorros (request #{self.request_count})")

        # Solo intentar transferir si tiene suficientes ahorros (simulado)
        # En un test real, primero consultaríamos los ahorros
        transfer_amount = 50000  # Monto mínimo

        try:
            response = self.client.post(
                "/driver-savings/transfer_saving_to_balance",
                json={"amount": transfer_amount},
                headers=headers,
                name="Transfer Savings"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("transfer_savings", duration, success)

            if success:
                print(
                    f"[SUCCESS] Transferencia exitosa: ${transfer_amount:,} ({duration:.2f}s)")
            else:
                print(
                    f"[INFO] Transferencia no realizada: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("transfer_savings", duration, False)
            print(f"[ERROR] Exception en transferencia: {e}")

    @task(2)
    def get_nearby_requests(self):
        """Obtener solicitudes de viaje cercanas"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando get_nearby_requests")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Buscando solicitudes cercanas (request #{self.request_count})")

        # Generar posición aleatoria para buscar solicitudes
        lat = 4.710989 + random.uniform(-0.01, 0.01)
        lng = -74.072092 + random.uniform(-0.01, 0.01)

        try:
            response = self.client.get(
                f"/client-request/nearby?driver_lat={lat}&driver_lng={lng}",
                headers=headers,
                name="Get Nearby Requests"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_nearby_requests", duration, success)

            if success:
                data = response.json()
                # El endpoint devuelve directamente un array, no un objeto con "requests"
                requests_count = len(data) if isinstance(data, list) else 0
                print(
                    f"[SUCCESS] Solicitudes encontradas: {requests_count} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error buscando solicitudes: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_nearby_requests", duration, False)
            print(f"[ERROR] Exception buscando solicitudes: {e}")

    @task(1)
    def create_trip_offer(self):
        """Crear oferta de viaje (simulado)"""
        if not self.auth_token:
            print(
                f"[WARNING] No hay token de autenticación, saltando create_trip_offer")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(
            f"Creando oferta de viaje (simulado) (request #{self.request_count})")

        # Simular creación de oferta (solo GET por ahora)
        try:
            response = self.client.get(
                "/drivers/me",
                headers=headers,
                name="Create Trip Offer (Simulated)"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("create_trip_offer", duration, success)

            if success:
                print(
                    f"[SUCCESS] Oferta de viaje creada (simulado) ({duration:.2f}s)")
            else:
                print(f"[ERROR] Error creando oferta: {response.status_code}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("create_trip_offer", duration, False)
            print(f"[ERROR] Exception creando oferta: {e}")


@events.request.add_listener
def my_request_handler(request_type, name, response_time, response_length, response, context, exception, start_time, url, **kwargs):
    """Manejador de eventos para requests fallidos"""
    if exception:
        print(f"[ERROR] Request failed: {name} - {exception}")
    elif response and response.status_code >= 400:
        print(
            f"[ERROR] Request failed: {name} - Status: {response.status_code}")


class DriverLoadTestConfig:
    """
    Configuración para el test de carga de conductores
    """

    # Configuración de usuarios
    USERS = 15
    SPAWN_RATE = 3  # Conductores por segundo

    # Configuración de tiempo
    RUN_TIME = "30s"  # 30 segundos para pruebas más largas

    # Configuración de host
    HOST = "http://localhost:8000"

    # Configuración de reportes
    HTML_REPORT = "driver_load_test_report.html"
    CSV_REPORT = "driver_load_test_results.csv"

    # Configuración de métricas
    FOCUS_METRICS = [
        "response_time_p95",
        "response_time_p99",
        "requests_per_sec",
        "failure_rate"
    ]

    # Umbrales de performance específicos para conductores
    PERFORMANCE_THRESHOLDS = {
        # 3 segundos (más permisivo para operaciones complejas)
        "response_time_p95": 3000,
        "response_time_p99": 8000,  # 8 segundos
        "failure_rate": 5.0,  # 5%
        "requests_per_sec": 15  # 15 requests por segundo
    }


if __name__ == "__main__":
    """
    Para ejecutar directamente con Python:
    python -m locust -f app/load_tests/locust/load_driver.py --host=http://localhost:8000
    """
    print("Test de carga para conductores")
    print(f"Conductores: {DriverLoadTestConfig.USERS}")
    print(f"Tiempo: {DriverLoadTestConfig.RUN_TIME}")
    print(f"Enfoque: Operaciones completas de conductores")
    print(f"Métricas: {', '.join(DriverLoadTestConfig.FOCUS_METRICS)}")
    print("\nPara ejecutar:")
    print("locust -f app/load_tests/locust/load_driver.py --host=http://localhost:8000")
