import unittest

# Importamos la aplicación Flask actual

from app import app

class TestSistemaInventario(unittest.TestCase):

```
def setUp(self):
    """Configura un cliente de prueba para Flask."""
    app.config["TESTING"] = True
    self.client = app.test_client()

# =====================================================
# LOGIN
# =====================================================

def test_pagina_login_carga(self):
    """Verifica que la pantalla de login cargue correctamente."""
    respuesta = self.client.get("/login")

    self.assertEqual(
        respuesta.status_code,
        200,
    )

# =====================================================
# SEGURIDAD - DASHBOARD
# =====================================================

def test_api_dashboard_sin_login(self):
    """
    Verifica que el dashboard no sea accesible
    sin iniciar sesión.
    """

    respuesta = self.client.get(
        "/api/dashboard"
    )

    self.assertEqual(
        respuesta.status_code,
        401,
    )

    self.assertTrue(
        respuesta.is_json
    )

# =====================================================
# SEGURIDAD - PRODUCTOS
# =====================================================

def test_api_productos_sin_login(self):
    """
    Verifica que la API de productos
    esté protegida.
    """

    respuesta = self.client.get(
        "/api/productos"
    )

    self.assertEqual(
        respuesta.status_code,
        401,
    )

    self.assertTrue(
        respuesta.is_json
    )

# =====================================================
# SEGURIDAD - FACTURAS
# =====================================================

def test_api_facturas_sin_login(self):
    """
    Verifica que la API de facturas
    esté protegida.
    """

    respuesta = self.client.get(
        "/api/facturas"
    )

    self.assertEqual(
        respuesta.status_code,
        401,
    )

    self.assertTrue(
        respuesta.is_json
    )

# =====================================================
# API DASHBOARD
# =====================================================

def test_api_dashboard_con_login(self):
    """
    Verifica que el dashboard funcione
    correctamente después de iniciar sesión.
    """

    with self.client.session_transaction() as sesion:
        sesion["usuario"] = "admin"
        sesion["rol"] = "admin"
        sesion["genero"] = "Hombre"

    respuesta = self.client.get(
        "/api/dashboard"
    )

    self.assertEqual(
        respuesta.status_code,
        200,
    )

    self.assertTrue(
        respuesta.is_json
    )

    datos = respuesta.get_json()

    self.assertIn(
        "inventario",
        datos,
    )

    self.assertIn(
        "ventas_dia",
        datos,
    )

    self.assertIn(
        "ventas_mes",
        datos,
    )

    self.assertIn(
        "compras_mes",
        datos,
    )

    self.assertIn(
        "productos_mas_vendidos",
        datos,
    )

    self.assertIn(
        "categorias_mas_rentables",
        datos,
    )

# =====================================================
# API PRODUCTOS
# =====================================================

def test_api_productos_con_login(self):
    """
    Verifica que la API de productos funcione
    después de iniciar sesión.
    """

    with self.client.session_transaction() as sesion:
        sesion["usuario"] = "admin"
        sesion["rol"] = "admin"
        sesion["genero"] = "Hombre"

    respuesta = self.client.get(
        "/api/productos"
    )

    self.assertEqual(
        respuesta.status_code,
        200,
    )

    self.assertTrue(
        respuesta.is_json
    )

    datos = respuesta.get_json()

    self.assertIn(
        "productos",
        datos,
    )

    self.assertIsInstance(
        datos["productos"],
        list,
    )

# =====================================================
# API FACTURAS
# =====================================================

def test_api_facturas_con_login(self):
    """
    Verifica que la API de facturas funcione
    después de iniciar sesión.
    """

    with self.client.session_transaction() as sesion:
        sesion["usuario"] = "admin"
        sesion["rol"] = "admin"
        sesion["genero"] = "Hombre"

    respuesta = self.client.get(
        "/api/facturas"
    )

    self.assertEqual(
        respuesta.status_code,
        200,
    )

    self.assertTrue(
        respuesta.is_json
    )

    datos = respuesta.get_json()

    self.assertIn(
        "facturas",
        datos,
    )

    self.assertIsInstance(
        datos["facturas"],
        list,
    )

# =====================================================
# CREAR FACTURA - VALIDACIÓN
# =====================================================

def test_crear_factura_sin_productos(self):
    """
    Verifica que el sistema rechace una factura
    que no contiene productos.
    """

    with self.client.session_transaction() as sesion:
        sesion["usuario"] = "admin"
        sesion["rol"] = "admin"
        sesion["genero"] = "Hombre"

    respuesta = self.client.post(
        "/api/facturas/crear",
        json={
            "detalles": []
        },
    )

    self.assertEqual(
        respuesta.status_code,
        400,
    )

    self.assertTrue(
        respuesta.is_json
    )

    datos = respuesta.get_json()

    self.assertIn(
        "error",
        datos,
    )

# =====================================================
# CREAR FACTURA - DATOS VACÍOS
# =====================================================

def test_crear_factura_sin_datos(self):
    """
    Verifica que el sistema rechace una petición
    sin datos JSON.
    """

    with self.client.session_transaction() as sesion:
        sesion["usuario"] = "admin"
        sesion["rol"] = "admin"
        sesion["genero"] = "Hombre"

    respuesta = self.client.post(
        "/api/facturas/crear"
    )

    self.assertEqual(
        respuesta.status_code,
        400,
    )

    self.assertTrue(
        respuesta.is_json
    )

    datos = respuesta.get_json()

    self.assertIn(
        "error",
        datos,
    )
```

# =========================================================

# EJECUTAR PRUEBAS

# =========================================================

if **name** == "**main**":
unittest.main()
