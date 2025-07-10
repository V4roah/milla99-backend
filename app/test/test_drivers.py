import io
from fastapi import status
from datetime import date
import json
from uuid import UUID
import traceback


def test_create_driver_full(client):
    # Datos de usuario
    user_data = {
        "full_name": "Carlos Prueba",
        "country_code": "+57",
        "phone_number": "3010000000"
    }
    driver_info_data = {
        "first_name": "Carlos",
        "last_name": "Gómez",
        "birth_date": str(date(1990, 1, 1)),
        "email": "carlos.prueba@example.com"
    }
    vehicle_info_data = {
        "brand": "Toyota",
        "model": "Corolla",
        "model_year": 2020,
        "color": "Blanco",
        "plate": "ABC123",
        "vehicle_type_id": 1
    }
    driver_documents_data = {
        "license_expiration_date": str(date(2026, 1, 1)),
        "soat_expiration_date": str(date(2025, 12, 31)),
        "vehicle_technical_inspection_expiration_date": str(date(2025, 12, 31)),
        # URLs opcionales (simuladas)
        "property_card_front_url": None,
        "property_card_back_url": None,
        "license_front_url": None,
        "license_back_url": None,
        "soat_url": None,
        "vehicle_technical_inspection_url": None
    }

    # Archivos simulados en memoria (filename, fileobj, content_type)
    selfie = ("selfie.jpg", io.BytesIO(b"fake-selfie-data"), "image/jpeg")
    property_card_front = ("property_front.jpg", io.BytesIO(
        b"fake-property-front"), "image/jpeg")
    property_card_back = ("property_back.jpg", io.BytesIO(
        b"fake-property-back"), "image/jpeg")
    license_front = ("license_front.jpg", io.BytesIO(
        b"fake-license-front"), "image/jpeg")
    license_back = ("license_back.jpg", io.BytesIO(
        b"fake-license-back"), "image/jpeg")
    soat = ("soat.jpg", io.BytesIO(b"fake-soat"), "image/jpeg")
    vehicle_technical_inspection = (
        "tech.jpg", io.BytesIO(b"fake-tech"), "image/jpeg")

    # Construir el payload multipart/form-data
    data = {
        "user": (None, json.dumps(user_data), "application/json"),
        "driver_info": (None, json.dumps(driver_info_data), "application/json"),
        "vehicle_info": (None, json.dumps(vehicle_info_data), "application/json"),
        "driver_documents": (None, json.dumps(driver_documents_data), "application/json"),
        "selfie": selfie,
        "property_card_front": property_card_front,
        "property_card_back": property_card_back,
        "license_front": license_front,
        "license_back": license_back,
        "soat": soat,
        "vehicle_technical_inspection": vehicle_technical_inspection,
    }

    response = client.post("/drivers/", files=data)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    resp_json = response.json()
    assert resp_json["user"]["full_name"] == user_data["full_name"]
    assert resp_json["driver_info"]["first_name"] == driver_info_data["first_name"]
    assert resp_json["vehicle_info"]["brand"] == vehicle_info_data["brand"]
    # Verifica que las URLs de los documentos y selfie estén presentes
    assert resp_json["user"]["selfie_url"]


