#!/usr/bin/env python3
"""
Script para ejecutar test de carga de operaciones bancarias
Enfoque: Consulta de bancos, creación de cuentas, validación, métodos de pago
"""

import subprocess
import sys
import os
from datetime import datetime
import requests


def run_bank_operations_load_test():
    """Ejecuta el test de carga para operaciones bancarias"""

    print("INICIANDO TEST DE CARGA - OPERACIONES BANCARIAS")
    print("ENFOQUE: Consulta de bancos, creación de cuentas, validación")
    print("=" * 60)

    # Crear carpeta de reportes si no existe
    response_dir = "app/load_tests/response"
    if not os.path.exists(response_dir):
        os.makedirs(response_dir)

    # Configuración del test
    config = {
        "users": 1,
        "spawn_rate": 1,
        "run_time": "30s",
        "host": "http://localhost:8000",
        "locustfile": "app/load_tests/locust/load_bank_operations.py"
    }

    print(f"Usuarios concurrentes: {config['users']}")
    print(f"Tasa de spawn: {config['spawn_rate']} usuarios/segundo")
    print(f"Duración: {config['run_time']}")
    print(f"Host: {config['host']}")
    print(f"Archivo: {config['locustfile']}")
    print("=" * 60)

    # Verificar que el servidor esté corriendo
    print("Verificando que el servidor esté corriendo...")
    try:
        response = requests.get(f"{config['host']}/docs", timeout=5)
        if response.status_code == 200:
            print("Servidor está corriendo")
        else:
            print("Servidor responde pero con estado inesperado")
    except Exception as e:
        print(f"Error conectando al servidor: {e}")
        print(
            "Asegúrate de que el servidor esté corriendo con: uvicorn app.main:app --reload")
        return False

    # Generar timestamp para los archivos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_report = os.path.join(
        response_dir, f"bank_operations_load_test_report_{timestamp}.html")
    csv_report = os.path.join(
        response_dir, f"bank_operations_load_test_results_{timestamp}.csv")

    # Comando de Locust
    cmd = [
        "locust",
        "-f", config["locustfile"],
        "--host", config["host"],
        "--users", str(config["users"]),
        "--spawn-rate", str(config["spawn_rate"]),
        "--run-time", config["run_time"],
        "--headless",
        "--html", html_report,
        "--csv", csv_report,
        "--stop-timeout", "10"
    ]

    print(f"Comando: {' '.join(cmd)}")
    print("=" * 60)
    print("Ejecutando test... (puede tomar unos segundos)")
    print("Los logs detallados aparecerán a continuación:")
    print("=" * 60)

    try:
        # Ejecutar comando con output en tiempo real
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Mostrar output en tiempo real
        for line in process.stdout:
            print(line.rstrip())

        # Esperar a que termine
        process.wait()

        if process.returncode == 0:
            print("\n" + "=" * 60)
            print("Test completado exitosamente")
            print("Reporte HTML generado:", html_report)
            print("Datos CSV generados en:", csv_report)

            # Verificar archivos generados
            print("\nArchivos generados:")
            if os.path.exists(html_report):
                file_size = os.path.getsize(html_report)
                print(f"  Reporte HTML: {html_report} ({file_size} bytes)")
            else:
                print(f"  Reporte HTML: {html_report} (no encontrado)")

            if os.path.exists(csv_report):
                file_size = os.path.getsize(csv_report)
                print(f"  Estadísticas CSV: {csv_report} ({file_size} bytes)")
            else:
                print(f"  Estadísticas CSV: {csv_report} (no encontrado)")

            return True
        else:
            print(f"\nTest falló con código de salida: {process.returncode}")
            return False

    except subprocess.CalledProcessError as e:
        print(f"Test falló")
        print(f"Error: {e}")
        if e.stdout:
            print("Output:", e.stdout)
        if e.stderr:
            print("Error:", e.stderr)
        return False
    except Exception as e:
        print(f"Error ejecutando test: {e}")
        return False


def show_help():
    """Muestra ayuda sobre cómo usar el script"""
    print("""
USO DEL SCRIPT DE TEST DE CARGA - OPERACIONES BANCARIAS

Este script ejecuta un test de carga completo para operaciones bancarias
con enfoque en consulta de bancos, creación de cuentas y validación.

REQUISITOS:
1. Servidor corriendo en http://localhost:8000
2. Locust instalado: pip install locust
3. Base de datos con datos de prueba
4. Usuarios con roles aprobados (CLIENT o DRIVER)

EJECUCIÓN:
python app/load_tests/run/run_bank_operations_load_test.py

MÉTRICAS QUE SE MIDEN:
- Response Time (min, max, avg) por endpoint
- Requests per second (RPS) por endpoint
- Failure rate (%) por endpoint
- Comportamiento específico de cada operación bancaria

ENDPOINTS ANALIZADOS:
- List Banks (consulta de bancos disponibles)
- Get Bank (consulta de banco específico)
- Create Bank Account (creación de cuenta bancaria)
- List My Bank Accounts (consulta de cuentas propias)
- Get Active Bank Accounts (consulta de cuentas activas)
- Update Bank Account (actualización de cuenta)
- Delete Bank Account (eliminación de cuenta)
- Get User Balance (consulta de saldo)

OPERACIONES SIMULADAS:
- Consulta de bancos disponibles
- Creación de cuentas bancarias con datos realistas
- Gestión completa de cuentas (CRUD)
- Consulta de saldos y balances
- Validación de datos bancarios

REPORTES GENERADOS:
- bank_operations_load_test_report_*.html: Reporte detallado con gráficos
- bank_operations_load_test_results_*.csv: Estadísticas por endpoint

CONFIGURACIÓN:
- 8 usuarios concurrentes
- 2 minutos de duración
- Comportamiento realista con think time
- Operaciones bancarias seguras con encriptación

ANÁLISIS AUTOMÁTICO:
- Alertas de performance lenta (>2s para operaciones complejas)
- Alertas de errores altos (>5%)
- Recomendaciones específicas por tipo de operación
- Análisis de carga en endpoints críticos (creación de cuentas)

CARACTERÍSTICAS ESPECIALES:
- Datos bancarios realistas (números de cuenta, cédulas)
- Encriptación de datos sensibles
- Validación de roles de usuario
- Gestión de cuentas activas/inactivas
- Consulta de saldos en tiempo real

ENDPOINTS ESPECÍFICOS PROBADOS:
- GET /banks/ - Lista de bancos
- GET /banks/{id} - Banco específico
- POST /bank-accounts/ - Crear cuenta
- GET /bank-accounts/me - Mis cuentas
- GET /bank-accounts/active - Cuentas activas
- PATCH /bank-accounts/{id} - Actualizar cuenta
- DELETE /bank-accounts/{id} - Eliminar cuenta
- GET /transactions/balance/me - Consultar saldo
""")


def main():
    """Función principal"""
    try:
        success = run_bank_operations_load_test()

        if success:
            print("\nTest de operaciones bancarias completado exitosamente!")
        else:
            print("\nEl test falló. Revisa los errores arriba.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nTest interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\nError inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        show_help()
    else:
        main()
