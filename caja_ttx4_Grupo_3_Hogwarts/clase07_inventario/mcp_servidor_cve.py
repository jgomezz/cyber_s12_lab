"""Servidor MCP del laboratorio: expone la herramienta buscar_cve.

No se ejecuta a mano: lo lanza escalon_2_herramienta.py como un proceso aparte
y se comunica con él por la entrada y la salida estándar (transporte stdio),
con mensajes JSON-RPC. Es el mismo protocolo de cualquier servidor MCP real;
la diferencia es que este responde desde data/cve_cache.json y no desde NVD.

stdout queda reservado para el protocolo. Lo que el servidor registra va a
stderr y aparece en la consola del cliente con el prefijo [servidor].
"""
import json
import sys
import time
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from cve import buscar_cve as _buscar_cve  # la misma función y el mismo caché de antes

mcp = FastMCP("andina-cve", log_level="WARNING")  # sin los registros internos del SDK


def _log(texto: str) -> None:
    print(f"[servidor] {texto}", file=sys.stderr, flush=True)


@mcp.tool()
def buscar_cve(
    producto: Annotated[str, Field(description="Nombre del producto, por ejemplo nginx u OpenSSH")],
    version: Annotated[str, Field(description="Versión exacta, por ejemplo 1.18.0 u 8.9p1")],
) -> str:
    """Busca vulnerabilidades conocidas (CVE) que afectan a un producto en una versión exacta. Llámala una vez por cada software del activo."""
    t0 = time.perf_counter()
    _log(f"recibí tools/call buscar_cve(producto={producto!r}, version={version!r})")
    resultado = _buscar_cve(producto, version)
    texto = json.dumps(resultado, ensure_ascii=False)
    ids = ", ".join(r["cve"] for r in resultado) or "ninguno"
    _log(f"devuelvo {len(resultado)} CVE ({ids}) · {len(texto)} caracteres · {1000 * (time.perf_counter() - t0):.1f} ms")
    return texto


if __name__ == "__main__":
    _log("iniciado: espero mensajes JSON-RPC por stdin")
    mcp.run(transport="stdio")
