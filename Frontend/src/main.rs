mod app;
mod screens;

fn main() -> iced::Result {
    iced::application(app::State::default, app::update, app::view)
        .title("MISYKS Beta")
        .run()
}
