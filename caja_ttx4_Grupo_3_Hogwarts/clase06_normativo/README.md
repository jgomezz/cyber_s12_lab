> TTX #4: mismo laboratorio de la Clase 6 con los documentos de **Universidad de Hogwarts**: su política de seguridad y el contrato con **AulaNube** (carpeta data/). El reglamento y los requisitos son los mismos de la clase.

# Clase 6 · Laboratorio: políticas y análisis normativo con IA

**Versión 6.1** · octubre de 2026

**Caso:** Andina Pagos S.A., fintech de pagos ficticia de Lima, quiere saber si su Política de Seguridad de la Información cumple el Reglamento de la Ley 29733 de protección de datos personales (DS 016-2024-JUS), sin exponer información interna.

**Lo que van a construir:** un flujo que convierte y anonimiza las políticas en su equipo, consulta el reglamento con RAG y genera una matriz de brechas en Excel, comparando dos modelos en la nube. La anonimización ocurre siempre en su equipo, antes de que algo salga.

**Novedades de la versión 6.1**

- Ya no se usa Mistral (dejó de tener API gratuita).
- Proveedores disponibles: Ollama Cloud (principal), Groq, NVIDIA y Ollama local (opcional).
- Los embeddings del RAG son locales: se calculan en su equipo, sin API ni descargas.
- NVIDIA usa `openai/gpt-oss-20b`, porque el endpoint gratuito del modelo anterior fue deprecado.

**Tiempo total:** unos 85 minutos, en equipos de tres (tiempos referenciales).

| Escalón | Qué hacen | Tiempo | Tecnología |
|---|---|---|---|
| 1 · Obligatorio | Convertir y anonimizar las políticas | ~15 min | markitdown, Presidio (local) y revisión con Ollama Cloud |
| 2 · Objetivo de la clase | Preguntar al reglamento con RAG | ~15 min | LlamaIndex, Chroma, embeddings locales |
| 3 · Comparar modelos | Matriz de brechas con dos modelos | ~30 min | Salida estructurada con Pydantic |
| 4 · Desafío (equipos rápidos) | El mismo análisis en un chat gratuito | ~15 min | Claude.ai, ChatGPT o Le Chat |

Al final, todos completan la hoja **Riesgos OWASP** de la planilla (~10 min).

---

## Roles del equipo (rotan en cada escalón)

- **Piloto:** ejecuta los comandos y comparte pantalla.
- **Navegante:** lee esta guía, anticipa el siguiente paso y detecta errores antes de ejecutar.
- **Analista:** revisa los resultados y completa la planilla `Planilla del lab - Clase 6.xlsx`.

| Escalón | Piloto | Navegante | Analista |
|---|---|---|---|
| 1 | A | B | C |
| 2 | B | C | A |
| 3 | C | A | B |
| 4 y riesgos | A | B | C |

Si el equipo tiene cuatro integrantes, el cuarto es **Revisor de riesgos**: completa la hoja Riesgos OWASP durante todo el lab y entra a la rotación.

Basta con que **un** integrante tenga el ambiente funcionando.

---

## 0. Preparación (si no hicieron la Guía 0, háganla ahora)

Necesitan Python 3.11 o superior y el archivo `.env` con sus claves (ver *Guía 0: preparación del ambiente y creación de cuentas*). Basta con **Ollama Cloud**; los demás proveedores sirven para comparar.

| Proveedor (`--proveedor`) | Modelo | Clave en `.env` | Uso en el lab |
|---|---|---|---|
| `ollama_cloud` (por defecto) | gpt-oss:120b | `OLLAMA_API_KEY` | Modelo principal |
| `ollama_cloud_20b` | gpt-oss:20b | la misma `OLLAMA_API_KEY` | Segundo modelo, en la misma cuenta |
| `groq` | llama-3.3-70b-versatile | `GROQ_API_KEY` | Alternativa rápida para comparar |
| `nvidia` | openai/gpt-oss-20b | `NVIDIA_API_KEY` | Alternativa para comparar |
| `ollama_local` (opcional) | llama3.2:3b | no necesita | En su equipo: nada sale de él (ver sección final) |

Desde esta carpeta:

