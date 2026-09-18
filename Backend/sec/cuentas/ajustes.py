"""El archivo `~/.misyks/config`: credenciales de cuenta y claves de las bases.

Era `sec/mail/config.py` y vivía dentro de `sec.mail` porque `sec.mail` era lo
único que había. Con `sec.agenda` deja de valer: **el consentimiento es uno por
cuenta y cubre correo y calendario** (ARQUITECTURA.md §8.6), así que la sección
`[oauth.google]` no es de ningún módulo en particular. Que `sec.agenda` tuviera
que importar `sec.mail` para leer un token sería una dependencia inventada entre
dos módulos que no se necesitan para nada más.

Lo que se queda en `sec/mail/config.py` es lo que sí es suyo: la ruta de su base.
Lo genérico está aquí.

Nada se guarda en ningún llavero del sistema operativo: la clave de la base vive
en el mismo archivo que las credenciales, no en el Keychain de macOS. Ambos, y
las bases, viven fuera del repo -- en `~/.misyks` y no en una ruta relativa al
repo, que dejaría de existir en cuanto la app se distribuya como binario.

**Este módulo escribe, no solo lee.** El refresh token se rota (Microsoft lo
cambia en cada renovación) y el access token caduca cada hora, así que quien
renueva tiene que poder guardar. `_escribir_seccion` toca solo su sección y
respeta el resto del archivo, con el mismo orden de escritura que usa el
Frontend (archivo temporal + reemplazo atómico) para que un corte a mitad no
deje la configuración sin la clave de una base, que la dejaría ilegible.
"""
import configparser
import os
import secrets
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

DATA_DIR = Path.home() / ".misyks"
CONFIG_PATH = DATA_DIR / "config"

# Proveedor con el que se trabaja mientras no haya varias cuentas a la vez.
PROVEEDOR_POR_DEFECTO = "google"


def proveedor_activo(seccion="correo"):
    """Proveedor de la cuenta conectada: 'google' o 'microsoft'.

    Sale de `[<seccion>] proveedor`. Con una sola cuenta conectada se deduce
    sola, que es el caso normal: nadie tiene que escribir nada para que
    funcione. `seccion` existe porque el día que el despacho tenga el correo en
    un proveedor y el calendario en otro, esto es lo único que hay que separar.
    """
    ini = _leer()
    elegido = _valor(ini, seccion, "proveedor")
    if elegido:
        return elegido
    conectados = [p for p in ("google", "microsoft") if _valor(ini, f"oauth.{p}", "refresh_token")]
    if len(conectados) == 1:
        return conectados[0]
    if not conectados:
        raise RuntimeError(
            "No hay ninguna cuenta conectada. Conéctala desde Ajustes, o con:\n"
            "    python -m sec.mail conectar google"
        )
    raise RuntimeError(
        f"Hay varias cuentas conectadas ({', '.join(conectados)}). Indica cuál usar en "
        f"[{seccion}] proveedor de {CONFIG_PATH}."
    )


def credenciales_oauth(proveedor):
    """(client_id, client_secret) de la app registrada ante el proveedor.

    No son secretos del usuario sino de la aplicación, y en una app de
    escritorio distribuida el secret es extraíble del binario de todas formas
    (§8.6): PKCE es lo que protege el intercambio, no el secret. Viven en
    configuración en vez de en el código porque todavía no hay una app
    publicada y verificada, y cada máquina de desarrollo usa la suya.
    """
    ini = _leer()
    seccion = f"oauth.{proveedor}"
    client_id = _valor(ini, seccion, "client_id")
    if not client_id:
        raise RuntimeError(
            f"Falta 'client_id' en la sección [{seccion}] de {CONFIG_PATH}. "
            f"Se obtiene registrando la aplicación ante {proveedor} (ver INSTALACION.md)."
        )
    return client_id, _valor(ini, seccion, "client_secret")


def tokens(proveedor):
    """Lo guardado de una cuenta conectada. Diccionario vacío si no hay ninguna."""
    ini = _leer(obligatorio=False)
    seccion = f"oauth.{proveedor}"
    return {
        clave: _valor(ini, seccion, clave)
        for clave in ("cuenta", "refresh_token", "access_token", "caduca_en")
    }


def guardar_tokens(proveedor, cuenta, refresh_token, access_token, caduca_en):
    _escribir_seccion(
        f"oauth.{proveedor}",
        {
            "cuenta": cuenta,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "caduca_en": f"{float(caduca_en):.0f}",
        },
    )


def borrar_tokens(proveedor):
    """Deja el client_id (es de la aplicación) y quita lo que es de la cuenta."""
    _escribir_seccion(
        f"oauth.{proveedor}",
        {"cuenta": "", "refresh_token": "", "access_token": "", "caduca_en": ""},
        quitar_vacios=True,
    )