def test_get_driver_me(client):
    # 1. Crear un driver nuevo
    phone_number = "3010000002"
    country_code = "+57"
    user_data = {
        "full_name": "Driver Me Test",
        "country_code": country_code,
        "phone_number": phone_number
    }
    driver_info_data = {
        "first_name": "DriverMe",
        "last_name": "Test",
        "birth_date": str(date(1992, 2, 2)),
        "email": "driver.me@example.com"
    }
    vehicle_info_data = {
        "brand": "Mazda",
        "model": "3",
        "model_year": 2021,
        "color": "Rojo",
        "plate": "XYZ987",
        "vehicle_type_id": 1
    }
    driver_documents_data = {
        "license_expiration_date": str(date(2027, 2, 2)),
        "soat_expiration_date": str(date(2025, 2, 2)),
        "property_card_expiration_date": str(date(2028, 2, 2)),
        "technical_inspection_expiration_date": str(date(2026, 2, 2))
    }
    files = {
        "selfie": ("selfie.jpg", io.BytesIO(b"fake-selfie-data"), "image/jpeg"),
        "property_card_front": ("property_front.jpg", io.BytesIO(b"fake-property-front"), "image/jpeg"),
        "property_card_back": ("property_back.jpg", io.BytesIO(b"fake-property-back"), "image/jpeg"),
        "license_front": ("license_front.jpg", io.BytesIO(b"fake-license-front"), "image/jpeg"),
        "license_back": ("license_back.jpg", io.BytesIO(b"fake-license-back"), "image/jpeg"),
        "soat": ("soat.jpg", io.BytesIO(b"fake-soat"), "image/jpeg"),
        "technical_inspection": ("tech.jpg", io.BytesIO(b"fake-tech"), "image/jpeg"),
    }
    data = {
        "user": json.dumps(user_data),
        "driver_info": json.dumps(driver_info_data),
        "vehicle_info": json.dumps(vehicle_info_data),
        "driver_documents": json.dumps(driver_documents_data),
    }
    resp = client.post("/drivers/", data=data, files=files)
    print("CREAR DRIVER:", resp.status_code, resp.text)
    assert resp.status_code == status.HTTP_201_CREATED

    # 2. Enviar código de verificación (simula WhatsApp)
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    print("ENVIAR CODIGO:", send_resp.status_code, send_resp.text)
    assert send_resp.status_code == 201
    msg = send_resp.json()["message"]
    code = msg.split()[-1]  # Toma el último fragmento, que es el código real
    print("CODIGO EXTRAIDO:", code)

    # 3. Verificar el código y obtener el token
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    print("VERIFICAR CODIGO:", verify_resp.status_code, verify_resp.text)
    print("VERIFICAR CODIGO JSON:", verify_resp.json())
    assert verify_resp.status_code == 200
    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Consultar /drivers/me con el token
    me_resp = client.get("/drivers/me", headers=headers)
    print("DRIVERS/ME:", me_resp.status_code, me_resp.text)
    assert me_resp.status_code == 200
    me_json = me_resp.json()
    print("RESPUESTA DRIVERS/ME:", me_json)
    assert me_json["user"]["phone_number"] == phone_number
    assert me_json["driver_info"]["first_name"] == "DriverMe"
    assert me_json["vehicle_info"]["plate"] == "XYZ987"


def test_patch_driver_me(client):
    # 1. Crear un driver nuevo
    phone_number = "3010000003"
    country_code = "+57"
    user_data = {
        "full_name": "Driver Patch Test",
        "country_code": country_code,
        "phone_number": phone_number
    }
    driver_info_data = {
        "first_name": "Patch",
        "last_name": "Original",
        "birth_date": str(date(1993, 3, 3)),
        "email": "patch.original@example.com"
    }
    vehicle_info_data = {
        "brand": "Kia",
        "model": "Rio",
        "model_year": 2019,
        "color": "Negro",
        "plate": "PATCH01",
        "vehicle_type_id": 1
    }
    driver_documents_data = {
        "license_expiration_date": str(date(2028, 3, 3)),
        "soat_expiration_date": str(date(2026, 3, 3)),
        "property_card_expiration_date": str(date(2029, 3, 3)),
        "technical_inspection_expiration_date": str(date(2027, 3, 3))
    }
    files = {
        "selfie": ("selfie.jpg", io.BytesIO(b"original-selfie"), "image/jpeg"),
        "property_card_front": ("property_front.jpg", io.BytesIO(b"original-property-front"), "image/jpeg"),
        "property_card_back": ("property_back.jpg", io.BytesIO(b"original-property-back"), "image/jpeg"),
        "license_front": ("license_front.jpg", io.BytesIO(b"original-license-front"), "image/jpeg"),
        "license_back": ("license_back.jpg", io.BytesIO(b"original-license-back"), "image/jpeg"),
        "soat": ("soat.jpg", io.BytesIO(b"original-soat"), "image/jpeg"),
        "technical_inspection": ("tech.jpg", io.BytesIO(b"original-tech"), "image/jpeg"),
    }
    data = {
        "user": json.dumps(user_data),
        "driver_info": json.dumps(driver_info_data),
        "vehicle_info": json.dumps(vehicle_info_data),
        "driver_documents": json.dumps(driver_documents_data),
    }
    resp = client.post("/drivers/", data=data, files=files)
    print("CREAR DRIVER:", resp.status_code, resp.text)
    assert resp.status_code == status.HTTP_201_CREATED

    # 2. Enviar código de verificación (simula WhatsApp)
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    print("ENVIAR CODIGO:", send_resp.status_code, send_resp.text)
    assert send_resp.status_code == 201
    msg = send_resp.json()["message"]
    code = msg.split()[-1]
    print("CODIGO EXTRAIDO:", code)

    # 3. Verificar el código y obtener el token
    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code",
        json={"code": code}
    )
    print("VERIFICAR CODIGO:", verify_resp.status_code, verify_resp.text)
    assert verify_resp.status_code == 200
    token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Obtener el estado actual antes del PATCH
    me_resp_before = client.get("/drivers/me", headers=headers)
    print("\n=== ESTADO ANTES DEL PATCH ===")
    print("GET /drivers/me antes del PATCH:", me_resp_before.status_code)
    print("Datos antes del PATCH:", json.dumps(
        me_resp_before.json(), indent=2, ensure_ascii=False))

    # 5. PATCH /drivers/me con nuevos datos y archivos
    patch_data = {
        "first_name": (None, "Patched"),
        "last_name": (None, "Updated"),
        "color": (None, "Azul"),
        "selfie": ("new_selfie.jpg", io.BytesIO(b"new-selfie-data"), "image/jpeg"),
    }
    patch_resp = client.patch("/drivers/me", files=patch_data, headers=headers)
    print("\n=== RESPUESTA DEL PATCH ===")
    print("PATCH /drivers/me status:", patch_resp.status_code)
    print("Datos después del PATCH:", json.dumps(
        patch_resp.json(), indent=2, ensure_ascii=False))

    # 6. Verificar el estado final
    me_resp_after = client.get("/drivers/me", headers=headers)
    print("\n=== ESTADO FINAL DESPUÉS DEL PATCH ===")
    print("GET /drivers/me después del PATCH:", me_resp_after.status_code)
    print("Datos finales:", json.dumps(
        me_resp_after.json(), indent=2, ensure_ascii=False))

    assert patch_resp.status_code == 200


