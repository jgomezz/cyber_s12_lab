# Hora cero II · La puerta del proveedor · Grupo 3 · Hogwarts · caja de herramientas

Martes 24 de noviembre de 2026, 07:30. El EDR de sga-app-02 detecta un ejecutable nuevo. Alguien entró por la VPN de
proveedores con cuentas de **AulaNube**. Tienen cinco inyecciones y esta caja de herramientas.

## Qué hay en la caja

| Carpeta | Caso de uso del curso | Qué trae de su caso |
| --- | --- | --- |
| `clase06_normativo/` | Clase 6 · Políticas y análisis normativo con IA (anonimizar, RAG sobre el reglamento, matriz de brechas) | Su política de seguridad y el contrato con AulaNube |
| `clase07_inventario/` | Clase 7 · Inventario de activos y vulnerabilidades con IA (normalizar, CVE con herramienta MCP, validar y priorizar) | El inventario en bruto de Universidad de Hogwarts |
| `clase09_codigo/` | Clase 9 · Revisión de código seguro con IA sobre MCP (Bandit, Semgrep, pip-audit, controles) | La API de integración con AulaNube |
| `clase10_triage/` | Clase 10 · Triage de un incidente con IA y RAG (SIEM, CMDB, directorio, inteligencia, historial, ATT&CK) | El SOC de Universidad de Hogwarts: seis días de logs y cuatro alertas |
| `evidencias/` | Sin herramienta: los archivos en bruto | Registro de la VPN, reporte estático de la muestra, boletín de vulnerabilidades, código, contrato, directorio de crisis y playbooks vigentes |

Cada laboratorio funciona igual que en clase (mismo `.env`, mismos proveedores, mismos controles C1 a C3).

## Las reglas del juego

1. **No todos los casos de uso sirven para todo.** Antes de correr nada, decidan cuál les sirve para la inyección y por qué.
   Algunos no sirven para ninguna; otros sirven para más de una. A veces lo más rápido es leer la evidencia en bruto.
2. **Cada respuesta parte diciendo qué caso de uso usaron** (o «ninguno: evidencia en bruto») y qué les mostró. Sin eso, no hay puntaje de evidencia.
3. La IA propone y el grupo decide. Verifiquen contra los datos lo que les diga cualquier herramienta (C3).
4. **Giros.** En algunas inyecciones la realidad no calza con lo que dice el libro. Usen la IA para saber qué dice el libro (NIST, ISO, CIS) y luego contrástenlo con lo que tienen. Pídanle el identificador exacto de cada control y verifíquenlo: la IA puede inventar números.

Los datos son ficticios.
