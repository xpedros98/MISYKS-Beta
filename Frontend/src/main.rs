// Sin esto Windows trata el binario como programa de consola y abre una ventana
// negra al lado de la aplicacion: se ve al arrancarla con doble clic, no con
// `cargo run`, porque entonces la consola es la del terminal.
//
// Solo en las compilaciones de entrega: en depuracion la consola se conserva a
// proposito, porque es donde sale un panico. Una app de ventana que se cierra
// sin decir nada es mucho peor de diagnosticar que una con una consola fea.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// MISYKS: la aplicacion del abogado.
//
// El trabajo del dia -- expedientes, correo, la cuenta -- y nada mas. Lo de
// mantenimiento vive en `Frontend_Admin`, que se compila aparte: el binario que
// recibe un despacho no lleva dentro las pantallas de diagnostico.
//
// Lo comun con esa otra aplicacion esta en el crate `nucleo`.
mod app;
mod screens;

fn main() -> iced::Result {
    iced::application(app::State::default, app::update, app::view)
        // El titulo dice de quien es la ventana, no solo como se llama el
        // programa: las dos aplicaciones se parecen y van a estar abiertas a la
        // vez en la misma pantalla.
        .title("MISYKS \u{2014} Usuario")
        .theme(|_: &app::State| nucleo::estilo::tema_usuario())
        .run()
}
