from fastapi.testclient import TestClient
from app.main import app
from app.models.referral_chain import Referral
from app.models.user import User
from sqlmodel import Session, select
from app.core.db import engine
from uuid import UUID
import traceback
import json

client = TestClient(app)


def test_referral_chain_creation():
    """
    Propósito:
        Verificar la creación de una cadena de referidos (nivel 1) y la consulta de la estructura de referidos.

    Flujo:
        1. Crear usuario padre (quien refiere).
        2. Autenticar usuario padre y obtener token.
        3. Crear usuario hijo (referido) usando el teléfono del padre.
        4. Verificar que se crea la relación de referido en la base de datos.
        5. Consultar /referrals/me/earnings-structured con el token del padre.
        6. Verificar que el hijo aparece en el nivel 1 de referidos.
    """
    print("\n=== INICIANDO TEST DE CREACIÓN DE CADENA DE REFERIDOS ===")

    try:
        # 1. Crear usuario padre (quien refiere)
        print("\n1. Creando usuario padre")
        parent_data = {
            "full_name": "Usuario Padre",
            "country_code": "+57",
            "phone_number": "3011111121"  # Nuevo número para evitar conflictos
        }
        parent_resp = client.post("/users/", json=parent_data)
        print(
            f"Respuesta creación padre: {parent_resp.status_code} - {parent_resp.text}")
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]
        print(f"Usuario padre creado con ID: {parent_id}")

        # Autenticar usuario padre
        send_parent_resp = client.post(
            f"/auth/verify/{parent_data['country_code']}/{parent_data['phone_number']}/send")
        print(
            f"Respuesta envío código padre: {send_parent_resp.status_code} - {send_parent_resp.text}")
        assert send_parent_resp.status_code == 201
        parent_code = send_parent_resp.json()["message"].split()[-1]

        verify_parent_resp = client.post(
            f"/auth/verify/{parent_data['country_code']}/{parent_data['phone_number']}/code",
            json={"code": parent_code}
        )
        print(
            f"Respuesta verificación código padre: {verify_parent_resp.status_code} - {verify_parent_resp.text}")
        assert verify_parent_resp.status_code == 200
        parent_token = verify_parent_resp.json()["access_token"]
        parent_headers = {"Authorization": f"Bearer {parent_token}"}

        # 2. Crear usuario hijo (referido) usando el teléfono del padre
        print("\n2. Creando usuario hijo (referido)")
        child_data = {
            "full_name": "Usuario Hijo",
            "country_code": "+57",
            "phone_number": "3011111122",  # Nuevo número para evitar conflictos
            "referral_phone": parent_data["phone_number"]  # Teléfono del padre
        }
        child_resp = client.post("/users/", json=child_data)
        print(
            f"Respuesta creación hijo: {child_resp.status_code} - {child_resp.text}")
        assert child_resp.status_code == 201
        child_id = child_resp.json()["id"]
        print(f"Usuario hijo creado con ID: {child_id}")

        # 3. Verificar que se creó la relación de referido
        print("\n3. Verificando relación de referido")
        with Session(engine) as session:
            # Buscar la relación de referido
            referral = session.exec(
                select(Referral).where(
                    Referral.user_id == UUID(child_id),
                    Referral.referred_by_id == UUID(parent_id)
                )
            ).first()

            print(f"Relación encontrada: {referral}")
            assert referral is not None, "No se encontró la relación de referido"
            print(f"Relación de referido creada: {referral.id}")

            # Verificar que el usuario hijo tiene el referido correcto
            child_user = session.exec(
                select(User).where(User.id == UUID(child_id))
            ).first()
            print(f"Usuario hijo encontrado: {child_user}")
            assert child_user is not None, "No se encontró el usuario hijo"

            # Verificar que el usuario padre existe
            parent_user = session.exec(
                select(User).where(User.id == UUID(parent_id))
            ).first()
            print(f"Usuario padre encontrado: {parent_user}")
            assert parent_user is not None, "No se encontró el usuario padre"

        # 4. Verificar que se puede consultar la cadena de referidos
        print("\n4. Verificando consulta de cadena de referidos")
        # Consultar referidos del padre
        parent_referrals_resp = client.get(
            "/referrals/me/earnings-structured",
            headers=parent_headers
        )
        print(
            f"Respuesta consulta referidos: {parent_referrals_resp.status_code}")
        print(
            f"Contenido de la respuesta: {json.dumps(parent_referrals_resp.json(), indent=2)}")
        assert parent_referrals_resp.status_code == 200
        parent_referrals = parent_referrals_resp.json()

        # Verificar la estructura de la respuesta
        assert "user_id" in parent_referrals, "La respuesta no contiene el ID del usuario"
        assert "full_name" in parent_referrals, "La respuesta no contiene el nombre del usuario"
        assert "phone_number" in parent_referrals, "La respuesta no contiene el teléfono del usuario"
        assert "levels" in parent_referrals, "La respuesta no contiene los niveles de referidos"

        # Verificar que el usuario padre tiene el nivel 1 con el hijo como referido
        assert len(parent_referrals["levels"]
                   ) > 0, "El usuario no tiene niveles de referidos"
        level_1 = next(
            (level for level in parent_referrals["levels"] if level["level"] == 1), None)
        assert level_1 is not None, "No se encontró el nivel 1 de referidos"
        assert level_1[
            "percentage"] == 2.0, f"El porcentaje del nivel 1 no es 2.0% (es {level_1['percentage']}%)"

        # Verificar que el hijo está en el nivel 1
        assert len(level_1["users"]
                   ) > 0, "El nivel 1 no tiene usuarios referidos"
        assert any(
            user["id"] == child_id
            for user in level_1["users"]
        ), f"El hijo {child_id} no aparece en el nivel 1. Usuarios encontrados: {[user['id'] for user in level_1['users']]}"

        print("\n=== TEST DE CREACIÓN DE CADENA DE REFERIDOS COMPLETADO EXITOSAMENTE ===")

    except Exception as e:
        print("\n=== ERROR EN EL TEST ===")
        print(f"Tipo de error: {type(e).__name__}")
        print(f"Mensaje de error: {str(e)}")
        print("\nTraceback completo:")
        print(traceback.format_exc())
        raise


