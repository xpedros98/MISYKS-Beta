mod app;
mod backend;
mod calendario;
mod estilo;
mod expedientes;
mod local_config;
mod proceso;
mod screens;
mod secretario;

fn main() -> iced::Result {
    iced::application(app::State::default, app::update, app::view)
        .title("MISYKS Beta")
        .run()
}
