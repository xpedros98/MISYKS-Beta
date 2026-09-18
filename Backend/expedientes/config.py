"""Rutas de expedientes. Las credenciales y las claves, en `sec.cuentas.ajustes`.

La base va en `~/.misyks/`, junto a las de correo y agenda: fuera del repo, para
que sigan funcionando cuando la app se distribuya como binario.
"""
from sec.cuentas.ajustes import DATA_DIR

DB_PATH = DATA_DIR / "expedientes.db"
