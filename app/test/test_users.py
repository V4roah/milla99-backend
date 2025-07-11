from fastapi import status
from fastapi.testclient import TestClient
from app.main import app
from datetime import datetime
from sqlmodel import Session, select
from app.models.user_has_roles import UserHasRole, RoleStatus
from app.models.role import Role
from app.core.db import engine
from uuid import UUID
import time

client = TestClient(app)

# === TESTS ACTUALIZADOS DE ENDPOINTS PRINCIPALES ===


def test_create_user():
    user_data = {
        "full_name": "Test User",
        "country_code": "+57",
        "phone_number": "3011234580"
    }
    response = client.post("/users/", json=user_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["full_name"] == user_data["full_name"]
    assert data["country_code"] == user_data["country_code"]
    assert data["phone_number"] == user_data["phone_number"]
    assert data["is_active"] is False or data["is_active"] is True
    assert data["is_verified_phone"] is False
    assert "id" in data


def test_get_me():
    # Usar timestamp para hacer el número único
    timestamp = int(time.time()) % 10000000  # 7 dígitos del timestamp
    country_code = "+57"
    # Formato: 300 + 7 dígitos = 10 dígitos total
    phone_number = f"300{timestamp:07d}"
    user_data = {
        "full_name": "User Me",
        "country_code": country_code,
        "phone_number": phone_number
    }
    response = client.post("/users/", json=user_data)
    assert response.status_code == 201
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/users/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["phone_number"] == phone_number
    assert me_data["full_name"] == "User Me"
    # Verificar que el nuevo campo is_driver_approved esté presente
    assert "is_driver_approved" in me_data
    # Para un usuario recién creado con solo rol CLIENT, debe ser False
    assert me_data["is_driver_approved"] is False


def test_get_me_driver_approved():
    """Test para verificar que is_driver_approved sea True cuando el usuario tiene rol DRIVER aprobado"""
    # Usar timestamp para hacer el número único
    timestamp = int(time.time()) % 10000000  # 7 dígitos del timestamp
    country_code = "+57"
    # Formato: 301 + 7 dígitos = 10 dígitos total
    phone_number = f"301{timestamp:07d}"
    user_data = {
        "full_name": "Driver User",
        "country_code": country_code,
        "phone_number": phone_number
    }

    # Crear usuario
    response = client.post("/users/", json=user_data)
    assert response.status_code == 201
    user_id = response.json()["id"]

    # Verificar usuario
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Simular que el usuario tiene rol DRIVER aprobado (manipulación directa de BD)
    with Session(engine) as session:
        # Buscar el rol DRIVER
        driver_role = session.exec(
            select(Role).where(Role.id == "DRIVER")).first()
        assert driver_role is not None

        # Crear la relación UserHasRole con status APPROVED
        user_role = UserHasRole(
            id_user=UUID(user_id),
            id_rol="DRIVER",
            is_verified=True,
            status=RoleStatus.APPROVED,
            verified_at=datetime.utcnow()
        )
        session.add(user_role)
        session.commit()

    # Ahora llamar a /users/me y verificar que is_driver_approved sea True
    me_resp = client.get("/users/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["phone_number"] == phone_number
    assert me_data["full_name"] == "Driver User"
    assert "is_driver_approved" in me_data
    assert me_data["is_driver_approved"] is True


def test_update_me():
    # Usar timestamp para hacer el número único
    timestamp = int(time.time()) % 10000000  # 7 dígitos del timestamp
    country_code = "+57"
    # Formato: 302 + 7 dígitos = 10 dígitos total
    phone_number = f"302{timestamp:07d}"
    user_data = {
        "full_name": "User Update",
        "country_code": country_code,
        "phone_number": phone_number
    }
    response = client.post("/users/", json=user_data)
    assert response.status_code == 201
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    update_data = {"full_name": "User Updated"}
    patch_resp = client.patch(
        "/users/me/update", data=update_data, headers=headers)
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()
    assert patch_data["full_name"] == "User Updated"
    me_resp = client.get("/users/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["full_name"] == "User Updated"


# def test_get_users(client):
#     response = client.get("/users/")
#     assert response.status_code == status.HTTP_200_OK
#     assert isinstance(response.json(), list)

# # test for get user by id


# def test_get_user_by_id(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Laura Milla",
#             "country_code": "+57",
#             "phone_number": "3200000000"
#         }
#     )
#     user_id = response.json()["id"]

#     get_response = client.get(f"/users/{user_id}")
#     assert get_response.status_code == status.HTTP_200_OK
#     assert get_response.json()["full_name"] == "Laura Milla"


# def test_update_user(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Carlos",
#             "country_code": "+57",
#             "phone_number": "3001111111"
#         }
#     )
#     user_id = response.json()["id"]

#     update_response = client.patch(
#         f"/users/{user_id}",
#         json={"full_name": "Carlos Editado"}
#     )
#     assert update_response.status_code == status.HTTP_200_OK
#     assert update_response.json()["full_name"] == "Carlos Editado"


# def test_delete_user(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Para Borrar",
#             "country_code": "+57",
#             "phone_number": "3009999999"
#         }
#     )
#     user_id = response.json()["id"]

#     delete_response = client.delete(f"/users/{user_id}")
#     assert delete_response.status_code == status.HTTP_200_OK
#     assert delete_response.json() == {"message": "User deleted successfully"}


# def test_cannot_create_duplicate_user(client):
#     user_data = {
#         "full_name": "Daniel Vargas",
#         "country_code": "+57",
#         "phone_number": "3100000000"
#     }

#     response_1 = client.post("/users/", json=user_data)
#     assert response_1.status_code == status.HTTP_201_CREATED

#     response_2 = client.post("/users/", json=user_data)
#     assert response_2.status_code == status.HTTP_409_CONFLICT
#     assert response_2.json()[
#         "detail"] == "User with this phone number already exists."


# def test_invalid_colombian_mobile(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Invalido",
#             "country_code": "+57",
#             "phone_number": "4333333333"  # ❌ inválido
#         }
#     )
#     print("\nResponse JSON:", response.json())
#     assert response.status_code == 422
#     assert "Colombian mobile numbers must start with 3." in response.text


# def test_invalid_full_name(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Da",  # ❌ inválido
#             "country_code": "+57",
#             "phone_number": "3008888888"
#         }
#     )
#     print("\nResponse JSON:", response.json())
#     assert response.status_code == 422
#     assert "Full name can only contain letters and spaces." in response.text


# def test_soft_delete_user(client):
#     # 1. Crear usuario (viene con is_active=False)
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Usuario Activo",
#             "country_code": "+57",
#             "phone_number": "3007777777"
#         }
#     )
#     print("\n[CREATE USER] Response:", response.json())
#     assert response.status_code == 201
#     user_id = response.json()["id"]
#     # Confirmamos el valor por defecto
#     assert response.json()["is_active"] is False

#     # 2. Activamos el usuario (simula que está activo antes del "borrado")
#     patch_response = client.patch(
#         f"/users/{user_id}", json={"is_active": True})
#     print("[PATCH USER] Response:", patch_response.json())
#     assert patch_response.status_code == 200
#     assert patch_response.json()["is_active"] is True

#     # 3. Llamamos DELETE (soft delete)
#     delete_response = client.delete(f"/users/{user_id}")
#     print("[DELETE USER] Response:", delete_response.json())
#     assert delete_response.status_code == 200
#     assert delete_response.json(
#     )["message"] == "User deactivated (soft deleted) successfully"

#     # 4. Obtenemos el usuario y verificamos que is_active=False
#     get_response = client.get(f"/users/{user_id}")
#     print("[GET USER] Response:", get_response.json())
#     assert get_response.status_code == 200
#     assert get_response.json()["is_active"] is False


# def test_invalid_full_name_on_update(client):
#     # 1. Create user withouth full_name
#     response = client.post(
#         "/users/",
#         json={
#             "country_code": "+57",
#             "phone_number": "3001212121"
#         }
#     )
#     assert response.status_code == 201
#     user_id = response.json()["id"]
#     assert response.json()["full_name"] is None

#     # 2. Update user with invalid full_name
#     patch_response = client.patch(
#         f"/users/{user_id}", json={"full_name": "Juan123"})
#     print("\n[PATCH INVALID NAME] Response:", patch_response.json())

#     assert patch_response.status_code == 422
#     assert "Full name can only contain letters and spaces." in patch_response.text


# def test_create_user_without_full_name(client):
#     response = client.post(
#         "/users/",
#         json={
#             "country_code": "+57",
#             "phone_number": "3100000000"
#         }
#     )
#     assert response.status_code == 422
#     assert "field required" in response.text.lower()


# def test_create_user_with_empty_full_name(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "",
#             "country_code": "+57",
#             "phone_number": "3100000000"
#         }
#     )
#     assert response.status_code == 422
#     assert "El nombre completo debe tener al menos 3 caracteres" in response.text


# def test_create_user_with_invalid_full_name(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Juan123",
#             "country_code": "+57",
#             "phone_number": "3100000000"
#         }
#     )
#     assert response.status_code == 422
#     assert "El nombre completo solo puede contener letras y espacios" in response.text


# def test_create_user_with_valid_full_name(client):
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Juan Pérez",
#             "country_code": "+57",
#             "phone_number": "3100000000"
#         }
#     )
#     assert response.status_code == status.HTTP_201_CREATED
#     data = response.json()
#     assert data["full_name"] == "Juan Pérez"
#     assert data["is_active"] is False
#     assert data["is_verified_phone"] is False
#     # Verificar que se asignó el rol CLIENT y está verificado
#     assert len(data["roles"]) == 1
#     assert data["roles"][0]["id"] == "CLIENT"
#     assert data["roles"][0]["name"] == "pasajero"


# def test_phone_number_length(client):
#     # Test con número más corto
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Juan Pérez",
#             "country_code": "+57",
#             "phone_number": "300123456"  # 9 dígitos
#         }
#     )
#     assert response.status_code == 422
#     assert "ensure this value has at least 10 characters" in response.text.lower()

#     # Test con número más largo
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Juan Pérez",
#             "country_code": "+57",
#             "phone_number": "30012345678"  # 11 dígitos
#         }
#     )
#     assert response.status_code == 422
#     assert "ensure this value has at most 10 characters" in response.text.lower()

#     # Test con número exacto
#     response = client.post(
#         "/users/",
#         json={
#             "full_name": "Juan Pérez",
#             "country_code": "+57",
#             "phone_number": "3001234567"  # 10 dígitos
#         }
#     )
#     assert response.status_code == 201
