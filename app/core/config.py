from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Configuración de la aplicación
    APP_NAME: str = "Milla99 API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Configuración de la base de datos
    DATABASE_URL: str = "mysql+pymysql://root:root@localhost:3307/milla99"
    TEST_DATABASE_URL: str = "mysql+pymysql://root:root@localhost:3307/milla99_test"

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    # Clave de encriptación para datos sensibles (se toma del .env)
    ENCRYPTION_KEY: str

    CLICK_SEND_USERNAME: str
    CLICK_SEND_PASSWORD: str
    CLICK_SEND_PHONE: str

    STATIC_URL_PREFIX: str = "http://localhost:8000/static/uploads"

    # Configuración de Google Maps
    GOOGLE_API_KEY: str

    # Configuración de Firebase (para notificaciones push)
    FIREBASE_PROJECT_ID: str
    FIREBASE_PRIVATE_KEY_ID: str
    FIREBASE_PRIVATE_KEY: str
    FIREBASE_CLIENT_EMAIL: str
    FIREBASE_CLIENT_ID: str
    FIREBASE_CLIENT_CERT_URL: str

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"  # Permitir campos extra en la configuración
    )


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
