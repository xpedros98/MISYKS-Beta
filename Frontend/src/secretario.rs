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
    Sincronizacion(String),
}

impl std::fmt::Display for SecMailError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SecMailError::DbNotFound(path) => write!(
                f,
                "No existe la base de datos en {path} todavia. Pulsa Refrescar para sincronizar."
            ),
            SecMailError::Sqlite(msg) => write!(f, "Error al leer la base de datos: {msg}"),
            SecMailError::Io(msg) => write!(f, "Error de E/S en la configuracion local: {msg}"),
            SecMailError::Sincronizacion(msg) => write!(f, "Fallo al sincronizar: {msg}"),
        }
    }
}

/// Ruta a Backend/ asumiendo que Frontend/ y Backend/ son carpetas hermanas
/// dentro del mismo checkout del repo (cierto durante desarrollo). Cuando la
/// app se distribuya como binario empaquetado esto tendra que resolverse de
/// otra forma -- no es el caso todavia.
fn backend_dir() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("Frontend/ deberia tener un padre")
        .join("Backend")
}

/// Invoca `python -m sec.mail sincronizar` en local, en tandas de `limite`
/// correos (los mas antiguos sin descargar todavia). Necesita que Ajustes ya
/// haya guardado usuario/password de Gmail en ~/.misyks/config -- si faltan,
/// sec.mail lo dira con su propio mensaje de error (RuntimeError de Python),
/// que se devuelve tal cual. No hay riesgo de duplicar: `guardar_correo`
/// ignora un gmail_msgid que ya estuviera guardado (UNIQUE en la tabla).
pub fn sincronizar(limite: i64) -> Result<String, SecMailError> {
    // Genera la clave de la base ANTES de invocar a Python: config.clave_db()
    // (Python) solo lee, nunca genera -- si no existe todavia (primera vez,
    // sin base creada aun) Python fallaria con un error confuso.
    LocalConfig::load()
        .clave_db_o_generarla()
        .map_err(|e| SecMailError::Io(e.to_string()))?;

    let backend = backend_dir();
    let python = backend.join(".venv/bin/python3");
    let salida = std::process::Command::new(&python)
        .args(["-m", "sec.mail", "sincronizar", "--limite", &limite.to_string()])
        .current_dir(&backend)
        .output()
        .map_err(|e| {
            SecMailError::Sincronizacion(format!(
                "no se pudo lanzar {}: {e}",
                python.display()
            ))
        })?;

    if !salida.status.success() {
        let stderr = String::from_utf8_lossy(&salida.stderr);
        return Err(SecMailError::Sincronizacion(stderr.trim().to_string()));
    }
    Ok(String::from_utf8_lossy(&salida.stdout).trim().to_string())
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
