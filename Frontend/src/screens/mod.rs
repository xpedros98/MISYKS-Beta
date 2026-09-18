pub mod detalle;
pub mod expedientes;
pub mod home;
pub mod secretario;
pub mod settings;

/// Las secciones de la aplicacion del abogado.
///
/// **No esta el calendario de festivos**, que se fue a `Frontend_Admin`: ensena
/// la cobertura de las fuentes y sus averias, no los plazos de nadie, y su
/// propia cabecera ya decia que el abogado no iba a abrirlo.
///
/// **Si estan los Ajustes**, aunque sean puesta a punto y no trabajo. El
/// permiso de la cuenta caduca -- cada siete dias mientras la app de Google siga
/// en estado *Testing* -- y quien tiene que volver a darlo es el abogado, en su
/// navegador y con su cuenta. Dejarlo solo en la aplicacion de control lo
/// habria dejado sin forma de reconectar su propio correo.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum Screen {
    #[default]
    Home,
    Expedientes,
    Secretario,
    Ajustes,
}

impl Screen {
    pub const TODAS: &'static [Screen] = &[
        Screen::Home,
        Screen::Expedientes,
        Screen::Secretario,
        Screen::Ajustes,
    ];

    /// Color con el que se identifica la seccion en la barra de navegacion.
    /// Vive aqui, junto a la etiqueta, porque es propiedad de la seccion.
    pub fn color(&self) -> iced::Color {
        match self {
            Screen::Home => nucleo::estilo::SECCION_INICIO,
            Screen::Expedientes => nucleo::estilo::SECCION_EXPEDIENTES,
            Screen::Secretario => nucleo::estilo::SECCION_SECRETARIO,
            Screen::Ajustes => nucleo::estilo::SECCION_AJUSTES,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Screen::Home => "Inicio",
            Screen::Expedientes => "Expedientes",
            Screen::Secretario => "Secretario",
            Screen::Ajustes => "Ajustes",
        }
    }
}
