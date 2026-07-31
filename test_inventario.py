import unittest
from app import app


class TestSistemaInventario(unittest.TestCase):

    def setUp(self):
        self.cliente = app.test_client()

    # =====================================================
    # PRUEBA 1 - LOGIN
    # =====================================================

    def test_pagina_login_carga(self):
        respuesta = self.cliente.get("/login")

        self.assertEqual(
            respuesta.status_code,
            200
        )

    # =====================================================
    # PRUEBA 2 - DASHBOARD PROTEGIDO
    # =====================================================

    def test_api_dashboard_requiere_login(self):
        respuesta = self.cliente.get(
            "/api/dashboard"
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )

    # =====================================================
    # PRUEBA 3 - PRODUCTOS PROTEGIDO
    # =====================================================

    def test_api_productos_requiere_login(self):
        respuesta = self.cliente.get(
            "/api/productos"
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )

    # =====================================================
    # PRUEBA 4 - FACTURAS PROTEGIDAS
    # =====================================================

    def test_api_facturas_requiere_login(self):
        respuesta = self.cliente.get(
            "/api/facturas"
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )

    # =====================================================
    # PRUEBA 5 - CREAR FACTURA PROTEGIDO
    # =====================================================

    def test_crear_factura_requiere_login(self):
        respuesta = self.cliente.post(
            "/api/facturas/crear",
            json={
                "detalles": [
                    {
                        "producto_id": 1,
                        "cantidad": 1,
                        "precio_unitario": 10000,
                        "descuento": 0
                    }
                ]
            }
        )

        self.assertEqual(
            respuesta.status_code,
            401
        )


if __name__ == "__main__":
    unittest.main()
