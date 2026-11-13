"""Escalón 2 · El modelo busca CVE con una herramienta servida por MCP.

La herramienta buscar_cve(producto, version) vive en un servidor MCP (mcp_servidor_cve.py).
Este programa es el cliente MCP y el que conversa con el modelo:

  1. Lanza el servidor como otro proceso y abre la sesión (initialize, notifications/initialized).
  2. Pregunta qué herramientas hay (tools/list) y las traduce al formato de tool calling del modelo.
  3. Por cada activo, el modelo decide si llama a buscar_cve. Cada pedido del modelo se reenvía
     al servidor (tools/call) y el resultado vuelve al modelo, que entrega un JSON final.
  4. Se mide si llamó la herramienta para todo el software y si reportó solo lo que el servidor devolvió.

En pantalla queda cada paso numerado: MCP → / MCP ← (cliente y servidor), LLM → / LLM ← (modelo)
y [servidor] (lo que registra el propio servidor).

Uso:
  python escalon_2_herramienta.py --activo api-pagos-01                # demo: un activo
  python escalon_2_herramienta.py --activo api-pagos-01 --detalle 2    # cada mensaje JSON completo
  python escalon_2_herramienta.py --proveedor ollama_cloud_20b
  python escalon_2_herramienta.py --proveedor groq --inventario salidas/inventario_ollama_cloud.json
  python escalon_2_herramienta.py --referencia                         # usa data/inventario_esperado.json
  python escalon_2_herramienta.py --simulado --activo api-pagos-01     # sin API: modelo simulado (plan B)

Resultado: salidas/cve_herramienta_<proveedor>.xlsx y .json, y el registro salidas/mcp_registro_<proveedor>.jsonl
"""
import argparse
import asyncio
import json
import os
import sys
import time

import anyio
import pandas as pd
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Implementation
from pydantic import BaseModel, Field

from cve import buscar_cve, fin_de_soporte, normalizar_producto
from llm import BASE, CONFIG, chat_herramientas, extraer_json

DATA, SALIDAS = BASE / "data", BASE / "salidas"

SISTEMA = """Eres analista de vulnerabilidades. Para el activo que te entregan:
1. Llama a la herramienta buscar_cve una vez por cada software que tenga versión.
2. Cuando tengas todos los resultados, responde SOLO con JSON:
   {"vulnerabilidades": [{"cve": "CVE-AAAA-NNNN", "producto": "...", "version": "...", "cvss": 0.0}], "resumen": "una oración"}
Reporta únicamente CVE que haya devuelto la herramienta. Si no devolvió ninguno, la lista va vacía."""


class Vuln(BaseModel):
    cve: str
    producto: str = ""
    version: str = ""
    cvss: float | None = None


class Respuesta(BaseModel):
    vulnerabilidades: list[Vuln] = Field(default_factory=list)
    resumen: str = ""


# ------------------------------------------------------------------ registro de lo que pasa por debajo
class Registro:
    """Imprime cada evento numerado y lo guarda en JSONL. detalle: 0 = nada en pantalla, 1 = una línea, 2 = JSON completo."""

    COLOR = {"MCP →": "36", "MCP ←": "96", "LLM →": "33", "LLM ←": "93", "INFO": "90"}

    def __init__(self, archivo, detalle: int):
        self.n, self.t0, self.detalle = 0, time.perf_counter(), detalle
        self.color = sys.stdout.isatty() and not os.getenv("NO_COLOR")
        if self.color and os.name == "nt":
            os.system("")  # activa los colores ANSI en la consola de Windows
        archivo.parent.mkdir(exist_ok=True)
        self.f = archivo.open("w", encoding="utf-8")

    def __call__(self, canal: str, texto: str, cuerpo=None):
        self.n += 1
        t = time.perf_counter() - self.t0
        self.f.write(json.dumps({"n": self.n, "t": round(t, 3), "canal": canal, "evento": texto, "cuerpo": cuerpo},
                                ensure_ascii=False, default=str) + "\n")
        self.f.flush()
        if self.detalle == 0:
            return
        linea = f"[{self.n:02d}] {t:6.2f}s  {canal:<5}  {texto}"
        print(f"\033[{self.COLOR.get(canal, '0')}m{linea}\033[0m" if self.color else linea)
        if self.detalle >= 2 and cuerpo is not None:
            s = json.dumps(cuerpo, ensure_ascii=False, indent=2, default=str)
            if len(s) > 3000:
                s = s[:3000] + "\n… (recortado en pantalla; completo en el registro)"
            print("        " + s.replace("\n", "\n        "))

    def cerrar(self):
        self.f.close()


