"""Calendario de festivos: base de datos local, sin cifrar.

A diferencia de `sec.mail`, aquí no hay nada confidencial. Los festivos son
dato público publicado en boletines oficiales, así que la base va en SQLite a
secas, sin SQLCipher y sin clave: cifrarla solo añadiría una dependencia y un
secreto que gestionar a cambio de proteger algo que cualquiera puede leer en
el BOE. La base *sí* vive en el mismo `~/.misyks` que el resto, porque
`pro.calendario` corre en el ordenador del letrado (ARQUITECTURA.md §1, «Dónde
corre cada agente»): el calendario podría vivir en el servidor, pero el motor
que lo consume no, y sin réplica local un corte de red dejaría al despacho sin
poder calcular ni un plazo.

Tres ideas sostienen el esquema:

**Los festivos se guardan dispersos, no día a día.** Una fila por día y
municipio serían unos seis millones de filas para decir «día normal» seis
millones de veces. Guardando solo los días que son festivos son unas decenas
de miles.

**Saber que un día no es festivo no es lo mismo que no saberlo.** Ausencia de
fila en `festivos` no significa «día hábil»: puede significar «los festivos
locales de ese municipio para ese año todavía no se han publicado». Esa
diferencia es la que decide si una fecha sale `firme` o `provisional`
(AGENTES.md, `pro.calendario`), y por eso existe `cobertura`, que responde por
separado a «¿tengo el dato?». Sin ella el sistema calcularía mal en silencio,
que es exactamente el riesgo que el catálogo describe.

**Las correcciones no borran.** Las comunidades rectifican sus festivos con el
año ya empezado (en 2026, Andalucía en febrero y abril; Aragón, en marzo). Si
una corrección sobrescribiera la fila, un plazo calculado en marzo dejaría de
poder reproducirse. En vez de eso, cada fila lleva la versión de calendario en
que nace (`alta`) y en la que deja de valer (`baja`), y toda consulta acepta
una versión: así el `version_calendario` que `pro.calendario` devuelve en cada
cálculo basta para repetirlo tal como se hizo.
"""
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".misyks"
DB_PATH = DATA_DIR / "calendario.db"

# Estados de `cobertura`. La diferencia entre los dos últimos importa: en
# `pendiente` el dato existe y aún no se ha recogido; en `sin_publicar` es que
# el boletín todavía no lo ha sacado (las locales salen entre agosto y
# diciembre del año anterior). Los dos producen fecha prudente, pero solo el
# segundo es normal y no hay nada que arreglar.
COBERTURA = ("confirmado", "pendiente", "sin_publicar")

# Los dos calendarios. No son el mismo con otro nombre: el judicial lo fija el
# art. 182 LOPJ por remisión a las fiestas laborales, y el administrativo sale
# de la resolución de días inhábiles de la AGE y de los acuerdos de cada
# comunidad (art. 30 Ley 39/2015). Confundirlos es uno de los «falla si» del
# catálogo.
COMPUTOS = ("judicial", "administrativo")

# Niveles de `ambitos`, de más general a más concreto. `insular` existe por
# Canarias, que añade fiestas por isla entre la comunidad y el municipio.
TIPOS_AMBITO = ("nacional", "autonomico", "insular", "local")

