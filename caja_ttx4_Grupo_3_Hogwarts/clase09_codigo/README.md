# Clase 9 · Revisión de código seguro con IA sobre MCP · código de Universidad de Hogwarts

El mismo laboratorio de la Clase 9. La aplicación que se revisa (`app_andina/app.py`, se mantuvo el nombre de la carpeta) es ahora la
**API de integración de Universidad de Hogwarts con AulaNube**. La referencia del profesor (`data/referencia_hallazgos.json`) es la de este código.

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-opcional.txt     # Semgrep (opcional)
copy .env.example .env
python a_mano.py                              # las alertas de Bandit, una por una
python revisor.py --controles todos --sin-parche
python revisor.py --controles C2,C3,C4 --sin-parche   # sin C1: ¿qué pasa con el comentario dirigido al revisor?
python -m pytest tests -q                     # dos pruebas de seguridad fallan con el código original
```
