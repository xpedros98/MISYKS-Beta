"""OAuth 2.0 para las cuentas de correo y calendario (ARQUITECTURA.md 8.6).

Sustituye a la contraseña de aplicación con la que `sec.mail` hablaba por IMAP
con Gmail. Cubre los dos primeros mundos de 8.6 -- Google y Microsoft --, que
son los que van por API autenticada con OAuth; el tercero (iCloud, Fastmail,
Nextcloud, servidor propio) sigue siendo IMAP con contraseña de aplicación y
no pasa por aquí.

Flujo: **PKCE con redirect a loopback**, el que corresponde a una aplicación
de escritorio distribuida. El `client_secret` no es confidencial -- está dentro
del binario y es extraíble --, así que la seguridad del intercambio no se apoya
en él sino en el `code_verifier`, que se genera nuevo en cada conexión y nunca
sale de esta máquina. Google exige además el `client_secret` en el intercambio
del código aunque haya PKCE; Microsoft, como cliente público, no lo acepta
siquiera. De ahí que sea opcional.

El puerto de loopback se pide al sistema (`127.0.0.1:0`): reservar uno fijo
fallaría en cuanto otro programa lo tuviera cogido. Google y Microsoft
permiten cualquier puerto en `127.0.0.1` justamente por eso.

Solo librería estándar, como el resto del Backend: `urllib` para las llamadas
y `http.server` para recibir el redirect.
"""
import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from . import config

# Margen con el que se considera caducado un access token antes de que lo esté
# de verdad: evita que una petición salga con un token que caduca en vuelo.
MARGEN_CADUCIDAD = 120


class ErrorOAuth(RuntimeError):
    """Fallo recuperable del flujo: red caída, respuesta rara del proveedor."""


class ConsentimientoRevocado(ErrorOAuth):
    """El refresh token ya no vale: hace falta volver a autorizar en el navegador.

    Es un estado distinto de «token caducado»: el caducado se renueva solo, este
    exige pasar otra vez por el consentimiento. Ocurre al cambiar la contraseña
    de la cuenta, al revocar el acceso desde la propia cuenta, cuando un
    administrador de Workspace o de Entra bloquea la app, y -- caso frecuente
    mientras se desarrolla -- cuando la app de Google sigue en estado *Testing*,
    donde Google caduca el refresh token a los 7 días por diseño.
    """


class Proveedor:
    def __init__(self, nombre, autorizacion, token, scopes, revocacion=None, extra=None):
        self.nombre = nombre
        self.autorizacion = autorizacion
        self.token = token
        self.scopes = scopes
        self.revocacion = revocacion
        self.extra = extra or {}


