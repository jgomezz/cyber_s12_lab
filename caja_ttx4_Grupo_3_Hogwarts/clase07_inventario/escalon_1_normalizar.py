"""Escalón 1 · Normalizar el inventario de Universidad de Hogwarts con salida estructurada.

El inventario viene de tres fuentes (CMDB, planilla de TI y escaneo de red), cada una con su formato.
El modelo convierte cada registro en un objeto `Activo` validado con Pydantic; el código une duplicados,
neutraliza fórmulas antes de escribir el Excel y compara con la respuesta de referencia.

Uso:
  python escalon_1_normalizar.py                      # proveedor por defecto (local)
  python escalon_1_normalizar.py --proveedor ollama_cloud_20b
  python escalon_1_normalizar.py --sin-sanear         # para ver el riesgo LLM10 en el Excel

Resultados: salidas/inventario_<proveedor>.json y salidas/inventario_<proveedor>.xlsx
"""
import argparse
import csv
import json
import time
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from cve import normalizar_producto
from llm import BASE, CONFIG, chat_json

DATA, SALIDAS = BASE / "data", BASE / "salidas"


class Software(BaseModel):
    producto: str
    version: str = ""


class Activo(BaseModel):
    hostname: str
    tipo: Literal["Servidor", "Base de datos", "Equipo de red", "Estación de trabajo", "Otro"]
    entorno: Literal["Producción", "Herramientas", "Estación de trabajo", "Oficina", "Desarrollo"]
    sistema_operativo: str = ""
    software: list[Software] = Field(default_factory=list)
    responsable: str = ""
    criticidad: Literal["Alta", "Media", "Baja"]
    justificacion_criticidad: str = ""


SISTEMA = """Eres analista de gestión de activos de Universidad de Hogwarts, una universidad privada (38.000 estudiantes y egresados). Conviertes un registro de inventario en JSON.
Responde SOLO con un objeto JSON con estas claves:
  "hostname": nombre del equipo (sin IP)
  "tipo": "Servidor" | "Base de datos" | "Equipo de red" | "Estación de trabajo" | "Otro"
  "entorno": "Producción" | "Herramientas" | "Estación de trabajo" | "Oficina" | "Desarrollo"
  "sistema_operativo": nombre y versión, o "" si no aparece
  "software": lista de {"producto": nombre del producto, "version": versión exacta como aparece}
              (incluye servidores web, bibliotecas, bases de datos y SSH; no incluyas el sistema operativo)
  "responsable": área o equipo responsable
  "criticidad": "Alta" | "Media" | "Baja"
  "justificacion_criticidad": una oración
Criterio de criticidad: Alta si procesa pagos o datos de clientes, está expuesto a Internet o da acceso a
producción (credenciales, salto SSH); Media si es una herramienta interna o de monitoreo; Baja si es de oficina.
Si el registro trae una criticidad explícita, úsala salvo que contradiga claramente el criterio.
Usa solo la información del registro: no inventes versiones."""