ESQUEMA = """
-- Cada recogida de datos que cambia algo abre una versión. Es lo que se
-- guarda junto a cada plazo calculado para poder repetir el cálculo después.
CREATE TABLE IF NOT EXISTS versiones (
    id        INTEGER PRIMARY KEY,
    creada_en TEXT NOT NULL,
    nota      TEXT
);
-- Las capas de festivos en un solo árbol. Un municipio no es una entidad
-- distinta de una comunidad a ojos del motor: los dos son «un sitio que
-- aporta días inhábiles», y resolver un día es subir la cadena
-- 08019 -> ES-CT -> ES. Con tablas separadas por nivel, añadir el nivel
-- insular de Canarias obligaría a tocar todas las consultas.
--
-- Los códigos de municipio son los del INE y van como TEXT, no como número:
-- son cinco dígitos con ceros por delante ('08019'), y guardarlos como
-- entero perdería el cero y con él la provincia.
CREATE TABLE IF NOT EXISTS ambitos (
    id     TEXT PRIMARY KEY,   -- 'ES', 'ES-CT', 'ES-TF-isla', '08019'
    tipo   TEXT NOT NULL,      -- nacional | autonomico | insular | local
    nombre TEXT NOT NULL,
    padre  TEXT REFERENCES ambitos(id)
);
CREATE INDEX IF NOT EXISTS ambitos_padre ON ambitos (padre);

-- De dónde salió cada dato. Dos URL a propósito: la de búsqueda es estable y
-- es por donde el recolector vuelve a entrar cada año; la del documento es la
-- publicación concreta que se encontró, y es la prueba que respalda la fecha.
CREATE TABLE IF NOT EXISTS fuentes (
    id            INTEGER PRIMARY KEY,
    ambito_id     TEXT NOT NULL REFERENCES ambitos(id),
    anio          INTEGER,
    boletin       TEXT NOT NULL,   -- BOE | DOGC | BOCYL-BU | BOTHA | BOB | BOG ...
    url_busqueda  TEXT NOT NULL,
    url_documento TEXT,
    descargado_en TEXT,
    sha256        TEXT,            -- huella del documento: delata una corrección
    UNIQUE (ambito_id, anio, boletin)
);

-- `computo` no es una etiqueta: son dos calendarios distintos con dos fuentes
-- distintas. El judicial sale de las fiestas laborales (art. 182 LOPJ remite a
-- ellas); el administrativo, de la resolución de días inhábiles de la AGE y de
-- los acuerdos equivalentes de cada comunidad. Un mismo día puede ser inhábil
-- en uno y hábil en el otro, así que cada cómputo lleva su propia fila aunque
-- la fecha coincida: solo así la explicación cita el boletín correcto.
CREATE TABLE IF NOT EXISTS festivos (
    ambito_id TEXT NOT NULL REFERENCES ambitos(id),
    fecha     TEXT NOT NULL,       -- ISO, YYYY-MM-DD
    computo   TEXT NOT NULL,       -- judicial | administrativo
    nombre    TEXT,
    fuente_id INTEGER REFERENCES fuentes(id),
    alta      INTEGER NOT NULL REFERENCES versiones(id),
    baja      INTEGER REFERENCES versiones(id),
    PRIMARY KEY (ambito_id, fecha, computo, alta)
);
CREATE INDEX IF NOT EXISTS festivos_fecha ON festivos (fecha);

CREATE TABLE IF NOT EXISTS cobertura (
    ambito_id     TEXT NOT NULL REFERENCES ambitos(id),
    anio          INTEGER NOT NULL,
    computo       TEXT NOT NULL,   -- judicial | administrativo
    estado        TEXT NOT NULL,   -- confirmado | pendiente | sin_publicar
    comprobado_en TEXT,
    fuente_id     INTEGER REFERENCES fuentes(id),
    alta          INTEGER NOT NULL REFERENCES versiones(id),
    baja          INTEGER REFERENCES versiones(id),
    PRIMARY KEY (ambito_id, anio, computo, alta)
);
CREATE INDEX IF NOT EXISTS cobertura_anio ON cobertura (anio);
"""

# Fragmento de WHERE que deja ver una fila tal como estaba en una versión
# dada. Una fila nace en `alta` y muere en `baja`, así que vale para la
# versión V si nació en V o antes y todavía no había muerto en V.
_VIGENTE = "{t}.alta <= :version AND ({t}.baja IS NULL OR {t}.baja > :version)"


def ventana(hoy=None):
    """Años que la base pretende cubrir: el corriente y el siguiente.

    Es ventana deslizante, no un rango fijo en el código. El suelo es el 1 de
    enero del año en curso y no el día de hoy porque el *dies a quo* suele
    estar en el pasado: una notificación llega fechada semanas atrás y su
    plazo ya está corriendo. El techo tampoco necesita tratarse aparte: un
    plazo que se vaya a 2029 no encontrará `cobertura` confirmada y saldrá
    provisional por el mismo camino que un festivo local sin publicar.
    """
    anio = (hoy or date.today()).year
    return (anio, anio + 1)


def abrir(ruta=DB_PATH):
    ruta = Path(ruta)
    ruta.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return Calendario(ruta)


