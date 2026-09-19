// Sin esto Windows trata el binario como programa de consola y abre una ventana
// negra al lado de la aplicacion: se ve al arrancarla con doble clic, no con
// `cargo run`, porque entonces la consola es la del terminal.
//
// Solo en las compilaciones de entrega: en depuracion la consola se conserva a
// proposito, porque es donde sale un panico. Una app de ventana que se cierra
// sin decir nada es mucho peor de diagnosticar que una con una consola fea.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// MISYKS Control: la aplicacion del equipo, no la del abogado.
//
// Existe porque el binario que se le entrega a un despacho **no debe llevar
// dentro** las pantallas de mantenimiento. No es una cuestion de permisos
// -- las bases y la configuracion estan en la misma maquina, y quien edite un
// fichero de texto ve lo que quiera --, sino de que se distribuyen cosas
// distintas a gente distinta: el abogado recibe una herramienta de trabajo y el
// equipo una de diagnostico.
//
// Lo comun con la aplicacion del abogado vive en el crate `nucleo`, que se
// comparte en vez de copiarse: dos copias de `local_config.rs` acabarian
// escribiendo con reglas distintas el archivo que guarda el refresh token del
// correo y la clave de las bases.
mod app;
mod screens;

fn main() -> iced::Result {
    iced::application(app::State::default, app::update, app::view)
        .title("MISYKS \u{2014} Administrador")
        // Fondo negro. Es la senal mas dificil de ignorar de que esto no es la
        // aplicacion del abogado: se ve antes de leer el titulo.
        .theme(|_: &app::State| nucleo::estilo::tema_administrador())
        .run()
}