def test_driver_creation_and_verification_flow(client):
    """
    Test que verifica el flujo completo de:
    1. Creación del driver (is_verified=False, status=PENDING)
    2. Verificación de documentos por admin
    3. Actualización de estado (is_verified=True, status=APPROVED)
    4. Intento de usar endpoints antes y después de verificación
    """
    print("\n=== INICIANDO TEST DE VERIFICACIÓN ===")

    # Usar una sesión explícita para el test
    from app.core.db import engine
    from sqlmodel import Session
    from app.models.user_has_roles import UserHasRole, RoleStatus
    from sqlmodel import select

    with Session(engine) as session:
        try:
            # 1. Crear un driver nuevo
            print("1. Preparando datos del driver...")
            phone_number = "3010000004"
            country_code = "+57"
            user_data = {
                "full_name": "Driver Test User",
                "country_code": country_code,
                "phone_number": phone_number
            }
            driver_info_data = {
                "first_name": "Verification",
                "last_name": "Test",
                "birth_date": "1990-01-01",
                "email": "verification.test@example.com"
            }
            vehicle_info_data = {
                "brand": "Test Brand",
                "model": "Test Model",
                "model_year": 2020,
                "color": "Test Color",
                "plate": "TEST123",
                "vehicle_type_id": 1
            }
            driver_documents_data = {
                "license_expiration_date": "2025-01-01",
                "soat_expiration_date": "2025-01-01",
                "vehicle_technical_inspection_expiration_date": "2025-01-01"
            }

            # Preparar los datos para la request
            data = {
                "user": json.dumps(user_data),
                "driver_info": json.dumps(driver_info_data),
                "vehicle_info": json.dumps(vehicle_info_data),
                "driver_documents": json.dumps(driver_documents_data)
            }

            # Crear archivos simulados para la request
            files = {
                "selfie": ("test_selfie.jpg", b"fake image data", "image/jpeg"),
                "license_front": ("test_license_front.jpg", b"fake image data", "image/jpeg"),
                "license_back": ("test_license_back.jpg", b"fake image data", "image/jpeg"),
                "soat": ("test_soat.pdf", b"fake pdf data", "application/pdf"),
                "vehicle_technical_inspection": ("test_tech.pdf", b"fake pdf data", "application/pdf")
            }

            print("2. Enviando request para crear driver...")
            # Crear el driver
            create_resp = client.post("/drivers/", data=data, files=files)
            print(f"Respuesta crear driver: {create_resp.status_code}")
            print(f"Contenido respuesta: {create_resp.text}")
            assert create_resp.status_code == status.HTTP_201_CREATED
            driver_data = create_resp.json()
            driver_id = UUID(driver_data["user"]["id"])
            print(f"Driver creado con ID: {driver_id}")

            # 2. Verificar que el driver se creó con estado inicial correcto
            print("3. Verificando estado inicial del driver...")
            # Obtener el rol del driver
            driver_role = session.exec(
                select(UserHasRole).where(
                    UserHasRole.id_user == UUID(str(driver_id)),
                    UserHasRole.id_rol == "DRIVER"
                )
            ).first()
            assert driver_role is not None
            assert driver_role.status == RoleStatus.PENDING
            print("Estado inicial verificado")

            # 3. Verificar que el driver no puede acceder a endpoints antes de verificación
            print("4. Verificando acceso a endpoints antes de verificación...")
            # Obtener código de verificación
            send_resp = client.post(
                f"/auth/verify/{country_code}/{phone_number}/send")
            print("ENVIAR CODIGO:", send_resp.status_code, send_resp.text)
            assert send_resp.status_code == 201
            msg = send_resp.json()["message"]
            # Toma el último fragmento, que es el código real
            code = msg.split()[-1]
            print("CODIGO EXTRAIDO:", code)

            # Verificar el código y obtener el token
            verify_resp = client.post(
                f"/auth/verify/{country_code}/{phone_number}/code",
                json={"code": code}
            )
            print("VERIFICAR CODIGO:", verify_resp.status_code, verify_resp.text)
            assert verify_resp.status_code == 200
            auth_token = verify_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {auth_token}"}

            # Intentar actualizar posición (debería fallar)
            position_data = {"lat": 4.6097, "lng": -74.0817}
            position_resp = client.post(
                "/drivers-position/", json=position_data, headers=headers)
            assert position_resp.status_code == status.HTTP_403_FORBIDDEN
            print("Acceso denegado correctamente antes de verificación")

            # 4. Simular verificación de documentos por admin
            print("5. Simulando verificación por admin...")
            driver_role.status = RoleStatus.APPROVED
            session.add(driver_role)
            session.commit()
            session.refresh(driver_role)
            print("Verificación completada")

            # Cerrar la sesión para asegurar visibilidad del cambio
            session.close()

            # Volver a autenticar al conductor para obtener un nuevo token
            print("7. Re-autenticando conductor después de aprobación...")
            send_resp = client.post(
                f"/auth/verify/{country_code}/{phone_number}/send")
            print("ENVIAR CODIGO (re-auth):",
                  send_resp.status_code, send_resp.text)
            assert send_resp.status_code == 201
            msg = send_resp.json()["message"]
            code = msg.split()[-1]
            print("CODIGO EXTRAIDO (re-auth):", code)
            verify_resp = client.post(
                f"/auth/verify/{country_code}/{phone_number}/code",
                json={"code": code}
            )
            print("VERIFICAR CODIGO (re-auth):",
                  verify_resp.status_code, verify_resp.text)
            assert verify_resp.status_code == 200
            auth_token = verify_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {auth_token}"}

            # 5. Verificar que el driver puede acceder después de verificación
            print("8. Verificando acceso después de re-autenticación...")
            position_resp = client.post(
                "/drivers-position/", json=position_data, headers=headers)
            print("RESPUESTA POSICION:",
                  position_resp.status_code, position_resp.text)
            assert position_resp.status_code == status.HTTP_201_CREATED
            print("Acceso permitido correctamente después de verificación")

            # 6. Verificar datos del driver
            print("9. Verificando datos del driver...")
            me_resp = client.get("/drivers/me", headers=headers)
            assert me_resp.status_code == status.HTTP_200_OK
            me_data = me_resp.json()
            assert me_data["driver_info"]["first_name"] == "Verification"
            print("Datos del driver verificados correctamente")

        except Exception as e:
            print(f"Error en el test: {str(e)}")
            print(traceback.format_exc())
            raise
        finally:
            # Asegurarnos de que la sesión se cierre
            session.close()


