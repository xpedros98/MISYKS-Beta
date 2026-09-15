"""Configuración de sec.mail.

Las credenciales de Gmail se escriben a mano en MISYKS-Beta/.config (ignorado
por git). La clave de la base de datos la genera el agente y la guarda en el
Llavero de macOS.
"""
import configparser
import subprocess
from pathlib import Path

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

CONFIG_PATH = Path(__file__).resolve().parents[3] / ".config"

# Fuera del repo, en la carpeta del usuario.
DATA_DIR = Path.home() / "Library" / "Application Support" / "MISYKS"
DB_PATH = DATA_DIR / "sec_mail.db"

CUENTA_LLAVERO = "sec.mail"
SERVICIO_CLAVE_DB = "MISYKS sec.mail clave DB"


def credenciales_gmail():
    ini = configparser.ConfigParser(interpolation=None)
    try:
        leidos = ini.read(CONFIG_PATH, encoding="utf-8")
    except configparser.Error as e:
        raise RuntimeError(f"{CONFIG_PATH} está mal escrito: {e}")
    if not leidos:
        raise RuntimeError(f"No existe {CONFIG_PATH}.")
    usuario = _valor(ini, "usuario")
    password = _valor(ini, "password").replace(" ", "")
    if not usuario or not password:
        raise RuntimeError(f"Rellena 'usuario' y 'password' en la sección [gmail] de {CONFIG_PATH}.")
    return usuario, password


def _valor(ini, clave):
    return ini.get("gmail", clave, fallback="").strip().strip("\"'")


def leer_secreto(servicio):
    """Devuelve el secreto guardado en el Llavero, o None si no existe."""
    r = subprocess.run(
        ["security", "find-generic-password", "-a", CUENTA_LLAVERO, "-s", servicio, "-w"],
        capture_output=True,
        text=True,
    )
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def guardar_secreto(servicio, valor):
    """Guarda (o reemplaza) un secreto en el Llavero.

    El valor se pasa por la entrada estándar de `security -i` para que no
    aparezca en la lista de procesos.
    """
    if not valor or any(c in valor for c in '"\\\n'):
        raise ValueError("Valor vacío o con comillas, barras invertidas o saltos de línea.")
    orden = f'add-generic-password -U -a {CUENTA_LLAVERO} -s "{servicio}" -w "{valor}"\n'
    r = subprocess.run(["security", "-i"], input=orden, capture_output=True, text=True)
    if leer_secreto(servicio) != valor:
        raise RuntimeError(f"No se pudo guardar en el Llavero: {r.stderr.strip()}")
