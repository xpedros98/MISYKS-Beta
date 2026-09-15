use iced::widget::text;
use iced::Element;

use crate::app::Message;

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum Screen {
    #[default]
    Home,
    Secretario,
}

impl Screen {
    pub fn label(&self) -> &'static str {
        match self {
            Screen::Home => "Inicio",
            Screen::Secretario => "Secretario",
        }
    }
}

pub fn view(screen: Screen) -> Element<'static, Message> {
    match screen {
        Screen::Home => text("MISYKS Beta — scaffold inicial").size(24).into(),
        // Pantalla vacia a proposito: se conecta a GET /api/v1/secretario?action=emails
        // en cuanto el backend (agents-api) reciba el push pendiente del otro ordenador.
        Screen::Secretario => text("Secretario (emails) — pendiente de conectar al backend")
            .size(24)
            .into(),
    }
}
