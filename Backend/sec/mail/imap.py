"""Conexión con Gmail por IMAP, solo con la librería estándar."""
import base64
import imaplib
import re
import ssl

from . import config

_CUERPO = re.compile(rb"BODY\[\] \{\d+\}$")
_LIST = re.compile(r'\((?P<marcas>[^)]*)\) (?:"[^"]*"|NIL) (?P<nombre>.+)$')
_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([^\s()]+)')


class ErrorImap(RuntimeError):
    pass


class Gmail:
    """Uso: `with Gmail(usuario, password) as gmail: ...`"""

    def __init__(self, usuario, password):
        self.usuario = usuario
        self.password = password
        self.conn = None

    def __enter__(self):
        self.conn = imaplib.IMAP4_SSL(
            config.IMAP_HOST, config.IMAP_PORT, ssl_context=ssl.create_default_context(), timeout=60
        )
        try:
            self.conn.login(self.usuario, self.password)
        except imaplib.IMAP4.error:
            self.conn.shutdown()
            raise
        return self

    def __exit__(self, *_):
        try:
            self.conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    def carpetas(self):
        """Lista de {"nombre", "marcas"}. Las marcas (\\Sent, \\All, \\Trash...) no dependen del idioma."""
        tipo, datos = self.conn.list()
        _ok(tipo, datos, "LIST")
        resultado = []
        for elem in datos:
            if isinstance(elem, tuple):  # nombre enviado como literal {n}
                marcas = re.match(r"\(([^)]*)\)", elem[0].decode()).group(1)
                nombre = elem[1].decode()
            elif elem:
                m = _LIST.match(elem.decode())
                if not m:
                    continue
                marcas, nombre = m.group("marcas"), _tokens(m.group("nombre"))[0]
            else:
                continue
            resultado.append({"nombre": _utf7_decodificar(nombre), "marcas": marcas.split()})
        return resultado

    def seleccionar(self, carpeta, solo_lectura=True):
        """Abre una carpeta y devuelve su UIDVALIDITY."""
        tipo, datos = self.conn.select(_entrecomillar(carpeta), readonly=solo_lectura)
        _ok(tipo, datos, f"SELECT {carpeta}")
        _, valor = self.conn.response("UIDVALIDITY")
        return int(valor[0])

    def uids_desde(self, ultimo_uid):
        """UIDs mayores que `ultimo_uid`, de menor a mayor."""
        tipo, datos = self.conn.uid("SEARCH", None, f"UID {ultimo_uid + 1}:*")
        _ok(tipo, datos, "SEARCH")
        # "n:*" siempre incluye el último UID aunque sea menor que n.
        return sorted(u for u in map(int, datos[0].split()) if u > ultimo_uid)

    def descargar(self, uid):
        """Descarga un correo sin marcarlo como leído. Devuelve None si ya no existe."""
        tipo, datos = self.conn.uid("FETCH", str(uid), "(X-GM-MSGID FLAGS BODY.PEEK[])")
        _ok(tipo, datos, f"FETCH {uid}")
        for i, elem in enumerate(datos):
            if isinstance(elem, tuple) and _CUERPO.search(elem[0]):
                cola = datos[i + 1] if i + 1 < len(datos) and isinstance(datos[i + 1], bytes) else b""
                meta = (elem[0] + b" " + cola).decode("utf-8", "replace")
                msgid = re.search(r"X-GM-MSGID (\d+)", meta)
                if not msgid:
                    raise ErrorImap(f"Gmail no devolvió X-GM-MSGID para el UID {uid}")
                return {
                    "gmail_msgid": msgid.group(1),
                    "leido": "\\Seen" in _tokens(_lista(meta, "FLAGS")),
                    "etiquetas": self._etiquetas(uid),
                    "eml": elem[1],
                }
        return None

    def _etiquetas(self, uid):
        tipo, datos = self.conn.uid("FETCH", str(uid), "(X-GM-LABELS)")
        _ok(tipo, datos, f"FETCH {uid}")
        meta = " ".join(e.decode("utf-8", "replace") for e in datos if isinstance(e, bytes))
        return [_utf7_decodificar(e) for e in _tokens(_lista(meta, "X-GM-LABELS"))]

    def buscar_msgid(self, gmail_msgid):
        """UID del correo en la carpeta abierta, o None si no está."""
        tipo, datos = self.conn.uid("SEARCH", None, f"X-GM-MSGID {gmail_msgid}")
        _ok(tipo, datos, "SEARCH")
        uids = datos[0].split()
        return int(uids[0]) if uids else None

    def marcar_leido(self, uid):
        tipo, datos = self.conn.uid("STORE", str(uid), "+FLAGS", "(\\Seen)")
        _ok(tipo, datos, f"STORE {uid}")

    def mover(self, uid, destino):
        tipo, datos = self.conn.uid("MOVE", str(uid), _entrecomillar(destino))
        _ok(tipo, datos, f"MOVE {uid} -> {destino}")


def _ok(tipo, datos, orden):
    if tipo != "OK":
        raise ErrorImap(f"{orden} falló: {datos}")


def _tokens(texto):
    """Separa una lista IMAP en elementos, respetando las comillas."""
    return [
        re.sub(r"\\(.)", r"\1", m.group(1)) if m.group(1) is not None else m.group(2)
        for m in _TOKEN.finditer(texto)
    ]


def _lista(texto, clave):
    """Contenido de 'CLAVE (...)' dentro de una respuesta, respetando las comillas."""
    inicio = texto.find(clave + " (")
    if inicio < 0:
        return ""
    inicio += len(clave) + 2
    i, comillas = inicio, False
    while i < len(texto):
        c = texto[i]
        if c == "\\" and comillas:
            i += 2
            continue
        if c == '"':
            comillas = not comillas
        elif c == ")" and not comillas:
            break
        i += 1
    return texto[inicio:i]


def _entrecomillar(nombre):
    n = _utf7_codificar(nombre).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{n}"'


# Los nombres de carpeta y etiqueta van en "UTF-7 modificado" (RFC 3501, 5.1.3).
def _utf7_codificar(texto):
    salida, pendiente = [], []

    def vaciar():
        if pendiente:
            b64 = base64.b64encode("".join(pendiente).encode("utf-16-be")).decode("ascii")
            salida.append("&" + b64.rstrip("=").replace("/", ",") + "-")
            pendiente.clear()

    for c in texto:
        if 0x20 <= ord(c) <= 0x7E:
            vaciar()
            salida.append("&-" if c == "&" else c)
        else:
            pendiente.append(c)
    vaciar()
    return "".join(salida)


def _utf7_decodificar(texto):
    def trozo(m):
        if not m.group(1):
            return "&"
        b64 = m.group(1).replace(",", "/")
        return base64.b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-16-be")

    return re.sub(r"&([A-Za-z0-9+,]*)-", trozo, texto)
