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
    -- La vida del hito. `vencido` NO está aquí: se deriva al leer (ver
    -- `vida_efectiva`), porque guardarlo sería que el sistema diera por muerto
    -- un plazo por su cuenta.
    estado        TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente | ocurrido | en_pausa | cancelado
    fecha         TEXT,            -- ISO; vacía mientras no se sepa
    clase_fecha   TEXT,            -- real | limite | provisional | sin_senalar
    -- Quién lo dio por hecho, y es la distinción que pide `pro.acuse`:
    -- `acuse` hay justificante y consta; `abogado` lo dice quien lo hizo por su
    -- cuenta, fuera de MISYKS, y es una declaración.
    cerrado_por   TEXT,            -- acuse | abogado
    cerrado_en    TEXT,            -- fecha del hecho, no del registro
    motivo        TEXT,            -- por qué se pausó o se canceló
    -- El documento que lo acredita. Reservado: todavía no hay dónde guardar
    -- documentos del expediente, así que hoy va siempre vacío.
    documento_id  INTEGER,
    revisado      INTEGER NOT NULL DEFAULT 0,  -- ¿lo ha validado un abogado?
    UNIQUE (expediente_id, orden)
);
"""

# Los estados por los que pasa un hito. Los tres últimos solo tienen sentido en
# los de clase `limite` -- los plazos --, que son los únicos que se suspenden o
# se cancelan; una vista o una sentencia solo están pendientes u ocurridas.
ESTADOS = ("pendiente", "ocurrido", "en_pausa", "cancelado")

# Quién da un hito por hecho. `acuse`: hay justificante y consta. `abogado`: lo
# hizo por su cuenta, fuera del sistema, y lo está declarando.
CIERRES = ("acuse", "abogado")


def vida_efectiva(hito, hoy=None):
    """En qué punto está el hito, contando el paso del tiempo.

    `vencido` se calcula aquí y no se guarda. Escribirlo significaría que el
    sistema decide por su cuenta que un plazo ha muerto, y dar un asunto por
    perdido es demasiado grave para hacerlo en silencio -- además de que la
    decisión es de `pro.caducidad`, no de un almacén.

    Solo vence un **plazo** (`limite`) con fecha **firme**: si la fecha es
    `provisional` todavía puede moverse, y con datos dudosos no hay vencido.
    """
    if hito["estado"] != "pendiente" or hito["clase"] != "limite":
        return hito["estado"]
    if hito["clase_fecha"] != "limite":
        return "pendiente"
    fecha = (hito["fecha"] or "")[:10]
    return "vencido" if fecha and fecha < (hoy or _hoy()) else "pendiente"


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
        self._anadir_columnas_que_falten()
        if nueva:
            os.chmod(ruta, 0o600)
        self.conn.row_factory = sqlcipher.Row

    def cerrar(self):
        self.conn.close()

    def _anadir_columnas_que_falten(self):
        """Pone al día una base creada por una versión anterior del esquema.

        `CREATE TABLE IF NOT EXISTS` no toca una tabla que ya existe, así que
        una columna añadida después no aparecería y la primera escritura
        fallaría con `no such column`.
        """
        columnas = {f[1] for f in self.conn.execute("PRAGMA table_info(hitos)")}
        for nombre, tipo in (("cerrado_por", "TEXT"), ("cerrado_en", "TEXT"),
                             ("motivo", "TEXT"), ("documento_id", "INTEGER")):
            if nombre not in columnas:
                self.conn.execute(f"ALTER TABLE hitos ADD COLUMN {nombre} {tipo}")
        self.conn.commit()

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

    # --- la vida de un hito -----------------------------------------------
    #
    # Las transiciones se **reciben**. Quien decide que algo ha ocurrido es el
    # acuse de `pro.acuse`, una notificación que entra por LexNET, o el abogado
    # diciendo que lo hizo por su cuenta. El almacén anota, no deduce.

    def marcar_hecho(self, expediente_id, orden, por="abogado", fecha=None,
                     documento_id=None):
        """Da un hito por realizado. `por` es 'acuse' o 'abogado'.

        La fecha es la **del hecho**, no la del registro, y se guarda siempre:
        de ella cuelgan plazos posteriores -- el del silencio administrativo se
        cuenta desde la presentación, no desde el día en que alguien pulsó el
        botón--, y marcar sin fecha es perder ese dato para siempre.

        `documento_id` está previsto y hoy va vacío: cuando el expediente tenga
        dónde guardar documentos, un hito `acuse` llevará el suyo y entonces
        acreditado dejará de ser una palabra para ser un fichero.
        """
        if por not in CIERRES:
            raise ValueError(f"Cierre desconocido: {por}. Los que hay: {', '.join(CIERRES)}.")
        return self._cambiar_hito(
            expediente_id, orden, "ocurrido",
            cerrado_por=por, cerrado_en=fecha or _hoy(), documento_id=documento_id,
        )

    def deshacer_hito(self, expediente_id, orden):
        """Devuelve a pendiente un hito marcado por error.

        Marcar es un clic y los clics se dan sin querer; si no se pudiera
        deshacer, el remedio sería peor: alguien editando la base a mano.
        """
        hito = self.hito(expediente_id, orden)
        if hito["estado"] != "ocurrido":
            raise ValueError(f"El hito {orden} no está marcado como hecho: está {hito['estado']}.")
        return self._cambiar_hito(expediente_id, orden, "pendiente",
                                  cerrado_por=None, cerrado_en=None, documento_id=None)

    def pausar_hito(self, expediente_id, orden, motivo):
        """Suspende un plazo por un hecho registrado. El motivo es obligatorio.

        Una pausa sin causa anotada no se puede explicar después, y explicar por
        qué una fecha es la que es forma parte del contrato de todo lo que toca
        plazos.
        """
        if not motivo:
            raise ValueError("Una pausa necesita motivo: sin él no se puede explicar la fecha.")
        return self._cambiar_hito(expediente_id, orden, "en_pausa", motivo=motivo)

    def reanudar_hito(self, expediente_id, orden, fecha=None):
        """Reanuda un plazo pausado, con la fecha que trae quien reanuda.

        La fecha nueva llega **ya recalculada**: al reanudarse el vencimiento se
        mueve -- eso es lo que distingue una pausa de una marca decorativa --,
        pero el cálculo es de `pro.caducidad`.
        """
        hito = self.hito(expediente_id, orden)
        if hito["estado"] != "en_pausa":
            raise ValueError(f"El hito {orden} no está en pausa: está {hito['estado']}.")
        campos = {"motivo": None}
        if fecha:
            campos["fecha"] = fecha
        return self._cambiar_hito(expediente_id, orden, "pendiente", **campos)

    def cancelar_hito(self, expediente_id, orden, motivo):
        """Cancela el hito por un motivo registrado. Nunca se borra."""
        if not motivo:
            raise ValueError("Cancelar un hito necesita motivo registrado.")
        return self._cambiar_hito(expediente_id, orden, "cancelado", motivo=motivo)

    def hito(self, expediente_id, orden):
        fila = self.conn.execute(
            "SELECT * FROM hitos WHERE expediente_id = ? AND orden = ?",
            (expediente_id, orden),
        ).fetchone()
        if fila is None:
            raise LookupError(f"El expediente {expediente_id} no tiene ningún hito {orden}.")
        return fila

    def _cambiar_hito(self, expediente_id, orden, estado, **campos):
        if estado not in ESTADOS:
            raise ValueError(f"Estado desconocido: {estado}. Los que hay: {', '.join(ESTADOS)}.")
        self.hito(expediente_id, orden)  # existe, o LookupError con su mensaje
        campos["estado"] = estado
        asignaciones = ", ".join(f"{c} = ?" for c in campos)
        self.conn.execute(
            f"UPDATE hitos SET {asignaciones} WHERE expediente_id = ? AND orden = ?",
            tuple(campos.values()) + (expediente_id, orden),
        )
        self.conn.commit()
        return self.hito(expediente_id, orden)

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


def _hoy():
    # Fecha local y no UTC: «hoy» para un plazo es el día del calendario en el
    # que vive el abogado.
    return date.today().isoformat()
