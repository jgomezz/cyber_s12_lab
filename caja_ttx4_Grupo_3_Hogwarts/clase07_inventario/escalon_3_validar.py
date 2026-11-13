"""Escalón 3 · ¿Inventa CVE el modelo? Validar y priorizar.

1. Pregunta al modelo, SIN herramienta, qué CVE afectan a cada software del inventario.
2. Valida cada CVE propuesto (formato, existencia y versión) contra el caché y, si quieren, contra NVD.
3. Compara con los CVE obtenidos CON herramienta en el escalón 2.
4. Arma un plan priorizado: CVSS × peso de la criticidad del activo, más los sistemas sin soporte.

Uso:
  python escalon_3_validar.py --proveedor ollama_cloud
  python escalon_3_validar.py --proveedor ollama_cloud_20b --en-linea      # valida además en NVD (lento: 6 s por CVE)
  python escalon_3_validar.py --validar CVE-2014-0160 --producto OpenSSL --version 3.0.2

Resultados: salidas/validacion_<proveedor>.xlsx y salidas/plan_priorizado_<proveedor>.xlsx
"""
import argparse
import json

import pandas as pd
from pydantic import BaseModel, Field

from cve import buscar_cve, fin_de_soporte, validar_cve
from llm import BASE, CONFIG, chat_json

DATA, SALIDAS = BASE / "data", BASE / "salidas"
PESO = {"Alta": 1.0, "Media": 0.7, "Baja": 0.4}


class Propuesto(BaseModel):
    cve: str
    motivo: str = ""


class Lista(BaseModel):
    cves: list[Propuesto] = Field(default_factory=list)


SISTEMA = """Eres analista de vulnerabilidades. Te dan un producto y su versión exacta.
Responde SOLO con JSON: {"cves": [{"cve": "CVE-AAAA-NNNN", "motivo": "una frase"}]}
Incluye solo CVE que afecten a ESA versión. Si no conoces ninguno con certeza, responde {"cves": []}."""


def cargar_inventario(proveedor):
    ruta = SALIDAS / f"inventario_{proveedor}.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8")), ruta.name
    return json.loads((DATA / "inventario_esperado.json").read_text(encoding="utf-8"))["activos"], "inventario_esperado.json (referencia)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", help="proveedor de config.yaml")
    ap.add_argument("--en-linea", action="store_true", help="valida en la API de NVD los CVE que no están en el caché")
    ap.add_argument("--validar", nargs="+", metavar="CVE", help="solo valida estos CVE (para el escalón 4)")
    ap.add_argument("--producto", default="")
    ap.add_argument("--version", default="")
    args = ap.parse_args()
    en_linea = args.en_linea or CONFIG.get("cve", {}).get("en_linea", False)

    if args.validar:
        for c in args.validar:
            print(f"  {c:<18} {validar_cve(c, args.producto, args.version, en_linea)}")
        return

    proveedor = args.proveedor or CONFIG["default"]
    activos, fuente = cargar_inventario(proveedor)
    software = sorted({(s["producto"], s["version"]) for a in activos for s in a["software"] if s.get("version")})
    print(f"Inventario: {fuente} · {len(software)} combinaciones producto-versión\nPreguntando al modelo '{proveedor}' SIN herramienta...\n")

    filas = []
    for prod, ver in software:
        try:
            lista, _ = chat_json(f"Producto: {prod}\nVersión: {ver}", Lista, provider=args.proveedor, system=SISTEMA)
            propuestos = lista.cves
        except ValueError:
            propuestos = []
        for p in propuestos:
            filas.append({"Método": "Sin herramienta", "Producto": prod, "Versión": ver, "CVE": p.cve, "Motivo del modelo": p.motivo,
                          "Validación": validar_cve(p.cve, prod, ver, en_linea)})
        print(f"  {prod} {ver}: {len(propuestos)} propuestos")

    e2 = SALIDAS / f"cve_herramienta_{proveedor}.json"
    if e2.exists():
        sw_por_host = {a["hostname"]: [s for s in a["software"] if s.get("version")] for a in activos}
        for f in json.loads(e2.read_text(encoding="utf-8")):
            # se valida contra el software real del activo, no contra lo que el modelo dijo que era
            estados = [validar_cve(f["CVE"], s["producto"], s["version"], en_linea) for s in sw_por_host.get(f["Activo"], [])] or [validar_cve(f["CVE"], en_linea=en_linea)]
            mejor = next((e for e in ("Verificado (aplica)", "Existe, pero no aplica a esa versión") if e in estados), estados[0])
            filas.append({"Método": "Con herramienta (escalón 2)", "Producto": f["Producto"] or f["Activo"], "Versión": f["Versión"], "CVE": f["CVE"],
                          "Motivo del modelo": "", "Validación": mejor})
    else:
        print(f"\n(No está {e2.name}: la comparación con herramienta queda vacía. Ejecuten el escalón 2.)")

    df = pd.DataFrame(filas, columns=["Método", "Producto", "Versión", "CVE", "Motivo del modelo", "Validación"])
    resumen = df.groupby(["Método", "Validación"]).size().unstack(fill_value=0) if len(df) else pd.DataFrame()
    if len(resumen):
        resumen["Total"] = resumen.sum(axis=1)
        resumen["% confiable"] = (resumen.get("Verificado (aplica)", 0) / resumen["Total"]).map("{:.0%}".format)

    # Plan priorizado: CVE del caché (fuente confiable), no lo que dijo el modelo
    plan = []
    for a in activos:
        for s in a["software"]:
            for c in buscar_cve(s["producto"], s.get("version", "")):
                plan.append({"Activo": a["hostname"], "Criticidad": a["criticidad"], "Software": f"{s['producto']} {s['version']}", "CVE": c["cve"],
                             "CVSS": c["cvss"], "Puntaje": round(c["cvss"] * PESO.get(a["criticidad"], 1), 1), "Descripción": c["descripcion"]})
        eol = fin_de_soporte(a.get("sistema_operativo", ""))
        if eol:
            plan.append({"Activo": a["hostname"], "Criticidad": a["criticidad"], "Software": a["sistema_operativo"], "CVE": "Sin soporte desde " + eol,
                         "CVSS": None, "Puntaje": round(7.0 * PESO.get(a["criticidad"], 1), 1), "Descripción": "Sistema sin parches de seguridad del fabricante"})
    dp = pd.DataFrame(plan).sort_values(["Puntaje", "Activo"], ascending=[False, True])
    dp.insert(0, "Prioridad", range(1, len(dp) + 1))

    SALIDAS.mkdir(exist_ok=True)
    with pd.ExcelWriter(SALIDAS / f"validacion_{proveedor}.xlsx", engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="CVE propuestos")
        if len(resumen):
            resumen.to_excel(xw, sheet_name="Resumen")
    with pd.ExcelWriter(SALIDAS / f"plan_priorizado_{proveedor}.xlsx", engine="openpyxl") as xw:
        dp.to_excel(xw, index=False, sheet_name="Plan")
        for i, w in enumerate([9, 20, 10, 26, 22, 7, 8, 70]):
            xw.sheets["Plan"].column_dimensions[chr(65 + i)].width = w

    print("\nResumen de la validación:")
    print(resumen.to_string() if len(resumen) else "  (sin CVE propuestos)")
    print(f"\nTop 5 del plan priorizado:\n{dp.head(5)[['Prioridad', 'Activo', 'CVE', 'CVSS', 'Puntaje']].to_string(index=False)}")
    print(f"\nArchivos: salidas/validacion_{proveedor}.xlsx y salidas/plan_priorizado_{proveedor}.xlsx")


if __name__ == "__main__":
    main()