class Calendario:
    def __init__(self, ruta):
        self.conn = sqlite3.connect(str(ruta))
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(ESQUEMA)
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            # El ámbito nacional no lo trae ningún boletín: es la raíz del
            # árbol y tiene que existir antes de que se cuelgue nada de él.
            self.conn.execute(
                "INSERT OR IGNORE INTO ambitos (id, tipo, nombre, padre)"
                " VALUES ('ES', 'nacional', 'España', NULL)"
            )

    def cerrar(self):
        self.conn.close()

    # --- versiones ---------------------------------------------------------

    def nueva_version(self, nota=None):
        """Abre una versión y devuelve su id. La abre quien va a escribir."""
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO versiones (creada_en, nota) VALUES (?, ?)", (_ahora(), nota)
            )
            return cur.lastrowid

    def version_actual(self):
        """Última versión escrita, o None en una base recién creada."""
        return self.conn.execute("SELECT max(id) AS v FROM versiones").fetchone()["v"]

    def _version(self, version):
        if version is not None:
            return version
        actual = self.version_actual()
        if actual is None:
            raise RuntimeError(
                "El calendario está vacío: no se ha recogido ningún festivo todavía."
            )
        return actual

    # --- escritura (la usa el recolector, no el motor) ---------------------

    def alta_ambito(self, id, tipo, nombre, padre=None):
        if tipo not in TIPOS_AMBITO:
            raise ValueError(f"Tipo de ámbito desconocido: {tipo}")
        with self.conn:
            # Upsert, no `INSERT OR REPLACE`: REPLACE borra la fila y la vuelve
            # a insertar, y al borrarla se lleva por delante a los ámbitos que
            # la tienen por padre (o falla por la clave ajena, según el orden).
            # Reimportar el callejero no puede desenganchar a los municipios de
            # su comunidad.
            self.conn.execute(
                """INSERT INTO ambitos (id, tipo, nombre, padre) VALUES (?, ?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET
                       tipo = excluded.tipo, nombre = excluded.nombre, padre = excluded.padre""",
                (id, tipo, nombre, padre),
            )

    def alta_fuente(self, ambito_id, anio, boletin, url_busqueda, url_documento=None, sha256=None):
        """Registra (o actualiza) una publicación. Devuelve su id."""
        with self.conn:
            self.conn.execute(
                """INSERT INTO fuentes
                       (ambito_id, anio, boletin, url_busqueda, url_documento, descargado_en, sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (ambito_id, anio, boletin) DO UPDATE SET
                       url_busqueda  = excluded.url_busqueda,
                       url_documento = excluded.url_documento,
                       descargado_en = excluded.descargado_en,
                       sha256        = excluded.sha256""",
                (ambito_id, anio, boletin, url_busqueda, url_documento, _ahora(), sha256),
            )
        # `lastrowid` no sirve aquí: en la rama DO UPDATE no hay fila nueva y
        # devuelve la de la última inserción, que puede ser de otra fuente.
        return self.conn.execute(
            "SELECT id FROM fuentes WHERE ambito_id = ? AND anio IS ? AND boletin = ?",
            (ambito_id, anio, boletin),
        ).fetchone()["id"]

    def anotar_festivo(self, ambito_id, fecha, computo, nombre, version, fuente_id=None):
        """Da de alta un festivo en `version`. Repetirlo no duplica nada."""
        _comprueba_computo(computo)
        if self._festivo_vigente(ambito_id, fecha, computo, version):
            return False
        with self.conn:
            self.conn.execute(
                """INSERT INTO festivos (ambito_id, fecha, computo, nombre, fuente_id, alta, baja)
                   VALUES (?, ?, ?, ?, ?, ?, NULL)""",
                (ambito_id, fecha, computo, nombre, fuente_id, version),
            )
        return True

    def retirar_festivo(self, ambito_id, fecha, computo, version):
        """Cierra un festivo que una corrección posterior ha quitado.

        No borra la fila: los plazos calculados antes de la corrección tienen
        que poder reproducirse con el calendario que se usó entonces.
        """
        _comprueba_computo(computo)
        with self.conn:
            cur = self.conn.execute(
                """UPDATE festivos SET baja = ?
                   WHERE ambito_id = ? AND fecha = ? AND computo = ? AND baja IS NULL""",
                (version, ambito_id, fecha, computo),
            )
            return cur.rowcount > 0

    def fijar_cobertura(self, ambito_id, anio, computo, estado, version, fuente_id=None):
        """Declara si se tiene el dato de ese ámbito, año y cómputo."""
        _comprueba_computo(computo)
        if estado not in COBERTURA:
            raise ValueError(f"Estado de cobertura desconocido: {estado}")
        with self.conn:
            # Solo se cierran las filas de versiones **anteriores**. Cerrar una
            # nacida en esta misma versión la dejaría con alta == baja, es
            # decir, viva durante ninguna versión, y además chocaría con la
            # clave primaria al reinsertar. Pasa en cuanto una comunidad tiene
            # varios boletines --Castilla y León tiene nueve-- y se declara su
            # cobertura una vez por cada uno.
            self.conn.execute(
                """UPDATE cobertura SET baja = ?
                   WHERE ambito_id = ? AND anio = ? AND computo = ?
                     AND baja IS NULL AND alta < ?""",
                (version, ambito_id, anio, computo, version),
            )
            self.conn.execute(
                """INSERT INTO cobertura
                       (ambito_id, anio, computo, estado, comprobado_en, fuente_id, alta, baja)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                   ON CONFLICT (ambito_id, anio, computo, alta) DO UPDATE SET
                       estado = excluded.estado,
                       comprobado_en = excluded.comprobado_en,
                       fuente_id = excluded.fuente_id,
                       baja = NULL""",
                (ambito_id, anio, computo, estado, _ahora(), fuente_id, version),
            )

    def _festivo_vigente(self, ambito_id, fecha, computo, version):
        return (
            self.conn.execute(
                "SELECT 1 FROM festivos f WHERE f.ambito_id = :a AND f.fecha = :f"
                f" AND f.computo = :c AND {_VIGENTE.format(t='f')}",
                {"a": ambito_id, "f": fecha, "c": computo, "version": version},
            ).fetchone()
            is not None
        )

    # --- lectura (la usa el motor) ----------------------------------------

    def cadena(self, ambito_id):
        """Los ámbitos que aportan festivos a un sitio, del concreto al nacional.

        Para un municipio de Canarias son cuatro (municipio, isla, comunidad,
        España); para uno de Madrid, tres. El motor no tiene que saber cuántos
        niveles hay: recorre lo que le devuelva esto.
        """
        cadena = []
        actual = ambito_id
        vistos = set()
        while actual and actual not in vistos:
            vistos.add(actual)
            fila = self.conn.execute(
                "SELECT id, tipo, nombre, padre FROM ambitos WHERE id = ?", (actual,)
            ).fetchone()
            if fila is None:
                raise KeyError(f"Ámbito desconocido: {actual}")
            cadena.append(fila)
            actual = fila["padre"]
        return cadena

    def inhabiles(self, ambito_id, computo, desde, hasta, version=None):
        """Festivos que afectan a un sitio entre dos fechas, ambas incluidas.

        Devuelve {fecha ISO: [(ámbito, nombre), ...]}. Un mismo día puede
        venir de dos capas (una fiesta local que cae en festivo autonómico) y
        se devuelven las dos, porque la explicación de la fecha las cita.

        `computo` no tiene valor por defecto a propósito: no hay un calendario
        «normal» del que el otro sea la excepción, y dejar que el motor se
        olvide de decirlo es precisamente el fallo de mezclar cómputo civil y
        administrativo que el catálogo marca.

        Ojo: no incluye sábados ni domingos. La inhabilidad del fin de semana,
        la de agosto y la de Navidad son reglas del motor, no datos de
        boletín, y mezclarlas aquí ataría el calendario al orden
        jurisdiccional, que este módulo no conoce.
        """
        _comprueba_computo(computo)
        version = self._version(version)
        ambitos = [a["id"] for a in self.cadena(ambito_id)]
        parametros = {"desde": desde, "hasta": hasta, "version": version, "c": computo}
        marcas = []
        for i, ambito in enumerate(ambitos):
            clave = f"a{i}"
            parametros[clave] = ambito
            marcas.append(f":{clave}")
        filas = self.conn.execute(
            f"""SELECT f.fecha, f.ambito_id, f.nombre
                FROM festivos f
                WHERE f.ambito_id IN ({", ".join(marcas)})
                  AND f.computo = :c
                  AND f.fecha BETWEEN :desde AND :hasta
                  AND {_VIGENTE.format(t='f')}
                ORDER BY f.fecha""",
            parametros,
        ).fetchall()
        dias = {}
        for fila in filas:
            dias.setdefault(fila["fecha"], []).append((fila["ambito_id"], fila["nombre"]))
        return dias

    def festivos_de(self, ambito_id, computo, desde, hasta, version=None):
        """Fechas anotadas **en ese ámbito y solo en ese**, sin subir la cadena.

        Es lo contrario de `inhabiles`, y las dos hacen falta. El motor
        pregunta por la cadena, porque a un plazo de Barcelona le afectan los
        festivos de España, de Cataluña y de la ciudad. El recolector pregunta
        por el ámbito suelto, porque cuando relee la publicación de Cataluña
        solo puede retirar festivos de Cataluña: los nacionales que la cadena
        le devolvería no son suyos y retirarlos sería destruir el calendario.
        """
        _comprueba_computo(computo)
        version = self._version(version)
        return [
            fila["fecha"]
            for fila in self.conn.execute(
                "SELECT f.fecha FROM festivos f WHERE f.ambito_id = :a AND f.computo = :c"
                f" AND f.fecha BETWEEN :desde AND :hasta AND {_VIGENTE.format(t='f')}"
                " ORDER BY f.fecha",
                {
                    "a": ambito_id, "c": computo, "desde": desde,
                    "hasta": hasta, "version": version,
                },
            )
        ]

    def lagunas(self, ambito_id, computo, anios, version=None):
        """Lo que no se sabe de un sitio en esos años, y por qué.

        Devuelve [(ámbito, año, estado)] con todo lo que no está `confirmado`,
        incluidos los ámbitos de los que no hay ni fila de cobertura: para el
        motor, «nunca lo he comprobado» y «lo comprobé y falta» pesan igual.
        Lista vacía significa que la fecha puede salir `firme`.
        """
        _comprueba_computo(computo)
        version = self._version(version)
        faltan = []
        for ambito in self.cadena(ambito_id):
            for anio in anios:
                estado = self._cobertura(ambito["id"], anio, computo, version)
                if estado != "confirmado":
                    faltan.append((ambito["id"], anio, estado))
        return faltan

    def mapa_cobertura(self, anios, version=None):
        """Estado de todos los ámbitos, para la pantalla de mantenimiento.

        Devuelve [(ámbito, tipo, nombre, año, cómputo, estado)]. Es la vista
        que evita que el calendario envejezca en silencio.
        """
        version = self._version(version)
        ambitos = self.conn.execute(
            "SELECT id, tipo, nombre FROM ambitos ORDER BY tipo, nombre"
        ).fetchall()
        return [
            (a["id"], a["tipo"], a["nombre"], anio, computo,
             self._cobertura(a["id"], anio, computo, version))
            for a in ambitos
            for anio in anios
            for computo in COMPUTOS
        ]

    def fuentes_a_revisar(self, anios):
        """Publicaciones por las que el recolector tiene que volver a pasar.

        Incluye las de `anio` nulo: son las fuentes que no dependen del año
        (portada de un boletín, buscador), por donde se entra a buscar la
        publicación del año que toque.
        """
        marcas = ", ".join("?" * len(anios))
        return self.conn.execute(
            f"""SELECT id, ambito_id, anio, boletin, url_busqueda, url_documento, sha256
                FROM fuentes WHERE anio IS NULL OR anio IN ({marcas})
                ORDER BY ambito_id, anio""",
            tuple(anios),
        ).fetchall()

    def _cobertura(self, ambito_id, anio, computo, version):
        fila = self.conn.execute(
            "SELECT c.estado FROM cobertura c WHERE c.ambito_id = :a AND c.anio = :anio"
            f" AND c.computo = :c AND {_VIGENTE.format(t='c')}",
            {"a": ambito_id, "anio": anio, "c": computo, "version": version},
        ).fetchone()
        return fila["estado"] if fila else "pendiente"


def _comprueba_computo(computo):
    if computo not in COMPUTOS:
        raise ValueError(f"Cómputo desconocido: {computo}. Debe ser uno de {COMPUTOS}.")


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
