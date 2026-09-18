"""Configuración de sec.mail: lo que es suyo y no de la cuenta.

Lo genérico -- el archivo `~/.misyks/config`, las credenciales OAuth, los
tokens y las claves de las bases -- vive en `sec.cuentas.ajustes` desde que
`sec.agenda` existe: el consentimiento es uno por cuenta y cubre correo y
calendario (ARQUITECTURA.md §8.6), así que no podía seguir dentro de `sec.mail`
sin obligar a `sec.agenda` a importarlo.

Aquí se queda la ruta de la base de correo. Los nombres genéricos se reexportan
para que el resto de `sec.mail` siga escribiendo `config.tokens(...)` como hasta
ahora: quien los usa no tiene por qué saber que se han mudado.

El transporte del tercer mundo de §8.6 (iCloud, Fastmail, servidores propios) ya
no está aquí: `imap.py`, `credenciales_imap` y el host de IMAP se han borrado.
Lo que había era del Gmail de antes de OAuth —host fijo `imap.gmail.com`,
identidad por `X-GM-MSGID`, etiquetas propias de Gmail—, es decir, justo lo que
un adaptador de iCloud tendría que cambiar entero. Cuando toque ese mundo se
escribe contra la interfaz `Correo`; el archivo viejo está en el historial de
git si sirve de referencia.

sec.mail corre en local, en el ordenador del abogado (no en el servidor): es
quien tiene el acceso al correo y lee el contenido sin anonimizar, así que
nunca sale de esta máquina.
"""
from ..cuentas.ajustes import (  # noqa: F401  (reexportados a propósito)
    CONFIG_PATH,
    DATA_DIR,
    PROVEEDOR_POR_DEFECTO,
    borrar_tokens,
    credenciales_oauth,
    guardar_tokens,
    proveedor_activo,
    tokens,
)
from ..cuentas.ajustes import clave_db as _clave_db

DB_PATH = DATA_DIR / "sec_mail.db"


def clave_db():
    """Clave que cifra `sec_mail.db`, de `[secmail] clave`.

    Solo la lee: la genera la app (Frontend, `LocalConfig::clave_db_o_generarla`)
    la primera vez que hace falta, antes de invocar a sec.mail. Si falta, es que
    algo ha ido mal antes de llegar aquí, y por eso falla en vez de crear una
    nueva -- una clave nueva no abriría la base que ya existe, la dejaría por
    ilegible. Sin la app, se pone a mano:

        python3 -c "import secrets; print(secrets.token_hex(32))"
    """
    return _clave_db("secmail")
