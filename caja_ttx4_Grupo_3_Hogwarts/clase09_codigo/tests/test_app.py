"""Pruebas funcionales mínimas de la API de integración (TTX #4)."""
import importlib.util
import os
import pathlib

APP_DIR = pathlib.Path(os.environ.get("APP_DIR", pathlib.Path(__file__).resolve().parent.parent / "app_andina"))


def cargar():
    spec = importlib.util.spec_from_file_location("app_ttx4", APP_DIR / "app.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.app.test_client()


def test_salud():
    assert cargar().get("/salud").status_code == 200


def test_registros_pendientes():
    r = cargar().get("/registros?estado=pendiente")
    assert r.status_code == 200 and len(r.get_json()) == 1
