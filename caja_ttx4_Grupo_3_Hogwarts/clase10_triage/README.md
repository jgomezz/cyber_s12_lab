# Clase 10 · Triage de un incidente asistido por IA, con RAG · datos de Universidad de Hogwarts

El mismo laboratorio de la Clase 10, con el SOC de **Universidad de Hogwarts** (una universidad privada (38.000 estudiantes y egresados)). Martes 24 de noviembre de 2026, 07:30.
Hay cuatro alertas en la cola (A-0001 a A-0004), una base de logs de seis días, la CMDB, el directorio, la inteligencia de
amenazas, el historial de incidentes de Universidad de Hogwarts y MITRE ATT&CK.

```bash
python -m venv .venv && .venv\Scripts\activate     # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                              # y su GROQ_API_KEY
python triage.py --cola                             # las cuatro alertas, priorizadas y relacionadas
python triage.py --alerta A-0001                    # triage de una alerta
python siem.py --usuario <cuenta>                   # la base de logs a mano
python rag.py historial "proveedor"                 # el historial a mano
python triage.py --controles C2,C3                  # sin C1: ¿qué pasa con el texto dirigido a la IA?
```
`--simulado` solo prueba que el programa corre: con datos de un caso nuevo no analiza nada.
