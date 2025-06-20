import random
import time
from locust import HttpUser, task, between, events
from typing import Dict, List, Optional
import json
from datetime import datetime, date
from uuid import UUID
import io


class BankOperationsLoadTest(HttpUser):
    """
    Usuario virtual que simula operaciones bancarias
    Enfoque: Creación de cuentas bancarias, CRUD de cuentas propias, consulta de balances
    """

    # Tiempo de espera entre tareas (1-3 segundos para simular comportamiento real)
    wait_time = between(1, 3)

    # Token de autenticación
    auth_token: str = None

    # Datos del usuario
    user_data: Dict = None

    # Contador de requests
    request_count: int = 0

    # Cuentas bancarias creadas por este usuario
    created_accounts: List[str] = []

    # Métricas de performance por endpoint
    endpoint_metrics: Dict = {}

    def on_start(self):
        """Se ejecuta al iniciar cada usuario virtual"""
        print("Iniciando usuario virtual para operaciones bancarias")
        self.request_count = 0
        self.created_accounts = []
        self.initialize_metrics()
        self.create_test_user()
        self.authenticate_user()
        print("Usuario de operaciones bancarias inicializado completamente")

    def initialize_metrics(self):
        """Inicializa las métricas por endpoint"""
        self.endpoint_metrics = {
            "create_user": {"requests": 0, "total_duration": 0, "errors": 0},
            "send_verification": {"requests": 0, "total_duration": 0, "errors": 0},
            "verify_code": {"requests": 0, "total_duration": 0, "errors": 0},
            "create_bank_account": {"requests": 0, "total_duration": 0, "errors": 0},
            "list_my_accounts": {"requests": 0, "total_duration": 0, "errors": 0},
            "update_bank_account": {"requests": 0, "total_duration": 0, "errors": 0},
            "delete_bank_account": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_active_accounts": {"requests": 0, "total_duration": 0, "errors": 0},
            "get_balance": {"requests": 0, "total_duration": 0, "errors": 0}
        }

    def create_test_user(self):
        """Crea un usuario de prueba único"""
        start_time = time.time()

        # Generar número de teléfono colombiano válido
        prefix = 300
        suffix = random.randint(1000000, 9999999)
        phone_number = f"{prefix}{suffix}"

        # Generar nombre real
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
        print(f"Cuentas bancarias creadas: {len(self.created_accounts)}")

        for endpoint, metrics in self.endpoint_metrics.items():
            if metrics["requests"] > 0:
                avg_duration = metrics["total_duration"] / metrics["requests"]
                error_rate = (metrics["errors"] / metrics["requests"]) * 100
                print(
                    f"  {endpoint}: {metrics['requests']} requests, {avg_duration:.3f}s avg, {error_rate:.1f}% errors")

    @task(4)
    def create_bank_account(self):
        """
        Crear una nueva cuenta bancaria
        Peso: 4 (frecuente - simula registro de cuentas)
        """
        if not self.auth_token:
            print(
                "[WARNING] No hay token de autenticación, saltando creación de cuenta")
            return

        self.request_count += 1
        start_time = time.time()

        # Generar datos de cuenta bancaria realistas
        nombres = ["Juan", "María", "Carlos", "Ana", "Luis"]
        apellidos = ["García", "Rodríguez", "López", "Martínez", "González"]

        nombre = random.choice(nombres)
        apellido = random.choice(apellidos)
        account_holder = f"{nombre} {apellido}"

        # Generar número de cuenta aleatorio
        account_number = str(random.randint(1000000000, 9999999999))

        # Generar cédula aleatoria
        identification_number = str(random.randint(10000000, 99999999))

        # Datos de la cuenta bancaria
        bank_account_data = {
            "bank_id": random.randint(1, 10),  # Banco aleatorio
            "account_type": random.choice(["savings", "checking"]),
            "account_holder_name": account_holder,
            "type_identification": random.choice(["CC", "CE"]),
            "account_number": account_number,
            "identification_number": identification_number
        }

        try:
            response = self.client.post(
                "/bank-accounts/",
                json=bank_account_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                name="Create Bank Account"
            )

            duration = time.time() - start_time
            success = response.status_code == 201
            self.record_metric("create_bank_account", duration, success)

            if success:
                account_data = response.json()
                account_id = account_data.get("id")
                if account_id:
                    self.created_accounts.append(account_id)
                print(
                    f"[SUCCESS] Cuenta bancaria creada: {account_holder} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error creando cuenta bancaria: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("create_bank_account", duration, False)
            print(
                f"[ERROR] Exception creando cuenta bancaria: {e} ({duration:.2f}s)")

    @task(6)
    def list_my_bank_accounts(self):
        """
        Consultar mis cuentas bancarias
        Peso: 6 (muy frecuente - simula consultas de cuentas propias)
        """
        if not self.auth_token:
            print(
                "[WARNING] No hay token de autenticación, saltando consulta de cuentas")
            return

        self.request_count += 1
        start_time = time.time()

        try:
            response = self.client.get(
                "/bank-accounts/me",
                headers={"Authorization": f"Bearer {self.auth_token}"},
                name="List My Bank Accounts"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("list_my_accounts", duration, success)

            if success:
                accounts_data = response.json()
                print(
                    f"[SUCCESS] Cuentas consultadas: {len(accounts_data)} cuentas ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error consultando cuentas: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("list_my_accounts", duration, False)
            print(
                f"[ERROR] Exception consultando cuentas: {e} ({duration:.2f}s)")

    @task(3)
    def get_active_bank_accounts(self):
        """
        Consultar solo cuentas bancarias activas
        Peso: 3 (frecuente - simula consultas de cuentas activas)
        """
        if not self.auth_token:
            print(
                "[WARNING] No hay token de autenticación, saltando consulta de cuentas activas")
            return

        self.request_count += 1
        start_time = time.time()

        try:
            response = self.client.get(
                "/bank-accounts/active",
                headers={"Authorization": f"Bearer {self.auth_token}"},
                name="Get Active Bank Accounts"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_active_accounts", duration, success)

            if success:
                accounts_data = response.json()
                print(
                    f"[SUCCESS] Cuentas activas consultadas: {len(accounts_data)} cuentas ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error consultando cuentas activas: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_active_accounts", duration, False)
            print(
                f"[ERROR] Exception consultando cuentas activas: {e} ({duration:.2f}s)")

    @task(2)
    def update_bank_account(self):
        """
        Actualizar una cuenta bancaria existente
        Peso: 2 (frecuente - simula actualizaciones ocasionales)
        """
        if not self.auth_token or not self.created_accounts:
            print("[WARNING] No hay token o cuentas creadas, saltando actualización")
            return

        self.request_count += 1
        start_time = time.time()

        # Seleccionar una cuenta aleatoria de las creadas
        account_id = random.choice(self.created_accounts)

        # Datos de actualización
        update_data = {
            "account_holder_name": f"Actualizado {random.randint(1000, 9999)}"
        }

        try:
            response = self.client.patch(
                f"/bank-accounts/{account_id}",
                json=update_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                name="Update Bank Account"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("update_bank_account", duration, success)

            if success:
                print(
                    f"[SUCCESS] Cuenta bancaria actualizada: {account_id} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error actualizando cuenta: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("update_bank_account", duration, False)
            print(
                f"[ERROR] Exception actualizando cuenta: {e} ({duration:.2f}s)")

    @task(1)
    def delete_bank_account(self):
        """
        Eliminar (desactivar) una cuenta bancaria
        Peso: 1 (poco frecuente - simula eliminaciones ocasionales)
        """
        if not self.auth_token or not self.created_accounts:
            print("[WARNING] No hay token o cuentas creadas, saltando eliminación")
            return

        self.request_count += 1
        start_time = time.time()

        # Seleccionar una cuenta aleatoria de las creadas
        account_id = random.choice(self.created_accounts)

        try:
            response = self.client.delete(
                f"/bank-accounts/{account_id}",
                headers={"Authorization": f"Bearer {self.auth_token}"},
                name="Delete Bank Account"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("delete_bank_account", duration, success)

            if success:
                # Remover de la lista de cuentas creadas
                if account_id in self.created_accounts:
                    self.created_accounts.remove(account_id)
                print(
                    f"[SUCCESS] Cuenta bancaria eliminada: {account_id} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error eliminando cuenta: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("delete_bank_account", duration, False)
            print(
                f"[ERROR] Exception eliminando cuenta: {e} ({duration:.2f}s)")

    @task(4)
    def get_user_balance(self):
        """
        Consultar balance del usuario
        Peso: 4 (frecuente - simula consultas de saldo)
        """
        if not self.auth_token:
            print(
                "[WARNING] No hay token de autenticación, saltando consulta de balance")
            return

        self.request_count += 1
        start_time = time.time()

        try:
            response = self.client.get(
                "/transactions/balance/me",
                headers={"Authorization": f"Bearer {self.auth_token}"},
                name="Get User Balance"
            )

            duration = time.time() - start_time
            success = response.status_code == 200
            self.record_metric("get_balance", duration, success)

            if success:
                balance_data = response.json()
                available = balance_data.get("available", 0)
                print(
                    f"[SUCCESS] Balance consultado: ${available:,} ({duration:.2f}s)")
            else:
                print(
                    f"[ERROR] Error consultando balance: {response.status_code} - {response.text}")

        except Exception as e:
            duration = time.time() - start_time
            self.record_metric("get_balance", duration, False)
            print(
                f"[ERROR] Exception consultando balance: {e} ({duration:.2f}s)")


@events.request.add_listener
def my_request_handler(request_type, name, response_time, response_length, response, context, exception, start_time, url, **kwargs):
    """Manejador de eventos para requests"""
    if exception:
        print(f"[ERROR] Request failed: {name} - {exception}")
    elif response and response.status_code >= 400:
        print(
            f"[WARNING] Request returned error: {name} - {response.status_code}")


class BankOperationsLoadTestConfig:
    """
    Configuración para el test de carga de operaciones bancarias
    """

    # Configuración de usuarios
    USERS = 8
    SPAWN_RATE = 2  # Usuarios por segundo

    # Configuración de tiempo
    RUN_TIME = "2m"  # 2 minutos para pruebas completas

    # Configuración de host
    HOST = "http://localhost:8000"

    # Configuración de reportes
    HTML_REPORT = "bank_operations_load_test_report.html"
    CSV_REPORT = "bank_operations_load_test_results.csv"

    # Configuración de métricas
    FOCUS_METRICS = [
        "response_time_p95",
        "response_time_p99",
        "requests_per_sec",
        "failure_rate"
    ]

    # Umbrales de performance específicos para operaciones bancarias
    PERFORMANCE_THRESHOLDS = {
        "create_bank_account": {"max_response_time": 3.0, "max_error_rate": 5.0},
        "list_my_accounts": {"max_response_time": 1.5, "max_error_rate": 2.0},
        "update_bank_account": {"max_response_time": 2.0, "max_error_rate": 3.0},
        "get_balance": {"max_response_time": 1.0, "max_error_rate": 2.0}
    }

    # Configuración de datos de prueba
    TEST_DATA = {
        "accounts_per_user": 3,
        "account_types": ["savings", "checking"],
        "identification_types": ["CC", "CE"]
    }