def test_sql_injection_on_create_driver(client):
    malicious_data = {
        "full_name": "Driver'; DROP TABLE users; --",
        "country_code": "+57",
        "phone_number": "3001234567"
    }
    response = client.post("/drivers/", json=malicious_data)
    assert response.status_code == 422  # Código de error esperado
    # Verifica que se maneje el error de validación
    assert "detail" in response.json()


def create_and_approve_driver(client, phone_number, country_code):
    from app.core.db import engine
    from sqlmodel import Session, select
    from app.models.user import User
    from app.models.user_has_roles import UserHasRole, RoleStatus
    from uuid import UUID

    driver_id = None

    with Session(engine) as session:
        user = session.exec(select(User).where(
            User.phone_number == phone_number)).first()

        if user:
            # Si el usuario ya existe (viene de init_data), solo lo aprobamos
            driver_id = user.id
            driver_role = session.exec(select(UserHasRole).where(
                UserHasRole.id_user == driver_id, UserHasRole.id_rol == "DRIVER")).first()
            if not driver_role:
                raise Exception(
                    f"El usuario {phone_number} existe pero no tiene el rol de DRIVER.")

            if driver_role.status != RoleStatus.APPROVED:
                # Buscar el rol DRIVER de manera más robusta
                driver_role = session.exec(select(UserHasRole).where(
                    UserHasRole.id_user == driver_id, UserHasRole.id_rol == "DRIVER")).first()

                # Si no se encuentra, intentar crear el rol manualmente
                if driver_role is None:
                    print(
                        f"Rol DRIVER no encontrado para usuario {driver_id}, creándolo manualmente...")
                    try:
                        driver_role = UserHasRole(
                            id_user=driver_id,
                            id_rol="DRIVER",
                            status=RoleStatus.PENDING
                        )
                        session.add(driver_role)
                        session.commit()
                        session.refresh(driver_role)
                        print("Rol DRIVER creado manualmente")
                    except Exception as e:
                        print(f"Error creando rol manualmente: {e}")
                        # Si falla, intentar buscar de nuevo (puede que se haya creado en otro proceso)
                        session.rollback()
                        driver_role = session.exec(select(UserHasRole).where(
                            UserHasRole.id_user == driver_id, UserHasRole.id_rol == "DRIVER")).first()
                        if driver_role is None:
                            raise Exception(
                                f"No se pudo crear ni encontrar el rol DRIVER para usuario {driver_id}")
                        print("Rol DRIVER encontrado después del rollback")

                assert driver_role is not None
                driver_role.status = RoleStatus.APPROVED
                session.add(driver_role)
                session.commit()
        else:
            # Si el usuario no existe, lo creamos desde cero
            user_data = {
                "full_name": f"Driver Test User",
                "country_code": country_code,
                "phone_number": phone_number
            }
            driver_info_data = {
                "first_name": "Driver", "last_name": "Test", "birth_date": str(
                    date(1990, 1, 1)), "email": f"driver.test.{phone_number}@example.com"
            }
            vehicle_info_data = {
                "brand": "Toyota", "model": "Corolla", "model_year": 2020, "color": "Blanco", "plate": f"TEST{phone_number[-4:]}", "vehicle_type_id": 1
            }
            driver_documents_data = {
                "license_expiration_date": str(date(2026, 1, 1)),
                "soat_expiration_date": str(date(2025, 12, 31)),
                "vehicle_technical_inspection_expiration_date": str(
                    date(2025, 12, 31))
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

            response = client.post("/drivers/", data=data_parts, files=files)

            if response.status_code != status.HTTP_201_CREATED:
                print(
                    f"Error creando conductor ({phone_number}): {response.text}")
            assert response.status_code == status.HTTP_201_CREATED
            driver_data = response.json()
            driver_id = UUID(driver_data["user"]["id"])

            # Buscar el rol DRIVER de manera más robusta
            driver_role = session.exec(select(UserHasRole).where(
                UserHasRole.id_user == driver_id, UserHasRole.id_rol == "DRIVER")).first()

            # Si no se encuentra, intentar crear el rol manualmente
            if driver_role is None:
                print(
                    f"Rol DRIVER no encontrado para usuario {driver_id}, creándolo manualmente...")
                try:
                    driver_role = UserHasRole(
                        id_user=driver_id,
                        id_rol="DRIVER",
                        status=RoleStatus.PENDING
                    )
                    session.add(driver_role)
                    session.commit()
                    session.refresh(driver_role)
                    print("Rol DRIVER creado manualmente")
                except Exception as e:
                    print(f"Error creando rol manualmente: {e}")
                    # Si falla, intentar buscar de nuevo (puede que se haya creado en otro proceso)
                    session.rollback()
                    driver_role = session.exec(select(UserHasRole).where(
                        UserHasRole.id_user == driver_id, UserHasRole.id_rol == "DRIVER")).first()
                    if driver_role is None:
                        raise Exception(
                            f"No se pudo crear ni encontrar el rol DRIVER para usuario {driver_id}")
                    print("Rol DRIVER encontrado después del rollback")

            assert driver_role is not None
            driver_role.status = RoleStatus.APPROVED
            session.add(driver_role)
            session.commit()

    # Autenticar al conductor para obtener el token
    send_resp = client.post(f"/auth/verify/{country_code}/{phone_number}/send")
    assert send_resp.status_code == 201, f"Falló al enviar código a {phone_number}: {send_resp.text}"

    code = send_resp.json()["message"].split()[-1]

    verify_resp = client.post(
        f"/auth/verify/{country_code}/{phone_number}/code", json={"code": code})
    assert verify_resp.status_code == 200, f"Falló al verificar código para {phone_number}: {verify_resp.text}"

    response_data = verify_resp.json()

    return response_data["access_token"], driver_id
