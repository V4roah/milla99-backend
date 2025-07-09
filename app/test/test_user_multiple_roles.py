import pytest
import json
import io
from datetime import date
from uuid import UUID
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.core.db import engine
from app.models.user import User
from app.models.user_has_roles import UserHasRole, RoleStatus

client = TestClient(app)


def test_user_has_role_table_records():
    """
    Test que verifica que cuando se crea un usuario como CLIENT y luego como DRIVER,
    en la tabla user_has_role se crean DOS registros separados para el mismo usuario:
    - Un registro con rol CLIENT
    - Un registro con rol DRIVER
    """

    # Número de teléfono único que no está en init_data
    phone_number = "3004444461"
    country_code = "+57"
    full_name = "Usuario Test Roles"

    print(f"\n=== TEST: Verificar registros en tabla user_has_role ===")
    print(f"📱 Teléfono: {phone_number}")

    # PASO 1: Crear usuario como CLIENT
    print("\n1️⃣ Creando usuario como CLIENT...")
    user_data = {
        "full_name": full_name,
        "country_code": country_code,
        "phone_number": phone_number
    }

    create_user_response = client.post("/users/", json=user_data)
    assert create_user_response.status_code == 201, f"Error creando usuario: {create_user_response.text}"

    user_id_str = create_user_response.json()["id"]
    user_id = UUID(user_id_str)  # Convertir string a UUID
    print(f"✅ Usuario creado con ID: {user_id}")

    # Verificar que existe UN registro en user_has_role con rol CLIENT
    with Session(engine) as session:
        client_role_record = session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user_id,
                UserHasRole.id_rol == "CLIENT"
            )
        ).first()

        assert client_role_record is not None, "No existe registro CLIENT en user_has_role"
        assert client_role_record.status == RoleStatus.APPROVED, "Rol CLIENT no está aprobado"
        print(f"✅ Registro CLIENT creado en user_has_role")
        print(f"   - ID Usuario: {client_role_record.id_user}")
        print(f"   - Rol: {client_role_record.id_rol}")
        print(f"   - Status: {client_role_record.status}")

        # Verificar que NO existe registro DRIVER aún
        driver_role_record = session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user_id,
                UserHasRole.id_rol == "DRIVER"
            )
        ).first()

        assert driver_role_record is None, "Ya existe registro DRIVER cuando no debería"
        print(f"✅ No existe registro DRIVER (correcto)")

        # Verificar que hay exactamente 1 registro
        all_records = session.exec(
            select(UserHasRole).where(UserHasRole.id_user == user_id)
        ).all()

        assert len(
            all_records) == 1, f"Debe haber exactamente 1 registro, hay {len(all_records)}"
        print(f"✅ Total registros en user_has_role: {len(all_records)}")

    # PASO 2: Registrar el mismo usuario como DRIVER
    print("\n2️⃣ Registrando el mismo usuario como DRIVER...")

    driver_info_data = {
        "first_name": "Usuario",
        "last_name": "Test",
        "birth_date": str(date(1990, 1, 1)),
        "email": f"usuario.test.{phone_number}@example.com"
    }

    vehicle_info_data = {
        "brand": "Toyota",
        "model": "Corolla",
        "model_year": 2020,
        "color": "Blanco",
        "plate": f"TEST{phone_number[-4:]}",
        "vehicle_type_id": 1
    }

    driver_documents_data = {
        "license_expiration_date": str(date(2026, 1, 1)),
        "soat_expiration_date": str(date(2025, 12, 31)),
        "vehicle_technical_inspection_expiration_date": str(date(2025, 12, 31))
    }

    files = {
        "selfie": ("selfie.jpg", io.BytesIO(b"fake-selfie-data"), "image/jpeg"),
        "property_card_front": ("property_front.jpg", io.BytesIO(b"fake-property-front"), "image/jpeg"),
        "property_card_back": ("property_back.jpg", io.BytesIO(b"fake-property-back"), "image/jpeg"),
        "license_front": ("license_front.jpg", io.BytesIO(b"fake-license-front"), "image/jpeg"),
        "license_back": ("license_back.jpg", io.BytesIO(b"fake-license-back"), "image/jpeg"),
        "soat": ("soat.jpg", io.BytesIO(b"fake-soat"), "image/jpeg"),
        "vehicle_technical_inspection": ("tech.jpg", io.BytesIO(b"fake-tech"), "image/jpeg")
    }

    data_parts = {
        "user": json.dumps(user_data),
        "driver_info": json.dumps(driver_info_data),
        "vehicle_info": json.dumps(vehicle_info_data),
        "driver_documents": json.dumps(driver_documents_data)
    }

    create_driver_response = client.post(
        "/drivers/", data=data_parts, files=files)
    assert create_driver_response.status_code == 201, f"Error creando conductor: {create_driver_response.text}"

    driver_user_id_str = create_driver_response.json()["user"]["id"]
    driver_user_id = UUID(driver_user_id_str)  # Convertir string a UUID
    assert driver_user_id == user_id, "Los IDs de usuario no coinciden"
    print(f"✅ Conductor registrado (mismo usuario ID: {user_id})")

    # PASO 3: Verificar que ahora existen DOS registros en user_has_role
    print("\n3️⃣ Verificando registros en tabla user_has_role...")

    with Session(engine) as session:
        # Verificar que mantiene el registro CLIENT
        client_role_record = session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user_id,
                UserHasRole.id_rol == "CLIENT"
            )
        ).first()

        assert client_role_record is not None, "Registro CLIENT se perdió"
        assert client_role_record.status == RoleStatus.APPROVED, "Rol CLIENT ya no está aprobado"
        print(f"✅ Registro CLIENT mantenido")
        print(f"   - ID Usuario: {client_role_record.id_user}")
        print(f"   - Rol: {client_role_record.id_rol}")
        print(f"   - Status: {client_role_record.status}")

        # Verificar que ahora existe registro DRIVER
        driver_role_record = session.exec(
            select(UserHasRole).where(
                UserHasRole.id_user == user_id,
                UserHasRole.id_rol == "DRIVER"
            )
        ).first()

        assert driver_role_record is not None, "No existe registro DRIVER"
        print(f"✅ Registro DRIVER creado")
        print(f"   - ID Usuario: {driver_role_record.id_user}")
        print(f"   - Rol: {driver_role_record.id_rol}")
        print(f"   - Status: {driver_role_record.status}")

        # Verificar que hay exactamente 2 registros
        all_records = session.exec(
            select(UserHasRole).where(UserHasRole.id_user == user_id)
        ).all()

        assert len(
            all_records) == 2, f"Debe haber exactamente 2 registros, hay {len(all_records)}"
        print(f"✅ Total registros en user_has_role: {len(all_records)}")

        # Mostrar todos los registros
        print(f"\n📋 RESUMEN DE REGISTROS EN user_has_role:")
        for i, record in enumerate(all_records, 1):
            print(f"   Registro {i}:")
            print(f"     - ID Usuario: {record.id_user}")
            print(f"     - Rol: {record.id_rol}")
            print(f"     - Status: {record.status}")
            print(f"     - Verificado: {record.is_verified}")
            print(f"     - Creado: {record.created_at}")

    print(f"\n🎉 TEST COMPLETADO!")
    print(
        f"✅ Usuario {phone_number} tiene 2 registros separados en user_has_role:")
    print(f"   - 1 registro con rol CLIENT")
    print(f"   - 1 registro con rol DRIVER")
    print(f"   - Ambos con el mismo ID de usuario")
