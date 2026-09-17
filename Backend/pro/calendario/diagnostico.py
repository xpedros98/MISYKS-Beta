"""Por qué no se puede leer un boletín: TLS, certificado o JavaScript.

Cuando una fuente falla hay que saber **cuál de los tres problemas es**, porque
la solución es distinta en cada caso y confundirlos lleva al atajo peligroso
(desactivar la verificación). Este módulo hace el mismo interrogatorio que uno
haría a mano, siempre en el mismo orden y dejando el diagnóstico por escrito.

Los tres casos vistos hasta ahora en boletines españoles, que son los que
justifican que esto exista:

- **Raíz de CA ausente.** El certificado es legítimo pero lo emite una
  autoridad del sector público que Python no trae: IZENPE (Gobierno Vasco),
  Firmaprofesional (Ajuntament de Barcelona). Se arregla añadiendo esa raíz
  concreta en `~/.misyks/ca/`, nunca desactivando la comprobación.
- **Handshake rechazado.** El servidor negocia con cifrados que OpenSSL ya no
  acepta por defecto (`portaldogc.gencat.cat`). No es un problema de confianza
  sino de protocolo, y bajar el nivel de seguridad es una decisión que toma una
  persona, no este programa.
- **Página montada con JavaScript.** Responde 200 y el HTML no trae el
  contenido (`dogc.gencat.cat`). Ninguna raíz arregla esto: hace falta un
  navegador.

No arregla nada por su cuenta. Solo dice qué pasa y qué haría falta.
"""
import re
import socket
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import certificados

AGENTE = "MISYKS/pro.calendario (despacho de abogados; lectura de calendario oficial)"

# Por debajo de esto, una página que responde 200 casi seguro trae solo el
# armazón. No es una medida exacta: es un aviso para que alguien mire.
MINIMO_TEXTO = 2000


def revisar(url, esperado=None, timeout=30):
    """Interroga una fuente. Devuelve un dict con el veredicto.

    Claves: `url`, `estado` (ok | dudoso | sin_contenido | ca_ausente |
    handshake | http | red), `detalle`, `emisor` y `remedio`.

    **`esperado` es lo que de verdad decide.** Medir el tamaño del texto no
    sirve para saber si una página se monta con JavaScript: el DOGC devuelve
    cuatro mil caracteres de menú y aviso de cookies, y por tamaño pasaba por
    buena. Lo que sí distingue es preguntar por algo que tiene que estar si la
    descarga ha servido de algo -- el nombre del municipio, el número de la
    orden --, que además es la misma idea que la cita: no se da por buena una
    lectura, se comprueba contra el texto. Sin `esperado`, el veredicto mejor
    posible es `dudoso`, y se dice así en vez de fingir certeza.
    """
    informe = {"url": url, "estado": None, "detalle": "", "emisor": None, "remedio": ""}
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]

    try:
        cuerpo = _descarga(url, timeout)
    except urllib.error.URLError as e:
        razon = str(getattr(e, "reason", e))
        # El emisor se lee **sin verificar** a propósito y solo para informar:
        # saber quién firma es justo lo que dice qué raíz hay que instalar.
        informe["emisor"] = emisor(host, timeout)
        if "CERTIFICATE_VERIFY_FAILED" in razon:
            informe["estado"] = "ca_ausente"
            informe["detalle"] = razon
            informe["remedio"] = (
                f"Descarga la raíz de «{informe['emisor'] or 'la autoridad emisora'}» "
                f"de su sede, comprueba su huella y déjala en {certificados.CA_DIR}."
            )
        elif "HANDSHAKE" in razon.upper() or "SSLV3" in razon.upper():
            informe["estado"] = "handshake"
            informe["detalle"] = razon
            informe["remedio"] = (
                "El servidor negocia con cifrados que OpenSSL rechaza por defecto. "
                "Usar un navegador, o decidir expresamente rebajar el nivel de "
                "seguridad para este host (no lo hace el programa por su cuenta)."
            )
        else:
            informe["estado"] = "red"
            informe["detalle"] = razon
            informe["remedio"] = "Comprobar conectividad o si la URL ha cambiado."
        return informe
    except urllib.error.HTTPError as e:
        informe["estado"] = "http"
        informe["detalle"] = f"HTTP {e.code}"
        informe["remedio"] = "La URL ha cambiado o exige cabeceras propias de navegador."
        return informe

    texto = _texto_visible(cuerpo)
    medida = f"{len(cuerpo)} bytes de HTML, {len(texto)} de texto"
    if esperado is not None:
        if _normaliza(esperado) in _normaliza(texto):
            informe["estado"] = "ok"
            informe["detalle"] = f"{medida}; contiene «{esperado}»"
        else:
            informe["estado"] = "sin_contenido"
            informe["detalle"] = f"{medida}; NO contiene «{esperado}»"
            informe["remedio"] = (
                "Responde, pero el contenido no está en el HTML: casi siempre la "
                "página se monta con JavaScript. Hace falta un navegador, o buscar "
                "otra URL del mismo organismo que sirva el documento entero."
            )
    elif len(texto) < MINIMO_TEXTO:
        informe["estado"] = "sin_contenido"
        informe["detalle"] = f"{medida}: demasiado poco para un boletín"
        informe["remedio"] = "Probablemente se monta con JavaScript. Hace falta un navegador."
    else:
        informe["estado"] = "dudoso"
        informe["detalle"] = medida
        informe["remedio"] = (
            "Responde y trae texto, pero sin saber qué buscar no se puede afirmar "
            "que sea el documento. Repite con lo que tenga que aparecer."
        )
    return informe


def _normaliza(texto):
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def _descarga(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    return urllib.request.urlopen(req, timeout=timeout, context=certificados.contexto()).read()


def _texto_visible(cuerpo):
    html = cuerpo.decode("utf-8", "replace")
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def emisor(host, timeout=15):
    """Quién firma el certificado de ese host, o None.

    Se conecta **sin verificar**, y eso aquí no es un atajo: el objetivo es
    precisamente averiguar quién es la autoridad que no reconocemos. Nada de
    lo que devuelve entra en la base; solo sirve para decirle a una persona qué
    raíz tiene que ir a buscar.
    """
    try:
        ctx = ssl._create_unverified_context()
        with socket.create_connection((host, 443), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                der = ss.getpeercert(True)
    except Exception:
        return None
    ruta = Path(tempfile.gettempdir()) / f"{host}.der"
    ruta.write_bytes(der)
    try:
        salida = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-in", str(ruta), "-noout", "-issuer"],
            capture_output=True, text=True, timeout=timeout,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        ruta.unlink(missing_ok=True)
    nombre = re.search(r"O\s*=\s*([^,/]+)", salida)
    return nombre.group(1).strip() if nombre else (salida.strip() or None)
