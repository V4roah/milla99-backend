#!/usr/bin/env python3
"""
Script para ejecutar test de carga de usuarios
Enfoque: Operaciones básicas de usuarios (creación, autenticación, perfil)
"""

import subprocess
import sys
import os
from datetime import datetime
import requests


def run_load_test():
    """Ejecuta el test de carga para usuarios básicos"""

    print("INICIANDO TEST DE CARGA - USUARIOS SIMPLES")
    print("ENFOQUE: Operaciones básicas de usuarios")
    print("=" * 60)

    # Crear carpeta de reportes si no existe
    response_dir = "app/load_tests/response"
    if not os.path.exists(response_dir):
        os.makedirs(response_dir)

    # Configuración del test
    config = {
        "users": 50,
        "spawn_rate": 10,
        "run_time": "30s",
        "host": "http://localhost:8000",
        "locustfile": "app/load_tests/locust/load_user.py"
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
        response = requests.get(f"{config['host']}/health", timeout=5)
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
        response_dir, f"user_load_test_report_{timestamp}.html")
    csv_report = os.path.join(
        response_dir, f"user_load_test_results_{timestamp}.csv")

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
USO DEL SCRIPT DE TEST DE CARGA

Este script ejecuta un test de carga completo para operaciones básicas de usuarios
con enfoque en creación, autenticación y consulta de perfiles.

REQUISITOS:
1. Servidor corriendo en http://localhost:8000
2. Locust instalado: pip install locust
3. Base de datos con datos de prueba

EJECUCIÓN:
python app/load_tests/run/run_load_user_test.py

MÉTRICAS QUE SE MIDEN:
- Response Time (min, max, avg) por endpoint
- Requests per second (RPS) por endpoint
- Failure rate (%) por endpoint
- Comportamiento específico de cada operación

ENDPOINTS ANALIZADOS:
- Create User
- Send Verification Code
- Verify Code
- Get User Profile
- Update User Profile (simulado)
- Check User Status

REPORTES GENERADOS:
- user_load_test_report_*.html: Reporte detallado con gráficos
- user_load_test_results_*.csv: Estadísticas por endpoint

CONFIGURACIÓN:
- 10 usuarios concurrentes
- 15 segundos de duración
- Comportamiento realista con think time

ANÁLISIS AUTOMÁTICO:
- Alertas de performance lenta (>2s)
- Alertas de errores altos (>5%)
- Recomendaciones específicas por tipo de error
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
