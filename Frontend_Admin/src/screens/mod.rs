pub mod calendario;

/// Las secciones de la aplicacion de control.
///
/// Hoy solo una. Se deja el enum y la barra montados porque lo que viene ya
/// esta escrito en ARQUITECTURA.md 8.5 -- hitos sin revisar, registro de
/// acciones, diagnostico de fuentes -- y son secciones de esta misma
/// aplicacion, no ventanas aparte.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum Screen {
    #[default]
    Calendario,
}

impl Screen {
    pub const TODAS: &'static [Screen] = &[Screen::Calendario];

    pub fn color(&self) -> iced::Color {
        match self {
            Screen::Calendario => nucleo::estilo::SECCION_CALENDARIO,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Screen::Calendario => "Calendario",
        }
    }
}
