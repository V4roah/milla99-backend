from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from fastapi.staticfiles import StaticFiles

from app.routers import config_service_value_admin, project_settings
from app.routers.transaction import router as transaction_router
from app.routers.bank_accounts import router as bank_accounts_router
from app.routers.bank import router as bank_router
from app.routers.test_runner import router as test_runner_router
from app.routers.metrics import router as metrics_router
from app.routers.admin_logs import router as admin_logs_router

from .core.db import create_all_tables, get_environment_info
from .routers import config_service_value, referrals, users, drivers, auth, verify_docs, driver_position, driver_trip_offer, client_request, login_admin, withdrawal, driver_savings, withdrawal_admin, admin_statistics, admin_drivers, user_fcm_token, chat, trip_stops
from .core.config import settings
from .core.init_data import init_data
from .core.middleware.auth import JWTAuthMiddleware
from .core.middleware.metrics import MetricsMiddleware
from .core.middleware.admin_logs import create_admin_log_middleware
from .core.sio_events import sio
import socketio


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Iniciando la aplicación...")

    # Mostrar información del entorno
    env_info = get_environment_info()
    print(f"🌍 Entorno: {env_info['environment']}")
    print(f"📊 Base de datos: {env_info['database_url']}")
    print(f"🔒 Seguro para inicialización: {env_info['safe_for_init']}")

    # Crear tablas
    create_all_tables()

    # Inicializar datos (con validaciones automáticas)
    init_data()

    print("✅ Aplicación iniciada correctamente")
    yield
    print("🔚 Cerrando la aplicación...")

fastapi_app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    description="Una API simple creada con FastAPI",
    version=settings.APP_VERSION
)

# Configuración CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

fastapi_app.mount("/static", StaticFiles(directory="static"), name="static")

# Agregar middleware de métricas (debe ir antes del de autenticación)
fastapi_app.add_middleware(MetricsMiddleware)

# Agregar middleware de logs de administrador
fastapi_app.add_middleware(create_admin_log_middleware)

# Agregar middleware de autenticación
fastapi_app.add_middleware(JWTAuthMiddleware)

# Agregar routers
fastapi_app.include_router(users.router)
fastapi_app.include_router(auth.router)
fastapi_app.include_router(drivers.router)
fastapi_app.include_router(client_request.router)
fastapi_app.include_router(trip_stops.router)
fastapi_app.include_router(driver_position.router)
fastapi_app.include_router(config_service_value.router)
fastapi_app.include_router(driver_trip_offer.router)
fastapi_app.include_router(transaction_router)
fastapi_app.include_router(withdrawal.router)
fastapi_app.include_router(driver_savings.router)
fastapi_app.include_router(referrals.router)
fastapi_app.include_router(bank_router)
fastapi_app.include_router(bank_accounts_router)
fastapi_app.include_router(user_fcm_token.router)
fastapi_app.include_router(chat.router)
fastapi_app.include_router(login_admin.router)
fastapi_app.include_router(verify_docs.router)
fastapi_app.include_router(config_service_value_admin.router)
fastapi_app.include_router(withdrawal_admin.router)
fastapi_app.include_router(project_settings.router)
fastapi_app.include_router(admin_statistics.router)
fastapi_app.include_router(admin_drivers.router)
fastapi_app.include_router(test_runner_router)
fastapi_app.include_router(metrics_router)
fastapi_app.include_router(admin_logs_router)

# Socket.IO debe ser lo último
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
