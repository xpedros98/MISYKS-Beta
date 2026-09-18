// Los expedientes: el catalogo de tipos documentales y los expedientes abiertos.
//
// Dos fuentes distintas y conviene saber por que:
//
// - **El catalogo** (89 tipos) se lee del CSV del Backend,
//   `Backend/expedientes/datos/tipos.csv`. Es dato del repo, no de la maquina:
//   no hay base que abrir ni clave que pedir, y leerlo cuesta lo que leer un
//   fichero de 4 KB. Se acopla a un fichero de datos, que cambia mucho menos
//   que un esquema de base.
// - **Los expedientes** salen de `~/.misyks/expedientes.db`, cifrada con
//   SQLCipher porque lleva nombres de clientes. Igual que `secretario.rs` con
//   los correos: leer aqui, escribir por el Backend.
//
// Esa asimetria -- leer directo, escribir por Python -- es deliberada. Una
// lectura que se desincronice ensena un dato de menos; una escritura que se
// desincronice corrompe. Quien escribe es siempre el modulo que manda.
use rusqlite::Connection;

use crate::backend;
use crate::local_config::LocalConfig;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TipoDoc {
    pub tipo: String,
    pub arquetipo: String,
    pub destino: String,
}

impl std::fmt::Display for TipoDoc {
    /// Lo que se ve en el desplegable. El identificador se lee mejor con
    /// espacios que con guiones bajos, y el arquetipo va detras porque es lo
    /// que decide la ruta: dos tipos del mismo arquetipo se tratan igual.
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}  ·  {}", self.tipo.replace('_', " "), self.arquetipo)
    }
}

#[derive(Debug, Clone)]
pub struct Expediente {
    pub id: i64,
    pub referencia: String,
    pub tipo: String,
    pub arquetipo: String,
    pub titulo: Option<String>,
    pub destino: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Hito {
    pub orden: i64,
    pub nombre: String,
    /// `acto` · `limite` · `senalamiento` · `resolucion`. Dice que se puede
    /// esperar de su fecha, no como se pinta.
    pub clase: String,
    pub norma: Option<String>,
    pub ocurrido: bool,
    pub fecha: Option<String>,
    /// `real` · `limite` · `provisional` · `sin_senalar`. **Esto** es lo que
    /// decide como se pinta: «2 de octubre» como tope propio y «2 de octubre»
    /// como dia de vista no pueden parecer lo mismo.
    pub clase_fecha: Option<String>,
    /// Si la plantilla de la que salio la ha validado un abogado. Hoy, ninguna.
    pub revisado: bool,
}

impl Hito {
    /// Como se lee la fecha debajo del nodo.
    ///
    /// Un senalamiento sin fecha **no es un hueco**: es que el juzgado no lo ha
    /// fijado, y puede tardar meses. Decirlo es informacion; dejarlo en blanco
    /// parece un error del programa.
    pub fn fecha_legible(&self) -> String {
        match (&self.fecha, self.clase.as_str()) {
            (Some(f), _) => f.clone(),
            (None, "senalamiento") => "sin senalar".to_string(),
            (None, _) => "—".to_string(),
        }
    }

    /// La etiqueta que distingue que clase de fecha es. Vacia cuando no aporta.
    pub fn matiz(&self) -> &'static str {
        match self.clase_fecha.as_deref() {
            Some("limite") => "ultimo dia",
            Some("provisional") => "provisional",
            Some("real") => "",
            _ => "",
        }
    }
}

#[derive(Debug, Clone)]
pub enum ExpedientesError {
    SinCatalogo(String),
    Sqlite(String),
    Backend(String),
}

impl std::fmt::Display for ExpedientesError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ExpedientesError::SinCatalogo(detalle) => write!(
                f,
                "No se pudo leer el catalogo de tipos documentales: {detalle}"
            ),
            ExpedientesError::Sqlite(msg) => write!(f, "Error al leer los expedientes: {msg}"),
            ExpedientesError::Backend(msg) => write!(f, "{msg}"),
        }
    }
}

/// Los 89 tipos, en el orden del catalogo.
///
/// Ese orden agrupa por rama del derecho y no alfabeticamente, y se respeta:
/// ordenarlos por nombre mezclaria lo laboral con lo penal y obligaria a leer
/// la lista entera para encontrar algo.
pub fn tipos() -> Result<Vec<TipoDoc>, ExpedientesError> {
    let ruta = backend::dir()
        .map_err(ExpedientesError::SinCatalogo)?
        .join("expedientes")
        .join("datos")
        .join("tipos.csv");
    let contenido = std::fs::read_to_string(&ruta)
        .map_err(|e| ExpedientesError::SinCatalogo(format!("{}: {e}", ruta.display())))?;

    let mut filas = Vec::new();
    for (n, linea) in contenido.lines().enumerate() {
        if n == 0 || linea.trim().is_empty() {
            continue; // la cabecera
        }
        let campos: Vec<&str> = linea.split(',').collect();
        if campos.len() < 4 {
            continue;
        }
        filas.push(TipoDoc {
            tipo: campos[0].trim().to_string(),
            arquetipo: campos[1].trim().to_string(),
            destino: campos[3].trim().to_string(),
        });
    }
    if filas.is_empty() {
        return Err(ExpedientesError::SinCatalogo(format!(
            "{} no tiene ninguna fila",
            ruta.display()
        )));
    }
    Ok(filas)
}