def una_linea(m: dict) -> str:
    """Describe en una línea un mensaje JSON-RPC."""
    if "method" in m:
        tipo = "notificación" if "id" not in m else f"petición id={m['id']}"
        extra = ""
        if m["method"] == "tools/call":
            p = m.get("params", {})
            extra = f"  {p.get('name')}({json.dumps(p.get('arguments', {}), ensure_ascii=False)})"
        return f"{m['method']} ({tipo}){extra}"
    if "error" in m:
        return f"error id={m.get('id')}: {m['error'].get('message')}"
    r = m.get("result", {})
    if "serverInfo" in r:
        return f"respuesta id={m.get('id')}: servidor '{r['serverInfo'].get('name')}', protocolo {r.get('protocolVersion')}"
    if "tools" in r:
        return f"respuesta id={m.get('id')}: {len(r['tools'])} herramienta(s): " + ", ".join(t["name"] for t in r["tools"])
    if "content" in r:
        texto = "".join(c.get("text", "") for c in r["content"])
        try:
            ids = [x["cve"] for x in json.loads(texto)]
            return f"respuesta id={m.get('id')}: {len(ids)} CVE" + (f" ({', '.join(ids)})" if ids else "")
        except (json.JSONDecodeError, TypeError, KeyError):
            return f"respuesta id={m.get('id')}: {len(texto)} caracteres" + (" · isError" if r.get("isError") else "")
    return f"respuesta id={m.get('id')}"


def intercalar_registro(read, write, reg: Registro):
    """Pone dos canales entre la sesión MCP y el transporte para registrar cada mensaje que pasa."""
    entrada_tx, entrada_rx = anyio.create_memory_object_stream(32)
    salida_tx, salida_rx = anyio.create_memory_object_stream(32)

    def dump(sm):
        return sm.message.model_dump(by_alias=True, exclude_none=True, mode="json")

    async def bombear_entrada():
        async with entrada_tx:
            async for sm in read:
                if not isinstance(sm, Exception):
                    d = dump(sm)
                    reg("MCP ←", una_linea(d), d)
                await entrada_tx.send(sm)

    async def bombear_salida():
        async with salida_rx:
            async for sm in salida_rx:
                d = dump(sm)
                reg("MCP →", una_linea(d), d)
                await write.send(sm)

    return entrada_rx, salida_tx, bombear_entrada, bombear_salida


def herramientas_para_el_modelo(tools) -> list:
    """De tools/list (formato MCP) al formato de tool calling que recibe el modelo."""
    return [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                               "parameters": t.inputSchema}} for t in tools]


# ------------------------------------------------------------------ modelo simulado (plan B sin API)
class _Llamada:
    def __init__(self, i, producto, version):
        self.id, self.type = f"sim_{i}", "function"
        self.function = type("F", (), {"name": "buscar_cve", "arguments": json.dumps({"producto": producto, "version": version})})()


def modelo_simulado(mensajes, activo):
    """Pide la herramienta para cada software y luego reporta exactamente lo que recibió."""
    respuestas = [m for m in mensajes if m["role"] == "tool"]
    if not respuestas:
        llamadas = [_Llamada(i, s["producto"], s["version"]) for i, s in enumerate(activo["software"]) if s.get("version")]
        return type("M", (), {"content": "", "tool_calls": llamadas})()
    vulns = [{"cve": c["cve"], "producto": "", "version": "", "cvss": c["cvss"]} for m in respuestas for c in json.loads(m["content"])]
    return type("M", (), {"content": json.dumps({"vulnerabilidades": vulns, "resumen": "Modelo simulado."}), "tool_calls": None})()


