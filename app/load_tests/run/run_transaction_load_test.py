#!/usr/bin/env python3
"""
Script para ejecutar tests de carga de transacciones financieras
Simula operaciones de dinero: depósitos, retiros, transferencias, consultas
"""

import os
import sys
import subprocess
import time
from datetime import datetime

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def run_transaction_load_test():
    """Ejecuta el test de carga de transacciones"""

    print("=" * 60)
    print("INICIANDO TEST DE CARGA DE TRANSACCIONES")
    print("=" * 60)
    print(f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Configuración del test
    config = {
        'users': 2,           # Número de usuarios concurrentes
        'spawn_rate': 1,      # Usuarios por segundo
        'run_time': '30s',     # Duración del test
        'host': 'http://localhost:8000',  # URL del servidor
        'locustfile': 'app/load_tests/locust/load_transactions.py'
    }

    print("CONFIGURACIÓN DEL TEST:")
    print(f"  • Usuarios concurrentes: {config['users']}")
    print(f"  • Tasa de spawn: {config['spawn_rate']} usuarios/segundo")
    print(f"  • Duración: {config['run_time']}")
    print(f"  • Servidor: {config['host']}")
    print(f"  • Archivo de test: {config['locustfile']}")
    print()

    # Verificar que el archivo existe
    if not os.path.exists(config['locustfile']):
        print(f"ERROR: No se encontró el archivo {config['locustfile']}")
        return False

    # Comando para ejecutar el test
    cmd = [
        'locust',
        '--headless',
        '--users', str(config['users']),
        '--spawn-rate', str(config['spawn_rate']),
        '--run-time', config['run_time'],
        '--host', config['host'],
        '--locustfile', config['locustfile'],
        '--html', 'app/load_tests/response/transaction_load_test_report.html',
        '--csv', 'app/load_tests/response/transaction_load_test'
    ]

    print("EJECUTANDO TEST...")
    print(f"Comando: {' '.join(cmd)}")
    print()

    try:
        # Ejecutar el comando
        start_time = time.time()
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True)
        end_time = time.time()

        print("TEST COMPLETADO EXITOSAMENTE")
        print(
            f"Tiempo total de ejecución: {end_time - start_time:.2f} segundos")
        print()

        # Mostrar salida del comando
        if result.stdout:
            print("SALIDA DEL TEST:")
            print(result.stdout)

        # Mostrar archivos generados
        print("ARCHIVOS GENERADOS:")
        report_files = [
            'app/load_tests/response/transaction_load_test_report.html',
            'app/load_tests/response/transaction_load_test_stats.csv',
            'app/load_tests/response/transaction_load_test_stats_history.csv',
            'app/load_tests/response/transaction_load_test_failures.csv'
        ]

        for file_path in report_files:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"  • {file_path} ({file_size} bytes)")
            else:
                print(f"  • {file_path} (no encontrado)")

        print()
        print("RECOMENDACIONES:")
        print("  • Revisa el reporte HTML para análisis detallado")
        print("  • Verifica las métricas de rendimiento en los archivos CSV")
        print("  • Analiza los errores en el archivo de fallos")
        print("  • Considera ajustar parámetros según los resultados")

        return True

    except subprocess.CalledProcessError as e:
        print("ERROR EJECUTANDO EL TEST")
        print(f"Código de salida: {e.returncode}")
        print()

        if e.stdout:
            print("SALIDA ESTÁNDAR:")
            print(e.stdout)

        if e.stderr:
            print("ERRORES:")
            print(e.stderr)

        return False

    except FileNotFoundError:
        print("ERROR: No se encontró el comando 'locust'")
        print("Asegúrate de tener Locust instalado:")
        print("  pip install locust")
        return False

    except Exception as e:
        print(f"ERROR INESPERADO: {e}")
        return False


def show_usage_examples():
    """Muestra ejemplos de uso con diferentes configuraciones"""

    print("EJEMPLOS DE CONFIGURACIÓN:")
    print()

    examples = [
        {
            'name': 'Test Ligero',
            'description': 'Pocos usuarios, corta duración - para pruebas rápidas',
            'users': 3,
            'spawn_rate': 1,
            'run_time': '1m'
        },
        {
            'name': 'Test Moderado',
            'description': 'Configuración balanceada - recomendada para desarrollo',
            'users': 5,
            'spawn_rate': 1,
            'run_time': '2m'
        },
        {
            'name': 'Test Intensivo',
            'description': 'Muchos usuarios, larga duración - para pruebas de producción',
            'users': 10,
            'spawn_rate': 2,
            'run_time': '5m'
        },
        {
            'name': 'Test de Estrés',
            'description': 'Máxima carga - para encontrar límites del sistema',
            'users': 20,
            'spawn_rate': 5,
            'run_time': '10m'
        }
    ]

    for i, example in enumerate(examples, 1):
        print(f"{i}. {example['name']}")
        print(f"   {example['description']}")
        print(
            f"   Usuarios: {example['users']}, Spawn: {example['spawn_rate']}/s, Duración: {example['run_time']}")
        print()


if __name__ == "__main__":
    # Mostrar ejemplos de uso
    show_usage_examples()

    # Ejecutar el test
    success = run_transaction_load_test()

    if success:
        print("TEST DE TRANSACCIONES COMPLETADO!")
    else:
        print("TEST DE TRANSACCIONES FALLÓ")
        sys.exit(1)
