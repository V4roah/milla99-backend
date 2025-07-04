import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import engine
from sqlmodel import Session, select
from app.models.user import User
from app.models.administrador import AdminRole

client = TestClient(app)


def test_send_verification_code():
    country_code = "+57"
    phone_number = "3004442444"
    response = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert response.status_code == 201
    data = response.json()
    assert "message" in data
    assert "Verification code sent successfully" in data["message"]


def test_verify_code():
    country_code = "+57"
    phone_number = "3004442444"

    # Enviar el código de verificación
    response = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert response.status_code == 201
    msg = response.json()["message"]
    code = msg.split()[-1]  # Extrae el código del mensaje

    # Verificar el código
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["phone_number"] == phone_number


def test_verify_code_incorrect():
    country_code = "+57"
    phone_number = "3004442444"  # Usuario existente
    # Enviar el código de verificación (opcional, solo para simular el flujo)
    response = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert response.status_code == 201
    # Usar un código incorrecto
    wrong_code = "000000"
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": wrong_code}
    )
    assert verify_resp.status_code in (400, 401, 404)


def test_access_with_invalid_token():
    # Intentar acceder a un endpoint protegido con un token inválido
    headers = {"Authorization": "Bearer invalidtoken123"}
    response = client.get("/users/me", headers=headers)
    assert response.status_code in (401, 403)


def test_admin_login_success():
    data = {"email": "admin", "password": "admin"}
    response = client.post("/login-admin/login", json=data)
    assert response.status_code == 200
    resp_json = response.json()
    assert "access_token" in resp_json
    assert resp_json["token_type"] == "bearer"
    # O el valor que corresponda a admin
    assert resp_json["role"] == AdminRole.BASIC.value


def test_admin_login_fail():
    data = {"email": "client", "password": "client"}
    response = client.post("/login-admin/login", json=data)
    assert response.status_code == 401 or response.status_code == 404
    resp_json = response.json()
    assert "access_token" not in resp_json


def test_access_with_other_user_token():
    # Crear usuario 1
    country_code = "+57"
    phone_number_1 = "3011234570"
    user_data_1 = {
        "full_name": "User One",
        "country_code": country_code,
        "phone_number": phone_number_1
    }
    response = client.post("/users/", json=user_data_1)
    assert response.status_code == 201
    # Enviar y verificar código para usuario 1
    send_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number_1}/send")
    assert send_resp.status_code == 201
    code_1 = send_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number_1}/code",
        json={"code": code_1}
    )
    assert verify_resp.status_code == 200
    token_1 = verify_resp.json()["access_token"]
    headers_1 = {"Authorization": f"Bearer {token_1}"}

    # Crear usuario 2
    phone_number_2 = "3011234571"
    user_data_2 = {
        "full_name": "User Two",
        "country_code": country_code,
        "phone_number": phone_number_2
    }
    response = client.post("/users/", json=user_data_2)
    assert response.status_code == 201
    # Enviar y verificar código para usuario 2 (solo para que exista)
    send_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number_2}/send")
    assert send_resp.status_code == 201

    # Intentar acceder a los datos protegidos de usuario 2 con el token de usuario 1
    # (por ejemplo, /users/me debería devolver los datos del usuario autenticado, pero si hay endpoints tipo /users/{id}, prueba con ese)
    # Aquí simulamos que el endpoint requiere ser owner
    with Session(engine) as session:
        user2 = session.exec(select(User).where(
            User.phone_number == phone_number_2)).first()
        user2_id = str(user2.id)

    # Intentar acceder a /users/{user2_id} con el token de user1
    resp = client.get(f"/users/{user2_id}", headers=headers_1)
    assert resp.status_code in (403, 404)