/// Los expedientes abiertos, el mas reciente primero.
///
/// Que la base no exista todavia **no es un error**: es lo normal antes de
/// abrir el primero. Devuelve lista vacia, y la pantalla dira que no hay
/// ninguno en vez de ensenar una averia que no lo es.
pub fn abiertos() -> Result<Vec<Expediente>, ExpedientesError> {
    let db_path = LocalConfig::data_dir().join("expedientes.db");
    if !db_path.exists() {
        return Ok(Vec::new());
    }
    // La clave la genera el Backend al abrir el primer expediente (no hay
    // pantalla que la cree antes, al reves que con sec_mail.db). Si no esta,
    // es que la base no se ha llegado a usar.
    let config = LocalConfig::load();
    let Some(clave) = config.get("expedientes", "clave") else {
        return Ok(Vec::new());
    };

    let conn = Connection::open(&db_path).map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;
    conn.execute_batch(&format!("PRAGMA key = \"x'{clave}'\""))
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;
    // Igual que en db.py y en secretario.rs: fuerza el descifrado antes de dar
    // la clave por buena -- sqlcipher no falla hasta el primer acceso real.
    conn.query_row("SELECT count(*) FROM sqlite_master", [], |_| Ok(()))
        .map_err(|e| ExpedientesError::Sqlite(format!("clave incorrecta o archivo danado: {e}")))?;

    let mut stmt = conn
        .prepare(
            "SELECT id, referencia, tipo, arquetipo, titulo, destino
             FROM expedientes WHERE estado = 'abierto' ORDER BY id DESC",
        )
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;

    let filas = stmt
        .query_map([], |row| {
            Ok(Expediente {
                id: row.get(0)?,
                referencia: row.get(1)?,
                tipo: row.get(2)?,
                arquetipo: row.get(3)?,
                titulo: row.get(4)?,
                destino: row.get(5)?,
            })
        })
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;

    filas
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))
}

/// Los hitos de un expediente, en orden.
///
/// Lista vacia significa que su tipo no tiene plantilla escrita todavia (hay
/// para 5 de los 89), o que el expediente se abrio antes de que existiera la
/// tabla. Las dos cosas se cuentan igual en la pantalla: no hay recorrido que
/// ensenar, y no se inventa ninguno.
pub fn hitos(expediente_id: i64) -> Result<Vec<Hito>, ExpedientesError> {
    let db_path = LocalConfig::data_dir().join("expedientes.db");
    if !db_path.exists() {
        return Ok(Vec::new());
    }
    let config = LocalConfig::load();
    let Some(clave) = config.get("expedientes", "clave") else {
        return Ok(Vec::new());
    };

    let conn = Connection::open(&db_path).map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;
    conn.execute_batch(&format!("PRAGMA key = \"x'{clave}'\""))
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;
    conn.query_row("SELECT count(*) FROM sqlite_master", [], |_| Ok(()))
        .map_err(|e| ExpedientesError::Sqlite(format!("clave incorrecta o archivo danado: {e}")))?;

    let mut stmt = conn
        .prepare(
            "SELECT orden, nombre, clase, norma, estado, fecha, clase_fecha, revisado
             FROM hitos WHERE expediente_id = ?1 ORDER BY orden",
        )
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;

    let filas = stmt
        .query_map([expediente_id], |row| {
            Ok(Hito {
                orden: row.get(0)?,
                nombre: row.get(1)?,
                clase: row.get(2)?,
                norma: row.get(3)?,
                ocurrido: row.get::<_, String>(4)? == "ocurrido",
                fecha: row.get(5)?,
                clase_fecha: row.get(6)?,
                revisado: row.get::<_, i64>(7)? != 0,
            })
        })
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))?;

    filas
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| ExpedientesError::Sqlite(e.to_string()))
}

/// Abre un expediente del tipo indicado. La referencia la pone el Backend.
pub fn abrir(tipo: &str) -> Result<String, ExpedientesError> {
    backend::ejecutar("expedientes", &["abrir", tipo]).map_err(ExpedientesError::Backend)
}

/// Borra **todos** los expedientes, sin dejar rastro.
///
/// El `--si` es la confirmacion que el Backend exige para no borrar por
/// accidente desde un terminal. Aqui la ha dado una persona pulsando dos veces
/// (ver la pantalla): esta funcion no se invoca sin eso.
pub fn vaciar() -> Result<String, ExpedientesError> {
    backend::ejecutar("expedientes", &["vaciar", "--si"]).map_err(ExpedientesError::Backend)
}

/// Borra un expediente concreto.
pub fn eliminar(id: i64) -> Result<String, ExpedientesError> {
    backend::ejecutar("expedientes", &["eliminar", &id.to_string(), "--si"])
        .map_err(ExpedientesError::Backend)
}
