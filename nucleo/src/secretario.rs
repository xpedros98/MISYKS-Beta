// Lee directamente la base SQLCipher que rellena el agente Python
// Backend/sec/mail (ver db.py) — mismo esquema, misma ruta, misma clave del
// archivo de config local (~/.misyks/config). Este modulo no sincroniza con
// el buzon ni escribe correos: solo lectura, igual que `python -m sec.mail
// listar`. sec.mail corre en local (no en el servidor) porque es quien tiene
// el acceso al correo — por eso ni la clave de la base ni los tokens de OAuth
// salen nunca de este ordenador.
use rusqlite::Connection;

use crate::backend;
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
    BackendNoEncontrado(String),
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
            SecMailError::BackendNoEncontrado(probadas) => write!(
                f,
                "No se encontro la carpeta Backend/ con el agente sec.mail. Buscada en: {probadas}. \
                 Define MISYKS_BACKEND si esta en otro sitio."
            ),
        }
    }
}

/// Invoca `python -m sec.mail sincronizar` en local, en tandas de `limite`
/// correos (los mas antiguos anunciados por el servidor y todavia sin bajar).
/// Necesita que haya una cuenta conectada por OAuth (boton «Conectar cuenta»
/// de Ajustes) -- si no la hay, sec.mail lo dira con su propio mensaje de
/// error, que se devuelve tal cual. No hay riesgo de duplicar: la base ignora
/// un mensaje ya guardado (indice unico por proveedor + identificador).
pub fn sincronizar(limite: i64) -> Result<String, SecMailError> {
    // Genera la clave de la base ANTES de invocar a Python: config.clave_db()
    // (Python) solo lee, nunca genera -- si no existe todavia (primera vez,
    // sin base creada aun) Python fallaria con un error confuso.
    LocalConfig::load()
        .clave_db_o_generarla()
        .map_err(|e| SecMailError::Io(e.to_string()))?;

    orden_secmail(&["sincronizar", "--limite", &limite.to_string()])
}

/// Lanza el consentimiento OAuth **en un hilo aparte** y avisa al terminar.
///
/// Es lo que permite que la ventana siga viva mientras la persona elige cuenta
/// en el navegador. Antes se llamaba a `conectar` dentro de `update`, que
/// bloquea el bucle de eventos de `iced` hasta cinco minutos: la ventana no
/// repintaba, el navegador podía abrirse detrás y desde fuera parecía que el
/// botón no hacía nada -- que es justo como se veía en macOS.
///
/// El trabajo va a un hilo del sistema y no al ejecutor asíncrono: es una
/// espera **bloqueante** de un subproceso, y meterla en una tarea asíncrona
/// ocuparía un hilo del ejecutor igual, solo que disimulado.
pub fn conectar_async(proveedor: String) -> iced::Task<Result<String, SecMailError>> {
    let (envio, recepcion) = iced::futures::channel::oneshot::channel();
    std::thread::spawn(move || {
        let _ = envio.send(conectar(&proveedor));
    });
    iced::Task::perform(
        async move {
            recepcion.await.unwrap_or_else(|_| {
                Err(SecMailError::Sincronizacion(
                    "el proceso de conexion termino sin decir nada".to_string(),
                ))
            })
        },
        |r| r,
    )
}

/// Lanza el consentimiento OAuth: abre el navegador en el dominio del
/// proveedor y espera a que la persona autorice.
///
/// Bloquea hasta que termina, y puede tardar lo que tarde alguien en elegir
/// cuenta y leer una pantalla de permisos (sec.mail espera hasta 5 minutos).
/// La contrasena no se escribe en ninguna ventana de esta aplicacion: la pide
/// Google en el navegador, que es justamente el motivo de haber dejado la
/// contrasena de aplicacion (ARQUITECTURA.md 8.6).
pub fn conectar(proveedor: &str) -> Result<String, SecMailError> {
    orden_secmail(&["conectar", proveedor])
}

/// Revoca el acceso en el proveedor y borra los tokens de ~/.misyks/config.
pub fn desconectar(proveedor: &str) -> Result<String, SecMailError> {
    orden_secmail(&["desconectar", proveedor])
}

/// Estado de cada proveedor: `sin_conectar`, `conectado` o `revocado`.
///
/// Una linea por proveedor, tal como la imprime `python -m sec.mail estado`.
/// `revocado` es un estado que hay que enseñar: el token caducado se renueva
/// solo, pero un consentimiento retirado (contrasena cambiada, administrador
/// que bloquea la app, o los 7 dias que dura un refresh token mientras la app
/// de Google siga en estado *Testing*) exige volver a conectar a mano.
pub fn estado_oauth() -> Result<Vec<(String, String, String)>, SecMailError> {
    let salida = orden_secmail(&["estado"])?;
    Ok(salida
        .lines()
        .filter_map(|linea| {
            let mut campos = linea.split_whitespace();
            let proveedor = campos.next()?.to_string();
            let estado = campos.next()?.to_string();
            let detalle = campos.collect::<Vec<_>>().join(" ");
            Some((proveedor, estado, detalle))
        })
        .collect())
}

/// Ejecuta `python -m sec.mail ...` en la carpeta del Backend y devuelve su
/// salida. Los errores de Python llegan por stderr con su mensaje ya
/// redactado para una persona; se propagan tal cual en vez de reescribirlos.
fn orden_secmail(args: &[&str]) -> Result<String, SecMailError> {
    // Localizar el Backend y elegir interprete es comun a todos los modulos y
    // vive en `backend.rs`; lo propio de aqui es traducir el fallo al
    // vocabulario de esta pantalla.
    backend::ejecutar("sec.mail", args).map_err(|e| {
        if e.starts_with("No se encontro la carpeta Backend/") {
            SecMailError::BackendNoEncontrado(e)
        } else {
            SecMailError::Sincronizacion(e)
        }
    })
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
