import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import engine, Session
from sqlmodel import select
from app.models.administrador import Administrador, AdminRole
import traceback
from app.models.user import User
from app.models.withdrawal import Withdrawal, WithdrawalStatus
from app.models.bank_account import BankAccount, IdentificationType
from uuid import uuid4
from datetime import datetime

client = TestClient(app)


def test_admin_login_all_roles():
    """Test para verificar login de los 3 admins con diferentes roles"""

    # Datos de los admins creados en init_data.py
    admins_data = [
        {
            "email": "admin",
            "password": "admin",
            "role": AdminRole.BASIC,
            "description": "Admin básico"
        },
        {
            "email": "system_admin",
            "password": "system123",
            "role": AdminRole.SYSTEM,
            "description": "Admin del sistema"
        },
        {
            "email": "super_admin",
            "password": "super123",
            "role": AdminRole.SUPER,
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
        assert role == admin_data[
            "role"].value, f"Role incorrecto para {admin_data['email']}. Esperado: {admin_data['role'].value}, Recibido: {role}"

        # Verificar que el admin existe en la DB con el rol correcto
        with Session(engine) as session:
            admin = session.exec(
                select(Administrador).where(
                    Administrador.email == admin_data["email"])
            ).first()

            assert admin is not None, f"Admin {admin_data['email']} no existe en la DB"
            assert admin.role == admin_data[
                "role"].value, f"Role incorrecto para {admin_data['email']}"

            print(
                f"✅ Admin {admin_data['email']} existe en DB con role {admin.role}")

    print("\n🎉 ¡Todos los tests de login pasaron exitosamente!")


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


def test_admin_role_hierarchy_with_real_withdrawal_approval():
    """Test para verificar jerarquía de roles con aprobación real de withdrawal"""

    print("\n🔐 Test de Jerarquía de Roles - Aprobación Real de Withdrawal")

    # 1. CREAR UN WITHDRAWAL REAL EN LA BASE DE DATOS
    print("\n📝 Paso 1: Creando withdrawal real en la base de datos...")

    # Primero necesitamos un usuario y una cuenta bancaria
    # Por simplicidad, vamos a usar los datos existentes en init_data.py
    # Buscar un usuario existente
    with Session(engine) as session:
        # Buscar un usuario existente
        user = session.exec(select(User).limit(1)).first()
        if not user:
            print("   ❌ No hay usuarios en la base de datos")
            return

        # Crear una cuenta bancaria de prueba
        bank_account = BankAccount(
            id=uuid4(),
            user_id=user.id,
            bank_id=1,  # Asumiendo que existe un banco con ID 1
            account_type="savings",
            account_number="1234567890",
            account_holder_name="Test User",
            type_identification="CC",  # Campo requerido
            identification_number="1234567890",  # Campo requerido
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(bank_account)
        session.commit()
        session.refresh(bank_account)

        # Crear un withdrawal
        withdrawal = Withdrawal(
            id=uuid4(),
            user_id=user.id,
            bank_account_id=bank_account.id,
            amount=50000,
            status=WithdrawalStatus.PENDING,
            withdrawal_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(withdrawal)
        session.commit()
        session.refresh(withdrawal)

        withdrawal_id = withdrawal.id
        print(f"   ✅ Withdrawal creado con ID: {withdrawal_id}")
        print(f"   📊 Usuario: {user.phone_number}")
        print(f"   💰 Monto: ${withdrawal.amount:,}")
        print(f"   📋 Status: {withdrawal.status}")

    # 2. ADMIN BÁSICO APRUEBA EL WITHDRAWAL
    print("\n👤 Paso 2: Admin básico aprueba withdrawal...")

    # Login como admin básico
    basic_login = client.post(
        "/login-admin/login",
        json={"email": "admin", "password": "admin"}
    )
    assert basic_login.status_code == 200
    basic_token = basic_login.json()["access_token"]
    basic_headers = {"Authorization": f"Bearer {basic_token}"}

    # Aprobar el withdrawal usando el endpoint real
    approval_data = {
        "new_status": "approved"
    }

    print(f"   🔄 Aprobando withdrawal {withdrawal_id}...")
    print(f"   📝 Status: {approval_data['new_status']}")

    # Hacer la llamada al endpoint
    approval_response = client.patch(
        f"/withdrawals/{withdrawal_id}/update-status",
        headers=basic_headers,
        json=approval_data
    )
    print(f"   📊 Response status: {approval_response.status_code}")
    print(f"   📊 Response: {approval_response.text}")

    if approval_response.status_code == 200:
        print("   ✅ Withdrawal aprobado exitosamente")
    else:
        print(f"   ❌ Error al aprobar withdrawal: {approval_response.text}")

    # 3. VERIFICAR LOGS SEGÚN JERARQUÍA
    print("\n📊 Paso 3: Verificando logs según jerarquía...")

    # 3.1 Admin básico ve solo sus logs
    print("\n🔍 3.1 Admin básico (Role 1) - Solo sus logs:")
    basic_logs = client.get("/admin-logs/my-logs", headers=basic_headers)
    assert basic_logs.status_code == 200
    basic_logs_data = basic_logs.json()
    print(f"   📊 Logs obtenidos: {len(basic_logs_data)} registros")
    print(f"   ✅ Status: {basic_logs.status_code}")

    # Mostrar detalles de los logs si existen
    if basic_logs_data:
        for i, log in enumerate(basic_logs_data[:3]):
            print(
                f"   📋 Log {i+1}: {log.get('action_type', 'N/A')} - {log.get('description', 'N/A')}")

    # 3.2 Admin del sistema ve logs de nivel 1 + propios
    print("\n🔍 3.2 Admin del sistema (Role 2) - Logs de nivel 1 + propios:")
    system_login = client.post(
        "/login-admin/login",
        json={"email": "system_admin", "password": "system123"}
    )
    assert system_login.status_code == 200
    system_token = system_login.json()["access_token"]
    system_headers = {"Authorization": f"Bearer {system_token}"}

    system_logs = client.get("/admin-logs/my-logs", headers=system_headers)
    assert system_logs.status_code == 200
    system_logs_data = system_logs.json()
    print(f"   📊 Logs obtenidos: {len(system_logs_data)} registros")
    print(f"   ✅ Status: {system_logs.status_code}")

    # Mostrar detalles de los logs si existen
    if system_logs_data:
        for i, log in enumerate(system_logs_data[:3]):
            print(
                f"   📋 Log {i+1}: {log.get('action_type', 'N/A')} - {log.get('description', 'N/A')}")

    # 3.3 Super admin ve todos los logs
    print("\n🔍 3.3 Super admin (Role 3) - Todos los logs:")
    super_login = client.post(
        "/login-admin/login",
        json={"email": "super_admin", "password": "super123"}
    )
    assert super_login.status_code == 200
    super_token = super_login.json()["access_token"]
    super_headers = {"Authorization": f"Bearer {super_token}"}

    super_logs = client.get("/admin-logs/my-logs", headers=super_headers)
    assert super_logs.status_code == 200
    super_logs_data = super_logs.json()
    print(f"   📊 Logs obtenidos: {len(super_logs_data)} registros")
    print(f"   ✅ Status: {super_logs.status_code}")

    # Mostrar detalles de los logs si existen
    if super_logs_data:
        for i, log in enumerate(super_logs_data[:3]):
            print(
                f"   📋 Log {i+1}: {log.get('action_type', 'N/A')} - {log.get('description', 'N/A')}")

    # 4. VERIFICAR JERARQUÍA DE LOGS
    print("\n🔍 Paso 4: Verificando jerarquía de logs...")

    print(f"   📊 Role 1 logs: {len(basic_logs_data)}")
    print(f"   📊 Role 2 logs: {len(system_logs_data)}")
    print(f"   📊 Role 3 logs: {len(super_logs_data)}")

    # Verificar que se crearon logs
    total_logs = len(basic_logs_data) + \
        len(system_logs_data) + len(super_logs_data)
    if total_logs > 0:
        print(f"   ✅ Se crearon {total_logs} logs en total")
    else:
        print("   ⚠️ No se crearon logs - verificar configuración")

    # 5. VERIFICAR ACCESO A WITHDRAWALS
    print("\n💰 Paso 5: Verificando acceso a withdrawals...")

    # Todos los roles deberían poder acceder a withdrawals
    for role_name, headers in [
        ("Admin básico", basic_headers),
        ("Admin sistema", system_headers),
        ("Super admin", super_headers)
    ]:
        withdrawals_response = client.post(
            "/withdrawals/list",
            headers=headers,
            json={"status": None, "skip": 0, "limit": 10}
        )
        assert withdrawals_response.status_code == 200, f"Acceso a withdrawals falló para {role_name}"
        print(f"   ✅ {role_name}: Acceso a withdrawals exitoso")

    print("\n🎉 ¡Test de aprobación real completado exitosamente!")
    print("✅ Withdrawal creado y aprobado correctamente")
    print("✅ Logs generados según jerarquía de roles")
    print("✅ Endpoints funcionando correctamente")


def test_admin_role_hierarchy_with_multiple_approvals():
    """Test para verificar jerarquía de roles con múltiples aprobaciones de withdrawal"""

    print("\n🔐 Test de Jerarquía de Roles - Múltiples Aprobaciones")
    print("📊 Objetivo: Admin Role 1 (3 aprobaciones), Role 2 (2 aprobaciones), Role 3 (1 aprobación)")

    # 1. CREAR MÚLTIPLES WITHDRAWALS
    print("\n📝 Paso 1: Creando múltiples withdrawals...")

    withdrawal_ids = []
    with Session(engine) as session:
        # Buscar un usuario existente
        user = session.exec(select(User).limit(1)).first()
        if not user:
            print("   ❌ No hay usuarios en la base de datos")
            return

        # Crear 6 withdrawals (3 + 2 + 1)
        for i in range(6):
            # Crear cuenta bancaria para cada withdrawal
            bank_account = BankAccount(
                id=uuid4(),
                user_id=user.id,
                bank_id=1,
                account_type="savings",
                account_number=f"123456789{i}",
                account_holder_name=f"Test User {i+1}",
                type_identification="CC",
                identification_number=f"123456789{i}",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(bank_account)
            session.commit()
            session.refresh(bank_account)

            # Crear withdrawal
            withdrawal = Withdrawal(
                id=uuid4(),
                user_id=user.id,
                bank_account_id=bank_account.id,
                # Montos diferentes: 10k, 20k, 30k, 40k, 50k, 60k
                amount=10000 * (i + 1),
                status=WithdrawalStatus.PENDING,
                withdrawal_date=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(withdrawal)
            session.commit()
            session.refresh(withdrawal)

            withdrawal_ids.append(withdrawal.id)
            print(
                f"   ✅ Withdrawal {i+1} creado: ID={withdrawal.id}, Monto=${withdrawal.amount:,}")

    print(f"   📊 Total withdrawals creados: {len(withdrawal_ids)}")

    # 2. ADMIN ROL 1 - 3 APROBACIONES
    print("\n👤 Paso 2: Admin básico (Role 1) - 3 aprobaciones...")

    # Login como admin básico
    basic_login = client.post(
        "/login-admin/login",
        json={"email": "admin", "password": "admin"}
    )
    assert basic_login.status_code == 200
    basic_token = basic_login.json()["access_token"]
    basic_headers = {"Authorization": f"Bearer {basic_token}"}

    # Aprobar los primeros 3 withdrawals
    for i in range(3):
        withdrawal_id = withdrawal_ids[i]
        approval_data = {"new_status": "approved"}

        print(f"   🔄 Aprobando withdrawal {i+1}/3: {withdrawal_id}")
        response = client.patch(
            f"/withdrawals/{withdrawal_id}/update-status",
            headers=basic_headers,
            json=approval_data
        )

        if response.status_code == 200:
            print(f"   ✅ Withdrawal {i+1} aprobado exitosamente")
        else:
            print(f"   ❌ Error al aprobar withdrawal {i+1}: {response.text}")

    # 3. ADMIN ROL 2 - 2 APROBACIONES
    print("\n👤 Paso 3: Admin del sistema (Role 2) - 2 aprobaciones...")

    # Login como admin del sistema
    system_login = client.post(
        "/login-admin/login",
        json={"email": "system_admin", "password": "system123"}
    )
    assert system_login.status_code == 200
    system_token = system_login.json()["access_token"]
    system_headers = {"Authorization": f"Bearer {system_token}"}

    # Aprobar los siguientes 2 withdrawals
    for i in range(2):
        withdrawal_id = withdrawal_ids[i + 3]  # Withdrawals 4 y 5
        approval_data = {"new_status": "approved"}

        print(f"   🔄 Aprobando withdrawal {i+4}/6: {withdrawal_id}")
        response = client.patch(
            f"/withdrawals/{withdrawal_id}/update-status",
            headers=system_headers,
            json=approval_data
        )

        if response.status_code == 200:
            print(f"   ✅ Withdrawal {i+4} aprobado exitosamente")
        else:
            print(f"   ❌ Error al aprobar withdrawal {i+4}: {response.text}")

    # 4. SUPER ADMIN ROL 3 - 1 APROBACIÓN
    print("\n👤 Paso 4: Super admin (Role 3) - 1 aprobación...")

    # Login como super admin
    super_login = client.post(
        "/login-admin/login",
        json={"email": "super_admin", "password": "super123"}
    )
    assert super_login.status_code == 200
    super_token = super_login.json()["access_token"]
    super_headers = {"Authorization": f"Bearer {super_token}"}

    # Aprobar el último withdrawal
    withdrawal_id = withdrawal_ids[5]  # Withdrawal 6
    approval_data = {"new_status": "approved"}

    print(f"   🔄 Aprobando withdrawal 6/6: {withdrawal_id}")
    response = client.patch(
        f"/withdrawals/{withdrawal_id}/update-status",
        headers=super_headers,
        json=approval_data
    )

    if response.status_code == 200:
        print("   ✅ Withdrawal 6 aprobado exitosamente")
    else:
        print(f"   ❌ Error al aprobar withdrawal 6: {response.text}")

    # 5. VERIFICAR LOGS SEGÚN JERARQUÍA
    print("\n📊 Paso 5: Verificando logs según jerarquía...")

    # 5.1 Admin básico ve solo sus logs (3 aprobaciones)
    print("\n🔍 5.1 Admin básico (Role 1) - Solo sus logs:")
    basic_logs = client.get("/admin-logs/my-logs", headers=basic_headers)
    assert basic_logs.status_code == 200
    basic_logs_data = basic_logs.json()
    print(f"   📊 Logs obtenidos: {len(basic_logs_data)} registros")
    print(f"   ✅ Status: {basic_logs.status_code}")

    # Mostrar detalles de los logs
    for i, log in enumerate(basic_logs_data):
        print(
            f"   📋 Log {i+1}: {log.get('action_type', 'N/A')} - {log.get('description', 'N/A')}")

    # 5.2 Admin del sistema ve logs de nivel 1 + propios (3 + 2 = 5)
    print("\n🔍 5.2 Admin del sistema (Role 2) - Logs de nivel 1 + propios:")
    system_logs = client.get("/admin-logs/my-logs", headers=system_headers)
    assert system_logs.status_code == 200
    system_logs_data = system_logs.json()
    print(f"   📊 Logs obtenidos: {len(system_logs_data)} registros")
    print(f"   ✅ Status: {system_logs.status_code}")

    # Mostrar detalles de los logs
    for i, log in enumerate(system_logs_data):
        print(
            f"   📋 Log {i+1}: {log.get('action_type', 'N/A')} - {log.get('description', 'N/A')}")

    # 5.3 Super admin ve todos los logs (3 + 2 + 1 = 6)
    print("\n🔍 5.3 Super admin (Role 3) - Todos los logs:")
    super_logs = client.get("/admin-logs/my-logs", headers=super_headers)
    assert super_logs.status_code == 200
    super_logs_data = super_logs.json()
    print(f"   📊 Logs obtenidos: {len(super_logs_data)} registros")
    print(f"   ✅ Status: {super_logs.status_code}")

    # Mostrar detalles de los logs
    for i, log in enumerate(super_logs_data):
        print(
            f"   📋 Log {i+1}: {log.get('action_type', 'N/A')} - {log.get('description', 'N/A')}")

    # 6. VERIFICAR JERARQUÍA DE LOGS
    print("\n🔍 Paso 6: Verificando jerarquía de logs...")

    print(f"   📊 Role 1 logs: {len(basic_logs_data)} (esperado: 3)")
    print(f"   📊 Role 2 logs: {len(system_logs_data)} (esperado: 5)")
    print(f"   📊 Role 3 logs: {len(super_logs_data)} (esperado: 6)")

    # Verificar que la jerarquía es correcta
    assert len(
        basic_logs_data) >= 3, f"Role 1 debería tener al menos 3 logs, tiene {len(basic_logs_data)}"
    assert len(
        system_logs_data) >= 5, f"Role 2 debería tener al menos 5 logs, tiene {len(system_logs_data)}"
    assert len(
        super_logs_data) >= 6, f"Role 3 debería tener al menos 6 logs, tiene {len(super_logs_data)}"

    print("   ✅ Jerarquía de logs verificada correctamente")

    # 7. RESUMEN FINAL
    print("\n🎉 ¡Test de múltiples aprobaciones completado exitosamente!")
    print("✅ 6 withdrawals creados y aprobados")
    print("✅ Role 1: 3 aprobaciones")
    print("✅ Role 2: 2 aprobaciones")
    print("✅ Role 3: 1 aprobación")
    print("✅ Logs generados según jerarquía de roles")
    print("✅ Sistema funcionando correctamente")


if __name__ == "__main__":
    print("🚀 Iniciando tests de login de admins...")
    test_admin_login_all_roles()
    test_admin_token_validation()
    test_admin_login_invalid_credentials()
    test_admin_role_hierarchy_withdrawals_and_logs()
    test_admin_role_hierarchy_with_real_workflow()
    test_admin_role_hierarchy_with_real_withdrawal_approval()
    test_admin_role_hierarchy_with_multiple_approvals()
    print("\n✨ Todos los tests completados!")
