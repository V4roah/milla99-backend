import firebase_admin
from firebase_admin import credentials
from app.core.config import settings


def initialize_firebase():
    """Inicializa Firebase solo si las credenciales están configuradas"""
    if not firebase_admin._apps:
        # Verificar si todas las credenciales están configuradas
        required_vars = [
            settings.FIREBASE_PROJECT_ID,
            settings.FIREBASE_PRIVATE_KEY_ID,
            settings.FIREBASE_PRIVATE_KEY,
            settings.FIREBASE_CLIENT_EMAIL,
            settings.FIREBASE_CLIENT_ID,
            settings.FIREBASE_CLIENT_CERT_URL
        ]

        if not all(required_vars):
            print(
                "⚠️ Firebase no configurado - las notificaciones push estarán deshabilitadas")
            print(
                "   Para habilitar notificaciones push, configura las variables FIREBASE_* en tu .env")
            return

        try:
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID,
                "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
                "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "client_id": settings.FIREBASE_CLIENT_ID,
                "client_x509_cert_url": settings.FIREBASE_CLIENT_CERT_URL,
            })
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK inicializado correctamente")
        except Exception as e:
            print(f"❌ Error inicializando Firebase: {e}")
            print("   Las notificaciones push estarán deshabilitadas")


# Llama a la función al importar el módulo
initialize_firebase()
