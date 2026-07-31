import unittest

# Importamos el archivo principal usando su nombre exacto con espacios
modulo = importlib.import_module("Ssitema de Inventario")
app = modulo.app

class TestSistemaInventario(unittest.TestCase):

    def setUp(self):
        """Configura un cliente de prueba para Flask."""
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_pagina_login_carga(self):
        """Verifica que la pantalla de login responda con código 200 (Éxito)."""
        respuesta = self.client.get('/login')
        self.assertEqual(respuesta.status_code, 200)

    def test_api_resumen_funciona(self):
        """Verifica que el endpoint de la API devuelva una respuesta válida (Código 200)."""
        respuesta = self.client.get('/api/resumen')
        self.assertEqual(respuesta.status_code, 200)

if __name__ == '__main__':
    unittest.main()
