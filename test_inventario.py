import unittest
from app import app

class TestSistemaInventario(unittest.TestCase):

def test_pagina_login_carga(self):
    respuesta = app.test_client().get("/login")
    self.assertEqual(respuesta.status_code, 200)

def test_api_dashboard_requiere_login(self):
    respuesta = app.test_client().get("/api/dashboard")
    self.assertEqual(respuesta.status_code, 401)

if name == "main":
unittest.main()
