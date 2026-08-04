import os

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "clave_secreta_inventario_2026",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:123456@localhost:5432/inventario_db",
)