from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List, Optional
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Configuración de la aplicación
    APP_NAME: str = "Milla99 API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Configuración de la base de datos
    DATABASE_URL: str
    TEST_DATABASE_URL: str

    # Configuración CORS
    CORS_ORIGINS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]

    # Teléfono de prueba para usuario de prueba
    TEST_CLIENT_PHONE: str = "+573148780278"

    # WhatsApp API Settings
    WHATSAPP_API_URL: str
    WHATSAPP_API_TOKEN: str
    WHATSAPP_PHONE_ID: str
    VERIFICATION_CODE_EXPIRY_MINUTES: int = 10
    MAX_VERIFICATION_ATTEMPTS: int = 3

    # Deberías cambiar esto
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hora (más seguro que 7 días)

    # Configuración de Refresh Tokens
    REFRESH_TOKEN_SECRET_KEY: str  # Clave separada para refresh tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 días por defecto
    ACCESS_TOKEN_EXPIRE_MINUTES_NEW: int = 60  # 1 hora para access tokens nuevos
    REFRESH_TOKEN_ROTATION: bool = True  # Rotar refresh tokens en cada renovación

    # Clave de encriptación para datos sensibles (se toma del .env)
    ENCRYPTION_KEY: str

    CLICK_SEND_USERNAME: str
    CLICK_SEND_PASSWORD: str
    CLICK_SEND_PHONE: str

    STATIC_URL_PREFIX: str = "http://localhost:8000/static/uploads"

    # Configuración de Google Maps
    GOOGLE_API_KEY: str

    # Configuración de Firebase (para notificaciones push)
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_PRIVATE_KEY_ID: Optional[str] = None
    FIREBASE_PRIVATE_KEY: Optional[str] = None
    FIREBASE_CLIENT_EMAIL: Optional[str] = None
    FIREBASE_CLIENT_ID: Optional[str] = None
    FIREBASE_CLIENT_CERT_URL: Optional[str] = None

    model_config = ConfigDict(
        env_file=".env",  # Por defecto, pero se sobreescribe abajo
        case_sensitive=True,
        extra="allow"  # Permitir campos extra en la configuración
    )

    def __init__(self, **kwargs):
        # Detectar el entorno automáticamente
        environment = os.getenv("ENVIRONMENT", "development")

        # Determinar qué archivo de configuración usar
        if environment == "qa":
            env_file = "env.qa"
        elif environment == "production":
            env_file = "env.production"
        else:
            env_file = ".env"  # Fallback al archivo original

        # Configurar el archivo de entorno
        kwargs["_env_file"] = env_file

        super().__init__(**kwargs)


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
