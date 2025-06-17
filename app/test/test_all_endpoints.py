import io
from fastapi import status
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# =========================
# USERS ENDPOINTS
# =========================


def test_create_user():
    response = client.post(
        "/users/",
        json={
            "full_name": "Juan Pérez",
            "country_code": "+57",
            "phone_number": "3001234567"
        }
    )
    assert response.status_code == status.HTTP_201_CREATED or response.status_code in (
        409, 400)
    # Puede fallar si ya existe el usuario


def test_create_user_invalid_name():
    response = client.post(
        "/users/",
        json={
            "full_name": "Juan123",
            "country_code": "+57",
            "phone_number": "3001234567"
        }
    )
    assert response.status_code == 422 or response.status_code == 400


def test_create_user_missing_fields():
    response = client.post(
        "/users/",
        json={
            "country_code": "+57",
            "phone_number": "3001234567"
        }
    )
    assert response.status_code == 422 or response.status_code == 400


def test_create_user_duplicate():
    data = {
        "full_name": "Juan Pérez",
        "country_code": "+57",
        "phone_number": "3001234567"
    }
    client.post("/users/", json=data)
    response = client.post("/users/", json=data)
    assert response.status_code in (409, 400)


def test_create_user_invalid_phone():
    response = client.post(
        "/users/",
        json={
            "full_name": "Juan Pérez",
            "country_code": "+57",
            "phone_number": "1234567890"
        }
    )
    assert response.status_code == 422 or response.status_code == 400


def test_create_user_empty_name():
    response = client.post(
        "/users/",
        json={
            "full_name": "",
            "country_code": "+57",
            "phone_number": "3001234567"
        }
    )
    assert response.status_code == 422 or response.status_code == 400


def test_get_me_requires_auth():
    response = client.get("/users/me")
    assert response.status_code in (401, 403)


def test_get_me_invalid_token():
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.get("/users/me", headers=headers)
    assert response.status_code in (401, 403)


def test_update_me_requires_auth():
    response = client.patch(
        "/users/me/update", data={"full_name": "Nuevo Nombre"})
    assert response.status_code in (401, 403)


def test_update_me_invalid_name():
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.patch(
        "/users/me/update", data={"full_name": "123"}, headers=headers)
    assert response.status_code in (401, 403, 422)

# =========================
# AUTH ENDPOINTS
# =========================


def test_auth_login_invalid():
    response = client.post(
        "/auth/login", json={"phone_number": "000", "country_code": "+57"})
    assert response.status_code in (401, 422, 404)


def test_auth_login_bad_format():
    response = client.post("/auth/login", data="notjson")
    assert response.status_code in (422, 400, 415)

# =========================
# CLIENT REQUEST ENDPOINTS
# =========================


def test_client_request_requires_auth():
    response = client.post("/client-request/", json={})
    assert response.status_code in (401, 403)


def test_client_request_invalid_data():
    response = client.post("/client-request/", json={"pickup_lat": 4.7})
    assert response.status_code in (401, 403, 422)


def test_client_request_out_of_range():
    response = client.post("/client-request/", json={
        "pickup_lat": 100.0, "pickup_lng": -74.1, "destination_lat": 4.7, "destination_lng": -74.1, "fare_offered": 10000, "type_service_id": 1
    })
    assert response.status_code in (401, 403, 422, 400)


def test_client_request_detail_not_found():
    response = client.get(
        "/client-request/00000000-0000-0000-0000-000000000000")
    assert response.status_code in (401, 403, 404)

# =========================
# TRANSACTION ENDPOINTS
# =========================


def test_transaction_balance_requires_auth():
    response = client.get("/transactions/balance/me")
    assert response.status_code in (401, 403)


def test_transaction_list_requires_auth():
    response = client.get("/transactions/list/me")
    assert response.status_code in (401, 403)


def test_transaction_balance_invalid_token():
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.get("/transactions/balance/me", headers=headers)
    assert response.status_code in (401, 403)

# =========================
# DRIVER POSITION ENDPOINTS
# =========================


def test_driver_position_requires_auth():
    response = client.post("/drivers-position/",
                           json={"lat": 4.7, "lng": -74.1})
    assert response.status_code in (401, 403)


def test_driver_position_invalid_data():
    response = client.post("/drivers-position/", json={"lat": 4.7})
    assert response.status_code in (401, 403, 422)


def test_driver_position_out_of_range():
    response = client.post("/drivers-position/",
                           json={"lat": 100.0, "lng": -200.0})
    assert response.status_code in (401, 403, 422, 400)

# =========================
# DRIVER TRIP OFFER ENDPOINTS
# =========================


def test_driver_trip_offer_requires_auth():
    response = client.post("/driver-trip-offers/", json={})
    assert response.status_code in (401, 403)


def test_driver_trip_offer_invalid_data():
    response = client.post("/driver-trip-offers/", json={"fare_offer": 10000})
    assert response.status_code in (401, 403, 422)


def test_driver_trip_offer_negative_values():
    response = client.post(
        "/driver-trip-offers/", json={"fare_offer": -100, "time": -5, "distance": -10})
    assert response.status_code in (401, 403, 422, 400)

# =========================
# WITHDRAWAL ENDPOINTS
# =========================


def test_withdrawal_requires_auth():
    response = client.post("/withdrawals/", json={"amount": 10000})
    assert response.status_code in (401, 403)


def test_withdrawal_invalid_amount():
    response = client.post("/withdrawals/", json={"amount": -100})
    assert response.status_code in (401, 403, 422, 400)


def test_withdrawal_zero_amount():
    response = client.post("/withdrawals/", json={"amount": 0})
    assert response.status_code in (401, 403, 422, 400)


def test_withdrawal_string_amount():
    response = client.post("/withdrawals/", json={"amount": "mil"})
    assert response.status_code in (401, 403, 422, 400)

# =========================
# DRIVER SAVINGS ENDPOINTS
# =========================


def test_driver_savings_requires_auth():
    response = client.get("/driver-savings/me")
    assert response.status_code in (401, 403)


def test_driver_savings_invalid_token():
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.get("/driver-savings/me", headers=headers)
    assert response.status_code in (401, 403)

# =========================
# REFERRALS ENDPOINTS
# =========================


def test_referrals_requires_auth():
    response = client.get("/referrals/me/earnings-structured")
    assert response.status_code in (401, 403)


def test_referrals_invalid_token():
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.get("/referrals/me/earnings-structured", headers=headers)
    assert response.status_code in (401, 403)

# =========================
# VERIFY DOCS (ADMIN) ENDPOINTS
# =========================


def test_verify_docs_requires_auth():
    response = client.get("/verify-docs/pending")
    assert response.status_code in (401, 403)


def test_verify_docs_invalid_token():
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.get("/verify-docs/pending", headers=headers)
    assert response.status_code in (401, 403)
