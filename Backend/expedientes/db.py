"""Base de expedientes, cifrada con SQLCipher.

Cifrada, y aquí no hay debate posible: un expediente lleva el nombre del cliente,
el del contrario y el asunto. Es lo contrario del calendario de festivos, que va
en SQLite a secas porque es dato público del BOE.

La referencia (`EXP-2026-001`) la pone la base y no quien llama: es lo que el
abogado va a usar para nombrar el asunto en voz alta, y tiene que ser correlativa
por año sin huecos raros. Se calcula dentro de la misma transacción que la
inserción, o dos expedientes abiertos a la vez se llevarían el mismo número.
"""
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from sec.cuentas import ajustes

from . import catalogo, config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS expedientes (
    id          INTEGER PRIMARY KEY,
    referencia  TEXT NOT NULL UNIQUE,     -- EXP-2026-001, lo que se dice en voz alta
    tipo        TEXT NOT NULL,            -- uno de los 89 de datos/tipos.csv
    arquetipo   TEXT NOT NULL,            -- A-J, copiado del catálogo al abrir
    destino     TEXT,                     -- canal de salida previsto, del catálogo
    titulo      TEXT,                     -- cómo lo llama el despacho
    cliente     TEXT,
    contrario   TEXT,
    organo      TEXT,                     -- juzgado o administración, cuando se sabe
    estado      TEXT NOT NULL DEFAULT 'abierto',   -- abierto | cerrado
    abierto_en  TEXT NOT NULL,
    cerrado_en  TEXT
);
CREATE INDEX IF NOT EXISTS expedientes_por_estado ON expedientes (estado);
-- Los hitos del caso: por dónde pasa este expediente. Se instancian al abrirlo
-- desde la plantilla del tipo (datos/hitos.csv) y a partir de ahí son suyos: si
-- mañana se corrige la plantilla, un expediente vivo no cambia de recorrido.
CREATE TABLE IF NOT EXISTS hitos (
    id            INTEGER PRIMARY KEY,
    expediente_id INTEGER NOT NULL REFERENCES expedientes(id) ON DELETE CASCADE,
    orden         INTEGER NOT NULL,
    nombre        TEXT NOT NULL,
    clase         TEXT NOT NULL,   -- acto | limite | senalamiento | resolucion
    norma         TEXT,
    estado        TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente | ocurrido
    fecha         TEXT,            -- ISO; vacía mientras no se sepa
    clase_fecha   TEXT,            -- real | limite | provisional | sin_senalar
    revisado      INTEGER NOT NULL DEFAULT 0,  -- ¿lo ha validado un abogado?
    UNIQUE (expediente_id, orden)
);
"""

# El arquetipo y el destino se copian del catálogo al abrir, en vez de mirarse
# cada vez: si mañana se corrige la matriz de §5, un expediente ya abierto no
# debe cambiar de ruta por su cuenta -- eso es lo que hace que un plazo calculado
# hace tres meses deje de poder explicarse.


def abrir_base(ruta=None):
    ruta = Path(ruta or config.DB_PATH)
    clave = ajustes.clave_db("expedientes", generar=True)
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

    def abrir_expediente(self, tipo, titulo=None, cliente=None, contrario=None, organo=None):
        """Crea el expediente y devuelve su fila. La referencia la pone la base.

        El tipo se valida contra el catálogo antes de tocar nada: un expediente
        de un tipo inexistente no tendría ruta, ni plazos, ni canal de salida.
        """
        ficha = catalogo.tipo(tipo)
        plantilla = catalogo.hitos(tipo)
        with self.conn:  # una transacción: numerar y guardar no pueden separarse
            referencia = self._siguiente_referencia()
            cursor = self.conn.execute(
                "INSERT INTO expedientes (referencia, tipo, arquetipo, destino, titulo, "
                "cliente, contrario, organo, abierto_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    referencia,
                    ficha["tipo"],
                    ficha["arquetipo"],
                    ficha["destino"],
                    titulo or ficha["tipo"].replace("_", " ").capitalize(),
                    cliente,
                    contrario,
                    organo,
                    _ahora(),
                ),
            )
            # Los hitos se copian de la plantilla, no se consultan cada vez. Un
            # expediente abierto hace tres meses tiene que seguir enseñando el
            # recorrido con el que se abrió, aunque la plantilla haya cambiado:
            # es la misma razón por la que el arquetipo se copia y no se mira.
            for h in plantilla:
                self.conn.execute(
                    "INSERT INTO hitos (expediente_id, orden, nombre, clase, norma, "
                    "clase_fecha, revisado) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        cursor.lastrowid,
                        int(h["orden"]),
                        h["hito"],
                        h["clase"],
                        h["norma"],
                        # Un señalamiento nace sin fecha y eso es su estado
                        # normal, no un hueco que haya que rellenar.
                        "sin_senalar" if h["clase"] == "senalamiento" else None,
                        1 if h.get("revisado") == "si" else 0,
                    ),
                )
        return self.expediente(cursor.lastrowid)

    def _siguiente_referencia(self):
        """`EXP-<año>-<n>`, correlativo dentro del año en curso.

        Se cuenta sobre las referencias existentes del año y no sobre el total
        de filas: borrar un expediente no debe hacer que el siguiente repita un
        número que ya se usó en un escrito.
        """
        anio = date.today().year
        fila = self.conn.execute(
            "SELECT referencia FROM expedientes WHERE referencia LIKE ? "
            "ORDER BY referencia DESC LIMIT 1",
            (f"EXP-{anio}-%",),
        ).fetchone()
        siguiente = int(fila["referencia"].rsplit("-", 1)[1]) + 1 if fila else 1
        return f"EXP-{anio}-{siguiente:03d}"

    def hitos(self, expediente_id):
        """Los hitos del expediente, en orden. Lista vacía si su tipo no tiene plantilla."""
        return self.conn.execute(
            "SELECT * FROM hitos WHERE expediente_id = ? ORDER BY orden", (expediente_id,)
        ).fetchall()

    def fechar_hito(self, expediente_id, orden, fecha, clase_fecha, ocurrido=False):
        """Pone fecha a un hito y, si procede, lo da por ocurrido.

        **La barra no avanza sola.** Un hito pasa a `ocurrido` porque alguien
        —o algún día un acuse de `pro.acuse`, o una notificación de LexNET—
        aporta la prueba de que ocurrió. Si el sistema pudiera marcarlo por su
        cuenta, antes o después daría por presentado algo que no lo está.
        """
        cursor = self.conn.execute(
            "UPDATE hitos SET fecha = ?, clase_fecha = ?, estado = ? "
            "WHERE expediente_id = ? AND orden = ?",
            (fecha, clase_fecha, "ocurrido" if ocurrido else "pendiente", expediente_id, orden),
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            raise LookupError(f"El expediente {expediente_id} no tiene ningún hito {orden}.")

    def expediente(self, fila_id):
        return self.conn.execute("SELECT * FROM expedientes WHERE id = ?", (fila_id,)).fetchone()

    def listar(self, estado="abierto"):
        """Los expedientes, el más reciente primero. `estado=None` los trae todos."""
        if estado is None:
            return self.conn.execute(
                "SELECT * FROM expedientes ORDER BY id DESC"
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM expedientes WHERE estado = ? ORDER BY id DESC", (estado,)
        ).fetchall()

    def cerrar_expediente(self, fila_id):
        """Lo saca de los abiertos sin borrarlo. Es lo que debería usarse casi siempre."""
        self.conn.execute(
            "UPDATE expedientes SET estado = 'cerrado', cerrado_en = ? WHERE id = ?",
            (_ahora(), fila_id),
        )
        self.conn.commit()

    def eliminar(self, fila_id):
        """Borra el expediente de verdad. Devuelve cuántos ha borrado (0 o 1).

        Distinto de cerrar: esto no deja rastro. Hoy vale porque un expediente
        no es más que una ficha; en cuanto cuelguen de él documentos, plazos y
        acuses, borrar tendrá que dejar de estar disponible sin más y pasar a
        ser una operación con motivo y registro.
        """
        cursor = self.conn.execute("DELETE FROM expedientes WHERE id = ?", (fila_id,))
        self.conn.commit()
        return cursor.rowcount

    def vaciar(self):
        """Borra todos los expedientes. Devuelve cuántos había.

        Quien llama tiene que haber confirmado antes: aquí ya no se pregunta
        nada. Existe porque mientras se prueba el sistema se abren expedientes
        de mentira y hay que poder limpiarlos de una vez.
        """
        cuantos = self.conn.execute("SELECT count(*) FROM expedientes").fetchone()[0]
        self.conn.execute("DELETE FROM expedientes")
        self.conn.commit()
        return cuantos


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
