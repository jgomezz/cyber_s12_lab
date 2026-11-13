# Escalón 4 · Desafío: ¿qué CVE dice un chat gratuito?

**Tiempo:** unos 15 minutos, para los equipos que terminaron el escalón 3.
**Objetivo:** comprobar si un chat gratuito (Claude.ai, ChatGPT o Le Chat) inventa o equivoca CVE cuando no tiene herramientas, y validar sus respuestas con el mismo validador del lab.

## Antes de pegar nada

Respondan en la hoja **E4 Desafío** de la planilla:

1. El inventario es sintético, pero en una empresa real, ¿podrían pegar hostnames, versiones e IP internas en un chat público? ¿Por qué?
2. ¿En qué alcance de la Matriz de Alcance (Clase 4) queda este uso?

## Prompt

Peguen solo estas líneas (sin hostnames ni IP):

```
Eres analista de vulnerabilidades. Para cada software y versión, lista los CVE conocidos
que afectan a ESA versión exacta, con su puntaje CVSS. Si no estás seguro, dilo.

- nginx 1.18.0
- OpenSSL 3.0.2
- OpenSSH 8.4p1
- OpenSSH 9.6p1
- Log4j 2.14.1
- Grafana 8.2.6
- FortiOS 7.0.10
```

Si el chat tiene búsqueda web, pidan una segunda respuesta **con** búsqueda y comparen.

## Validen cada CVE que les entregue

```bash
python escalon_3_validar.py --validar CVE-AAAA-NNNN CVE-AAAA-NNNN --producto OpenSSL --version 3.0.2
python escalon_3_validar.py --validar CVE-AAAA-NNNN --producto OpenSSH --version 8.4p1 --en-linea
```

Preguntas trampa a las que deben poner atención:

- **OpenSSL 3.0.2 y Heartbleed (CVE-2014-0160):** Heartbleed afecta solo a 1.0.1 a 1.0.1f.
- **OpenSSH 8.4p1 y regreSSHion (CVE-2024-6387):** el rango afectado empieza en 8.5p1.

## Comparen

- ¿Cuántos CVE entregó el chat y cuántos quedaron **Verificado (aplica)**?
- ¿Alguno no existe en NVD?
- ¿El chat dijo "no estoy seguro" alguna vez?
- ¿Qué cambiarían en el proceso de Andina Pagos para que un analista no copie CVE sin validar?
