# sync_matricula.py · integración entre Universidad de Hogwarts y AulaNube (CÓDIGO FICTICIO PARA EL EJERCICIO, NO EJECUTAR EN PRODUCCIÓN)
import logging, sqlite3, requests

logging.basicConfig(filename="integracion.log", level=logging.DEBUG)
API = "https://sga.hogwarts.example/api/matricula"
TOKEN = "an_live_Q8r2Lp6Zt3Wm9Xk4"          # token de servicio entregado al proveedor en 2025
DB = "/data/estudiantes_matricula.db"


def buscar(filtro):
    con = sqlite3.connect(DB)
    q = f"SELECT nombre, dni, detalle FROM estudiantes_matricula WHERE estado = '{filtro}'"
    filas = con.execute(q).fetchall()
    for f in filas:
        logging.debug("registro enviado: %s %s", f[0], f[1])   # nombre y DNI al log
    return filas


def enviar(filtro="pendiente"):
    datos = buscar(filtro)
    r = requests.post(API, json={"registros": datos},
                      headers={"Authorization": f"Bearer {TOKEN}"},
                      verify=False, timeout=30)
    return r.status_code


if __name__ == "__main__":
    import sys
    print(enviar(sys.argv[1] if len(sys.argv) > 1 else "pendiente"))
