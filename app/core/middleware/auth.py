from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt, JWTError
from app.core.config import settings
from uuid import UUID


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Lista de rutas públicas que no requieren autenticación
        # Formato: (ruta, método_http)
        public_paths = [
            ("/users/", "POST"),
            ("/users/", "GET"),  # Solo el registro de usuarios
            ("/auth/verify/", "POST"),  # Rutas de verificación
            ("/auth/refresh", "POST"),  # Permitir refresh token sin autenticación
            ("/auth/logout", "POST"),  # Permitir logout (revocación de refresh token) sin autenticación
            ("/docs", "GET"),  # Documentación
            ("/openapi.json", "GET"),  # Esquema OpenAPI
            ("/drivers/", "POST"),  # creacion de drivers
            ("/drivers/", "PATCH"),  # actualizacion de drivers
            ("/openapi.json", "GET"),  # Esquema OpenAPI
            ("/verify-docs/", "GET"),  # Rutas de verify-docs
            ("/verify-docs/", "POST"),
            ("/static/uploads/", "GET"),
            ("/login-admin/", "POST"),
            ("/static/reports/", "GET"),   # Permitir ver reportes HTML
            ("/static/reports/", "POST"),  # Permitir post (por si acaso)
            # ("/drivers-position/", "POST"),  # Rutas POST de drivers-position
            # ("/drivers-position/", "GET"),  # Rutas GET de drivers-position
            # Rutas DELETE de drivers-position
            # ("/drivers-position/", "DELETE"),
            # Rutas POST de driver-trip-offers
            # ("/driver-trip-offers/", "POST"),
            # ("/driver-trip-offers/", "GET"),  # Rutas GET de driver-trip-offers
            # ("/distance-value/", "GET"),
            # ("/vehicle-type-configuration/", "GET"),
            # ("/referrals/", "POST"),
            # ("/referrals/", "GET"),
        ]

        # Verificar si la ruta y método actual están en la lista de públicas
        is_public = any(
            request.url.path.startswith(path) and request.method == method
            for path, method in public_paths
        )

        if is_public:
            return await call_next(request)

        # Para el resto de rutas, verificar token
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "No se proporcionó token de autenticación"}
                )

            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, settings.SECRET_KEY,
                                 algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")

            if not user_id:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token inválido"}
                )

            request.state.user_id = UUID(user_id)

        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido o expirado"}
            )

        return await call_next(request)
