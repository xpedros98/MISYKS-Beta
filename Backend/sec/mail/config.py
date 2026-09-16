"""Configuración de sec.mail.

sec.mail corre en local, en el ordenador del abogado (no en el servidor):
es quien tiene la contraseña de correo y lee el contenido sin anonimizar,
así que nunca sale de esta máquina. La app nativa (Frontend) es quien
gestiona este archivo desde su pantalla de Ajustes (textboxes, no edición a
mano); este módulo solo lo lee.

Nada se guarda en ningún llavero del sistema operativo: la clave de la base
de datos vive en el mismo archivo que las credenciales, no en el Keychain de
macOS. Ambos, además de la base de datos, viven fuera del repo, en
~/.misyks — no en una ruta relativa al propio repo, que dejaría de existir
en cuanto la app se distribuya como binario empaquetado.
"""
import configparser
from pathlib import Path

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

DATA_DIR = Path.home() / ".misyks"
CONFIG_PATH = DATA_DIR / "config"
DB_PATH = DATA_DIR / "sec_mail.db"


def credenciales_gmail():
    ini = _leer()
    usuario = _valor(ini, "gmail", "usuario")
    password = _valor(ini, "gmail", "password").replace(" ", "")
    if not usuario or not password:
        raise RuntimeError(f"Rellena 'usuario' y 'password' en la sección [gmail] de {CONFIG_PATH}.")
    return usuario, password


def clave_db():
    """Clave hexadecimal (64 caracteres) que cifra la base de datos.

    Vive en ~/.misyks/config, seccion [secmail], clave `clave`. Esta funcion
    solo la lee: la genera la app (Frontend, LocalConfig::clave_db_o_generarla)
    la primera vez que hace falta, antes de invocar a sec.mail. Si se usa el
    Backend por separado, sin la app, hay que ponerla a mano:

        python3 -c "import secrets; print(secrets.token_hex(32))"
    """
    ini = _leer()
    clave = _valor(ini, "secmail", "clave")
    if not clave:
        raise RuntimeError(
            f"Falta 'clave' en la sección [secmail] de {CONFIG_PATH}. "
            "Genera una con: python3 -c \"import secrets; print(secrets.token_hex(32))\" "
            "y pegala ahi."
        )
    return clave


def _leer():
    ini = configparser.ConfigParser(interpolation=None)
    try:
        leidos = ini.read(CONFIG_PATH, encoding="utf-8")
    except configparser.Error as e:
        raise RuntimeError(f"{CONFIG_PATH} está mal escrito: {e}")
    if not leidos:
        raise RuntimeError(f"No existe {CONFIG_PATH}.")
    return ini


def _valor(ini, seccion, clave):
    return ini.get(seccion, clave, fallback="").strip().strip("\"'")
