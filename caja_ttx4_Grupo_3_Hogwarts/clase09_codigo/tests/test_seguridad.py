"""Pruebas de seguridad mínimas (TTX #4): fallan con el código original."""
from test_app import cargar


def test_sql_injection():
    r = cargar().get("/registros?estado=x' OR '1'='1")
    assert len(r.get_json()) == 0


def test_exportar_requiere_autenticacion():
    assert cargar().get("/exportar").status_code in (401, 403)
