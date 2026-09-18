// Como se llama al Backend de Python desde la app.
//
// Estaba dentro de `secretario.rs` porque `sec.mail` era lo unico que se
// invocaba. Con `expedientes` ya son dos, y localizar la carpeta del Backend y
// elegir interprete no es asunto de ninguno de los dos en particular: es como
// esta app habla con Python. Mismo movimiento que `sec/cuentas` en el Backend.
//
// Lo que NO vive aqui: los errores. Cada modulo tiene los suyos, con el
// vocabulario de su pantalla; esto devuelve `String` y quien llama lo envuelve.
use std::path::{Path, PathBuf};

use crate::proceso::sin_consola;

/// Localiza la carpeta `Backend/` en tiempo de ejecucion.
///
/// Antes se resolvia con `env!("CARGO_MANIFEST_DIR")`, una ruta de *tiempo de
/// compilacion*: funciona con `cargo run` desde el checkout y deja de existir
/// en la maquina de cualquier otro en cuanto la app se distribuya como
/// binario. Orden de busqueda:
///
/// 1. `MISYKS_BACKEND`, para apuntar a mano (pruebas, instalaciones raras).
/// 2. `Backend/` junto al ejecutable: la app empaquetada.
/// 3. La carpeta hermana de `Frontend/` en el checkout: desarrollo.
///
/// Cada candidata se valida comprobando que contiene de verdad el Backend, no
/// solo que exista un directorio con ese nombre.
pub fn dir() -> Result<PathBuf, String> {
    let mut probadas = Vec::new();

    if let Some(ruta) = std::env::var_os("MISYKS_BACKEND") {
        let candidata = PathBuf::from(ruta);
        if es_backend(&candidata) {
            return Ok(candidata);
        }
        probadas.push(candidata);
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let candidata = dir.join("Backend");
            if es_backend(&candidata) {
                return Ok(candidata);
            }
            probadas.push(candidata);
        }
    }

    if let Some(padre) = Path::new(env!("CARGO_MANIFEST_DIR")).parent() {
        let candidata = padre.join("Backend");
        if es_backend(&candidata) {
            return Ok(candidata);
        }
        probadas.push(candidata);
    }

    Err(probadas
        .iter()
        .map(|p| p.display().to_string())
        .collect::<Vec<_>>()
        .join(", "))
}

/// `sec/mail/__main__.py` como senal de que esto es el Backend. Vale cualquier
/// fichero que solo exista ahi; se usa el del primer modulo que hubo.
fn es_backend(dir: &Path) -> bool {
    dir.join("sec").join("mail").join("__main__.py").is_file()
}

/// Interprete de Python con el que lanzar los modulos.
///
/// Prefiere el venv del propio Backend -- `Scripts\python.exe` en Windows,
/// `bin/python3` en el resto; con la ruta POSIX fija, el boton Refrescar no
/// arrancaba nada en Windows. Si no hay venv (app empaquetada, o alguien que
/// instalo las dependencias en el Python del sistema) cae al del PATH en vez
/// de fallar: el modulo avisara por su cuenta si le falta `sqlcipher3`.
pub fn interprete(backend: &Path) -> PathBuf {
    let venv = if cfg!(windows) {
        backend.join(".venv").join("Scripts").join("python.exe")
    } else {
        backend.join(".venv").join("bin").join("python3")
    };
    if venv.is_file() {
        return venv;
    }
    PathBuf::from(if cfg!(windows) { "python" } else { "python3" })
}

/// Ejecuta `python -m <modulo> <args...>` en la carpeta del Backend y devuelve
/// su salida.
///
/// Los errores de Python llegan por stderr con su mensaje ya redactado para una
/// persona -- «No hay ninguna cuenta conectada. Conectala desde Ajustes...» --,
/// asi que se propagan tal cual en vez de reescribirlos aqui, donde se sabe
/// menos de lo que ha pasado.
pub fn ejecutar(modulo: &str, args: &[&str]) -> Result<String, String> {
    let backend = dir().map_err(|probadas| {
        format!("No se encontro la carpeta Backend/. Buscada en: {probadas}. \
                 Define MISYKS_BACKEND si esta en otro sitio.")
    })?;
    let python = interprete(&backend);
    let mut orden = std::process::Command::new(&python);
    orden.arg("-m").arg(modulo).args(args).current_dir(&backend);
    sin_consola(&mut orden);
    let salida = orden
        .output()
        .map_err(|e| format!("no se pudo lanzar {}: {e}", python.display()))?;

    if !salida.status.success() {
        return Err(String::from_utf8_lossy(&salida.stderr).trim().to_string());
    }
    Ok(String::from_utf8_lossy(&salida.stdout).trim().to_string())
}
