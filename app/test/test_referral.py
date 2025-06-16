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
    Test que verifica la creación de una cadena de referidos:
    1. Crear usuario padre (quien refiere)
    2. Crear usuario hijo (referido) usando el teléfono del padre
    3. Verificar que se crea la relación de referido
    4. Verificar que se puede consultar la cadena de referidos
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