# Los scopes son el mínimo que cubre el contrato del agente (8.6): `gmail.modify`
# permite leer, marcar como leído y mover de etiqueta, pero no borrar
# definitivamente; `calendar.events` da eventos, no la agenda completa.
GOOGLE = Proveedor(
    nombre="google",
    autorizacion="https://accounts.google.com/o/oauth2/v2/auth",
    token="https://oauth2.googleapis.com/token",
    revocacion="https://oauth2.googleapis.com/revoke",
    scopes=[
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
    # `access_type=offline` es lo que hace que Google entregue refresh token, y
    # `prompt=consent` que lo vuelva a entregar en una reconexión: sin él, la
    # segunda autorización de la misma cuenta devuelve solo access token y la
    # aplicación se queda sin poder renovar.
    extra={"access_type": "offline", "prompt": "consent"},
)

# `common` acepta tanto cuentas de organización (Microsoft 365, cualquier
# tenant) como personales (@outlook.com, @hotmail.com). `offline_access` es el
# scope que pide el refresh token; en Microsoft no es implícito.
MICROSOFT = Proveedor(
    nombre="microsoft",
    autorizacion="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    token="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    scopes=[
        "offline_access",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Calendars.ReadWrite",
        "https://graph.microsoft.com/User.Read",
    ],
)

PROVEEDORES = {p.nombre: p for p in (GOOGLE, MICROSOFT)}


def proveedor(nombre):
    if nombre not in PROVEEDORES:
        raise ErrorOAuth(f"Proveedor desconocido: {nombre}. Los que hay: {', '.join(PROVEEDORES)}.")
    return PROVEEDORES[nombre]


def conectar(nombre_proveedor, abrir_navegador=True):
    """Flujo completo de consentimiento. Guarda los tokens y devuelve la cuenta.

    Se ejecuta una vez por cuenta. La persona no escribe su contraseña en
    ninguna ventana de la aplicación: se la pide el proveedor en su dominio.
    """
    prov = proveedor(nombre_proveedor)
    client_id, client_secret = config.credenciales_oauth(prov.nombre)

    verificador = secrets.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode("ascii")).digest()).decode("ascii").rstrip("=")
    estado = secrets.token_urlsafe(24)

    receptor = _Receptor(estado)
    with receptor:
        parametros = {
            "client_id": client_id,
            "redirect_uri": receptor.redirect_uri,
            "response_type": "code",
            "scope": " ".join(prov.scopes),
            "state": estado,
            "code_challenge": reto,
            "code_challenge_method": "S256",
            **prov.extra,
        }
        url = prov.autorizacion + "?" + urllib.parse.urlencode(parametros)
        if abrir_navegador:
            webbrowser.open(url)
        codigo = receptor.esperar(url)

    respuesta = _pedir_token(
        prov,
        {
            "client_id": client_id,
            "code": codigo,
            "code_verifier": verificador,
            "grant_type": "authorization_code",
            "redirect_uri": receptor.redirect_uri,
            **({"client_secret": client_secret} if client_secret else {}),
        },
    )
    if not respuesta.get("refresh_token"):
        raise ErrorOAuth(
            "El proveedor no devolvió refresh token: sin él habría que pedir consentimiento "
            "en cada sincronización. Revisa los scopes de la app registrada."
        )

    cuenta = _cuenta(prov, respuesta)
    config.guardar_tokens(
        prov.nombre,
        cuenta=cuenta,
        refresh_token=respuesta["refresh_token"],
        access_token=respuesta.get("access_token", ""),
        caduca_en=_caducidad(respuesta),
    )
    return cuenta


class ErrorApi(RuntimeError):
    """Respuesta de error de la API del proveedor, con su código HTTP."""

    def __init__(self, codigo, cuerpo, url):
        super().__init__(f"{codigo} en {urllib.parse.urlsplit(url).path}: {cuerpo[:400]}")
        self.codigo = codigo
        self.cuerpo = cuerpo


class Sesion:
    """Un acceso vivo a una cuenta ya conectada. Renueva el token cuando toca.

    Los adaptadores (Gmail API, Microsoft Graph) hablan con el proveedor a
    través de `pedir` y no saben nada de tokens: aquí es donde se distingue un
    token caducado -- que se renueva sin que nadie se entere -- de un
    consentimiento revocado, que sube como `ConsentimientoRevocado` hasta la
    pantalla de Ajustes.
    """

    def __init__(self, nombre_proveedor):
        self.proveedor = proveedor(nombre_proveedor)
        # Los tokens se miran antes que el client_id: no tener cuenta conectada
        # es un estado normal («conéctala»), y sin este orden se contaría como
        # un fallo de configuración de la aplicación, que es otra cosa.
        guardado = config.tokens(self.proveedor.nombre)
        if not guardado.get("refresh_token"):
            raise ConsentimientoRevocado(
                f"No hay ninguna cuenta de {self.proveedor.nombre} conectada. Conéctala desde "
                f"Ajustes, o con: python -m sec.mail conectar {self.proveedor.nombre}"
            )
        self.cuenta = guardado.get("cuenta", "")
        self._refresh_token = guardado["refresh_token"]
        self._access_token = guardado.get("access_token", "")
        self._caduca_en = _numero(guardado.get("caduca_en"))

    def token(self):
        if not self._access_token or time.time() >= self._caduca_en - MARGEN_CADUCIDAD:
            self._renovar()
        return self._access_token

    def pedir(self, url, metodo="GET", cuerpo=None, params=None, crudo=False):
        """Llamada autenticada a la API del proveedor.

        Reintenta una vez ante un 401 renovando el token: el proveedor puede
        invalidar un access token antes de su caducidad nominal (cambio de
        sesión, política del tenant) y eso no debe romper una sincronización.
        """
        try:
            return self._llamar(url, metodo, cuerpo, params, crudo)
        except ErrorApi as e:
            if e.codigo != 401:
                raise
            self._renovar()
            return self._llamar(url, metodo, cuerpo, params, crudo)

    def _llamar(self, url, metodo, cuerpo, params, crudo):
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        cabeceras = {"Authorization": f"Bearer {self.token()}"}
        if datos is not None:
            cabeceras["Content-Type"] = "application/json"
        peticion = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(peticion, timeout=60) as r:
                contenido = r.read()
        except urllib.error.HTTPError as e:
            raise ErrorApi(e.code, e.read().decode("utf-8", "replace"), url)
        except urllib.error.URLError as e:
            raise ErrorOAuth(f"No se pudo contactar con {urllib.parse.urlsplit(url).netloc}: {e.reason}")
        if crudo:
            return contenido
        return json.loads(contenido) if contenido else {}

    def _renovar(self):
        client_id, client_secret = config.credenciales_oauth(self.proveedor.nombre)
        datos = {
            "client_id": client_id,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }
        if client_secret:
            datos["client_secret"] = client_secret
        if self.proveedor is MICROSOFT:
            # Entra exige repetir los scopes en la renovación; Google los ignora.
            datos["scope"] = " ".join(self.proveedor.scopes)
        respuesta = _pedir_token(self.proveedor, datos)
        self._access_token = respuesta.get("access_token", "")
        self._caduca_en = _caducidad(respuesta)
        # Microsoft rota el refresh token en cada renovación; Google lo mantiene
        # y no lo devuelve. Guardar el nuevo solo cuando viene cubre los dos.
        self._refresh_token = respuesta.get("refresh_token") or self._refresh_token
        config.guardar_tokens(
            self.proveedor.nombre,
            cuenta=self.cuenta,
            refresh_token=self._refresh_token,
            access_token=self._access_token,
            caduca_en=self._caduca_en,
        )


