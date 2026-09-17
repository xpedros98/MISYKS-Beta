// Lee la base de festivos que rellena `Backend/pro/calendario` (ver db.py).
//
// A diferencia de `sec_mail.db`, esta base **no esta cifrada**: los festivos son
// dato publico del BOE, asi que no hay clave que gestionar ni nada que pedirle
// al config. Se abre ademas en **solo lectura**, por dos razones: el frontend no
// tiene por que escribir aqui, y `recolectar` puede estar corriendo en un
// terminal mientras alguien mira esta pantalla.
//
// ACOPLAMIENTO CON EL BACKEND. Este modulo conoce el esquema de la base, igual
// que `secretario.rs` conoce el de los correos, y eso significa que hay dos
// sitios que saben lo mismo sin nada que los ate. Si Python renombra una
// columna, Rust compila igual y el fallo aparece en ejecucion -- o peor, deja de
// mostrar un dato sin decir nada, que es el modo de fallo que este proyecto
// persigue. Mitigacion: `comprobar_esquema` mira que esten las columnas que se
// usan y falla con un mensaje que nombra lo que falta, en vez de devolver una
// lista vacia que parece un calendario sin festivos.
use rusqlite::{Connection, OpenFlags};

use crate::local_config::LocalConfig;

/// Columnas de las que depende este modulo. Si el Backend cambia el esquema,
/// esto es lo que avisa; la lista se actualiza a mano cuando cambie la consulta.
const COLUMNAS: &[(&str, &[&str])] = &[
    ("ambitos", &["id", "tipo", "nombre", "padre"]),
    ("festivos", &["ambito_id", "fecha", "computo", "nombre", "alta", "baja"]),
    ("cobertura", &["ambito_id", "anio", "computo", "estado", "detalle", "alta", "baja"]),
    ("versiones", &["id"]),
];

pub const COMPUTOS: [&str; 2] = ["judicial", "administrativo"];

#[derive(Debug, Clone)]
pub enum CalendarioError {
    SinBase(String),
    Esquema(String),
    Sqlite(String),
    Vacio,
}

impl std::fmt::Display for CalendarioError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CalendarioError::SinBase(path) => write!(
                f,
                "No hay calendario todavia ({path}).\n\
                 Desde Backend/: python -m pro.calendario recolectar"
            ),
            CalendarioError::Esquema(detalle) => write!(
                f,
                "La base de festivos no tiene la forma esperada: {detalle}.\n\
                 El Backend ha cambiado el esquema y este modulo no se ha actualizado."
            ),
            CalendarioError::Sqlite(e) => write!(f, "Error leyendo el calendario: {e}"),
            CalendarioError::Vacio => write!(
                f,
                "El calendario esta creado pero vacio.\n\
                 Desde Backend/: python -m pro.calendario recolectar"
            ),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Ambito {
    pub id: String,
    pub nombre: String,
}