def clave_db(seccion, generar=False):
    """Clave hexadecimal (64 caracteres) que cifra una base local.

    `[secmail] clave` cifra `sec_mail.db`; `[secagenda] clave`, `sec_agenda.db`.
    Cada base tiene la suya: son archivos distintos y no hay ninguna razón para
    que comprometer una comprometa la otra.

    **Quién la crea no es igual en las dos, y conviene saberlo.** La de
    `sec.mail` la genera el Frontend (`LocalConfig::clave_db_o_generarla`) antes
    de invocar al Backend, así que aquí solo se lee: si falta, es que algo ha
    ido mal y hay que enterarse. La de `sec.agenda` no la genera todavía nadie
    -- no hay pantalla suya --, y fallar exigiría a quien usa la CLI pegar a
    mano un hexadecimal de 64 caracteres para poder guardar una reunión. Con
    `generar=True` se crea al vuelo y se guarda. En cuanto el Frontend tenga
    pantalla de agenda, esto pasa a ser `generar=False` como el otro.
    """
    ini = _leer(obligatorio=not generar)
    clave = _valor(ini, seccion, "clave")
    if clave:
        return clave
    if not generar:
        raise RuntimeError(
            f"Falta 'clave' en la sección [{seccion}] de {CONFIG_PATH}. "
            "Genera una con: python3 -c \"import secrets; print(secrets.token_hex(32))\" "
            "y pégala ahí."
        )
    clave = secrets.token_hex(32)
    _escribir_seccion(seccion, {"clave": clave})
    return clave


def _leer(obligatorio=True):
    ini = configparser.ConfigParser(interpolation=None)
    try:
        leidos = ini.read(CONFIG_PATH, encoding="utf-8")
    except configparser.Error as e:
        raise RuntimeError(f"{CONFIG_PATH} está mal escrito: {e}")
    if not leidos and obligatorio:
        raise RuntimeError(f"No existe {CONFIG_PATH}.")
    return ini


def _valor(ini, seccion, clave):
    return ini.get(seccion, clave, fallback="").strip().strip("\"'")


def _escribir_seccion(seccion, valores, quitar_vacios=False):
    """Actualiza una sección conservando el resto del archivo.

    El archivo se escribe entero a un temporal en el mismo directorio y se
    reemplaza de golpe: `os.replace` es atómico, así que una interrupción deja
    el archivo anterior intacto en vez de uno truncado sin la clave de la base
    de datos, que dejaría la base ilegible.

    Y después hay que volver a cerrar los permisos, que es lo que no es obvio:
    el archivo que queda es el temporal, con los permisos que heredó del
    directorio, no los del archivo al que sustituye. Sin `_restringir_permisos`
    cada renovación de token deshacía en silencio el endurecimiento que hace el
    Frontend (`local_config.rs`), dejando el refresh token y la clave de la
    base legibles para `SYSTEM` y `Administrators`.
    """
    ini = _leer(obligatorio=False)
    if not ini.has_section(seccion):
        ini.add_section(seccion)
    for clave, valor in valores.items():
        if quitar_vacios and not valor:
            ini.remove_option(seccion, clave)
        else:
            ini.set(seccion, clave, str(valor))

    CONFIG_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=str(CONFIG_PATH.parent), prefix=".config-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            ini.write(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, CONFIG_PATH)
    except BaseException:
        os.unlink(temporal)
        raise
    _restringir_permisos(CONFIG_PATH)


def _restringir_permisos(ruta):
    """Deja el archivo accesible solo a quien lo usa. Equivale a `0600`.

    En Windows no basta con `chmod`, que el sistema ignora casi por completo:
    hace falta reescribir la ACL. Se usa `icacls` por lo mismo que el Frontend
    (`local_config.rs`) -- `/inheritance:r` borra los permisos heredados y
    `/grant:r` deja solo el de la cuenta actual --, y se mantienen los dos
    lados equivalentes a propósito: quien escriba el archivo, lo cierra.

    Si falla no se aborta la operación: el token ya está guardado y perderlo
    por no haber podido ajustar una ACL sería peor. Pero se avisa, porque un
    archivo de secretos con permisos abiertos no debe pasar desapercibido.
    """
    if os.name != "nt":
        os.chmod(ruta, stat.S_IRUSR | stat.S_IWUSR)
        return

    usuario = os.environ.get("USERNAME", "")
    if not usuario:
        return
    dominio = os.environ.get("USERDOMAIN", "")
    cuenta = f"{dominio}\\{usuario}" if dominio else usuario
    try:
        resultado = subprocess.run(
            ["icacls", str(ruta), "/inheritance:r", "/grant:r", f"{cuenta}:(F)", "/q"],
            capture_output=True,
            text=True,
            # Sin ventana de consola: la app es de ventana, no de terminal.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as e:
        print(f"Aviso: no se pudieron restringir los permisos de {ruta}: {e}", file=sys.stderr)
        return
    if resultado.returncode != 0:
        print(
            f"Aviso: icacls no pudo restringir los permisos de {ruta}: {resultado.stderr.strip()}",
            file=sys.stderr,
        )
