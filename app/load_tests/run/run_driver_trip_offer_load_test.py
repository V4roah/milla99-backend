#!/usr/bin/env python3
"""
Script para ejecutar el load test de Driver Trip Offer.
Simula múltiples conductores enviando ofertas a solicitudes de viaje.
"""

import os
import sys
import subprocess
import time
import requests
from datetime import datetime

# Agregar el directorio raíz del proyecto al path
# El script está en app/load_tests/run, así que subimos 3 niveles para llegar a la raíz.
project_root = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)


def run_load_test():
    """Ejecuta el load test de Driver Trip Offer."""

    # --- PARÁMETROS ESPECÍFICOS PARA ESTE TEST ---
    USERS = 2
    SPAWN_RATE = 1
    RUN_TIME = "1m"
    HOST = "http://localhost:8000"
    # ---------------------------------------------

    print("=" * 80)
    print("INICIANDO TEST DE CARGA PARA DRIVER TRIP OFFER")
    print("=" * 80)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Enfoque: Múltiples conductores enviando ofertas de viaje.")
    print(f"Usuarios: {USERS}")
    print(f"Duración: {RUN_TIME}")
    print(f"Spawn Rate: {SPAWN_RATE} usuarios/segundo")
    print("=" * 80)

    # Verificar que el servidor esté corriendo
    print("Verificando que el servidor esté corriendo...")
    try:
        # Usar un endpoint público en lugar de /health que requiere autenticación
        response = requests.get(f"{HOST}/docs", timeout=5)
        if response.status_code == 200:
            print("Servidor está corriendo correctamente")
        else:
            print(
                f"Servidor responde pero con estado inesperado: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("Error: No se puede conectar al servidor")
        print("   Asegúrate de que el servidor esté corriendo con:")
        print("   uvicorn app.main:app --reload")
        return False
    except requests.exceptions.Timeout:
        print("Error: Timeout al conectar con el servidor")
        print("   El servidor puede estar sobrecargado o no responder")
        return False
    except Exception as e:
        print(f"Error conectando al servidor: {e}")
        print("   Asegúrate de que el servidor esté corriendo con:")
        print("   uvicorn app.main:app --reload")
        return False

    # Crear directorio de reportes si no existe
    os.makedirs("app/load_tests/response", exist_ok=True)

    # Configuración del test usando los parámetros definidos arriba
    config = {
        "users": USERS,
        "spawn_rate": SPAWN_RATE,
        "run_time": RUN_TIME,
        "host": HOST,
        "locust_file": "app/load_tests/locust/load_driver_trip_offer.py",
        "html_report": "app/load_tests/response/driver_trip_offer_report.html",
        "csv_report": "app/load_tests/response/driver_trip_offer_results"
    }

    # Comando para ejecutar el load test
    cmd = [
        "locust",
        "-f", config["locust_file"],
        "--host", config["host"],
        "--users", str(config["users"]),
        "--spawn-rate", str(config["spawn_rate"]),
        "--run-time", config["run_time"],
        "--headless",
        "--html", config["html_report"],
        "--csv", config["csv_report"]
    ]

    print("Configuración:")
    print(f"   Archivo: {config['locust_file']}")
    print(f"   Host: {config['host']}")
    print(f"   Reporte HTML: {config['html_report']}")
    print(f"   Reporte CSV: {config['csv_report']}_stats.csv")
    print("=" * 80)

    try:
        print("Ejecutando load test...")
        print("Esto puede tomar varios minutos...")
        print("-" * 80)

        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True,
                                text=True, cwd=project_root)
        end_time = time.time()

        execution_time = end_time - start_time

        print("-" * 80)
        print("RESULTADOS DEL LOAD TEST")
        print("-" * 80)

        if result.returncode == 0:
            print("Load test completado exitosamente")
            print(f"Tiempo de ejecución: {execution_time:.2f} segundos")

            # Verificar archivos generados
            print("\nArchivos generados:")
            if os.path.exists(config["html_report"]):
                file_size = os.path.getsize(config["html_report"])
                print(
                    f"   Reporte HTML: {config['html_report']} ({file_size} bytes)")
            else:
                print(
                    f"   Reporte HTML: {config['html_report']} (no encontrado)")

            csv_stats_file = f"{config['csv_report']}_stats.csv"
            if os.path.exists(csv_stats_file):
                file_size = os.path.getsize(csv_stats_file)
                print(
                    f"   Estadísticas CSV: {csv_stats_file} ({file_size} bytes)")
            else:
                print(f"   Estadísticas CSV: {csv_stats_file} (no encontrado)")

            return True
        else:
            print("Error ejecutando load test")
            print(f"Código de salida: {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return False

        print("=" * 80)

    except FileNotFoundError:
        print(
            "Error: No se encontró el comando 'locust'. Asegúrate de que está instalado.")
        print("   pip install locust")
        print("=" * 80)
        return False
    except Exception as e:
        print(f"Error inesperado: {e}")
        print("=" * 80)
        return False


def show_help():
    """Muestra ayuda sobre cómo usar el script"""
    print("""
USO DEL SCRIPT DE TEST DE CARGA - DRIVER TRIP OFFER

Este script ejecuta un test de carga completo para conductores enviando ofertas de viaje
con enfoque en la creación de ofertas competitivas.

REQUISITOS:
1. Servidor corriendo en http://localhost:8000
2. Locust instalado: pip install locust
3. Base de datos con datos de prueba y client requests disponibles

EJECUCIÓN:
python app/load_tests/run/run_driver_trip_offer_load_test.py

MÉTRICAS QUE SE MIDEN:
- Response Time (min, max, avg) por endpoint
- Requests per second (RPS) por endpoint
- Failure rate (%) por endpoint
- Comportamiento específico de cada operación

ENDPOINTS ANALIZADOS:
- Create Driver (setup)
- Approve Driver Role (setup)
- Send Verification Code (auth)
- Verify Code (auth)
- Get Nearby Requests
- Create Trip Offer

REPORTES GENERADOS:
- driver_trip_offer_report.html: Reporte detallado con gráficos
- driver_trip_offer_results_stats.csv: Estadísticas por endpoint

CONFIGURACIÓN:
- 2 usuarios concurrentes (conductores)
- 1 minuto de duración
- Comportamiento realista con think time

CARACTERÍSTICAS ESPECIALES:
- Posiciones aleatorias para cada conductor
- Números de teléfono únicos
- Datos de vehículo aleatorios
- Ofertas competitivas basadas en tarifa base
""")


def main():
    """Función principal"""
    try:
        success = run_load_test()

        if success:
            print("\nTest completado exitosamente!")
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
    main()
