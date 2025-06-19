import random
import time
from locust import HttpUser, task, between, events
from typing import Dict, List
import json
from datetime import datetime


class TransactionLoadTest(HttpUser):
    """
    Test de carga para transacciones financieras
    Simula operaciones de dinero: consultas de balance, historial de transacciones
    """

    # Tiempo de espera entre tareas (1-3 segundos para simular comportamiento real)
    wait_time = between(1, 3)

    # Token de autenticación
    auth_token: str = None

    # Datos del usuario
    user_data: Dict = None

    # Contador de requests
    request_count: int = 0

    # Métricas de performance por endpoint
    endpoint_metrics: Dict = {}

    def on_start(self):
        """Se ejecuta al iniciar cada usuario virtual"""
        print("Iniciando usuario de transacciones virtual")
        self.request_count = 0
        self.initialize_metrics()
        self.create_test_user()
        self.authenticate_user()
        print("Usuario de transacciones inicializado completamente")

    def initialize_metrics(self):
        """Inicializa las métricas por endpoint"""
        self.endpoint_metrics = {
            "create_user": {"requests": 0, "total_duration": 0, "errors": 0},
            "send_verification": {"requests": 0, "total_duration": 0, "errors": 0},
            "verify_code": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_balance": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_transactions": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_profile": {"requests": 0, "total_duration": 0, "errors": 0}
        }

    def create_test_user(self):
        """Crea un usuario de prueba único"""
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

        # Datos del usuario
        self.user_data = {
            "full_name": full_name,
            "country_code": "+57",
            "phone_number": phone_number,
            "referral_phone": None
        }

        print(f"Creando usuario: {full_name} - {phone_number}")

        try:
            response = self.client.post(
                "/users/",
                json=self.user_data,
                name="Create User"
            )

            duration = time.time() - start_time
            success = response.status_code in [
                201, 409]  # 201 = creado, 409 = ya existe
            self.record_metric("create_user", duration, success)

            if response.status_code == 201:
                print(
                    f"[SUCCESS] Usuario creado: {phone_number} ({duration:.2f}s)")
            elif response.status_code == 409:
                print(
                    f"[INFO] Usuario ya existe: {phone_number} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error creando usuario: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("create_user", duration, False)
            print(f"[ERROR] Exception creando usuario: {e} ({duration:.2f}s)")

    def authenticate_user(self):
        """Autentica al usuario y obtiene token"""
        try:
            print(
                f"Iniciando autenticación para {self.user_data['phone_number']}")

            # Enviar código de verificación
            start_time = time.time()

            response = self.client.post(
                f"/auth/verify/{self.user_data['country_code']}/{self.user_data['phone_number']}/send",
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
                # Buscar código en el mensaje (formato: "Verification code sent successfully 123456")
                if "successfully" in message:
                    code = message.split()[-1]  # Última palabra del mensaje

                    # Verificar código usando el endpoint correcto
                    verify_start = time.time()
                    verify_response = self.client.post(
                        f"/auth/verify/{self.user_data['country_code']}/{self.user_data['phone_number']}/code",
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
                            f"[SUCCESS] Usuario autenticado: {self.user_data['phone_number']} ({total_duration:.2f}s)")
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
            f"\n[METRICS] Métricas finales del usuario {self.user_data['phone_number']}:")
        print(f"Total de requests procesados: {self.request_count}")

        for endpoint, metrics in self.endpoint_metrics.items():
            if metrics["requests"] > 0:
                avg_duration = metrics["total_duration"] / metrics["requests"]
                error_rate = (metrics["errors"] / metrics["requests"]) * 100
                print(
                    f"  {endpoint}: {metrics['requests']} requests, {avg_duration:.3f}s avg, {error_rate:.1f}% errors")

    @task(3)
    def get_user_balance(self):
        """
        Consultar balance del usuario autenticado
        Peso: 3 (frecuente - simula consultas de saldo)
        """
        if not self.auth_token:
            print(
                "[WARNING] No hay token de autenticación, saltando consulta de balance")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Consultando balance (request #{self.request_count})")

        try:
            response = self.client.get(
                "/transactions/balance/me",
                headers=headers,
                name="Get User Balance"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_balance", duration, success)

            if success:
                try:
                    data = response.json()
                    available = data.get("available", 0)
                    withdrawable = data.get("withdrawable", 0)
                    mount = data.get("mount", 0)
                    print(
                        f"[SUCCESS] Balance: Disponible=${available:,}, Retirable=${withdrawable:,}, Total=${mount:,} ({duration:.2f}s)")
                except Exception as e:
                    print(f"[ERROR] Error procesando respuesta: {e}")
                    self.record_metric("get_balance", duration, False)
            else:
                print(
                    f"[ERROR] Error consultando balance: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_balance", duration, False)
            print(f"[ERROR] Exception consultando balance: {e}")

    @task(2)
    def get_user_transactions(self):
        """
        Consultar historial de transacciones del usuario
        Peso: 2 (frecuencia media - simula consultas de historial)
        """
        if not self.auth_token:
            print(
                "[WARNING] No hay token de autenticación, saltando consulta de transacciones")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Consultando transacciones (request #{self.request_count})")

        try:
            response = self.client.get(
                "/transactions/list/me",
                headers=headers,
                name="Get User Transactions"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_transactions", duration, success)

            if success:
                try:
                    data = response.json()
                    transaction_count = len(
                        data) if isinstance(data, list) else 0
                    print(
                        f"[SUCCESS] Transacciones encontradas: {transaction_count} ({duration:.2f}s)")
                except Exception as e:
                    print(f"[ERROR] Error procesando transacciones: {e}")
                    self.record_metric("get_transactions", duration, False)
            else:
                print(
                    f"[ERROR] Error consultando transacciones: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_transactions", duration, False)
            print(f"[ERROR] Exception consultando transacciones: {e}")

    @task(1)
    def get_user_profile(self):
        """
        Obtener perfil del usuario autenticado
        Peso: 1 (menos frecuente - simula consultas de perfil)
        """
        if not self.auth_token:
            print(
                "[WARNING] No hay token de autenticación, saltando consulta de perfil")
            return

        self.request_count += 1
        start_time = time.time()
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        print(f"Consultando perfil (request #{self.request_count})")

        try:
            response = self.client.get(
                "/users/me",
                headers=headers,
                name="Get User Profile"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_profile", duration, success)

            if success:
                try:
                    data = response.json()
                    user_name = data.get("full_name", "N/A")
                    is_active = data.get("is_active", False)
                    print(
                        f"[SUCCESS] Perfil: {user_name}, Activo: {'Sí' if is_active else 'No'} ({duration:.2f}s)")
                except Exception as e:
                    print(f"[ERROR] Error procesando perfil: {e}")
                    self.record_metric("get_profile", duration, False)
            else:
                print(
                    f"[ERROR] Error consultando perfil: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_profile", duration, False)
            print(f"[ERROR] Exception consultando perfil: {e}")


@events.request.add_listener
def my_request_handler(request_type, name, response_time, response_length, response, context, exception, start_time, url, **kwargs):
    """Manejador de eventos para requests fallidos"""
    if exception:
        print(f"[ERROR] Request failed: {name} - {exception}")
    elif response and response.status_code >= 400:
        print(
            f"[ERROR] Request failed: {name} - Status: {response.status_code}")


class LoadTestConfig:
    """
    Configuración para el test de carga de transacciones
    """

    # Configuración de usuarios
    USERS = 5
    SPAWN_RATE = 1  # Usuarios por segundo

    # Configuración de tiempo
    RUN_TIME = "2m"  # 2 minutos para pruebas completas

    # Configuración de host
    HOST = "http://localhost:8000"

    # Configuración de reportes
    HTML_REPORT = "transaction_load_test_report.html"
    CSV_REPORT = "transaction_load_test_results.csv"

    # Configuración de métricas
    FOCUS_METRICS = [
        "response_time_p95",
        "response_time_p99",
        "requests_per_sec",
        "failure_rate"
    ]

    # Umbrales de performance
    PERFORMANCE_THRESHOLDS = {
        "response_time_p95": 2000,  # 2 segundos
        "response_time_p99": 5000,  # 5 segundos
        "failure_rate": 5.0,  # 5%
        "requests_per_sec": 15  # 15 requests por segundo
    }


if __name__ == "__main__":
    """
    Para ejecutar directamente con Python:
    python -m locust -f app/load_tests/locust/load_transactions.py --host=http://localhost:8000
    """
    print("Test de carga para transacciones financieras")
    print(f"Usuarios: {LoadTestConfig.USERS}")
    print(f"Tiempo: {LoadTestConfig.RUN_TIME}")
    print(f"Enfoque: Operaciones de transacciones (balance, historial)")
    print(f"Métricas: {', '.join(LoadTestConfig.FOCUS_METRICS)}")
    print("\nPara ejecutar:")
    print("locust -f app/load_tests/locust/load_transactions.py --host=http://localhost:8000")
