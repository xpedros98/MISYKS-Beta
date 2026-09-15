// Lee directamente la base SQLCipher que rellena el agente Python
// Backend/sec/mail (ver db.py) — mismo esquema, misma ruta, misma clave del
// archivo de config local (~/.misyks/config). Este modulo no sincroniza con
// Gmail ni escribe correos: solo lectura, igual que `python -m sec.mail
// listar`. sec.mail corre en local (no en el servidor) porque es quien tiene
// la contrasena de correo — por eso ni la clave de la base ni las
// credenciales salen nunca de este ordenador.
use rusqlite::Connection;

use crate::local_config::LocalConfig;

#[derive(Debug, Clone)]
// id y carpeta no se muestran todavia en la lista (screens/secretario.rs),
// pero hacen falta en cuanto haya acciones (marcar leido, mover) sobre una
// fila concreta — se quedan en la struct en vez de recalcularse luego.
#[allow(dead_code)]
pub struct EmailSummary {
    pub id: i64,
    pub fecha: Option<String>,
    pub carpeta: String,
    pub leido: bool,
    pub remitente: Option<String>,
    pub asunto: Option<String>,
    pub adjuntos: i64,
}

#[derive(Debug, Clone)]
pub enum SecMailError {
    DbNotFound(String),
    Sqlite(String),
    Io(String),
}

impl std::fmt::Display for SecMailError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SecMailError::DbNotFound(path) => write!(
                f,
                "No existe la base de datos en {path}. Sincroniza primero con el agente Python \
                 (python -m sec.mail sincronizar), tras rellenar las credenciales en Ajustes."
            ),
            SecMailError::Sqlite(msg) => write!(f, "Error al leer la base de datos: {msg}"),
            SecMailError::Io(msg) => write!(f, "Error de E/S en la configuracion local: {msg}"),
        }
    }
}

pub fn list_emails(limit: i64) -> Result<Vec<EmailSummary>, SecMailError> {
    let db_path = LocalConfig::data_dir().join("sec_mail.db");
    if !db_path.exists() {
        return Err(SecMailError::DbNotFound(db_path.display().to_string()));
    }

    let mut config = LocalConfig::load();
    let key = config
        .clave_db_o_generarla()
        .map_err(|e| SecMailError::Io(e.to_string()))?;

    let conn = Connection::open(&db_path).map_err(|e| SecMailError::Sqlite(e.to_string()))?;
    conn.execute_batch(&format!("PRAGMA key = \"x'{key}'\""))
        .map_err(|e| SecMailError::Sqlite(e.to_string()))?;
    // Misma comprobacion que db.py: fuerza el descifrado antes de asumir que
    // la clave es correcta (con una clave mala, sqlcipher no falla hasta el
    // primer acceso real a las paginas de la base).
    conn.query_row("SELECT count(*) FROM sqlite_master", [], |_| Ok(()))
        .map_err(|e| SecMailError::Sqlite(format!("clave incorrecta o archivo danado: {e}")))?;

    let mut stmt = conn
        .prepare(
            "SELECT id, fecha, carpeta, leido, remitente, asunto,
                    (SELECT count(*) FROM adjuntos WHERE correo_id = correos.id) AS adjuntos
             FROM correos ORDER BY id DESC LIMIT ?1",
        )
        .map_err(|e| SecMailError::Sqlite(e.to_string()))?;

    let rows = stmt
        .query_map([limit], |row| {
            Ok(EmailSummary {
                id: row.get(0)?,
                fecha: row.get(1)?,
                carpeta: row.get(2)?,
                leido: row.get::<_, i64>(3)? != 0,
                remitente: row.get(4)?,
                asunto: row.get(5)?,
                adjuntos: row.get(6)?,
            })
        })
        .map_err(|e| SecMailError::Sqlite(e.to_string()))?;

    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| SecMailError::Sqlite(e.to_string()))
}
