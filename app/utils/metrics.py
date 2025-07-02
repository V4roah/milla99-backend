import time
import psutil
from datetime import datetime
from typing import Dict, Any
from collections import defaultdict
import threading
import json
import os


class SimpleMetrics:
    """
    Sistema de métricas simple y ligero para Milla99
    No requiere dependencias externas pesadas
    """

    def __init__(self):
        self.request_counts = defaultdict(int)
        self.response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.start_time = datetime.now()
        self.lock = threading.Lock()

        # Métricas del sistema
        self.system_metrics = {
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_usage': 0
        }

        # Actualizar métricas del sistema cada 30 segundos
        self._start_system_monitoring()

    def _start_system_monitoring(self):
        """Actualiza métricas del sistema en background"""
        def update_system_metrics():
            while True:
                try:
                    self.system_metrics['cpu_percent'] = psutil.cpu_percent(
                        interval=1)
                    self.system_metrics['memory_percent'] = psutil.virtual_memory(
                    ).percent
                    self.system_metrics['disk_usage'] = psutil.disk_usage(
                        '/').percent
                except:
                    pass
                time.sleep(30)  # Cada 30 segundos

        thread = threading.Thread(target=update_system_metrics, daemon=True)
        thread.start()

    def record_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """Registra una request"""
        with self.lock:
            key = f"{method}_{endpoint}"
            self.request_counts[key] += 1

            # Solo guardar los últimos 100 tiempos de respuesta por endpoint
            if len(self.response_times[key]) >= 100:
                self.response_times[key] = self.response_times[key][-50:]

            self.response_times[key].append(duration)

            if status_code >= 400:
                self.error_counts[key] += 1

    def get_metrics(self) -> str:
        """Retorna métricas en formato Prometheus"""
        with self.lock:
            metrics = []

            # Métricas de requests
            for key, count in self.request_counts.items():
                method, endpoint = key.split('_', 1)
                metrics.append(
                    f'http_requests_total{{method="{method}",endpoint="{endpoint}"}} {count}')

            # Métricas de tiempo de respuesta
            for key, times in self.response_times.items():
                if times:
                    method, endpoint = key.split('_', 1)
                    avg_time = sum(times) / len(times)
                    metrics.append(
                        f'http_request_duration_seconds{{method="{method}",endpoint="{endpoint}"}} {avg_time}')

            # Métricas de errores
            for key, count in self.error_counts.items():
                method, endpoint = key.split('_', 1)
                metrics.append(
                    f'http_errors_total{{method="{method}",endpoint="{endpoint}"}} {count}')

            # Métricas del sistema
            metrics.append(
                f'system_cpu_percent {self.system_metrics["cpu_percent"]}')
            metrics.append(
                f'system_memory_percent {self.system_metrics["memory_percent"]}')
            metrics.append(
                f'system_disk_usage_percent {self.system_metrics["disk_usage"]}')

            # Uptime
            uptime = (datetime.now() - self.start_time).total_seconds()
            metrics.append(f'application_uptime_seconds {uptime}')

            return '\n'.join(metrics)

    def get_business_metrics(self) -> Dict[str, Any]:
        """Métricas específicas de negocio de Milla99"""
        # Aquí puedes agregar métricas específicas de tu negocio
        # Por ejemplo: viajes activos, conductores online, etc.
        return {
            'active_trips': 0,  # Implementar lógica real
            'online_drivers': 0,  # Implementar lógica real
            'total_revenue_today': 0,  # Implementar lógica real
            'requests_per_minute': sum(self.request_counts.values()) / max(1, (datetime.now() - self.start_time).total_seconds() / 60)
        }


# Instancia global
metrics = SimpleMetrics()