# ------------------------------------------------------------------ análisis de un activo
async def analizar(session, herramientas, activo: dict, args, reg: Registro, max_vueltas: int = 8) -> dict:
    datos = {k: activo[k] for k in ("hostname", "sistema_operativo", "software")}
    mensajes = [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": "Activo:\n" + json.dumps(datos, ensure_ascii=False)}]
    llamadas, devueltos, enviados, msg = [], set(), 0, None
    for vuelta in range(1, max_vueltas + 1):
        nuevos = mensajes[enviados:]
        reg("LLM →", f"vuelta {vuelta}: se envían {len(nuevos)} mensaje(s) nuevo(s) y {len(herramientas)} herramienta(s)", nuevos)
        enviados = len(mensajes)
        if args.simulado:
            msg = modelo_simulado(mensajes, activo)
        else:
            msg = await asyncio.to_thread(chat_herramientas, mensajes, herramientas, args.proveedor)
        tcs = getattr(msg, "tool_calls", None) or []
        if not tcs:
            reg("LLM ←", "respuesta final, sin pedir herramientas", msg.content)
            break
        reg("LLM ←", f"pide {len(tcs)} llamada(s): " + "; ".join(f"{t.function.name}({t.function.arguments})" for t in tcs),
            [{"id": t.id, "name": t.function.name, "arguments": t.function.arguments} for t in tcs])
        mensajes.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in tcs]})
        for t in tcs:
            try:
                arg = json.loads(t.function.arguments or "{}")
            except json.JSONDecodeError:
                arg = {}
            if not arg:
                reg("INFO", f"argumentos no válidos: {t.function.arguments!r}; se responde con error sin llamar al servidor")
                contenido = json.dumps({"error": "argumentos no son JSON"})
            else:
                res = await session.call_tool(t.function.name, arg)
                contenido = "".join(getattr(c, "text", "") for c in res.content)
                try:
                    resultado = json.loads(contenido)
                    devueltos |= {r["cve"] for r in resultado} if isinstance(resultado, list) else set()
                except json.JSONDecodeError:
                    pass
            llamadas.append(f"{arg.get('producto', '?')} {arg.get('version', '')}".strip())
            mensajes.append({"role": "tool", "tool_call_id": t.id, "name": t.function.name, "content": contenido})
    else:
        reg("INFO", f"se alcanzó el límite de {max_vueltas} vueltas sin respuesta final (LLM06, consumo no acotado)")
    try:
        resp = Respuesta.model_validate(extraer_json(msg.content or ""))
    except Exception:
        resp = Respuesta(resumen=f"Respuesta final no válida: {(msg.content or '')[:120]}")
    return {"llamadas": llamadas, "devueltos": devueltos, "respuesta": resp}