**Windows (PowerShell)**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download es_core_news_md
copy .env.example .env      # y peguen sus claves en .env
python check_env.py
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_md
cp .env.example .env        # y peguen sus claves en .env
python check_env.py
```

`check_env.py` debe mostrar **OK** en `ollama_cloud` y en al menos otro proveedor (`ollama_cloud_20b` cuenta). Si no instalaron Ollama local, `ollama_local` aparece como **OPCIONAL**: es lo esperado. Para cambiar de modelo no se toca código: se usa `--proveedor` o se edita `config.yaml`.

---

## Escalón 1 · Convertir y anonimizar (obligatorio, ~15 min)

**Pregunta:** ¿qué datos de Andina Pagos saldrían de la empresa si enviáramos estas políticas a una API gratuita?

```bash
python escalon_1_anonimizar.py
```

El script hace tres cosas, todas en su equipo salvo que cambien el proveedor:

1. **Convierte** `data/politica_seguridad_andina_pagos.docx` y `data/procedimiento_accesos_respaldos.pdf` a Markdown (`salidas/md/`).
2. **Anonimiza** con Presidio nombres, correos, teléfonos, DNI, IP y el nombre de la empresa, y los reemplaza por etiquetas como `<PERSONA_1>` (`salidas/anonimizado/`). La tabla para revertir los reemplazos queda en `salidas/privado/` y **nunca se comparte**.
3. **Revisa** con Ollama Cloud, sobre el texto ya anonimizado, si quedó algún dato identificable (`salidas/anonimizado/revision_*.json`).

**Qué hacer con el resultado**

- Abran `salidas/anonimizado/procedimiento_accesos_respaldos.md` y busquen datos que se hayan escapado.
- Busquen **falsos positivos**: palabras que Presidio reemplazó sin ser datos personales. Agréguenlas a `anonimizacion.permitidos` en `config.yaml` y vuelvan a ejecutar.
- Anoten en la hoja **E1 Anonimización**: cuántos datos detectó Presidio, qué encontró el modelo, falsos positivos y falsos negativos.

---

## Escalón 2 · Preguntar al reglamento con RAG (~15 min)

**Pregunta:** ¿puede un modelo responder sobre el reglamento sin inventar, citando el artículo?

```bash
python escalon_2_rag.py
```

La primera vez crea el índice vectorial del reglamento en `salidas/chroma/` (un fragmento por artículo). Luego responde 6 preguntas y guarda las respuestas en `salidas/respuestas_rag_<proveedor>.md`.

Repitan con otro modelo y comparen:

```bash
python escalon_2_rag.py --proveedor ollama_cloud_20b
python escalon_2_rag.py --pregunta "¿Qué debe contener el documento de seguridad?"
```

**Qué revisar**

- ¿Cada cita `[Art. N]` corresponde de verdad a lo que dice ese artículo en `data/reglamento_ley29733_extracto.md`?
- La pregunta 6 (monto de la multa) **no** está en el extracto: ¿el modelo lo reconoce o inventa una cifra?
- Anoten en la hoja **E2 RAG** si cada respuesta es correcta, si la cita es correcta y el tiempo.

> Los embeddings son **locales** (`embeddings.provider: local`): se calculan en su equipo, sin descargas ni API, buscando por los términos de cada artículo. Si tienen Ollama local (opcional), pueden cambiar a `ollama` para comparar con embeddings semánticos; el índice se reconstruye solo.

---

## Escalón 3 · Matriz de brechas con dos modelos (~30 min)

**Pregunta:** ¿cumple la política de Andina Pagos los 16 requisitos de `data/requisitos_reglamento.json`? ¿Responden igual dos modelos distintos?

```bash
python escalon_3_brechas.py --proveedor ollama_cloud
python escalon_3_brechas.py --proveedor ollama_cloud_20b
python escalon_3_brechas.py --comparar salidas/matriz_brechas_ollama_cloud.xlsx salidas/matriz_brechas_ollama_cloud_20b.xlsx
```

Para cada requisito, el script recupera los fragmentos más parecidos de la política anonimizada, pide al modelo un JSON con estado, evidencia, brecha y recomendación, lo valida con Pydantic y comprueba si la evidencia citada **existe textualmente** en la política.

**Qué revisar**

- `salidas/comparacion_modelos.xlsx`: los requisitos donde los modelos no coinciden. Lean la política y decidan quién tiene razón.
- La columna **¿Evidencia verificada?**: un "No" indica que el modelo citó algo que no está en la política.
- Anoten en la hoja **E3 Comparación** el tiempo, los resultados y su juicio de calidad de cada modelo.

> También pueden comparar con `--proveedor groq`, `nvidia` u `ollama_local`. Ollama Cloud gratuito atiende una consulta a la vez por cuenta: no corran dos escalones al mismo tiempo.

---

## Escalón 4 · Desafío para equipos rápidos (~15 min)

Sigan `escalon_4_desafio.md`: el mismo análisis en un chat gratuito, con los prompts de la clase anterior adaptados, y una comparación con su matriz.

---

## Cierre del lab: riesgos OWASP (~10 min, todos los equipos)

Completen la hoja **Riesgos OWASP** de la planilla para lo que construyeron hoy. Pongan especial atención a:

- **LLM02 Divulgación de información sensible:** ¿qué pasa si la anonimización falla y el texto llega a una API gratuita que entrena con sus datos?
- **LLM07 Desinformación:** ¿qué pasa si la Gerencia Legal confía en una brecha o una cita inventada?

---

## Para el plenario (3 minutos por equipo)

1. ¿Qué dato se les escapó a la anonimización y cómo lo detectaron?
2. ¿Qué modelo usarían para la matriz de brechas de Andina Pagos y por qué?
3. ¿Cuál es la brecha más importante de la política frente al reglamento?

---

## Estructura de la carpeta

```
lab/
├── README.md                       # esta guía
├── VERSION.txt                     # versión 6.1 y cambios
├── diag_nvidia.py                  # diagnóstico de la API de NVIDIA
├── config.yaml                     # proveedores, embeddings y anonimización
├── .env.example                    # plantilla para sus claves (copiar como .env)
├── llm.py                          # cliente único de modelos (kit común)
├── check_env.py                    # prueba de proveedores
├── rag.py                          # funciones de RAG compartidas
├── escalon_1_anonimizar.py
├── escalon_2_rag.py
├── escalon_3_brechas.py
├── escalon_4_desafio.md
├── data/
│   ├── politica_seguridad_andina_pagos.docx      # ficticia
│   ├── procedimiento_accesos_respaldos.pdf       # ficticio
│   ├── reglamento_ley29733_extracto.md           # artículos 34 a 58
│   └── requisitos_reglamento.json                # 16 requisitos a evaluar
└── salidas/                        # se crea al ejecutar
```

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `Can't find model 'es_core_news_md'` | Ejecuten `python -m spacy download es_core_news_md` con el entorno virtual activo. |
| `Connection refused` en `ollama_local` | Abran la aplicación Ollama o ejecuten `ollama serve`. Si no instalaron Ollama, ignórenlo: es opcional. |
| `model not found` en `ollama_local` | `ollama pull llama3.2:3b` (y `ollama pull nomic-embed-text` si usan embeddings `ollama`). |
| Error 401 en cualquier proveedor | Clave mal copiada o con un espacio al final: revisen `.env` y prueben con `python check_env.py <proveedor>`. |
| NVIDIA da `401 Invalid JWT serialization` | El modelo no acepta la clave en el endpoint gratuito. Ejecuten `python diag_nvidia.py <modelo>`: revisa la clave y si el modelo está en la lista gratuita. |
| NVIDIA responde que el modelo está deprecado | Elijan en build.nvidia.com un modelo con *Free Endpoint* disponible y cambien `model` de `nvidia` en `config.yaml` (con el prefijo `openai/`). |
| El RAG recupera artículos que no corresponden | Los embeddings locales buscan por términos: reformulen la pregunta con las palabras del reglamento o prueben `-k 6`. |
| El escalón 3 tarda mucho o da error 429 con Ollama Cloud | El plan gratuito atiende una consulta a la vez: usen `--proveedor groq` o `nvidia` para el segundo modelo. |
| `No hay documentos anonimizados` | Ejecuten primero el escalón 1. |
| Error 429 | Límite gratuito por minuto: esperen un minuto o cambien de proveedor. |

