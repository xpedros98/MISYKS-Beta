"""Base de datos local cifrada con SQLCipher."""
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS correos (
    id            INTEGER PRIMARY KEY,
    proveedor     TEXT NOT NULL DEFAULT 'google',  -- google | microsoft | imap
    cuenta        TEXT,                     -- dirección del buzón del que vino
    mensaje_id    TEXT NOT NULL,            -- identificador del mensaje en el proveedor
    message_id    TEXT,                     -- cabecera Message-ID del correo (no es lo mismo)
    carpeta       TEXT NOT NULL,            -- carpeta o etiqueta donde está (cambia al moverlo)
    remitente     TEXT,
    destinatarios TEXT,
    cc            TEXT,
    asunto        TEXT,
    fecha         TEXT,
    cuerpo_texto  TEXT,
    etiquetas     TEXT,                     -- JSON, tal como estaban al guardarlo
    leido         INTEGER NOT NULL DEFAULT 0,
    eml           BLOB NOT NULL,            -- correo original completo
    sha256        TEXT NOT NULL,            -- huella del EML
    guardado_en   TEXT NOT NULL
);
-- La identidad es (proveedor, mensaje_id), no el identificador a secas: dos
-- proveedores distintos pueden dar el mismo y no son el mismo correo.
CREATE UNIQUE INDEX IF NOT EXISTS correos_identidad ON correos (proveedor, mensaje_id);
CREATE TABLE IF NOT EXISTS adjuntos (
    id        INTEGER PRIMARY KEY,
    correo_id INTEGER NOT NULL REFERENCES correos(id),
    nombre    TEXT,
    tipo      TEXT,
    bytes     INTEGER NOT NULL,
    contenido BLOB NOT NULL,
    sha256    TEXT NOT NULL
);
-- Cursor de sincronización incremental, opaco: historyId en Google, deltaLink
-- en Graph. sec.mail lo guarda y lo devuelve sin interpretarlo.
CREATE TABLE IF NOT EXISTS sincronizacion (
    proveedor TEXT NOT NULL,
    carpeta   TEXT NOT NULL,
    cursor    TEXT,
    PRIMARY KEY (proveedor, carpeta)
);
-- Cola de correos que el servidor ya ha anunciado y que aún no se han bajado.
-- Es lo que permite que el cursor avance de golpe (que es como lo dan las dos
-- APIs) sin perder correos al descargar en tandas: el cursor dice hasta dónde
-- se ha *preguntado*, y la cola, qué falta por *traer*.
CREATE TABLE IF NOT EXISTS pendientes (
    id         INTEGER PRIMARY KEY,
    proveedor  TEXT NOT NULL,
    carpeta    TEXT NOT NULL,
    mensaje_id TEXT NOT NULL,
    UNIQUE (proveedor, carpeta, mensaje_id)
);
CREATE TABLE IF NOT EXISTS acciones (
    id        INTEGER PRIMARY KEY,
    correo_id INTEGER NOT NULL REFERENCES correos(id),
    accion    TEXT NOT NULL,
    detalle   TEXT,
    fecha     TEXT NOT NULL
);
"""


def abrir(ruta=config.DB_PATH):
    """Abre la base. La clave se lee de ~/.misyks/config (ver config.clave_db)."""
    ruta = Path(ruta)
    clave = config.clave_db()
    ruta.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return BaseDatos(ruta, clave)


class BaseDatos:
    def __init__(self, ruta, clave):
        if not re.fullmatch(r"[0-9a-f]{64}", clave):
            raise ValueError("La clave debe tener 64 caracteres hexadecimales.")
        nueva = not os.path.exists(ruta)
        self.conn = sqlcipher.connect(str(ruta))
        self.conn.execute(f"PRAGMA key = \"x'{clave}'\"")
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            # Comprueba la clave antes que nada: con una clave incorrecta,
            # executescript lanza MemoryError en vez de DatabaseError.
            self.conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlcipher.DatabaseError as e:
            self.conn.close()
            raise RuntimeError(f"No se pudo abrir {ruta}: clave incorrecta o archivo dañado ({e}).")
        self._migrar_de_imap()
        self._reparar_referencias()
        self.conn.executescript(ESQUEMA)
        if nueva:
            os.chmod(ruta, 0o600)
        self.conn.row_factory = sqlcipher.Row

    def _migrar_de_imap(self):
        """Pasa una base creada por el sec.mail de IMAP al esquema de OAuth.

        Los correos ya descargados no se vuelven a bajar: el `id` de la Gmail
        API es el mismo número que el `X-GM-MSGID` de IMAP, en hexadecimal en
        vez de en decimal, así que el identificador se convierte en sitio y
        sigue resolviendo contra el mismo mensaje de la cuenta.

        La tabla `sincronizacion` antigua (UIDVALIDITY + último UID) no tiene
        traducción: los UID no significan nada para la API. Se tira, y la
        primera sincronización tras la migración hace inventario completo de
        la carpeta -- lista identificadores, no descarga: los que ya están
        guardados se descartan contra `correos`.

        La tabla se reconstruye en vez de parchearse con `ALTER TABLE`, porque
        la columna vieja `gmail_msgid` es `NOT NULL UNIQUE` y los correos que
        lleguen por Graph no tienen ninguno: añadir columnas al lado dejaría
        una base que solo admite correos de Gmail.
        """
        columnas = {f[1] for f in self.conn.execute("PRAGMA table_info(correos)")}
        if not columnas or "mensaje_id" in columnas:
            return  # base nueva, o ya migrada

        # Las claves ajenas se apagan durante la reconstrucción: `adjuntos` y
        # `acciones` apuntan a `correos(id)` y los ids se conservan, pero
        # SQLite no sabe eso mientras la tabla no existe.
        self.conn.execute("PRAGMA foreign_keys = OFF")
        # Y además hay que pedirle a SQLite que NO sea listo con el rename.
        # Desde 3.25 `ALTER TABLE ... RENAME` reescribe las referencias que
        # otras tablas hacen a la renombrada: `adjuntos` pasaría a apuntar a
        # `correos_imap`, y al borrar esa tabla al final de la migración se
        # quedaría señalando a algo inexistente. La base sigue abriendo y
        # leyendo con normalidad -- el fallo solo aparece al insertar un
        # adjunto, mucho después y lejos de aquí. `legacy_alter_table`
        # devuelve el rename a lo que hace falta: mover la tabla y nada más.
        self.conn.execute("PRAGMA legacy_alter_table = ON")
        try:
            self.conn.execute("ALTER TABLE correos RENAME TO correos_imap")
            # La `sincronizacion` vieja lleva UIDVALIDITY y último UID; se
            # borra antes de crear el esquema nuevo porque `CREATE TABLE IF
            # NOT EXISTS` no sustituiría una tabla que ya existe.
            self.conn.execute("DROP TABLE IF EXISTS sincronizacion")
            self.conn.executescript(ESQUEMA)
            with self.conn:
                self.conn.execute(
                    """INSERT INTO correos
                       (id, proveedor, cuenta, mensaje_id, message_id, carpeta, remitente,
                        destinatarios, cc, asunto, fecha, cuerpo_texto, etiquetas, leido, eml,
                        sha256, guardado_en)
                       SELECT id, 'google', NULL,
                              printf('%x', CAST(gmail_msgid AS INTEGER)),
                              message_id, carpeta, remitente, destinatarios, cc, asunto, fecha,
                              cuerpo_texto, etiquetas, leido, eml, sha256, guardado_en
                       FROM correos_imap"""
                )
                self.conn.execute("DROP TABLE correos_imap")
        finally:
            self.conn.execute("PRAGMA legacy_alter_table = OFF")
            self.conn.execute("PRAGMA foreign_keys = ON")

    def _reparar_referencias(self):
        """Arregla las bases que migró la primera versión de `_migrar_de_imap`.

        Aquella renombraba `correos` sin `legacy_alter_table`, así que SQLite
        reescribió las claves ajenas de `adjuntos` y `acciones` para que
        apuntaran a `correos_imap`, una tabla que la propia migración borraba
        a continuación. El síntoma no era un error al abrir sino un
        `no such table: main.correos_imap` al guardar el primer adjunto.

        La reparación reconstruye esas tablas conservando sus filas. Es
        idempotente y no toca nada si las referencias están bien, así que
        puede correr en cada apertura.
        """
        rotas = [
            fila[0]
            for fila in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND sql LIKE '%correos_imap%'"
            )
        ]
        if not rotas:
            return

        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute("PRAGMA legacy_alter_table = ON")
        try:
            for tabla in rotas:
                columnas = [f[1] for f in self.conn.execute(f"PRAGMA table_info({tabla})")]
                lista = ", ".join(columnas)
                self.conn.execute(f"ALTER TABLE {tabla} RENAME TO {tabla}_rota")
                self.conn.executescript(ESQUEMA)  # recrea la tabla con la referencia correcta
                with self.conn:
                    self.conn.execute(
                        f"INSERT INTO {tabla} ({lista}) SELECT {lista} FROM {tabla}_rota"
                    )
                    self.conn.execute(f"DROP TABLE {tabla}_rota")
        finally:
            self.conn.execute("PRAGMA legacy_alter_table = OFF")
            self.conn.execute("PRAGMA foreign_keys = ON")

    def cerrar(self):
        self.conn.close()

    def guardar_correo(self, correo):
        """Guarda un correo con sus adjuntos. Devuelve su id, o None si ya estaba."""
        with self.conn:
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO correos
                   (proveedor, cuenta, mensaje_id, message_id, carpeta, remitente, destinatarios, cc,
                    asunto, fecha, cuerpo_texto, etiquetas, leido, eml, sha256, guardado_en)
                   VALUES (:proveedor, :cuenta, :mensaje_id, :message_id, :carpeta, :remitente,
                           :destinatarios, :cc, :asunto, :fecha, :cuerpo_texto, :etiquetas, :leido,
                           :eml, :sha256, :guardado_en)""",
                {**correo, "guardado_en": _ahora()},
            )
            if cur.rowcount == 0:
                return None
            correo_id = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO adjuntos (correo_id, nombre, tipo, bytes, contenido, sha256) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (correo_id, a["nombre"], a["tipo"], a["bytes"], a["contenido"], a["sha256"])
                    for a in correo["adjuntos"]
                ],
            )
            return correo_id

    def cursor_sincronizacion(self, proveedor, carpeta):
        fila = self.conn.execute(
            "SELECT cursor FROM sincronizacion WHERE proveedor = ? AND carpeta = ?",
            (proveedor, carpeta),
        ).fetchone()
        return fila["cursor"] if fila else None

    def guardar_cursor(self, proveedor, carpeta, cursor):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO sincronizacion (proveedor, carpeta, cursor) VALUES (?, ?, ?)",
                (proveedor, carpeta, cursor),
            )

    def encolar(self, proveedor, carpeta, mensaje_ids):
        """Apunta identificadores por descargar.

        Los que ya están guardados no entran en la cola: tras un inventario
        completo la lista trae toda la carpeta, y sin este filtro la cola
        tendría el histórico entero cada vez.
        """
        if not mensaje_ids:
            return
        with self.conn:
            self.conn.executemany(
                """INSERT OR IGNORE INTO pendientes (proveedor, carpeta, mensaje_id)
                   SELECT ?, ?, ?
                   WHERE NOT EXISTS (
                       SELECT 1 FROM correos WHERE proveedor = ? AND mensaje_id = ?
                   )""",
                [(proveedor, carpeta, m, proveedor, m) for m in mensaje_ids],
            )

    def pendientes(self, proveedor, carpeta, limite=None):
        """Identificadores por descargar, en orden de llegada. `limite` corta la tanda."""
        consulta = (
            "SELECT mensaje_id FROM pendientes WHERE proveedor = ? AND carpeta = ? ORDER BY id"
        )
        parametros = [proveedor, carpeta]
        if limite is not None:
            consulta += " LIMIT ?"
            parametros.append(limite)
        return [f["mensaje_id"] for f in self.conn.execute(consulta, parametros)]

    def cuantos_pendientes(self, proveedor, carpeta):
        return self.conn.execute(
            "SELECT count(*) AS n FROM pendientes WHERE proveedor = ? AND carpeta = ?",
            (proveedor, carpeta),
        ).fetchone()["n"]

    def desencolar(self, proveedor, carpeta, mensaje_id):
        with self.conn:
            self.conn.execute(
                "DELETE FROM pendientes WHERE proveedor = ? AND carpeta = ? AND mensaje_id = ?",
                (proveedor, carpeta, mensaje_id),
            )

    def correo(self, correo_id):
        return self.conn.execute(
            "SELECT id, proveedor, cuenta, mensaje_id, carpeta FROM correos WHERE id = ?", (correo_id,)
        ).fetchone()

    def listar(self, limite):
        return self.conn.execute(
            """SELECT id, fecha, carpeta, leido, remitente, asunto,
                      (SELECT count(*) FROM adjuntos WHERE correo_id = correos.id) AS adjuntos
               FROM correos ORDER BY id DESC LIMIT ?""",
            (limite,),
        ).fetchall()

    def marcar_leido(self, correo_id):
        with self.conn:
            self.conn.execute("UPDATE correos SET leido = 1 WHERE id = ?", (correo_id,))
            self._accion(correo_id, "marcar_leido", None)

    def mover(self, correo_id, origen, destino, mensaje_id=None):
        """Anota el movimiento. `mensaje_id` solo cuando el proveedor lo cambia.

        Microsoft Graph devuelve un mensaje nuevo al mover: si no se guardara
        el identificador nuevo, la fila apuntaría a un mensaje que ya no
        existe y la siguiente acción sobre ese correo fallaría.
        """
        with self.conn:
            if mensaje_id:
                self.conn.execute(
                    "UPDATE correos SET carpeta = ?, mensaje_id = ? WHERE id = ?",
                    (destino, mensaje_id, correo_id),
                )
            else:
                self.conn.execute("UPDATE correos SET carpeta = ? WHERE id = ?", (destino, correo_id))
            self._accion(correo_id, "mover", f"{origen} -> {destino}")

    def _accion(self, correo_id, accion, detalle):
        self.conn.execute(
            "INSERT INTO acciones (correo_id, accion, detalle, fecha) VALUES (?, ?, ?, ?)",
            (correo_id, accion, detalle, _ahora()),
        )


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
