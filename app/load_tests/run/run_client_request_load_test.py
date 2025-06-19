#!/usr/bin/env python3
"""
Script para ejecutar el load test completo de client request
Simula el flujo completo: creación de solicitudes, asignación de conductor, cambio de estados
"""

import os
import sys
import subprocess
import time
from datetime import datetime

# Agregar el directorio raíz del proyecto al path
project_root = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def run_load_test():
    """Ejecuta el load test completo de client request"""

    print("=" * 80)
    print("🚀 INICIANDO LOAD TEST COMPLETO DE CLIENT REQUEST")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Enfoque: Flujo completo con cambio de estados")
    print(f"👥 Usuarios: 10 (70% clientes, 30% conductores)")
    print(f"⏱️  Duración: 2 minutos")
    print(f"🔄 Spawn Rate: 2 usuarios/segundo")
    print("=" * 80)

    # Configuración del test
    config = {
        "users": 10,
        "spawn_rate": 2,
        "run_time": "2m",
        "host": "http://localhost:8000",
        "locust_file": "app/load_tests/locust/load_client_request.py",
        "html_report": "app/load_tests/response/client_request_load_test_report.html",
        "csv_report": "app/load_tests/response/client_request_load_test_results.csv"
    }

    # Crear directorio de reportes si no existe
    os.makedirs("app/load_tests/response", exist_ok=True)

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
    print(f"   👥 Usuarios: {config['users']}")
    print(f"   🚀 Spawn Rate: {config['spawn_rate']}/s")
    print(f"   ⏱️  Duración: {config['run_time']}")
    print(f"   📊 Reporte HTML: {config['html_report']}")
    print(f"   📈 Reporte CSV: {config['csv_report']}")
    print("=" * 80)

    try:
        print("🚀 Ejecutando load test...")
        print("⏳ Esto puede tomar varios minutos...")
        print("-" * 80)

        # Ejecutar el comando
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

            # Mostrar métricas clave del output
            if result.stdout:
                lines = result.stdout.split('\n')
                for line in lines:
                    if any(keyword in line for keyword in [
                        "requests/sec", "response time", "failure rate",
                        "Total requests", "Total failures"
                    ]):
                        print(f"📈 {line.strip()}")

            print(f"\n📊 Reportes generados:")
            print(f"   📄 HTML: {config['html_report']}")
            print(f"   📈 CSV: {config['csv_report']}")

        else:
            print("❌ Error ejecutando load test")
            print(f"🔍 Código de salida: {result.returncode}")
            if result.stderr:
                print(f"📝 Error: {result.stderr}")
            if result.stdout:
                print(f"📄 Output: {result.stdout}")

        print("=" * 80)

    except FileNotFoundError:
        print("❌ Error: No se encontró el comando 'locust'")
        print("💡 Asegúrate de tener Locust instalado:")
        print("   pip install locust")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        print("=" * 80)


def show_test_description():
    """Muestra la descripción del test"""
    print("📋 DESCRIPCIÓN DEL LOAD TEST COMPLETO")
    print("=" * 80)
    print("🎯 Objetivo: Simular el flujo completo de client request con cambio de estados")
    print()
    print("🔄 Flujo del Test:")
    print("   1. 📱 Crear usuarios (70% clientes, 30% conductores)")
    print("   2. 🔐 Autenticar usuarios")
    print("   3. 🚗 Clientes crean solicitudes de viaje")
    print("   4. 🔍 Conductores buscan solicitudes cercanas")
    print("   5. 👨‍💼 Conductores se asignan a solicitudes")
    print("   6. 📍 Conductores actualizan posición GPS")
    print("   7. 🔄 Simular cambio de estados del viaje:")
    print("      • ON_THE_WAY → Conductor en camino")
    print("      • ARRIVED → Conductor llegó")
    print("      • TRAVELLING → Viaje en curso")
    print("      • FINISHED → Viaje finalizado")
    print("      • PAID → Viaje pagado")
    print("   8. 📊 Consultar solicitudes por estado")
    print("   9. 📋 Obtener detalles de solicitudes")
    print()
    print("📊 Métricas que se miden:")
    print("   • Tiempo de respuesta (p95, p99)")
    print("   • Requests por segundo")
    print("   • Tasa de fallos")
    print("   • Duración por endpoint")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        show_test_description()
    else:
        run_load_test()