def test_create_level1_referral():
    """
    Propósito:
        Verificar la creación de un referido de nivel 1 y la consulta de la estructura de referidos.

    Flujo:
        1. Crear usuario padre.
        2. Autenticar usuario padre y obtener token.
        3. Crear usuario hijo con referral_phone del padre.
        4. Verificar en la base de datos la relación Referral.
        5. Consultar /referrals/me/earnings-structured con el token del padre.
        6. Verificar que el hijo aparece en el nivel 1 de referidos.
    """
    # 1. Crear usuario padre
    parent_data = {
        "full_name": "Referral Parent",
        "country_code": "+57",
        "phone_number": "3012222233"
    }
    parent_resp = client.post("/users/", json=parent_data)
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["id"]

    # 2. Autenticar usuario padre y obtener token
    send_code_resp = client.post(
        f"/auth/verify/{parent_data['country_code']}/{parent_data['phone_number']}/send")
    assert send_code_resp.status_code == 201
    code = send_code_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/{parent_data['country_code']}/{parent_data['phone_number']}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    parent_token = verify_resp.json()["access_token"]
    parent_headers = {"Authorization": f"Bearer {parent_token}"}

    # 3. Crear usuario hijo con referral_phone del padre
    child_data = {
        "full_name": "Referral Child",
        "country_code": "+57",
        "phone_number": "3012222234",
        "referral_phone": parent_data["phone_number"]
    }
    child_resp = client.post("/users/", json=child_data)
    assert child_resp.status_code == 201
    child_id = child_resp.json()["id"]

    # 4. Verificar en la base de datos la relación Referral
    with Session(engine) as session:
        referral = session.exec(
            select(Referral).where(
                Referral.user_id == UUID(child_id),
                Referral.referred_by_id == UUID(parent_id)
            )
        ).first()
        assert referral is not None, "Referral relationship not found"

    # 5. Consultar la estructura de referidos del padre
    resp = client.get("/referrals/me/earnings-structured",
                      headers=parent_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Verificar que el hijo aparece en el nivel 1
    level_1 = next(
        (level for level in data["levels"] if level["level"] == 1), None)
    assert level_1 is not None, "Level 1 of referrals not found"
    assert any(user["id"] == child_id for user in level_1["users"]
               ), "Child does not appear in level 1 referrals"


def test_user_without_referrals():
    """
    Propósito:
        Verificar que el endpoint de referidos responde correctamente cuando el usuario no tiene referidos.

    Flujo:
        1. Crear un usuario sin referidos.
        2. Autenticar el usuario y obtener su token.
        3. Consultar /referrals/me/earnings-structured.
        4. Verificar que la respuesta contiene el mensaje: "El usuario no tiene referidos."
    """
    # 1. Crear un usuario sin referidos
    user_data = {
        "full_name": "No Referral User",
        "country_code": "+57",
        "phone_number": "3013333344"
    }
    user_resp = client.post("/users/", json=user_data)
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    # 2. Autenticar usuario y obtener token
    send_code_resp = client.post(
        f"/auth/verify/{user_data['country_code']}/{user_data['phone_number']}/send")
    assert send_code_resp.status_code == 201
    code = send_code_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/{user_data['country_code']}/{user_data['phone_number']}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    user_token = verify_resp.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 3. Consultar la estructura de referidos del usuario
    resp = client.get("/referrals/me/earnings-structured",
                      headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Verificar que la respuesta contiene el mensaje esperado
    assert "message" in data, "No se encontró el campo 'message' en la respuesta"
    assert data[
        "message"] == "El usuario no tiene referidos.", f"Mensaje inesperado: {data['message']}"


def test_referral_chain_multiple_levels():
    """
    Propósito:
        Verificar la creación de una cadena de referidos de varios niveles y la correcta estructura de niveles.

    Flujo:
        1. Crear usuario A (padre).
        2. Autenticar usuario A y obtener token.
        3. Crear usuario B con A como referido.
        4. Crear usuario C con B como referido.
        5. Crear usuario D con C como referido.
        6. Consultar /referrals/me/earnings-structured con el token de A.
        7. Verificar que B está en nivel 1, C en nivel 2, D en nivel 3.
    """
    # 1. Crear usuario A (padre)
    user_a = {
        "full_name": "Usuario A",
        "country_code": "+57",
        "phone_number": "3013333341"
    }
    resp_a = client.post("/users/", json=user_a)
    assert resp_a.status_code == 201
    user_a_id = resp_a.json()["id"]

    # 2. Autenticar usuario A y obtener token
    send_code_a = client.post(
        f"/auth/verify/{user_a['country_code']}/{user_a['phone_number']}/send")
    assert send_code_a.status_code == 201
    code_a = send_code_a.json()["message"].split()[-1]
    verify_a = client.post(
        f"/auth/verify/{user_a['country_code']}/{user_a['phone_number']}/code",
        json={"code": code_a}
    )
    assert verify_a.status_code == 200
    token_a = verify_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 3. Crear usuario B con A como referido
    user_b = {
        "full_name": "Usuario B",
        "country_code": "+57",
        "phone_number": "3013333342",
        "referral_phone": user_a["phone_number"]
    }
    resp_b = client.post("/users/", json=user_b)
    assert resp_b.status_code == 201
    user_b_id = resp_b.json()["id"]

    # 4. Crear usuario C con B como referido
    user_c = {
        "full_name": "Usuario C",
        "country_code": "+57",
        "phone_number": "3013333343",
        "referral_phone": user_b["phone_number"]
    }
    resp_c = client.post("/users/", json=user_c)
    assert resp_c.status_code == 201
    user_c_id = resp_c.json()["id"]

    # 5. Crear usuario D con C como referido
    user_d = {
        "full_name": "Usuario D",
        "country_code": "+57",
        "phone_number": "3013333344",
        "referral_phone": user_c["phone_number"]
    }
    resp_d = client.post("/users/", json=user_d)
    assert resp_d.status_code == 201
    user_d_id = resp_d.json()["id"]

    # 6. Consultar la estructura de referidos de A
    resp_structure = client.get(
        "/referrals/me/earnings-structured", headers=headers_a)
    assert resp_structure.status_code == 200
    data = resp_structure.json()
    assert "levels" in data

    # 7. Verificar que B está en nivel 1, C en nivel 2, D en nivel 3
    level_1 = next((lvl for lvl in data["levels"] if lvl["level"] == 1), None)
    level_2 = next((lvl for lvl in data["levels"] if lvl["level"] == 2), None)
    level_3 = next((lvl for lvl in data["levels"] if lvl["level"] == 3), None)
    assert level_1 is not None, "No se encontró el nivel 1"
    assert level_2 is not None, "No se encontró el nivel 2"
    assert level_3 is not None, "No se encontró el nivel 3"

    assert any(u["id"] == user_b_id for u in level_1["users"]
               ), f"Usuario B no está en nivel 1: {level_1['users']}"
    assert any(u["id"] == user_c_id for u in level_2["users"]
               ), f"Usuario C no está en nivel 2: {level_2['users']}"
    assert any(u["id"] == user_d_id for u in level_3["users"]
               ), f"Usuario D no está en nivel 3: {level_3['users']}"


def test_referral_percentages_verification():
    """
    Propósito:
        Verificar que los porcentajes por nivel en /referrals/me/earnings-structured coinciden con la configuración de project_settings.

    Flujo:
        1. Crear usuario padre.
        2. Autenticar usuario padre y obtener token.
        3. Crear usuarios en diferentes niveles (hasta nivel 5).
        4. Consultar /referrals/me/earnings-structured.
        5. Verificar que los porcentajes coinciden con la configuración:
           - Nivel 1: 2.0%
           - Nivel 2: 1.25%
           - Nivel 3: 0.75%
           - Nivel 4: 0.5%
           - Nivel 5: 0.5%
    """
    # 1. Crear usuario padre
    parent_data = {
        "full_name": "Usuario Padre Porcentajes",
        "country_code": "+57",
        "phone_number": "3015555561"  # Número único
    }
    parent_resp = client.post("/users/", json=parent_data)
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["id"]

    # 2. Autenticar usuario padre y obtener token
    send_code_resp = client.post(
        f"/auth/verify/{parent_data['country_code']}/{parent_data['phone_number']}/send")
    assert send_code_resp.status_code == 201
    code = send_code_resp.json()["message"].split()[-1]
    verify_resp = client.post(
        f"/auth/verify/{parent_data['country_code']}/{parent_data['phone_number']}/code",
        json={"code": code}
    )
    assert verify_resp.status_code == 200
    parent_token = verify_resp.json()["access_token"]
    parent_headers = {"Authorization": f"Bearer {parent_token}"}

    # 3. Crear usuarios en diferentes niveles (hasta nivel 5)
    users = []
    current_phone = parent_data["phone_number"]

    for i in range(5):
        user_data = {
            # A, B, C, D, E en lugar de 1, 2, 3, 4, 5
            "full_name": f"Usuario Nivel {chr(65 + i)}",
            "country_code": "+57",
            "phone_number": f"301555556{i+2}",  # Números únicos
            "referral_phone": current_phone
        }
        user_resp = client.post("/users/", json=user_data)
        assert user_resp.status_code == 201
        user_id = user_resp.json()["id"]
        users.append({"id": user_id, "phone": user_data["phone_number"]})
        current_phone = user_data["phone_number"]

    # 4. Consultar estructura de referidos
    structure_resp = client.get(
        "/referrals/me/earnings-structured", headers=parent_headers)
    assert structure_resp.status_code == 200
    data = structure_resp.json()
    assert "levels" in data

    # 5. Verificar que los porcentajes coinciden con la configuración
    expected_percentages = {
        1: 2.0,    # referral_1: "0.02" -> 2.0%
        2: 1.25,   # referral_2: "0.0125" -> 1.25%
        3: 0.75,   # referral_3: "0.0075" -> 0.75%
        4: 0.5,    # referral_4: "0.005" -> 0.5%
        5: 0.5     # referral_5: "0.005" -> 0.5%
    }

    for level_data in data["levels"]:
        level = level_data["level"]
        percentage = level_data["percentage"]
        expected = expected_percentages.get(level)

        assert expected is not None, f"Nivel {level} no está en la configuración esperada"
        assert percentage == expected, f"Porcentaje del nivel {level} es {percentage}%, se esperaba {expected}%"

        # Verificar que hay usuarios en este nivel
        assert len(level_data["users"]
                   ) > 0, f"El nivel {level} no tiene usuarios"

    # Verificar que se crearon todos los niveles esperados
    created_levels = [level["level"] for level in data["levels"]]
    expected_levels = list(expected_percentages.keys())
    assert created_levels == expected_levels, f"Niveles creados: {created_levels}, esperados: {expected_levels}"
