// Detalles de lanzar subprocesos que difieren por plataforma.
//
// MISYKS-Beta es una app de ventana, no de terminal, y lanza dos subprocesos:
// `python -m sec.mail` (sincronizar) e `icacls` (permisos del archivo de
// secretos). En Windows, un proceso GUI que arranca un ejecutable de consola
// hace parpadear una ventana negra en pantalla; en macOS y Linux no pasa nada
// parecido, asi que esto no tiene equivalente ahi.
use std::process::Command;

/// Evita que el subproceso abra una ventana de consola. No hace nada fuera de
/// Windows.
pub fn sin_consola(orden: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW, de la API de creacion de procesos de Win32.
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        orden.creation_flags(CREATE_NO_WINDOW);
    }
    // Fuera de Windows el parametro no se usa; nombrarlo evita el aviso.
    let _ = orden;
}
