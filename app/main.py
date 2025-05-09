from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.db import create_all_tables
from .routers import customers, transactions
from .core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código que se ejecuta al iniciar la aplicación
    print("Iniciando la aplicación...")
    # Crear las tablas
    for _ in create_all_tables(app):
        pass
    yield
    # Código que se ejecuta al cerrar la aplicación
    print("Cerrando la aplicación...")

app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    description="Una API simple creada con FastAPI",
    version=settings.APP_VERSION
)

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

app.include_router(customers.router)
app.include_router(transactions.router)