## Opcional: Ollama en su equipo

Solo si el computador tiene 16 GB de RAM o GPU (con 8 GB funciona, pero lento). La ventaja: nada sale del equipo, ni siquiera el texto anonimizado.

1. Instalen Ollama desde [ollama.com/download](https://ollama.com/download). En Linux: `curl -fsSL https://ollama.com/install.sh | sh`. Queda corriendo en segundo plano.
2. Descarguen el modelo y pruébenlo (salgan con `/bye`):
    ```bash
    ollama pull llama3.2:3b
    ollama run llama3.2:3b "Hola, responde en una frase"
    ```
3. Verifiquen el servidor con `ollama list` (debe aparecer `llama3.2:3b`) y luego `python check_env.py ollama_local` (debe decir OK). No hay que tocar `config.yaml`.
4. Úsenlo con `--proveedor ollama_local` en cualquier escalón, o cambien `default: ollama_cloud` por `default: ollama_local` en `config.yaml`.
5. Para embeddings semánticos en vez de los locales: `ollama pull nomic-embed-text`, cambien `embeddings.provider: local` por `ollama` y ejecuten el escalón 2 con `--reconstruir`.

Si el equipo se queda sin memoria, usen `llama3.2:1b` (`ollama pull llama3.2:1b` y cambien el `model` de `ollama_local`). El escalón 3 son 16 consultas: sin GPU puede tardar varios minutos.

---

**Todos los documentos de Andina Pagos son ficticios.** El reglamento es texto normativo público publicado en el diario oficial El Peruano el 30 de noviembre de 2024.
