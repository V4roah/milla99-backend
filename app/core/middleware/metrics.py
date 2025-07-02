import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.metrics import metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware para capturar métricas automáticamente
    """

    async def dispatch(self, request: Request, call_next):
        # Tiempo de inicio
        start_time = time.time()

        # Procesar la request
        response = await call_next(request)

        # Calcular duración
        duration = time.time() - start_time

        # Extraer información de la request
        endpoint = request.url.path
        method = request.method
        status_code = response.status_code

        # Registrar métricas
        metrics.record_request(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration=duration
        )

        return response
