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
    /// Color con el que se identifica la seccion en la barra de navegacion.
    /// Vive aqui, junto a la etiqueta, porque es propiedad de la seccion.
    pub fn color(&self) -> iced::Color {
        match self {
            Screen::Home => crate::estilo::SECCION_INICIO,
            Screen::Secretario => crate::estilo::SECCION_SECRETARIO,
            Screen::Calendario => crate::estilo::SECCION_CALENDARIO,
            Screen::Ajustes => crate::estilo::SECCION_AJUSTES,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Screen::Home => "Inicio",
            Screen::Secretario => "Secretario",
            Screen::Calendario => "Calendario",
            Screen::Ajustes => "Ajustes",
        }
    }
}
