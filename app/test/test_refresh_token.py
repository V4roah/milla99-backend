from fastapi import status
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_refresh_token_flow():
    # 1. Crear usuario y verificar
    user_data = {
        "full_name": "Refresh Token User",
        "country_code": "+57",
        "phone_number": "3019999999"
    }
    resp = client.post("/users/", json=user_data)
    assert resp.status_code == 201
    send_resp = client.post(f"/auth/verify/+57/3019999999/send")
    assert send_resp.status_code == 201
    code = send_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/+57/3019999999/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # 2. Acceso con access token
    headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = client.get("/users/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["phone_number"] == "3019999999"

    # 3. Renovar access token con refresh token
    refresh_resp = client.post(
        "/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    assert "access_token" in refresh_data
    assert "refresh_token" in refresh_data
    new_access_token = refresh_data["access_token"]
    new_refresh_token = refresh_data["refresh_token"]
    assert new_access_token != access_token  # Debe ser diferente
    assert new_refresh_token != refresh_token  # Si hay rotación

    # 4. Revocar refresh token
    logout_resp = client.post(
        "/auth/logout", json={"refresh_token": new_refresh_token})
    assert logout_resp.status_code == 200
    assert "revoked" in logout_resp.json()["message"].lower()

    # 5. Intentar renovar con refresh token revocado
    refresh_fail = client.post(
        "/auth/refresh", json={"refresh_token": new_refresh_token})
    assert refresh_fail.status_code == 401 or refresh_fail.status_code == 400

    # 6. Revocar todos los tokens
    # Primero, hacer login de nuevo para obtener tokens válidos
    send_resp2 = client.post(f"/auth/verify/+57/3019999999/send")
    code2 = send_resp2.json()["message"].split()[-1]
    verify_resp2 = client.post(
        f"/auth/verify/+57/3019999999/code",
        json={"code": code2}
    )
    access_token2 = verify_resp2.json()["access_token"]
    refresh_token2 = verify_resp2.json()["refresh_token"]
    headers2 = {"Authorization": f"Bearer {access_token2}"}
    logout_all = client.post("/auth/logout-all", headers=headers2)
    assert logout_all.status_code == 200
    assert "revoked" in logout_all.json()["message"].lower()

    # 7. Intentar renovar con cualquier refresh token después de logout-all
    refresh_fail2 = client.post(
        "/auth/refresh", json={"refresh_token": refresh_token2})
    assert refresh_fail2.status_code == 401 or refresh_fail2.status_code == 400
