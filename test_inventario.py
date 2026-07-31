import unittest
from app import app


class TestSistemaInventario(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.cliente = app.test_client()

    # =====================================================
    # LOGIN
    # =====================================================

    def test_pagina_login_carga(self):
        respuesta = self.cliente.get("/login")

        self.assertEqual(
            respuesta.status_code,
            200
        )

    # =====================================================
    # RUTAS PROTEGIDAS
    # =====================================================

    def test_api_dashboard_requiere_login(self):
        respuesta = self.cliente.get(
            "/api/dashboard"
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )

    def test_api_productos_requiere_login(self):
        respuesta = self.cliente.get(
            "/api/productos"
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )

    def test_api_facturas_requiere_login(self):
        respuesta = self.cliente.get(
            "/api/facturas"
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )

    def test_api_factura_individual_requiere_login(self):
        respuesta = self.cliente.get(
            "/api/facturas/1"
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )

    # =====================================================
    # PÁGINAS PROTEGIDAS
    # =====================================================

    def test_inicio_requiere_login(self):
        respuesta = self.cliente.get(
            "/"
        )

        self.assertEqual(
            respuesta.status_code,
            302
        )

    def test_facturacion_requiere_login(self):
        respuesta = self.cliente.get(
            "/facturacion"
        )

        self.assertEqual(
            respuesta.status_code,
            302
        )

    def test_movimientos_requiere_login(self):
        respuesta = self.cliente.get(
            "/movimientos"
        )

        self.assertEqual(
            respuesta.status_code,
            302
        )

    def test_proveedores_requiere_login(self):
        respuesta = self.cliente.get(
            "/proveedores"
        )

        self.assertEqual(
            respuesta.status_code,
            302
        )


if __name__ == "__main__":
    unittest.main()
