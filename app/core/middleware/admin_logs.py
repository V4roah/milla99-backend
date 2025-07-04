import time
from typing import Dict, Any, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.models.admin_log import AdminActionType, LogSeverity
from app.models.administrador import Administrador


class AdminLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging automático de acciones de administradores
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.endpoint_mapping = self._create_endpoint_mapping()

    def _create_endpoint_mapping(self) -> Dict[str, Dict[str, Any]]:
        """
        Crear mapeo de endpoints a tipos de acción y severidad
        SOLO para endpoints que realmente existen
        """
        return {
            # ============================================================================
            # CONSULTAS GENERALES - MIDDLEWARE AUTOMÁTICO
            # ============================================================================
            "/admin/withdrawals/list": {
                "action_type": AdminActionType.WITHDRAWAL_LIST_VIEWED,
                "severity": LogSeverity.MEDIUM,
                "resource_type": "withdrawal"
            }
        }

    async def dispatch(self, request: Request, call_next):
        """
        Interceptar requests y crear logs automáticos
        """
        start_time = time.time()

        # Solo procesar requests de administrador
        if not self._is_admin_request(request):
            response = await call_next(request)
            return response

        # Obtener información de la request
        path = request.url.path
        method = request.method
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Verificar si el endpoint tiene decorador específico
        if not self._has_specific_decorator(path, method):
            # Solo crear log si NO tiene decorador específico
            action_info = self._get_action_info(path, method)

            if action_info:
                try:
                    # Obtener el administrador actual
                    admin = await self._get_current_admin(request)

                    if admin:
                        # Ajustar action_type basado en el body de la request si es necesario
                        final_action_type = action_info["action_type"]

                        # Para endpoints de actualización de retiros, distinguir aprobación/rechazo
                        if path.endswith("/update-status") and method == "PATCH":
                            try:
                                # Intentar leer el body de la request
                                body = await request.json()
                                if body.get("new_status") == "approved":
                                    final_action_type = AdminActionType.WITHDRAWAL_APPROVED
                                elif body.get("new_status") == "rejected":
                                    final_action_type = AdminActionType.WITHDRAWAL_REJECTED
                            except:
                                pass  # Si no se puede leer el body, usar el tipo por defecto

                        # Crear el log automático
                        await self._create_admin_log(
                            admin_id=admin.id,
                            action_type=final_action_type,
                            resource_type=action_info["resource_type"],
                            severity=action_info["severity"],
                            ip_address=ip_address,
                            user_agent=user_agent,
                            path=path,
                            method=method
                        )

                except Exception as e:
                    # No fallar la request si el logging falla
                    print(f"Error en AdminLogMiddleware: {str(e)}")
        else:
            # Endpoint tiene decorador específico, no crear log automático
            print(
                f"Endpoint {path} tiene decorador específico, omitiendo log automático")

        # Continuar con la request
        response = await call_next(request)

        # Calcular tiempo de respuesta
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        return response

    def _is_admin_request(self, request: Request) -> bool:
        """
        Verificar si es una request de administrador
        """
        path = request.url.path

        # Lista de patrones de endpoints de administrador
        admin_patterns = [
            "/admin/",
            "/api/admin/",
            "/administrator/",
            "/dashboard/",
            "/admin-dashboard/"
        ]

        return any(pattern in path for pattern in admin_patterns)

    def _get_action_info(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información de acción basada en el path y método
        """
        # Buscar coincidencia exacta primero
        if path in self.endpoint_mapping:
            return self.endpoint_mapping[path]

        # Buscar coincidencia con parámetros
        for endpoint, info in self.endpoint_mapping.items():
            if self._path_matches(endpoint, path):
                return info

        # Si no hay mapeo específico, usar mapeo genérico
        return self._get_generic_action_info(path, method)

    def _path_matches(self, pattern: str, path: str) -> bool:
        """
        Verificar si un path coincide con un patrón
        """
        # Implementación simple de matching de paths
        # En una implementación real, usarías una librería como pathlib
        pattern_parts = pattern.split("/")
        path_parts = path.split("/")

        if len(pattern_parts) != len(path_parts):
            return False

        for pattern_part, path_part in zip(pattern_parts, path_parts):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                continue  # Es un parámetro
            if pattern_part != path_part:
                return False

        return True

    def _has_specific_decorator(self, path: str, method: str) -> bool:
        """
        Verificar si el endpoint tiene decorador específico
        """
        # Lista de endpoints que tienen decoradores específicos
        endpoints_with_decorators = [
            # Retiros (tienen decorador específico)
            "/admin/withdrawals/{withdrawal_id}/update-status",
        ]

        # Verificar si el path coincide con algún endpoint que tiene decorador
        for endpoint in endpoints_with_decorators:
            if self._path_matches(endpoint, path):
                return True

        return False

    def _get_generic_action_info(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información de acción genérica basada en el path y método
        SOLO para endpoints que NO tienen decorador específico
        """
        # Si tiene decorador específico, no crear log genérico
        if self._has_specific_decorator(path, method):
            return None

        # Mapeo genérico solo para endpoints sin decorador
        if "statistics" in path or "metrics" in path:
            return {
                "action_type": AdminActionType.STATISTICS_SUMMARY_VIEWED,
                "severity": LogSeverity.MEDIUM,
                "resource_type": "statistics"
            }

        elif "dashboard" in path:
            return {
                "action_type": AdminActionType.ADMIN_DASHBOARD_ACCESSED,
                "severity": LogSeverity.LOW,
                "resource_type": "dashboard"
            }

        elif "reports" in path:
            return {
                "action_type": AdminActionType.REPORTS_SECTION_ACCESSED,
                "severity": LogSeverity.LOW,
                "resource_type": "reports"
            }

        # Acción genérica para cualquier request de admin sin decorador
        return {
            "action_type": AdminActionType.ADMIN_DASHBOARD_ACCESSED,
            "severity": LogSeverity.LOW,
            "resource_type": "general"
        }

    async def _get_current_admin(self, request: Request) -> Optional[Administrador]:
        """
        Obtener el administrador actual de la request
        """
        try:
            # En producción, usarías get_current_admin
            # Por ahora retornamos None para evitar errores
            return None
        except Exception as e:
            print(f"Error obteniendo admin: {str(e)}")
            return None

    async def _create_admin_log(
        self,
        admin_id: str,
        action_type: AdminActionType,
        resource_type: str,
        severity: LogSeverity,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        path: str = "",
        method: str = "",
        request_body: Optional[dict] = None
    ):
        """
        Crear log de administrador
        """
        try:
            # Crear descripción basada en la acción
            description = f"{method} {path} - {action_type.value}"

            # Mejorar descripción para retiros
            if "withdrawal" in resource_type and "update-status" in path:
                if action_type == AdminActionType.WITHDRAWAL_APPROVED:
                    description = f"Retiro aprobado: {path}"
                elif action_type == AdminActionType.WITHDRAWAL_REJECTED:
                    description = f"Retiro rechazado: {path}"
                elif action_type == AdminActionType.WITHDRAWAL_LIST_VIEWED:
                    description = f"Lista de retiros consultada"

                    # Por ahora solo imprimimos para debug
            # En producción, usarías el servicio real de logs
            print(
                f"ADMIN LOG: {admin_id} - {action_type.value} - {severity.value} - {description}")

        except Exception as e:
            print(f"❌ Error al crear admin log: {str(e)}")
            # Fallback: solo imprimir si falla el servicio
            print(
                f"ADMIN LOG (FALLBACK): {admin_id} - {action_type.value} - {severity.value} - {description}")


def create_admin_log_middleware(app: ASGIApp) -> AdminLogMiddleware:
    """
    Factory function para crear el middleware de logs de administrador
    """
    return AdminLogMiddleware(app)
