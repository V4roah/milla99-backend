#!/usr/bin/env python3
"""
Script para ejecutar test de carga de conductores
Enfoque: Operaciones completas de conductores (registro, documentos, posición, ahorros, ofertas)
"""

import subprocess
import sys
import os
from datetime import datetime
import requests


def run_driver_load_test():
    """Ejecuta el test de carga para conductores"""

    print("INICIANDO TEST DE CARGA - CONDUCTORES")
    print("ENFOQUE: Operaciones completas de conductores")
    print("=" * 60)

    # Crear carpeta de reportes si no existe
    response_dir = "app/load_tests/response"
    if not os.path.exists(response_dir):
        os.makedirs(response_dir)

    # Configuración del test
    config = {
        "users": 2,
        "spawn_rate": 1,
        "run_time": "2m",
        "host": "http://localhost:8000",
        "locustfile": "app/load_tests/locust/load_driver.py"
    }

    print(f"Conductores concurrentes: {config['users']}")
    print(f"Tasa de spawn: {config['spawn_rate']} conductores/segundo")
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
        response_dir, f"driver_load_test_report_{timestamp}.html")
    csv_report = os.path.join(
        response_dir, f"driver_load_test_results_{timestamp}.csv")

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
        "--stop-timeout", "15"
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
USO DEL SCRIPT DE TEST DE CARGA PARA CONDUCTORES

Este script ejecuta un test de carga completo para operaciones de conductores
con enfoque en registro, documentos, posición, ahorros y ofertas de viaje.

REQUISITOS:
1. Servidor corriendo en http://localhost:8000
2. Locust instalado: pip install locust
3. Base de datos con datos de prueba
4. Configuración de archivos de prueba

EJECUCIÓN:
python app/load_tests/run/run_driver_load_test.py

MÉTRICAS QUE SE MIDEN:
- Response Time (min, max, avg) por endpoint
- Requests per second (RPS) por endpoint
- Failure rate (%) por endpoint
- Comportamiento específico de cada operación de conductor

ENDPOINTS ANALIZADOS:
- Create Driver (registro completo con documentos)
- Send Verification Code
- Verify Code
- Get Driver Profile
- Update Driver Position (GPS)
- Get Driver Position
- Get Driver Savings
- Transfer Savings
- Create Trip Offer (simulado)
- Get Nearby Requests

OPERACIONES SIMULADAS:
- Registro completo de conductores con documentos
- Autenticación por WhatsApp
- Actualización de posición GPS en tiempo real
- Consulta de ahorros y transferencias
- Búsqueda de solicitudes de viaje cercanas
- Creación de ofertas de viaje

REPORTES GENERADOS:
- driver_load_test_report_*.html: Reporte detallado con gráficos
- driver_load_test_results_*.csv: Estadísticas por endpoint

CONFIGURACIÓN:
- 20 conductores concurrentes
- 45 segundos de duración
- Comportamiento realista con think time
- Operaciones más complejas que usuarios básicos

ANÁLISIS AUTOMÁTICO:
- Alertas de performance lenta (>3s para operaciones complejas)
- Alertas de errores altos (>5%)
- Recomendaciones específicas por tipo de operación
- Análisis de carga en endpoints críticos (GPS, documentos)

CARACTERÍSTICAS ESPECIALES:
- Simulación de archivos (selfie, documentos)
- Coordenadas GPS realistas en Bogotá
- Datos de vehículos variados
- Comportamiento de ahorros y retiros
- Búsqueda de solicitudes de viaje

NOTAS IMPORTANTES:
- Los tests incluyen operaciones complejas (subida de archivos)
- Se simulan coordenadas GPS realistas
- Se incluyen operaciones financieras (ahorros)
- Los tiempos de respuesta son más permisivos para operaciones complejas
""")


def main():
    """Función principal"""
    try:
        success = run_driver_load_test()

        if success:
            print("\nTest completado exitosamente!")
            print("\nANÁLISIS DE RESULTADOS:")
            print("- Revisa el reporte HTML para gráficos detallados")
            print("- Analiza el CSV para métricas específicas por endpoint")
            print("- Verifica los logs para comportamientos específicos")
            print("- Compara con los umbrales de performance definidos")
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
