#!/usr/bin/env python3
"""
Script para ejecutar el load test de Driver Trip Offer.
Simula múltiples conductores enviando ofertas a solicitudes de viaje.
"""

import os
import sys
import subprocess
import time
from datetime import datetime

# Agregar el directorio raíz del proyecto al path
# El script está en app/load_tests/run, así que subimos 3 niveles para llegar a la raíz.
project_root = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)


def run_load_test():
    """Ejecuta el load test de Driver Trip Offer."""

    # --- PARÁMETROS ESPECÍFICOS PARA ESTE TEST ---
    USERS = 10
    SPAWN_RATE = 2
    RUN_TIME = "2m"
    HOST = "http://localhost:8000"
    # ---------------------------------------------

    print("=" * 80)
    print("🚀 INICIANDO TEST DE CARGA PARA DRIVER TRIP OFFER")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Enfoque: Múltiples conductores enviando ofertas de viaje.")
    print(f"👥 Usuarios: {USERS}")
    print(f"⏱️  Duración: {RUN_TIME}")
    print(f"🔄 Spawn Rate: {SPAWN_RATE} usuarios/segundo")
    print("=" * 80)

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

    print("🔧 Configuración:")
    print(f"   📁 Archivo: {config['locust_file']}")
    print(f"   🌐 Host: {config['host']}")
    print(f"   📊 Reporte HTML: {config['html_report']}")
    print(f"   📈 Reporte CSV: {config['csv_report']}_stats.csv")
    print("=" * 80)

    try:
        print("🚀 Ejecutando load test...")
        print("⏳ Esto puede tomar varios minutos...")
        print("-" * 80)

        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True,
                                text=True, cwd=project_root)
        end_time = time.time()

        execution_time = end_time - start_time

        print("-" * 80)
        print("📊 RESULTADOS DEL LOAD TEST")
        print("-" * 80)

        if result.returncode == 0:
            print("✅ Load test completado exitosamente")
            print(f"⏱️  Tiempo de ejecución: {execution_time:.2f} segundos")
        else:
            print("❌ Error ejecutando load test")
            print(f"🔍 Código de salida: {result.returncode}")
            if result.stderr:
                print(f"📝 Error: {result.stderr}")

        print("=" * 80)

    except FileNotFoundError:
        print(
            "❌ Error: No se encontró el comando 'locust'. Asegúrate de que está instalado.")
        print("   pip install locust")
        print("=" * 80)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        print("=" * 80)


if __name__ == "__main__":
    run_load_test()
