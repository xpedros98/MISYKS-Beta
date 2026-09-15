"""Convierte un correo crudo (EML) en campos limpios para guardar."""
import email
import hashlib
from email import policy
from html.parser import HTMLParser


def parsear(eml):
    msg = email.message_from_bytes(eml, policy=policy.default)
    return {
        "message_id": _cabecera(msg, "Message-ID"),
        "remitente": _cabecera(msg, "From"),
        "destinatarios": _cabecera(msg, "To"),
        "cc": _cabecera(msg, "Cc"),
        "asunto": _cabecera(msg, "Subject"),
        "fecha": _fecha(msg),
        "cuerpo_texto": _cuerpo(msg),
        "adjuntos": _adjuntos(msg),
        "sha256": hashlib.sha256(eml).hexdigest(),
    }


# Una cabecera mal formada no debe impedir guardar el correo: el original
# completo queda en el EML de todas formas.
def _cabecera(msg, nombre):
    try:
        valor = msg.get(nombre)
    except Exception:
        return None
    return str(valor).strip() if valor is not None else None


def _fecha(msg):
    try:
        cabecera = msg.get("Date")
        return cabecera.datetime.isoformat() if cabecera is not None and cabecera.datetime else None
    except Exception:
        return None


def _cuerpo(msg):
    parte = msg.get_body(preferencelist=("plain", "html"))
    if parte is None:
        return None
    try:
        texto = parte.get_content()
    except (LookupError, UnicodeDecodeError):  # charset desconocido o roto
        texto = (parte.get_payload(decode=True) or b"").decode("utf-8", "replace")
    return _html_a_texto(texto) if parte.get_content_subtype() == "html" else texto


def _adjuntos(parte):
    tipo = parte.get_content_type()
    if tipo == "message/rfc822":  # correo reenviado como adjunto: se guarda entero
        nombre = parte.get_filename() or "correo_adjunto.eml"
        return [_adjunto(nombre, tipo, parte.get_payload(0).as_bytes())]
    if parte.is_multipart():
        return [a for sub in parte.iter_parts() for a in _adjuntos(sub)]
    nombre = parte.get_filename()
    if not nombre and parte.get_content_disposition() != "attachment":
        return []
    return [_adjunto(nombre, tipo, parte.get_payload(decode=True) or b"")]


def _adjunto(nombre, tipo, contenido):
    return {
        "nombre": nombre,
        "tipo": tipo,
        "bytes": len(contenido),
        "contenido": contenido,
        "sha256": hashlib.sha256(contenido).hexdigest(),
    }


class _Texto(HTMLParser):
    _IGNORAR = {"script", "style", "title"}
    _BLOQUES = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.partes = []
        self._ignorando = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._IGNORAR:
            self._ignorando += 1
        elif tag in self._BLOQUES:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self._IGNORAR and self._ignorando:
            self._ignorando -= 1

    def handle_data(self, data):
        if not self._ignorando:
            self.partes.append(data)


def _html_a_texto(html):
    p = _Texto()
    p.feed(html)
    p.close()
    lineas = (" ".join(linea.split()) for linea in "".join(p.partes).splitlines())
    return "\n".join(linea for linea in lineas if linea)
