// Lee directamente la base SQLCipher que rellena el agente Python
// Backend/sec/mail (ver db.py) — mismo esquema, misma ruta, misma clave del
// Llavero. Este modulo no sincroniza con Gmail ni escribe nada: solo lectura,
// igual que `python -m sec.mail listar`.

#[derive(Debug, Clone)]
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
    OnlyMacOs,
    KeychainKeyMissing,
    DbNotFound(String),
    Sqlite(String),
}

impl std::fmt::Display for SecMailError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SecMailError::OnlyMacOs => {
                write!(f, "sec.mail solo funciona en macOS (usa el Llavero del sistema).")
            }
            SecMailError::KeychainKeyMissing => write!(
                f,
                "No se encontro la clave de la base de datos en el Llavero. \
                 Ejecuta el agente Python al menos una vez (python -m sec.mail sincronizar)."
            ),
            SecMailError::DbNotFound(path) => write!(
                f,
                "No existe la base de datos en {path}. Sincroniza primero con el agente Python."
            ),
            SecMailError::Sqlite(msg) => write!(f, "Error al leer la base de datos: {msg}"),
        }
    }
}

#[cfg(target_os = "macos")]
pub fn list_emails(limit: i64) -> Result<Vec<EmailSummary>, SecMailError> {
    use rusqlite::Connection;

    let db_path = db_path();
    if !std::path::Path::new(&db_path).exists() {
        return Err(SecMailError::DbNotFound(db_path));
    }
    let key = keychain_key()?;

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

#[cfg(not(target_os = "macos"))]
pub fn list_emails(_limit: i64) -> Result<Vec<EmailSummary>, SecMailError> {
    Err(SecMailError::OnlyMacOs)
}

#[cfg(target_os = "macos")]
fn db_path() -> String {
    let home = std::env::var("HOME").expect("HOME no esta definido");
    format!("{home}/Library/Application Support/MISYKS/sec_mail.db")
}

#[cfg(target_os = "macos")]
fn keychain_key() -> Result<String, SecMailError> {
    use security_framework::passwords::get_generic_password;

    // Mismos valores que config.CUENTA_LLAVERO / config.SERVICIO_CLAVE_DB en
    // Backend/sec/mail/config.py (cuenta="sec.mail", servicio="MISYKS sec.mail clave DB").
    let bytes = get_generic_password("MISYKS sec.mail clave DB", "sec.mail")
        .map_err(|_| SecMailError::KeychainKeyMissing)?;
    String::from_utf8(bytes).map_err(|_| SecMailError::KeychainKeyMissing)
}