#[derive(Debug, Clone)]
pub struct Festivo {
    pub fecha: String,
    pub ambito: String,
    pub tipo: String,
    pub nombre: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Laguna {
    pub ambito: String,
    pub estado: String,
}

#[derive(Debug, Clone)]
pub struct Averia {
    pub ambito: String,
    pub anio: i64,
    pub computo: String,
    pub detalle: Option<String>,
}

/// Lo que se ve de un vistazo: version, cobertura por nivel y lo que ha fallado.
#[derive(Debug, Clone)]
pub struct Resumen {
    pub version: i64,
    pub ultimo_festivo: Option<String>,
    /// (nivel, confirmado, pendiente, sin_publicar, fallido)
    pub cobertura: Vec<(String, i64, i64, i64, i64)>,
    pub averias: Vec<Averia>,
}

fn abrir() -> Result<Connection, CalendarioError> {
    let ruta = LocalConfig::data_dir().join("calendario.db");
    if !ruta.exists() {
        return Err(CalendarioError::SinBase(ruta.display().to_string()));
    }
    // Solo lectura: ni escribimos, ni queremos estorbar a un `recolectar` que
    // pueda estar corriendo a la vez.
    let conn = Connection::open_with_flags(&ruta, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    comprobar_esquema(&conn)?;
    Ok(conn)
}

fn comprobar_esquema(conn: &Connection) -> Result<(), CalendarioError> {
    for (tabla, esperadas) in COLUMNAS {
        let mut stmt = conn
            .prepare(&format!("PRAGMA table_info({tabla})"))
            .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
        let presentes: Vec<String> = stmt
            .query_map([], |row| row.get::<_, String>(1))
            .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
            .collect::<Result<_, _>>()
            .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
        if presentes.is_empty() {
            return Err(CalendarioError::Esquema(format!("falta la tabla `{tabla}`")));
        }
        for columna in *esperadas {
            if !presentes.iter().any(|p| p == columna) {
                return Err(CalendarioError::Esquema(format!(
                    "`{tabla}` no tiene la columna `{columna}`"
                )));
            }
        }
    }
    Ok(())
}

fn version(conn: &Connection) -> Result<i64, CalendarioError> {
    conn.query_row("SELECT max(id) FROM versiones", [], |row| {
        row.get::<_, Option<i64>>(0)
    })
    .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
    .ok_or(CalendarioError::Vacio)
}

pub fn resumen() -> Result<Resumen, CalendarioError> {
    let conn = abrir()?;
    let v = version(&conn)?;

    let mut stmt = conn
        .prepare(
            "SELECT a.tipo, c.estado, count(*)
             FROM cobertura c JOIN ambitos a ON a.id = c.ambito_id
             WHERE c.alta <= ?1 AND (c.baja IS NULL OR c.baja > ?1)
             GROUP BY a.tipo, c.estado",
        )
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    let filas: Vec<(String, String, i64)> = stmt
        .query_map([v], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
        .collect::<Result<_, _>>()
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;

    // Mismo orden que `TIPOS_AMBITO` en db.py: de lo general a lo concreto.
    let mut cobertura = Vec::new();
    for nivel in ["nacional", "autonomico", "insular", "local"] {
        let cuenta = |estado: &str| {
            filas
                .iter()
                .find(|(t, e, _)| t == nivel && e == estado)
                .map(|(_, _, n)| *n)
                .unwrap_or(0)
        };
        let fila = (
            nivel.to_string(),
            cuenta("confirmado"),
            cuenta("pendiente"),
            cuenta("sin_publicar"),
            cuenta("fallido"),
        );
        if fila.1 + fila.2 + fila.3 + fila.4 > 0 {
            cobertura.push(fila);
        }
    }

    let ultimo_festivo = conn
        .query_row(
            "SELECT max(fecha) FROM festivos
             WHERE alta <= ?1 AND (baja IS NULL OR baja > ?1)",
            [v],
            |row| row.get::<_, Option<String>>(0),
        )
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;

    let mut stmt = conn
        .prepare(
            "SELECT ambito_id, anio, computo, detalle FROM cobertura
             WHERE estado = 'fallido' AND alta <= ?1 AND (baja IS NULL OR baja > ?1)
             ORDER BY ambito_id, anio",
        )
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    let averias = stmt
        .query_map([v], |row| {
            Ok(Averia {
                ambito: row.get(0)?,
                anio: row.get(1)?,
                computo: row.get(2)?,
                detalle: row.get(3)?,
            })
        })
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
        .collect::<Result<_, _>>()
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;

    Ok(Resumen { version: v, ultimo_festivo, cobertura, averias })
}

/// El primer ano que cubre la base, que es el ano en curso segun `db.ventana()`.
///
/// Se lee de la base en vez de calcularlo del reloj del sistema: el Backend ya
/// decidio que ventana cubre al recolectar, y derivarlo aparte aqui seria
/// arriesgarse a que las dos mitades discrepen --justo en un proyecto donde
/// equivocarse de ano es un plazo perdido--.
pub fn anio_base() -> Result<i32, CalendarioError> {
    let conn = abrir()?;
    conn.query_row("SELECT min(anio) FROM cobertura", [], |row| {
        row.get::<_, Option<i32>>(0)
    })
    .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
    .ok_or(CalendarioError::Vacio)
}

/// Los municipios, para el selector. Solo el nivel local: son los sitios donde
/// se litiga, y preguntar por una comunidad suelta no le sirve a nadie.
pub fn municipios() -> Result<Vec<Ambito>, CalendarioError> {
    let conn = abrir()?;
    let mut stmt = conn
        .prepare("SELECT id, nombre FROM ambitos WHERE tipo = 'local' ORDER BY nombre")
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    let filas = stmt
        .query_map([], |row| {
            Ok(Ambito { id: row.get(0)?, nombre: row.get(1)? })
        })
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    Ok(filas)
}

/// Dias inhabiles de un sitio en un ano, subiendo la cadena de ambitos.
///
/// La cadena se recorre con un CTE recursivo en vez de a mano: es la misma
/// operacion que hace `cadena()` en db.py --municipio, isla si la hay,
/// comunidad, Espana-- y resolverla en SQL evita que el frontend tenga que
/// saber cuantos niveles existen.
pub fn dias_inhabiles(
    ambito: &str,
    computo: &str,
    anio: i32,
) -> Result<Vec<Festivo>, CalendarioError> {
    let conn = abrir()?;
    let v = version(&conn)?;
    let mut stmt = conn
        .prepare(
            "WITH RECURSIVE cadena(id) AS (
                 SELECT ?1
                 UNION
                 SELECT a.padre FROM ambitos a JOIN cadena c ON a.id = c.id
                 WHERE a.padre IS NOT NULL
             )
             SELECT f.fecha, f.ambito_id, a.tipo, f.nombre
             FROM festivos f
             JOIN cadena c ON c.id = f.ambito_id
             JOIN ambitos a ON a.id = f.ambito_id
             WHERE f.computo = ?2
               AND f.fecha BETWEEN ?3 AND ?4
               AND f.alta <= ?5 AND (f.baja IS NULL OR f.baja > ?5)
             ORDER BY f.fecha",
        )
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    let filas = stmt
        .query_map(
            rusqlite::params![
                ambito,
                computo,
                format!("{anio}-01-01"),
                format!("{anio}-12-31"),
                v
            ],
            |row| {
                Ok(Festivo {
                    fecha: row.get(0)?,
                    ambito: row.get(1)?,
                    tipo: row.get(2)?,
                    nombre: row.get(3)?,
                })
            },
        )
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    Ok(filas)
}

/// Lo que falta de la cadena de un sitio. Lista vacia = la fecha puede ser firme.
///
/// Ausencia de fila cuenta como `pendiente`, igual que en db.py: una base que no
/// sabe nada tiene que comportarse como tal, no como si todo estuviera bien.
pub fn lagunas(ambito: &str, computo: &str, anio: i32) -> Result<Vec<Laguna>, CalendarioError> {
    let conn = abrir()?;
    let v = version(&conn)?;
    let mut stmt = conn
        .prepare(
            "WITH RECURSIVE cadena(id) AS (
                 SELECT ?1
                 UNION
                 SELECT a.padre FROM ambitos a JOIN cadena c ON a.id = c.id
                 WHERE a.padre IS NOT NULL
             )
             SELECT c.id, COALESCE(co.estado, 'pendiente')
             FROM cadena c
             LEFT JOIN cobertura co
               ON co.ambito_id = c.id AND co.anio = ?2 AND co.computo = ?3
              AND co.alta <= ?4 AND (co.baja IS NULL OR co.baja > ?4)
             WHERE COALESCE(co.estado, 'pendiente') <> 'confirmado'",
        )
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    let filas = stmt
        .query_map(rusqlite::params![ambito, anio, computo, v], |row| {
            Ok(Laguna { ambito: row.get(0)?, estado: row.get(1)? })
        })
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| CalendarioError::Sqlite(e.to_string()))?;
    Ok(filas)
}
