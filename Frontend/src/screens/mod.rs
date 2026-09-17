pub mod calendario;
pub mod home;
pub mod secretario;
pub mod settings;

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum Screen {
    #[default]
    Home,
    Secretario,
    Calendario,
    Ajustes,
}

impl Screen {
    pub fn label(&self) -> &'static str {
        match self {
            Screen::Home => "Inicio",
            Screen::Secretario => "Secretario",
            Screen::Calendario => "Calendario",
            Screen::Ajustes => "Ajustes",
        }
    }
}
