"""Búsqueda y validación de CVE (caché local de referencia + consulta opcional a NVD).

Es la "herramienta" que el modelo puede llamar en el escalón 2 y el validador del escalón 3.
"""
import json
import re
import time

from pathlib import Path

BASE = Path(__file__).resolve().parent  # sin importar llm.py: el servidor MCP arranca más rápido

CACHE = json.loads((BASE / "data" / "cve_cache.json").read_text(encoding="utf-8"))
FORMATO_CVE = re.compile(r"^CVE-(1999|20\d{2})-\d{4,7}$")
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def normalizar_producto(producto: str) -> str:
    p = re.sub(r"\s+", " ", (producto or "").lower().strip())
    p = re.sub(r"\s*\(.*?\)", "", p)
    return CACHE["alias"].get(p, p)


def version_tupla(version: str) -> tuple:
    """'8.9p1' -> (8, 9, 1); '2.0-beta9' -> (2, 0, 9). Suficiente para comparar rangos simplificados."""
    return tuple(int(n) for n in re.findall(r"\d+", version or "")) or (0,)


def en_rango(version: str, rangos: list) -> bool:
    v = version_tupla(version)
    return any(version_tupla(a) <= v <= version_tupla(b) for a, b in rangos)


def buscar_cve(producto: str, version: str) -> list[dict]:
    """CVE del caché que afectan a ese producto y versión."""
    prod = normalizar_producto(producto)
    return [{"cve": c["cve"], "cvss": c["cvss"], "versiones_afectadas": c["versiones_afectadas"], "descripcion": c["descripcion"]}
            for c in CACHE["cves"] if c["producto"] == prod and en_rango(version, c["rangos"])]


def fin_de_soporte(sistema: str) -> str | None:
    s = (sistema or "").lower()
    return next((f for k, f in CACHE["fin_de_soporte"].items() if k in s), None)


def consultar_nvd(cve_id: str, timeout: int = 20) -> dict | None:
    """Consulta un CVE en la API pública de NVD. Devuelve None si no existe; lanza excepción si no hay red."""
    import httpx
    r = httpx.get(NVD_URL, params={"cveId": cve_id}, timeout=timeout)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    vulns = r.json().get("vulnerabilities", [])
    time.sleep(6)  # sin clave, NVD permite unas 5 consultas cada 30 segundos
    if not vulns:
        return None
    c = vulns[0]["cve"]
    desc = next((d["value"] for d in c.get("descriptions", []) if d["lang"] == "en"), "")
    return {"cve": cve_id, "descripcion": desc[:200], "publicado": c.get("published", "")[:10]}


def validar_cve(cve_id: str, producto: str = "", version: str = "", en_linea: bool = False) -> str:
    """Clasifica un CVE propuesto por el modelo.

    Formato inválido · Verificado (aplica) · Existe, pero no aplica a esa versión · Existe, pero es de otro producto ·
    Existe en NVD (no está en el caché) · No existe en NVD · Sin verificar (no está en el caché; usen --en-linea)
    """
    cve_id = (cve_id or "").strip().upper()
    if not FORMATO_CVE.match(cve_id):
        return "Formato inválido"
    reg = next((c for c in CACHE["cves"] if c["cve"] == cve_id), None)
    if reg:
        if producto and normalizar_producto(producto) != reg["producto"]:
            return "Existe, pero es de otro producto"
        if version and not en_rango(version, reg["rangos"]):
            return "Existe, pero no aplica a esa versión"
        return "Verificado (aplica)"
    if en_linea:
        try:
            return "Existe en NVD (no está en el caché)" if consultar_nvd(cve_id) else "No existe en NVD"
        except Exception as e:
            return f"Sin verificar (error de red: {type(e).__name__})"
    return "Sin verificar (no está en el caché; usen --en-linea)"
