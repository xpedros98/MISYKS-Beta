"""Base de datos local de la agenda, cifrada con SQLCipher.

Base propia (`~/.misyks/sec_agenda.db`) y no una tabla más dentro de la de
correo: son dos módulos y cada uno responde de lo suyo. Comparten el archivo de
credenciales porque la cuenta es una sola; no tienen por qué compartir datos.

**Una sola tabla de eventos, con `tipo` y `origen`.** Un juicio que llega del
calendario del abogado, una reunión escrita a mano y un plazo que entrega
`procesal` acaban todos en la misma agenda y se miran juntos o no sirven de
nada. Lo que cambia entre ellos -- si se pueden mover, quién los produjo, si
son firmes -- son columnas, no tablas.
"""
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from ..cuentas import ajustes
from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id           INTEGER PRIMARY KEY,
    proveedor    TEXT NOT NULL,            -- google | microsoft | '' si no vino de fuera
    cuenta       TEXT,                     -- calendario del que vino
    evento_id    TEXT NOT NULL,            -- identificador en el proveedor, o el nuestro
    serie_id     TEXT,                     -- serie a la que pertenece, si es una repetición
    repeticion   TEXT,                     -- RRULE con la que se creó, si nació aquí
    tipo         TEXT NOT NULL,            -- sin_clasificar | reunion | vista | plazo | obligacion
    origen       TEXT NOT NULL,            -- calendario | procesal | manual
    abogado      TEXT,                     -- de quién es la agenda; se cruzan entre sí
    titulo       TEXT,
    lugar        TEXT,
    descripcion  TEXT,
    inicio_local TEXT,                     -- la hora que se lee, sin desplazamiento
    fin_local    TEXT,
    zona         TEXT,                     -- nombre de zona del proveedor, opaco
    inicio_utc   TEXT,                     -- el instante; con esto se comparan solapes
    fin_utc      TEXT,
    todo_el_dia  INTEGER NOT NULL DEFAULT 0,
    cancelado    INTEGER NOT NULL DEFAULT 0,
    organizador  TEXT,
    asistentes   TEXT,
    expediente   TEXT,                     -- plazos y obligaciones
    estado       TEXT,                     -- firme | provisional, lo dice procesal
    franja       TEXT,                     -- holgado | ajustado | critico | vencido
    actualizado_en TEXT,
    guardado_en  TEXT NOT NULL
);
-- La identidad es (proveedor, evento_id), por lo mismo que en sec.mail: dos
-- proveedores pueden dar el mismo identificador y no son el mismo evento. Los
-- de origen interno llevan proveedor '' y un evento_id nuestro ('plazo:123').
CREATE UNIQUE INDEX IF NOT EXISTS eventos_identidad ON eventos (proveedor, evento_id);
CREATE INDEX IF NOT EXISTS eventos_por_fecha ON eventos (inicio_local);
-- Cursor de sincronización incremental, opaco: syncToken en Google, deltaLink
-- en Graph. Se guarda con la ventana que se usó al pedirlo, porque el cursor
-- la lleva dentro y reusarlo con otra ventana deja huecos en silencio.
CREATE TABLE IF NOT EXISTS sincronizacion (
    proveedor   TEXT NOT NULL,
    calendario  TEXT NOT NULL,
    cursor      TEXT,
    desde       TEXT,
    hasta       TEXT,
    PRIMARY KEY (proveedor, calendario)
);
CREATE TABLE IF NOT EXISTS acciones (
    id        INTEGER PRIMARY KEY,
    evento_id INTEGER NOT NULL REFERENCES eventos(id),
    accion    TEXT NOT NULL,
    detalle   TEXT,
    fecha     TEXT NOT NULL
);
"""

# `sin_clasificar` es el tipo con el que entra todo lo que viene del calendario
# del abogado: la API no dice si un evento es un juicio o un café, y suponerlo
# es exactamente lo que no debe hacer un módulo. Lo fija después `clasificar`.
TIPOS = ("sin_clasificar", "reunion", "vista", "plazo", "obligacion")

# Los que ocupan una hora del abogado y por tanto pueden chocar entre sí. Un
# plazo es una fecha dura sin hora: no colisiona con nadie, vence.
#
# `sin_clasificar` cuenta como ocupado a propósito, y es la misma prudencia que
# `pro.calendario` aplica a los festivos que le faltan: un aviso de colisión que
# resulta ser un café se descarta en dos segundos; una vista sin clasificar que
# no avisa de que pisa otra se descubre el día del señalamiento.
TIPOS_CON_HORA = ("sin_clasificar", "reunion", "vista")


def abrir(ruta=None):
    """Abre la base. La clave sale de `[secagenda] clave` (ver ajustes.clave_db)."""
    ruta = Path(ruta or config.DB_PATH)
    clave = ajustes.clave_db("secagenda", generar=True)
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
            # Igual que en sec.mail: con clave incorrecta, executescript lanza
            # MemoryError en vez de DatabaseError, así que se comprueba antes.
            self.conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlcipher.DatabaseError as e:
            self.conn.close()
            raise RuntimeError(f"No se pudo abrir {ruta}: clave incorrecta o archivo dañado ({e}).")
        self.conn.executescript(ESQUEMA)
        self._anadir_columnas_que_falten()
        if nueva:
            os.chmod(ruta, 0o600)
        self.conn.row_factory = sqlcipher.Row

    def _anadir_columnas_que_falten(self):
        """Pone al día una base creada por una versión anterior del esquema.

        `CREATE TABLE IF NOT EXISTS` no toca una tabla que ya existe, así que
        una columna añadida después no aparecería y la primera escritura
        fallaría con `no such column`. Se comparan las columnas reales con las
        del esquema y se añade lo que falte, que es lo único que SQLite permite
        hacer sin reconstruir la tabla.
        """
        # Por posición y no por nombre: `row_factory` todavía no está puesto
        # cuando esto corre, así que las filas son tuplas. En `table_info`, el
        # nombre de la columna es el campo 1.
        columnas = {f[1] for f in self.conn.execute("PRAGMA table_info(eventos)")}
        # `letrado` pasó a llamarse `abogado`: son la misma persona y el sistema
        # habla de una sola. «Letrado» se reserva para el **Letrado de la
        # Administración de Justicia**, que es otro papel —firma decretos y
        # notifica por LexNET— y aparece en las resoluciones que hay que leer.
        # Se renombra la columna en vez de crear otra: los datos son los mismos.
        if "letrado" in columnas and "abogado" not in columnas:
            self.conn.execute("ALTER TABLE eventos RENAME COLUMN letrado TO abogado")
            columnas.add("abogado")
        for nombre, tipo in (("repeticion", "TEXT"),):
            if nombre not in columnas:
                self.conn.execute(f"ALTER TABLE eventos ADD COLUMN {nombre} {tipo}")
        self.conn.commit()

    def cerrar(self):
        self.conn.close()

    # --- sincronización ---------------------------------------------------

    def cursor_sincronizacion(self, proveedor, calendario, desde, hasta):
        """El cursor guardado, o None si no sirve para esta ventana.

        Devolver None obliga a un recorrido completo, que es lo correcto: el
        cursor se emitió con otra ventana y no sabe nada de los días que ahora
        se piden de más.
        """
        fila = self.conn.execute(
            "SELECT cursor, desde, hasta FROM sincronizacion WHERE proveedor = ? AND calendario = ?",
            (proveedor, calendario),
        ).fetchone()
        if fila is None or not fila["cursor"]:
            return None
        if fila["desde"] != desde or fila["hasta"] != hasta:
            return None
        return fila["cursor"]

    def guardar_cursor(self, proveedor, calendario, cursor, desde, hasta):
        self.conn.execute(
            "INSERT INTO sincronizacion (proveedor, calendario, cursor, desde, hasta) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(proveedor, calendario) DO UPDATE SET cursor = excluded.cursor, "
            "desde = excluded.desde, hasta = excluded.hasta",
            (proveedor, calendario, cursor, desde, hasta),
        )
        self.conn.commit()

    # --- eventos ----------------------------------------------------------

    def guardar_evento(self, evento):
        """Inserta o actualiza por (proveedor, evento_id). Devuelve qué pasó.

        'nuevo', 'actualizado' o 'igual'. Distinguirlos no es cosmético: es lo
        que permite que `sec.notificador` avise solo de lo que ha cambiado en
        vez de repetir la agenda entera cada vez que alguien sincroniza.

        El `tipo` y el `abogado` de una fila ya existente **no se pisan**: los
        pone quien clasifica (hoy, una persona), y una sincronización posterior
        no tiene por qué saber que aquel evento del calendario era una vista.
        """
        campos = {
            clave: evento.get(clave)
            for clave in (
                "proveedor", "cuenta", "evento_id", "serie_id", "repeticion", "tipo",
                "origen", "abogado",
                "titulo", "lugar", "descripcion", "inicio_local", "fin_local", "zona",
                "inicio_utc", "fin_utc", "todo_el_dia", "cancelado", "organizador",
                "asistentes", "expediente", "estado", "franja",
            )
        }
        campos["todo_el_dia"] = int(bool(campos.get("todo_el_dia")))
        campos["cancelado"] = int(bool(campos.get("cancelado")))
        if campos.get("tipo") not in TIPOS:
            raise ValueError(f"Tipo de evento desconocido: {campos.get('tipo')}. Los que hay: {', '.join(TIPOS)}.")

        anterior = self.evento_por_identidad(campos["proveedor"], campos["evento_id"])
        ahora = _ahora()
        if anterior is None:
            campos["actualizado_en"] = ahora
            campos["guardado_en"] = ahora
            columnas = ", ".join(campos)
            huecos = ", ".join("?" for _ in campos)
            cursor = self.conn.execute(
                f"INSERT INTO eventos ({columnas}) VALUES ({huecos})", tuple(campos.values())
            )
            self.conn.commit()
            return "nuevo", cursor.lastrowid

        cambios = {
            clave: valor
            for clave, valor in campos.items()
            # `tipo` y `abogado` se respetan si ya estaban clasificados a mano.
            if clave not in ("tipo", "abogado") and valor != anterior[clave]
        }
        if not cambios:
            return "igual", anterior["id"]
        cambios["actualizado_en"] = ahora
        asignaciones = ", ".join(f"{c} = ?" for c in cambios)
        self.conn.execute(
            f"UPDATE eventos SET {asignaciones} WHERE id = ?",
            tuple(cambios.values()) + (anterior["id"],),
        )
        self.conn.commit()
        return "actualizado", anterior["id"]

    def evento_por_identidad(self, proveedor, evento_id):
        return self.conn.execute(
            "SELECT * FROM eventos WHERE proveedor = ? AND evento_id = ?",
            (proveedor or "", evento_id),
        ).fetchone()

    def evento(self, fila_id):
        return self.conn.execute("SELECT * FROM eventos WHERE id = ?", (fila_id,)).fetchone()

    def clasificar(self, fila_id, tipo=None, abogado=None, expediente=None):
        """Dice qué es un evento que llegó del calendario sin decirlo.

        Del calendario del abogado no viene el tipo: un evento llamado «Juicio
        Pérez» es una vista y otro llamado «Café con Marta» no, y nada en la
        API lo distingue. Hasta que `sec.clasificador` mire el título, esto lo
        pone una persona, y por eso una sincronización posterior no lo pisa.
        """
        cambios = {}
        if tipo is not None:
            if tipo not in TIPOS:
                raise ValueError(f"Tipo de evento desconocido: {tipo}. Los que hay: {', '.join(TIPOS)}.")
            cambios["tipo"] = tipo
        if abogado is not None:
            cambios["abogado"] = abogado
        if expediente is not None:
            cambios["expediente"] = expediente
        if not cambios:
            return
        cambios["actualizado_en"] = _ahora()
        asignaciones = ", ".join(f"{c} = ?" for c in cambios)
        self.conn.execute(
            f"UPDATE eventos SET {asignaciones} WHERE id = ?", tuple(cambios.values()) + (fila_id,)
        )
        self.conn.commit()

    def marcar_ausentes_como_cancelados(self, proveedor, cuenta, desde, hasta, vistos):
        """Cancela los eventos de la ventana que el proveedor ya no entrega.

        Solo se puede llamar tras un recorrido **completo**: en uno incremental,
        que un evento no venga significa que no ha cambiado, no que no exista.
        Confundir las dos cosas vacía la agenda de golpe.

        No borra: un señalamiento que se cae es información, y quien lo mire la
        semana que viene tiene que poder ver que estuvo ahí.
        """
        filas = self.conn.execute(
            "SELECT id, evento_id FROM eventos WHERE proveedor = ? AND cuenta = ? "
            "AND origen = 'calendario' AND cancelado = 0 "
            "AND substr(inicio_local, 1, 10) BETWEEN ? AND ?",
            (proveedor, cuenta, desde, hasta),
        ).fetchall()
        desaparecidos = [f["id"] for f in filas if f["evento_id"] not in vistos]
        for fila_id in desaparecidos:
            self.conn.execute(
                "UPDATE eventos SET cancelado = 1, actualizado_en = ? WHERE id = ?",
                (_ahora(), fila_id),
            )
            self.registrar(fila_id, "cancelado", "ya no está en el calendario del proveedor")
        self.conn.commit()
        return desaparecidos

    # --- plazos que entrega procesal --------------------------------------

    def anotar_plazo(self, plazo_id, fecha_limite, asunto, expediente=None, organo=None,
                     estado="firme", franja=None, abogado=None):
        """Anota o actualiza un plazo calculado por `procesal`.

        **La agenda no computa: recibe.** Aquí no se suma ni un día; lo que
        llega es una fecha ya calculada y lo único que se hace es guardarla y
        decir si se ha movido respecto a la anterior.

        Devuelve (`qué pasó`, `fecha anterior`), con «qué pasó» en
        'nuevo' · 'adelantado' · 'retrasado' · 'igual'. La distinción es la que
        necesita `sec.notificador` y está escrita en COMPONENTES.md: un plazo
        que se **adelanta** exige aviso inmediato porque puede costar el plazo;
        uno que se retrasa se actualiza sin interrumpir a nadie.
        """
        anterior = self.evento_por_identidad("", f"plazo:{plazo_id}")
        fecha_anterior = anterior["inicio_local"] if anterior else None
        self.guardar_evento(
            {
                "proveedor": "",
                "cuenta": "",
                "evento_id": f"plazo:{plazo_id}",
                "tipo": "plazo",
                "origen": "procesal",
                "abogado": abogado,
                "titulo": asunto,
                "lugar": organo,
                "inicio_local": fecha_limite,
                "fin_local": fecha_limite,
                "todo_el_dia": True,
                "expediente": expediente,
                "estado": estado,
                "franja": franja,
            }
        )
        fila = self.evento_por_identidad("", f"plazo:{plazo_id}")
        if anterior is None:
            self.registrar(fila["id"], "plazo_anotado", f"{fecha_limite} ({estado})")
            return "nuevo", None
        if fecha_anterior == fecha_limite:
            return "igual", fecha_anterior
        movimiento = "adelantado" if fecha_limite < fecha_anterior else "retrasado"
        # El detalle se escribe en ASCII a propósito: acaba imprimiéndose en la
        # consola, y la de Windows es cp1252, donde una flecha «→» no existe y
        # revienta el `print` entero con UnicodeEncodeError.
        self.registrar(fila["id"], f"plazo_{movimiento}", f"{fecha_anterior} -> {fecha_limite}")
        return movimiento, fecha_anterior

    # --- consultas --------------------------------------------------------

    def agenda(self, desde, hasta, abogado=None, incluir_cancelados=False):
        """Lo que hay entre dos fechas, en orden. Todo junto: es el punto."""
        condiciones = ["substr(inicio_local, 1, 10) BETWEEN ? AND ?"]
        valores = [desde, hasta]
        if abogado:
            condiciones.append("abogado = ?")
            valores.append(abogado)
        if not incluir_cancelados:
            condiciones.append("cancelado = 0")
        return self.conn.execute(
            f"SELECT * FROM eventos WHERE {' AND '.join(condiciones)} "
            "ORDER BY substr(inicio_local, 1, 10), todo_el_dia DESC, inicio_local",
            tuple(valores),
        ).fetchall()

    def colisiones(self, desde, hasta):
        """Pares de compromisos que se pisan. Cada par sale una vez.

        Se comparan **instantes** (`inicio_utc`), no horas locales: dos eventos
        creados en zonas distintas darían solapes inventados, y peor, dejarían
        de dar los reales.

        Solo chocan los que ocupan una hora -- reuniones y vistas --. Un plazo
        es una fecha dura sin hora: no colisiona, vence.

        Se devuelven también los pares de **abogados distintos**, marcados como
        'despacho'. No son un error pero hay que verlos: dos señalamientos a la
        misma hora en un despacho de dos personas son dos desplazamientos, y es
        lo que COMPONENTES.md exige al decir que fallar es «no cruzar agendas
        entre abogados del despacho».
        """
        tipos = ", ".join(f"'{t}'" for t in TIPOS_CON_HORA)
        return self.conn.execute(
            f"""
            SELECT a.id AS a_id, a.titulo AS a_titulo, a.inicio_local AS a_inicio,
                   a.fin_local AS a_fin, a.abogado AS a_abogado, a.tipo AS a_tipo,
                   b.id AS b_id, b.titulo AS b_titulo, b.inicio_local AS b_inicio,
                   b.fin_local AS b_fin, b.abogado AS b_abogado, b.tipo AS b_tipo,
                   CASE WHEN IFNULL(a.abogado, '') = IFNULL(b.abogado, '')
                        THEN 'mismo_abogado' ELSE 'despacho' END AS ambito
              FROM eventos a
              JOIN eventos b ON b.id > a.id
             WHERE a.cancelado = 0 AND b.cancelado = 0
               AND a.tipo IN ({tipos}) AND b.tipo IN ({tipos})
               AND a.inicio_utc <> '' AND a.fin_utc <> ''
               AND b.inicio_utc <> '' AND b.fin_utc <> ''
               AND a.inicio_utc < b.fin_utc AND b.inicio_utc < a.fin_utc
               AND substr(a.inicio_local, 1, 10) BETWEEN ? AND ?
             ORDER BY a.inicio_utc
            """,
            (desde, hasta),
        ).fetchall()

    def registrar(self, evento_fila_id, accion, detalle=None):
        """Todo lo que la agenda hace sobre un evento queda anotado.

        Mismo motivo que el registro de acciones de `sec.mail`: si un plazo se
        mueve o un señalamiento se cae, tiene que poder reconstruirse cuándo se
        supo, no solo cómo está ahora.
        """
        self.conn.execute(
            "INSERT INTO acciones (evento_id, accion, detalle, fecha) VALUES (?, ?, ?, ?)",
            (evento_fila_id, accion, detalle, _ahora()),
        )
        self.conn.commit()

    def acciones(self, limite=50):
        return self.conn.execute(
            "SELECT a.*, e.titulo FROM acciones a JOIN eventos e ON e.id = a.evento_id "
            "ORDER BY a.id DESC LIMIT ?",
            (limite,),
        ).fetchall()


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
