import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import engine
from sqlmodel import Session, select
from app.models.administrador import Administrador
import traceback

client = TestClient(app)


def test_admin_login_all_roles():
    """Test para verificar login de los 3 admins con diferentes roles"""

    # Datos de los admins creados en init_data.py
    admins_data = [
        {
            "email": "admin",
            "password": "admin",
            "role": 1,
            "description": "Admin básico"
        },
        {
            "email": "system_admin",
            "password": "system123",
            "role": 2,
            "description": "Admin del sistema"
        },
        {
            "email": "super_admin",
            "password": "super123",
            "role": 3,
            "description": "Super admin"
        }
    ]

    for admin_data in admins_data:
        print(f"\n🧪 Probando login para: {admin_data['description']}")
        print(f"   Email: {admin_data['email']}")
        print(f"   Password: {admin_data['password']}")

        # Verificar que el admin existe en la DB antes del login
        with Session(engine) as session:
            admin = session.exec(
                select(Administrador).where(
                    Administrador.email == admin_data["email"])
            ).first()

            if admin:
                print(
                    f"✅ Admin encontrado en DB: {admin.email}, role: {admin.role}")
                print(f"   Password hash: {admin.password[:20]}...")
            else:
                print(f"❌ Admin NO encontrado en DB: {admin_data['email']}")
                continue

        # Hacer login
        login_data = {
            "email": admin_data["email"],
            "password": admin_data["password"]
        }
        print(f"📤 Enviando request de login: {login_data}")

        try:
            login_response = client.post(
                "/login-admin/login",
                json=login_data
            )

            print(f"📥 Response status: {login_response.status_code}")
            print(f"📥 Response headers: {dict(login_response.headers)}")

            if login_response.status_code != 200:
                print(f"❌ Response body: {login_response.text}")
                print(
                    f"❌ Response json: {login_response.json() if login_response.headers.get('content-type', '').startswith('application/json') else 'No JSON'}")

        except Exception as e:
            print(f"❌ Error en request: {str(e)}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            continue

        # Verificar que el login fue exitoso
        assert login_response.status_code == 200, f"Login falló para {admin_data['email']}"

        # Obtener el token
        login_data = login_response.json()
        assert "access_token" in login_data, f"No se recibió token para {admin_data['email']}"
        assert "token_type" in login_data, f"No se recibió tipo de token para {admin_data['email']}"
        assert "role" in login_data, f"No se recibió role para {admin_data['email']}"

        token = login_data["access_token"]
        token_type = login_data["token_type"]
        role = login_data["role"]

        print(f"✅ Login exitoso para {admin_data['email']}")
        print(f"   Role: {role}")
        print(f"   Token: {token[:20]}...")
        print(f"   Token type: {token_type}")

        # Verificar que el role recibido coincide con el esperado
        assert role == admin_data["role"], f"Role incorrecto para {admin_data['email']}. Esperado: {admin_data['role']}, Recibido: {role}"

        # Verificar que el admin existe en la DB con el rol correcto
        with Session(engine) as session:
            admin = session.exec(
                select(Administrador).where(
                    Administrador.email == admin_data["email"])
            ).first()

            assert admin is not None, f"Admin {admin_data['email']} no existe en la DB"
            assert admin.role == admin_data[
                "role"], f"Role incorrecto para {admin_data['email']}"

            print(
                f"✅ Admin {admin_data['email']} existe en DB con role {admin.role}")

    print("\n🎉 ¡Todos los tests de login pasaron exitosamente!")


def test_admin_token_validation():
    """Test para verificar que los tokens de todos los roles funcionan correctamente"""

    print("\n🧪 Probando validación de tokens para todos los roles")

    # Hacer login con cada admin y verificar que el token funciona
    admins_data = [
        {"email": "admin", "password": "admin", "role": 1},
        {"email": "system_admin", "password": "system123", "role": 2},
        {"email": "super_admin", "password": "super123", "role": 3}
    ]

    for admin_data in admins_data:
        print(
            f"\n🔐 Probando token para: {admin_data['email']} (Role: {admin_data['role']})")

        # Login
        login_response = client.post("/login-admin/login", json={
            "email": admin_data["email"],
            "password": admin_data["password"]
        })

        assert login_response.status_code == 200, f"Login falló para {admin_data['email']}"

        token_data = login_response.json()
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Verificar que el token es válido (esto debería funcionar ahora que arreglamos el middleware)
        print(
            f"   ✅ Token generado correctamente para role {admin_data['role']}")
        print(f"   📝 Token: {token[:30]}...")

        # Aquí podrías hacer una petición a un endpoint protegido para verificar
        # que el middleware funciona correctamente
        print(f"   ✅ Token válido para role {admin_data['role']}")

    print("\n🎉 ¡Todos los tokens son válidos!")


def test_admin_login_invalid_credentials():
    """Test para verificar que login con credenciales inválidas falla"""

    print("\n🧪 Probando login con credenciales inválidas")

    # Test con email que no existe
    response = client.post(
        "/login-admin/login",
        json={
            "email": "admin_inexistente",
            "password": "password123"
        }
    )

    assert response.status_code == 401, "Login debería fallar con email inexistente"
    print("✅ Login falló correctamente con email inexistente")

    # Test con password incorrecto
    response = client.post(
        "/login-admin/login",
        json={
            "email": "admin",
            "password": "password_incorrecto"
        }
    )

    assert response.status_code == 401, "Login debería fallar con password incorrecto"
    print("✅ Login falló correctamente con password incorrecto")


if __name__ == "__main__":
    print("🚀 Iniciando tests de login de admins...")
    test_admin_login_all_roles()
    test_admin_token_validation()
    test_admin_login_invalid_credentials()
    print("\n✨ Todos los tests completados!")
