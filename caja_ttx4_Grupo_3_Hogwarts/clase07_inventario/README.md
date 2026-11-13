> TTX #4: mismo laboratorio de la Clase 7 con el inventario de **Universidad de Hogwarts** (data/inventario_bruto.csv).
> Ojo: el plan priorizado del escalón 3 usa CVSS × criticidad. ¿Es eso lo que importa en ESTE incidente?

# Clase 7 · Laboratorio: inventario de activos y vulnerabilidades con IA

**Caso (TTX #4):** Universidad de Hogwarts (una universidad privada (38.000 estudiantes y egresados)) tiene su inventario repartido en tres fuentes: la CMDB, una planilla de TI y un escaneo de red. Antes de priorizar parches necesita un inventario único y la lista de vulnerabilidades conocidas de cada activo, sin creerle a ciegas al modelo.

**Lo que van a construir:** un flujo que normaliza el inventario con **salida estructurada**, busca CVE con un modelo que **llama a una herramienta servida por MCP** y **valida** cada CVE propuesto para detectar los inventados.

**Tiempo total:** unos 85 minutos, en equipos de tres (tiempos referenciales).

| Escalón | Qué hacen | Tiempo | Tecnología |
|---|---|---|---|
| 1 · Obligatorio | Normalizar el inventario con salida estructurada | ~20 min | Pydantic, Ollama Cloud (120b y 20b) |
| 2 · Objetivo de la clase | El modelo busca CVE llamando a una herramienta por MCP | ~20 min | Tool calling con LiteLLM y servidor MCP |
| 3 · Comparar | ¿Inventa CVE sin herramienta? Validar y priorizar | ~20 min | Validador contra caché y NVD |
| 4 · Desafío (equipos rápidos) | Los CVE de un chat gratuito, validados | ~15 min | Claude.ai, ChatGPT o Le Chat |

Al final, todos completan la hoja **Riesgos OWASP** de la planilla (~10 min).

## Roles del equipo (rotan en cada escalón)

| Escalón | Piloto | Navegante | Analista |
|---|---|---|---|
| 1 | A | B | C |
| 2 | B | C | A |
| 3 | C | A | B |
| 4 y riesgos | A | B | C |

**Piloto:** ejecuta y comparte pantalla · **Navegante:** sigue esta guía y anticipa errores · **Analista:** revisa resultados y completa `Planilla del lab - Clase 7.xlsx`. Basta con que **un** integrante tenga el ambiente funcionando.

---

## 0. Preparación

Python 3.11 o superior y el archivo `.env` con sus claves (ver *Guía 0: preparación del ambiente y creación de cuentas*). Basta con **Ollama Cloud**; los demás proveedores sirven para comparar.

| Proveedor (`--proveedor`) | Modelo | Clave en `.env` | Uso en el lab |
|---|---|---|---|
| `ollama_cloud` (por defecto) | gpt-oss:120b | `OLLAMA_API_KEY` | Modelo principal |
| `ollama_cloud_20b` | gpt-oss:20b | la misma `OLLAMA_API_KEY` | Segundo modelo, en la misma cuenta |
| `groq` | qwen/qwen3.8-27b | `GROQ_API_KEY` | Alternativa rápida para comparar |
| `nvidia` | openai/gpt-oss-20b | `NVIDIA_API_KEY` | Alternativa para comparar |
| `ollama_local` (opcional) | llama3.2:3b | no necesita | En su equipo: nada sale de él (ver sección final) |

**Windows (PowerShell)**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # y peguen sus claves
python check_env.py
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python check_env.py
```

`check_env.py` debe mostrar **OK** en `ollama_cloud` y en al menos otro proveedor (`ollama_cloud_20b` cuenta). Si no instalaron Ollama local, `ollama_local` aparece como **OPCIONAL**: es lo esperado. Para cambiar de modelo no se toca código: se usa `--proveedor` o se edita `config.yaml`.

---

## Escalón 1 · Normalizar el inventario (obligatorio, ~20 min)

**Pregunta:** ¿puede un modelo convertir registros desordenados en un inventario confiable?

```bash
python escalon_1_normalizar.py                       # Ollama Cloud (por defecto)
python escalon_1_normalizar.py --proveedor ollama_cloud_20b    # modelo más pequeño (20b)
```

Cada registro de `data/inventario_bruto.csv` se convierte en un objeto `Activo` (hostname, tipo, entorno, sistema operativo, software con versión, responsable y criticidad) validado con **Pydantic**. Si el JSON no es válido, el script reintenta una vez explicando el error. Luego une los duplicados (api-pagos-01 aparece en la CMDB y en el escaneo) y compara con `data/inventario_esperado.json`.

**Qué revisar** en `salidas/inventario_<proveedor>.xlsx`, hoja **Evaluación**:

- ¿Qué criticidades no coinciden con la referencia? ¿Quién tiene razón? (jenkins-ci y conciliacion-01 son discutibles.)
- ¿Inventó alguna versión o se le escapó software?
- Busquen el registro **TI-080**: su campo responsable trae una fórmula de Excel. El script la neutraliza; prueben `--sin-sanear` y abran el Excel para ver el riesgo **LLM10** (no hagan clic en el enlace: apunta a una IP de documentación).

---

## Escalón 2 · Buscar CVE con una herramienta por MCP (~20 min)

**Pregunta:** si el modelo puede consultar una fuente confiable, ¿la usa bien? ¿Y qué pasa realmente entre el modelo y la herramienta?

```bash
python escalon_2_herramienta.py --referencia --activo api-pagos-01               # un activo: lean el registro paso a paso
python escalon_2_herramienta.py --referencia --activo api-pagos-01 --detalle 2   # cada mensaje JSON completo
python escalon_2_herramienta.py --proveedor ollama_cloud_20b --detalle 0          # todo el inventario, solo el resumen
python escalon_2_herramienta.py --proveedor groq --inventario salidas/inventario_ollama_cloud.json
```

La herramienta `buscar_cve(producto, version)` vive ahora en un **servidor MCP** (`mcp_servidor_cve.py`) que responde desde `data/cve_cache.json`. El script lo lanza como otro proceso, abre la sesión MCP, le pregunta qué herramientas tiene y se las entrega al modelo. Cuando el modelo pide una llamada, el script la reenvía al servidor y le devuelve el resultado al modelo, que al final responde con un JSON de vulnerabilidades.

En pantalla queda cada paso numerado:

| Etiqueta | Qué es |
|---|---|
| `MCP →` / `MCP ←` | Mensajes JSON-RPC entre el script (cliente) y el servidor: `initialize`, `tools/list`, `tools/call` y sus respuestas |
| `LLM →` / `LLM ←` | Cada vuelta con el modelo: qué se le envía y qué llamadas pide |
| `[servidor]` | Lo que registra el propio servidor al recibir y responder |
| `INFO` | El lanzamiento del servidor, la definición de la herramienta tal como la ve el modelo y el activo en curso |

Todo queda además en `salidas/mcp_registro_<proveedor>.jsonl`.

**Qué revisar en el registro** (con un solo activo):

- ¿En qué evento conoce el modelo la herramienta? ¿Qué información recibe de ella (evento "así queda la herramienta")?
- ¿Quién ejecuta la búsqueda: el modelo, el script o el servidor?
- ¿Cuántas llamadas pidió el modelo frente al software del activo?

**Qué revisar** en `salidas/cve_herramienta_<proveedor>.xlsx`:

- Hoja **Resumen**: ¿llamó la herramienta para todo el software (columna *Software consultado*)?
- Hoja **CVE por activo**: ¿agregó algún CVE que la herramienta no le devolvió?
- ¿Qué activos tienen el sistema operativo sin soporte?

---

## Escalón 3 · ¿Inventa CVE sin herramienta? (~20 min)

```bash
python escalon_3_validar.py --proveedor ollama_cloud
python escalon_3_validar.py --proveedor ollama_cloud_20b
python escalon_3_validar.py --proveedor groq --en-linea     # valida en NVD; lento (6 s por CVE)
```

El script pregunta al modelo, **sin herramienta**, qué CVE afectan a cada software y clasifica cada respuesta: *Verificado (aplica)*, *Existe, pero no aplica a esa versión*, *Existe, pero es de otro producto*, *No existe en NVD* o *Sin verificar*. Compara con lo obtenido con herramienta y arma un **plan priorizado** (CVSS × peso de la criticidad del activo).

**Qué revisar:** el porcentaje confiable de cada método, los CVE que existen pero no aplican (por ejemplo, Heartbleed en OpenSSL 3.0.2) y si el plan priorizado tiene sentido para Andina Pagos.

---

## Escalón 4 · Desafío (equipos rápidos, ~15 min)

Sigan `escalon_4_desafio.md`.

## Cierre del lab: riesgos OWASP (~10 min, todos los equipos)

Completen la hoja **Riesgos OWASP**, con foco en:

- **LLM10 Manejo inadecuado de la salida:** la fórmula del registro TI-080 llegando al Excel.
- **LLM07 Desinformación:** un CVE inventado o que no aplica, copiado a un informe.

## Para el plenario (3 minutos por equipo)

1. ¿Qué porcentaje de los CVE propuestos sin herramienta resultó confiable, y con herramienta?
2. ¿Qué activo pondrían primero en el plan de parches y por qué?
3. ¿Dónde pondrían la validación en un proceso real de Andina Pagos?

## Estructura de la carpeta

```
lab/
├── README.md
├── config.yaml                # proveedores y validación en línea
├── .env.example
├── llm.py · check_env.py      # kit común
├── diag_nvidia.py             # diagnóstico de errores 401 de NVIDIA
├── cve.py                     # búsqueda en el caché de CVE y validador
├── mcp_servidor_cve.py        # servidor MCP que expone buscar_cve (lo lanza el escalón 2)
├── escalon_1_normalizar.py
├── escalon_2_herramienta.py
├── escalon_3_validar.py
├── escalon_4_desafio.md
└── data/
    ├── inventario_bruto.csv        # 15 registros de 3 fuentes (ficticios)
    ├── inventario_esperado.json    # respuesta de referencia
    └── cve_cache.json              # 17 CVE reales con rangos simplificados
```

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `does not support tools` o error 400 en el escalón 2 | Ese modelo no soporta herramientas: usen `--proveedor groq` u `ollama_cloud`. |
| El modelo responde sin llamar la herramienta | Pasa más con modelos pequeños (20b, Ollama local): anótenlo y comparen con `ollama_cloud` o `groq`. |
| `Connection refused` en `ollama_local` | Abran la aplicación Ollama o ejecuten `ollama serve`. Si no instalaron Ollama, ignórenlo: es opcional. |
| `model not found` en `ollama_local` | `ollama pull llama3.2:3b`. |
| Error 401 en cualquier proveedor | Clave mal copiada o con un espacio al final: revisen `.env` y prueben con `python check_env.py <proveedor>`. |
| NVIDIA da `401 Invalid JWT serialization` | El modelo no acepta la clave en el endpoint gratuito. Ejecuten `python diag_nvidia.py <modelo>`: revisa la clave y si el modelo está en la lista gratuita. |
| NVIDIA responde que el modelo está deprecado o no existe | Elijan en build.nvidia.com un modelo con *Free Endpoint* y cambien `model` de `nvidia` en `config.yaml` (con el prefijo `openai/`). |
| `ModuleNotFoundError: No module named 'mcp'` | Falta instalar las dependencias nuevas: `pip install -r requirements.txt`. |
| `No module named 'mcp.server.fastmcp'` | Se instaló la versión 2 del SDK de MCP: `pip install "mcp>=1.10,<2"`. |
| El escalón 2 queda detenido después de `initialize` | El servidor no arrancó: ejecuten `python mcp_servidor_cve.py` para ver el error (se cierra con Ctrl+C). |
| `No existe salidas/inventario_<proveedor>.json` | Ejecuten el escalón 1 con ese proveedor o usen `--referencia`. |
| `--en-linea` muy lento o error 403 | NVD limita las consultas sin clave: esperen o validen solo algunos CVE con `--validar`. |
| Error 429 | Límite gratuito por minuto: esperen un minuto o cambien de proveedor. |


## Opcional: Ollama en su equipo

Solo si el computador tiene 16 GB de RAM o GPU (con 8 GB funciona, pero lento). La ventaja: nada sale del equipo.

1. Instalen Ollama desde [ollama.com/download](https://ollama.com/download). En Linux: `curl -fsSL https://ollama.com/install.sh | sh`. Queda corriendo en segundo plano.
2. Descarguen el modelo y pruébenlo (salgan con `/bye`):
    ```bash
    ollama pull llama3.2:3b
    ollama run llama3.2:3b "Hola, responde en una frase"
    ```
3. Verifiquen con `ollama list` (debe aparecer `llama3.2:3b`) y luego `python check_env.py ollama_local` (debe decir OK). No hay que tocar `config.yaml`.
4. Úsenlo con `--proveedor ollama_local` en cualquier escalón, o cambien `default: ollama_cloud` por `default: ollama_local` en `config.yaml`.

Los modelos de 3B suelen no llamar la herramienta del escalón 2 o llamarla solo una vez: es un buen hallazgo para comparar con los modelos en la nube.

---

**Todos los activos de Andina Pagos son ficticios.** Los CVE del caché son reales y sus rangos de versiones están simplificados para el ejercicio: verifiquen siempre en nvd.nist.gov.