# ------------------------------------------------------------------ programa principal
async def principal(args, activos, proveedor):
    etiqueta = "simulado" if args.simulado else proveedor
    reg = Registro(SALIDAS / f"mcp_registro_{etiqueta}.jsonl", args.detalle)
    log_servidor = None if args.detalle else (SALIDAS / f"mcp_servidor_{etiqueta}.log").open("w", encoding="utf-8")
    servidor = StdioServerParameters(command=sys.executable, args=[str(BASE / "mcp_servidor_cve.py")], cwd=str(BASE))
    reg("INFO", "lanzo el servidor MCP como otro proceso: python mcp_servidor_cve.py (transporte stdio)")

    filas, resumen, inicio = [], [], time.time()
    async with stdio_client(servidor, errlog=log_servidor or sys.stderr) as (read, write):
        rx, tx, entrada, salida = intercalar_registro(read, write, reg)
        async with anyio.create_task_group() as tg:
            tg.start_soon(entrada)
            tg.start_soon(salida)
            async with ClientSession(rx, tx, client_info=Implementation(name="lab-clase7", version="1.0")) as session:
                await session.initialize()
                herramientas = herramientas_para_el_modelo((await session.list_tools()).tools)
                reg("INFO", "así queda la herramienta en el formato que recibe el modelo", herramientas)

                for a in activos:
                    con_version = [s for s in a["software"] if s.get("version")]
                    eol = fin_de_soporte(a.get("sistema_operativo", ""))
                    if not con_version:
                        resumen.append({"Activo": a["hostname"], "Software con versión": 0, "Llamadas": 0, "CVE reportados": 0, "Precisión": "", "Cobertura": "", "Fin de soporte del SO": eol or ""})
                        continue
                    reg("INFO", f"── activo {a['hostname']}: " + ", ".join(f"{s['producto']} {s['version']}" for s in con_version))
                    t0 = time.time()
                    try:
                        r = await analizar(session, herramientas, a, args, reg)
                    except Exception as e:  # p. ej., el modelo no soporta herramientas
                        raise SystemExit(f"Error con '{proveedor}': {str(e).splitlines()[0][:150]}\nPrueben con --referencia, --proveedor deepseek o --simulado.")
                    esperados = {c["cve"] for s in con_version for c in buscar_cve(s["producto"], s["version"])}
                    reportados = {v.cve.strip().upper() for v in r["respuesta"].vulnerabilidades}
                    consultados = {normalizar_producto(x.rsplit(" ", 1)[0]) for x in r["llamadas"]}
                    cubiertos = sum(normalizar_producto(s["producto"]) in consultados for s in con_version)
                    for v in r["respuesta"].vulnerabilidades:
                        filas.append({"Activo": a["hostname"], "Criticidad": a["criticidad"], "CVE": v.cve, "Producto": v.producto, "Versión": v.version, "CVSS": v.cvss,
                                      "¿Lo devolvió la herramienta?": "Sí" if v.cve.strip().upper() in r["devueltos"] else "No (lo agregó el modelo)"})
                    resumen.append({"Activo": a["hostname"], "Software con versión": len(con_version), "Llamadas": len(r["llamadas"]), "Consultó": "; ".join(r["llamadas"]),
                                    "CVE reportados": len(reportados), "CVE que debía reportar": len(esperados),
                                    "Precisión": f"{len(reportados & esperados)}/{len(reportados)}" if reportados else "-",
                                    "Cobertura": f"{len(reportados & esperados)}/{len(esperados)}" if esperados else "-",
                                    "Software consultado": f"{cubiertos}/{len(con_version)}", "Fin de soporte del SO": eol or "", "Segundos": round(time.time() - t0, 1)})
                    print(f"  {a['hostname']:<20} {len(r['llamadas'])} llamadas · {len(reportados)} CVE reportados de {len(esperados)} esperados ({time.time() - t0:.1f} s)")
            tg.cancel_scope.cancel()
    if log_servidor:
        log_servidor.close()
    reg.cerrar()
    return filas, resumen, inicio, reg.n, etiqueta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proveedor", help="proveedor de config.yaml (debe soportar herramientas)")
    ap.add_argument("--inventario", help="JSON del escalón 1 (por defecto, el del mismo proveedor)")
    ap.add_argument("--referencia", action="store_true", help="usa el inventario de referencia en vez del escalón 1")
    ap.add_argument("--activo", help="revisa solo este hostname (útil para la demo)")
    ap.add_argument("--detalle", type=int, choices=[0, 1, 2], default=1,
                    help="0 = solo el resumen · 1 = una línea por mensaje (por defecto) · 2 = cada mensaje JSON completo")
    ap.add_argument("--simulado", action="store_true", help="modelo simulado: no usa API (plan B para la demo)")
    args = ap.parse_args()
    proveedor = args.proveedor or CONFIG["default"]
    if args.referencia:
        activos = json.loads((DATA / "inventario_esperado.json").read_text(encoding="utf-8"))["activos"]
    else:
        ruta = BASE / (args.inventario or f"salidas/inventario_{proveedor}.json")
        if not ruta.exists():
            raise SystemExit(f"No existe {ruta.name}. Ejecuten el escalón 1 con ese proveedor, indiquen --inventario o usen --referencia.")
        activos = json.loads(ruta.read_text(encoding="utf-8"))
    if args.activo:
        activos = [a for a in activos if a["hostname"] == args.activo]
        if not activos:
            raise SystemExit(f"No hay un activo '{args.activo}' en el inventario.")

    SALIDAS.mkdir(exist_ok=True)
    filas, resumen, inicio, eventos, etiqueta = asyncio.run(principal(args, activos, proveedor))

    df, dr = pd.DataFrame(filas), pd.DataFrame(resumen)
    archivo = SALIDAS / f"cve_herramienta_{etiqueta}.xlsx"
    with pd.ExcelWriter(archivo, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="CVE por activo")
        dr.to_excel(xw, index=False, sheet_name="Resumen")
    (SALIDAS / f"cve_herramienta_{etiqueta}.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    agregados = sum(f["¿Lo devolvió la herramienta?"] != "Sí" for f in filas)
    print(f"\n{len(filas)} CVE reportados · {agregados} agregados por el modelo sin respaldo de la herramienta · {time.time() - inicio:.0f} s")
    print(f"Detalle en {archivo.relative_to(BASE)} · registro MCP ({eventos} eventos) en salidas/mcp_registro_{etiqueta}.jsonl")


if __name__ == "__main__":
    main()