def estado_conexion(nombre_proveedor):
    """Qué contar en Ajustes: ("sin_conectar" | "conectado" | "revocado", detalle)."""
    try:
        sesion = Sesion(nombre_proveedor)
    except ConsentimientoRevocado:
        return "sin_conectar", ""
    except RuntimeError as e:
        # Incluye ErrorOAuth y el «falta client_id» de config: en los dos
        # casos no hay nada conectado y el detalle explica por qué.
        return "sin_conectar", str(e)
    try:
        sesion.token()
    except ConsentimientoRevocado as e:
        return "revocado", str(e)
    except ErrorOAuth as e:
        # Red caída: no es una revocación y no debe pintarse como tal, o la
        # persona reconectaría sin ninguna necesidad.
        return "conectado", f"{sesion.cuenta} (sin comprobar: {e})"
    return "conectado", sesion.cuenta


def desconectar(nombre_proveedor):
    """Revoca el acceso en el proveedor y borra los tokens locales."""
    prov = proveedor(nombre_proveedor)
    guardado = config.tokens(prov.nombre)
    if prov.revocacion and guardado.get("refresh_token"):
        try:
            peticion = urllib.request.Request(
                prov.revocacion,
                data=urllib.parse.urlencode({"token": guardado["refresh_token"]}).encode("ascii"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            urllib.request.urlopen(peticion, timeout=30).close()
        except (urllib.error.URLError, urllib.error.HTTPError):
            pass  # Sin red no se puede revocar en el servidor; en local se borra igual.
    config.borrar_tokens(prov.nombre)


def _pedir_token(prov, datos):
    peticion = urllib.request.Request(
        prov.token,
        data=urllib.parse.urlencode(datos).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        try:
            error = json.loads(cuerpo).get("error", "")
        except ValueError:
            error = ""
        # `invalid_grant` es lo que devuelven los dos proveedores cuando el
        # refresh token ya no sirve; cualquier otro 4xx es un fallo de la
        # petición o del registro de la app, no del consentimiento.
        if error == "invalid_grant":
            raise ConsentimientoRevocado(
                f"La cuenta de {prov.nombre} ya no autoriza a la aplicación: vuelve a conectarla "
                f"desde Ajustes. (respuesta del proveedor: {cuerpo[:200]})"
            )
        raise ErrorOAuth(f"{prov.nombre} rechazó la petición de token ({e.code}): {cuerpo[:400]}")
    except urllib.error.URLError as e:
        raise ErrorOAuth(f"No se pudo contactar con {prov.nombre}: {e.reason}")


def _caducidad(respuesta):
    return time.time() + _numero(respuesta.get("expires_in"), 3600)


def _numero(valor, por_defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return float(por_defecto)


def _cuenta(prov, respuesta):
    """Dirección de la cuenta recién conectada, para poder mostrarla en Ajustes.

    Sale del `id_token` cuando viene (Google lo incluye al pedir el scope
    `userinfo.email`) y, si no, se pregunta a la API. Que esto falle no debe
    tumbar una conexión que por lo demás ha ido bien: la cuenta es información
    para la pantalla, no algo de lo que dependa el acceso.
    """
    correo = _correo_de_id_token(respuesta.get("id_token"))
    if correo:
        return correo
    url = "https://www.googleapis.com/oauth2/v3/userinfo" if prov is GOOGLE else "https://graph.microsoft.com/v1.0/me"
    try:
        peticion = urllib.request.Request(url, headers={"Authorization": f"Bearer {respuesta['access_token']}"})
        with urllib.request.urlopen(peticion, timeout=30) as r:
            datos = json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError):
        return ""
    return datos.get("email") or datos.get("mail") or datos.get("userPrincipalName") or ""


def _correo_de_id_token(id_token):
    if not id_token or id_token.count(".") != 2:
        return ""
    # Solo se lee el claim; la firma no se valida porque el token viene por TLS
    # del propio endpoint del proveedor, no de un tercero.
    carga = id_token.split(".")[1]
    try:
        datos = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
    except ValueError:
        return ""
    return datos.get("email", "")


_PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8">
<title>MISYKS</title>
<body style="font-family: system-ui; margin: 4rem auto; max-width: 30rem; text-align: center">
<h1>{titulo}</h1><p>{texto}</p><p>Ya puedes cerrar esta pestaña.</p>
</body></html>"""


class _Receptor:
    """Servidor mínimo en 127.0.0.1 que recoge el redirect del proveedor.

    Atiende y muere. No escucha en ninguna interfaz externa: el código de
    autorización nunca sale de esta máquina.
    """

    def __init__(self, estado, espera=300):
        self.estado = estado
        self.espera = espera
        self.codigo = None
        self.error = None
        self._hecho = threading.Event()
        receptor = self

        class Manejador(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                consulta = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                if consulta.get("state", [""])[0] != receptor.estado:
                    # Petición que no viene de este flujo: se contesta con un
                    # error pero no se da por terminada la espera, o cualquier
                    # cosa que toque el puerto (un favicon del navegador)
                    # abortaría la conexión en curso.
                    self._responder(400, "No se pudo conectar", "Este redirect no corresponde a la conexión en curso.")
                elif "error" in consulta:
                    receptor.error = consulta.get("error_description", consulta["error"])[0]
                    self._responder(400, "No se pudo conectar", receptor.error)
                    receptor._hecho.set()
                else:
                    receptor.codigo = consulta.get("code", [""])[0]
                    self._responder(200, "Cuenta conectada", "MISYKS ya tiene acceso a tu correo y calendario.")
                    receptor._hecho.set()

            def _responder(self, codigo, titulo, texto):
                cuerpo = _PAGINA.format(titulo=titulo, texto=texto).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *_):
                pass  # Sin ruido en la consola de la app.

        self._servidor = http.server.HTTPServer(("127.0.0.1", 0), Manejador)
        self.puerto = self._servidor.server_address[1]
        self.redirect_uri = f"http://127.0.0.1:{self.puerto}"
        self._hilo = None

    def __enter__(self):
        self._hilo = threading.Thread(
            target=self._servidor.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True
        )
        self._hilo.start()
        return self

    def __exit__(self, *_):
        self._servidor.shutdown()
        self._servidor.server_close()

    def esperar(self, url):
        if not self._hecho.wait(self.espera):
            raise ErrorOAuth(
                f"Se agotó la espera ({self.espera}s) sin recibir la autorización. "
                f"Si el navegador no se abrió solo, entra en:\n{url}"
            )
        if self.error:
            raise ErrorOAuth(f"El proveedor rechazó la conexión: {self.error}")
        if not self.codigo:
            raise ErrorOAuth("El proveedor no devolvió código de autorización.")
        return self.codigo
