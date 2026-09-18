pub mod calendario;
pub mod detalle;
pub mod expedientes;
pub mod home;
pub mod secretario;
pub mod settings;

/// Las dos caras de la aplicacion.
///
/// **Despacho** es el trabajo del dia: expedientes, correo, lo que el abogado
/// abre cada manana. **Control** es mirar como esta el sistema: que sabe el
/// calendario y que le falta, que cuentas siguen conectadas, que se ha hecho.
///
/// Separarlas no es seguridad -- la base y la configuracion estan en la misma
/// maquina y quien edite un fichero de texto ve lo que quiera -- sino
/// atencion: una pantalla de mantenimiento en medio del trabajo es ruido, y
/// una pantalla de trabajo en medio del mantenimiento esconde lo que se ha
/// roto.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum Modo {
    #[default]
    Despacho,
    Control,
}

impl Modo {
    pub fn label(&self) -> &'static str {
        match self {
            Modo::Despacho => "Despacho",
            Modo::Control => "Control",
        }
    }

    /// Que hace cada una, en una linea. Se ensena junto a la pestana: sin esto
    /// hay que entrar para saber que hay dentro.
    pub fn descripcion(&self) -> &'static str {
        match self {
            Modo::Despacho => "el trabajo del dia",
            Modo::Control => "que sabe el sistema y que le falta",
        }
    }

    pub fn color(&self) -> iced::Color {
        match self {
            Modo::Despacho => crate::estilo::SECCION_SECRETARIO,
            Modo::Control => crate::estilo::SECCION_AJUSTES,
        }
    }

    /// Las secciones de cada cara, en el orden en que se ensenan.
    pub fn pantallas(&self) -> &'static [Screen] {
        match self {
            Modo::Despacho => &[Screen::Home, Screen::Expedientes, Screen::Secretario],
            Modo::Control => &[Screen::Calendario, Screen::Ajustes],
        }
    }

    /// Por donde se entra al cambiar de cara.
    pub fn inicio(&self) -> Screen {
        self.pantallas()[0]
    }
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum Screen {
    #[default]
    Home,
    Secretario,
    Expedientes,
    Calendario,
    Ajustes,
}

impl Screen {
    /// A que cara pertenece cada seccion.
    ///
    /// `Calendario` es de Control y no del Despacho aunque hable de fechas:
    /// ensena la **cobertura** del calendario de festivos y sus averias, no los
    /// plazos del abogado. Esa confusion estaba escrita en su propia cabecera
    /// desde el principio: «el abogado no va a abrir esto».
    ///
    /// `Ajustes` tambien: conectar una cuenta se hace una vez y es puesta a
    /// punto, no trabajo.
    pub fn modo(&self) -> Modo {
        match self {
            Screen::Home | Screen::Secretario | Screen::Expedientes => Modo::Despacho,
            Screen::Calendario | Screen::Ajustes => Modo::Control,
        }
    }

    /// Color con el que se identifica la seccion en la barra de navegacion.
    /// Vive aqui, junto a la etiqueta, porque es propiedad de la seccion.
    pub fn color(&self) -> iced::Color {
        match self {
            Screen::Home => crate::estilo::SECCION_INICIO,
            Screen::Secretario => crate::estilo::SECCION_SECRETARIO,
            Screen::Expedientes => crate::estilo::SECCION_EXPEDIENTES,
            Screen::Calendario => crate::estilo::SECCION_CALENDARIO,
            Screen::Ajustes => crate::estilo::SECCION_AJUSTES,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Screen::Home => "Inicio",
            Screen::Secretario => "Secretario",
            Screen::Expedientes => "Expedientes",
            Screen::Calendario => "Calendario",
            Screen::Ajustes => "Ajustes",
        }
    }
}
