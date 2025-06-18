import os
import pytest
import sqlalchemy
from sqlalchemy import create_engine
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session
from app.main import fastapi_app as app
from app.core.db import get_session
from app.core.init_data import init_data
from app.core.config import settings

TEST_DB_NAME = "milla99_test"


def clean_database():
    """Limpia todas las tablas de la base de datos de test"""
    try:
        # Obtener todas las tablas
        inspector = sqlalchemy.inspect(engine)
        table_names = inspector.get_table_names()

        # Desactivar foreign key checks temporalmente
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SET FOREIGN_KEY_CHECKS = 0"))

            # Limpiar todas las tablas
            for table_name in table_names:
                if table_name != 'alembic_version':  # No tocar la tabla de migraciones
                    conn.execute(sqlalchemy.text(
                        f"TRUNCATE TABLE {table_name}"))

            # Reactivar foreign key checks
            conn.execute(sqlalchemy.text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()
    except Exception as e:
        print(f"Error limpiando base de datos: {e}")


@pytest.fixture(autouse=True)
def create_and_drop_test_db():
    # Crear la base de datos
    engine = sqlalchemy.create_engine(settings.DATABASE_URL.rsplit('/', 1)[0])
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text(
            f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(sqlalchemy.text(f"CREATE DATABASE {TEST_DB_NAME}"))

    # Cambiar la variable de entorno para que los tests usen la nueva DB
    os.environ["DATABASE_URL"] = settings.TEST_DATABASE_URL
    yield

    # Eliminar la base de datos al finalizar los tests
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text(
            f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))


# Forzar uso de MySQL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or not DATABASE_URL.startswith("mysql"):
    raise RuntimeError(
        "Debes definir la variable de entorno DATABASE_URL con un DSN de MySQL para correr los tests.")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


@pytest.fixture(autouse=True)
def setup_db_data():
    # Limpiar la base de datos antes de cada test
    clean_database()

    # Crear las tablas si no existen
    SQLModel.metadata.create_all(engine)

    # Poblar con datos iniciales
    init_data()

    yield

    # Limpiar después del test
    clean_database()


@pytest.fixture(name="session")
def session_fixture():
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
