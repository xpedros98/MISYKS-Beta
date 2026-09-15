"""Base de datos local cifrada con SQLCipher."""
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS correos (
    id            INTEGER PRIMARY KEY,
    gmail_msgid   TEXT NOT NULL UNIQUE,
    message_id    TEXT,
    carpeta       TEXT NOT NULL,             -- carpeta de Gmail donde está (cambia al moverlo)
    remitente     TEXT,
    destinatarios TEXT,
    cc            TEXT,
    asunto        TEXT,
    fecha         TEXT,
    cuerpo_texto  TEXT,
    etiquetas     TEXT,                      -- JSON, tal como estaban al guardarlo
    leido         INTEGER NOT NULL DEFAULT 0,
    eml           BLOB NOT NULL,             -- correo original completo
    sha256        TEXT NOT NULL,             -- huella del EML
    guardado_en   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adjuntos (
    id        INTEGER PRIMARY KEY,
    correo_id INTEGER NOT NULL REFERENCES correos(id),
    nombre    TEXT,
    tipo      TEXT,
    bytes     INTEGER NOT NULL,
    contenido BLOB NOT NULL,
    sha256    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sincronizacion (
    carpeta     TEXT PRIMARY KEY,
    uidvalidity INTEGER NOT NULL,
    ultimo_uid  INTEGER NOT NULL
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
    """Abre la base. La primera vez crea la clave y la guarda en el Llavero."""
    ruta = Path(ruta)
    clave = config.leer_secreto(config.SERVICIO_CLAVE_DB)
    if clave is None:
        if ruta.exists():
            raise RuntimeError(f"Existe {ruta} pero su clave no está en el Llavero.")
        clave = secrets.token_hex(32)
        config.guardar_secreto(config.SERVICIO_CLAVE_DB, clave)
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
        self.conn.executescript(ESQUEMA)
        if nueva:
            os.chmod(ruta, 0o600)
        self.conn.row_factory = sqlcipher.Row

    def cerrar(self):
        self.conn.close()

    def guardar_correo(self, correo):
        """Guarda un correo con sus adjuntos. Devuelve su id, o None si ya estaba guardado."""
        with self.conn:
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO correos
                   (gmail_msgid, message_id, carpeta, remitente, destinatarios, cc, asunto, fecha,
                    cuerpo_texto, etiquetas, leido, eml, sha256, guardado_en)
                   VALUES (:gmail_msgid, :message_id, :carpeta, :remitente, :destinatarios, :cc, :asunto,
                           :fecha, :cuerpo_texto, :etiquetas, :leido, :eml, :sha256, :guardado_en)""",
                {**correo, "guardado_en": _ahora()},
            )
            if cur.rowcount == 0:
                return None
            correo_id = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO adjuntos (correo_id, nombre, tipo, bytes, contenido, sha256) VALUES (?, ?, ?, ?, ?, ?)",
                [(correo_id, a["nombre"], a["tipo"], a["bytes"], a["contenido"], a["sha256"]) for a in correo["adjuntos"]],
            )
            return correo_id

    def estado(self, carpeta):
        """(uidvalidity, ultimo_uid) de la última sincronización de la carpeta."""
        fila = self.conn.execute(
            "SELECT uidvalidity, ultimo_uid FROM sincronizacion WHERE carpeta = ?", (carpeta,)
        ).fetchone()
        return (fila["uidvalidity"], fila["ultimo_uid"]) if fila else (None, 0)

    def avanzar(self, carpeta, uidvalidity, ultimo_uid):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO sincronizacion (carpeta, uidvalidity, ultimo_uid) VALUES (?, ?, ?)",
                (carpeta, uidvalidity, ultimo_uid),
            )

    def correo(self, correo_id):
        return self.conn.execute(
            "SELECT id, gmail_msgid, carpeta FROM correos WHERE id = ?", (correo_id,)
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

    def mover(self, correo_id, origen, destino):
        with self.conn:
            self.conn.execute("UPDATE correos SET carpeta = ? WHERE id = ?", (destino, correo_id))
            self._accion(correo_id, "mover", f"{origen} -> {destino}")

    def _accion(self, correo_id, accion, detalle):
        self.conn.execute(
            "INSERT INTO acciones (correo_id, accion, detalle, fecha) VALUES (?, ?, ?, ?)",
            (correo_id, accion, detalle, _ahora()),
        )


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
