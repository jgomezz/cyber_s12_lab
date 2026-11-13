# Índice de playbooks de respuesta a incidentes · Universidad de Hogwarts (ficticio)

| ID | Playbook | Versión | Última revisión | Dueño | Estado |
| --- | --- | --- | --- | --- | --- |
| PB-01 | Phishing | 1.2 | 2023-05 | Jefe de TI | Vigente |
| PB-02 | Ransomware | 1.0 | 2022-08 | Jefe de TI | Vigente (sin probar) |
| PB-03 | Pérdida de equipo | 1.0 | 2022-08 | Jefe de TI | Vigente |
| PB-04 | Fuga de datos personales | — | — | — | No existe |
| PB-05 | Caída de servicio crítico | 0.9 | 2021-11 | Jefe de Infraestructura (ya no trabaja aquí) | Borrador |
| PB-06 | DDoS | — | — | — | No existe |
| PB-07 | Compromiso de terceros | — | — | — | En elaboración (acción de INC-2025-021, vencida 2025-09-30) |

## PB-02 Ransomware · versión 1.0 (agosto de 2022)

1. Aislar el equipo afectado de la red. No apagarlo.
2. Ingresar a los servidores con la cuenta de emergencia adm-emergencia (sobre sellado en la caja fuerte de TI).
3. Avisar al Jefe de TI y a Gerencia General.
4. Escalar a la mesa 24x7 de AulaNube (Anexo C del contrato) para coordinar la restauración de los servidores desde el NAS de respaldos.
5. Cambiar las contraseñas de los administradores.
6. Restaurar desde el último respaldo y volver a operar.
7. Cerrar el ticket en la mesa de ayuda.

Nota: este playbook no se ha ejercitado. No considera notificación a la autoridad ni a los titulares.