def sanear_celda(valor):
    """LLM10: una celda que empieza con = + - @ se ejecuta como fórmula al abrir el Excel."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
        return "'" + valor, True
    return valor, False


def unir_duplicados(activos: list[dict]) -> list[dict]:
    por_host = {}
    for a in activos:
        h = a["hostname"].strip().lower()
        if h not in por_host:
            por_host[h] = a
            continue
        b = por_host[h]
        vistos = {(normalizar_producto(s["producto"]), s["version"]) for s in b["software"]}
        b["software"] += [s for s in a["software"] if (normalizar_producto(s["producto"]), s["version"]) not in vistos]
        b["origen"] += a["origen"]
        for campo in ("sistema_operativo", "responsable"):
            b[campo] = b[campo] or a[campo]
    return list(por_host.values())


def evaluar(activos: list[dict]) -> pd.DataFrame:
    """Compara con data/inventario_esperado.json campo por campo."""
    esperado = {a["hostname"]: a for a in json.loads((DATA / "inventario_esperado.json").read_text(encoding="utf-8"))["activos"]}
    filas = []
    for host, e in esperado.items():
        a = next((x for x in activos if x["hostname"].strip().lower() == host), None)
        if a is None:
            filas.append({"hostname": host, "encontrado": "No"})
            continue
        sw_e = {(normalizar_producto(s["producto"]), s["version"]) for s in e["software"] if s["version"]}
        sw_a = {(normalizar_producto(s["producto"]), s["version"]) for s in a["software"]}
        filas.append({"hostname": host, "encontrado": "Sí", "tipo": a["tipo"] == e["tipo"], "entorno": a["entorno"] == e["entorno"],
                      "criticidad": a["criticidad"] == e["criticidad"], "criticidad modelo": a["criticidad"], "criticidad referencia": e["criticidad"],
                      "software encontrado": f"{len(sw_e & sw_a)}/{len(sw_e)}", "software extra": ", ".join(f"{p} {v}" for p, v in sorted(sw_a - sw_e))})
    return pd.DataFrame(filas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", help="proveedor de config.yaml")
    ap.add_argument("--sin-sanear", action="store_true", help="escribe el Excel sin neutralizar fórmulas (solo para ver el riesgo)")
    args = ap.parse_args()
    proveedor = args.proveedor or CONFIG["default"]
    SALIDAS.mkdir(exist_ok=True)

    with open(DATA / "inventario_bruto.csv", encoding="utf-8") as f:
        registros = list(csv.DictReader(f))
    print(f"Normalizando {len(registros)} registros con '{proveedor}'\n")
    activos, inicio = [], time.time()
    for reg in registros:
        t0 = time.time()
        try:
            act, intentos = chat_json(f"Fuente: {reg['fuente']}\nRegistro: {reg['registro']}", Activo, provider=args.proveedor, system=SISTEMA)
            d = act.model_dump()
            d["software"] = [s for s in d["software"] if s["producto"]]
            estado = f"ok ({intentos} intento{'s' if intentos > 1 else ''})"
        except ValueError as e:
            d = {"hostname": reg["id_origen"], "tipo": "Otro", "entorno": "Producción", "sistema_operativo": "", "software": [], "responsable": "",
                 "criticidad": "Alta", "justificacion_criticidad": f"ERROR: {e}"}
            estado = "JSON inválido"
        d["origen"] = [reg["id_origen"]]
        activos.append(d)
        print(f"  {reg['id_origen']:<10} {d['hostname']:<20} {d['criticidad']:<6} {len(d['software'])} software  {estado}  ({time.time() - t0:.1f} s)")

    activos = unir_duplicados(activos)
    (SALIDAS / f"inventario_{proveedor}.json").write_text(json.dumps(activos, ensure_ascii=False, indent=1), encoding="utf-8")

    filas, saneadas = [], 0
    for a in activos:
        fila = {"Hostname": a["hostname"], "Tipo": a["tipo"], "Entorno": a["entorno"], "Sistema operativo": a["sistema_operativo"],
                "Software": "; ".join(f"{s['producto']} {s['version']}".strip() for s in a["software"]), "Responsable": a["responsable"],
                "Criticidad": a["criticidad"], "Justificación": a["justificacion_criticidad"], "Origen": ", ".join(a["origen"])}
        if not args.sin_sanear:
            for k, v in fila.items():
                fila[k], cambio = sanear_celda(v)
                saneadas += cambio
        filas.append(fila)
    ev = evaluar(activos)
    archivo = SALIDAS / f"inventario_{proveedor}.xlsx"
    with pd.ExcelWriter(archivo, engine="openpyxl") as xw:
        pd.DataFrame(filas).to_excel(xw, index=False, sheet_name="Inventario")
        ev.to_excel(xw, index=False, sheet_name="Evaluación")
        for hoja, anchos in (("Inventario", [20, 16, 16, 20, 50, 20, 10, 50, 22]), ("Evaluación", [20, 11, 8, 9, 11, 16, 18, 18, 40])):
            for i, w in enumerate(anchos):
                xw.sheets[hoja].column_dimensions[chr(65 + i)].width = w

    ok = ev[ev["encontrado"] == "Sí"]
    print(f"\n{len(registros)} registros -> {len(activos)} activos únicos · {time.time() - inicio:.0f} s")
    if len(ok):
        print(f"Aciertos frente a la referencia: tipo {ok['tipo'].mean():.0%} · entorno {ok['entorno'].mean():.0%} · criticidad {ok['criticidad'].mean():.0%}")
    print(f"Celdas neutralizadas antes de escribir el Excel (LLM10): {saneadas}" if not args.sin_sanear else "ATENCIÓN: Excel escrito sin neutralizar fórmulas.")
    print(f"Inventario en {archivo.relative_to(BASE)} (hojas Inventario y Evaluación)")


if __name__ == "__main__":
    main()
