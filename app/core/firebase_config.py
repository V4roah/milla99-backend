import firebase_admin
from firebase_admin import credentials
from app.core.config import settings


def initialize_firebase():
    if not firebase_admin._apps:
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


# Llama a la función al importar el módulo
initialize_firebase()
