// Pantalla de Ajustes: el usuario escribe aqui sus credenciales de Gmail
// para sec.mail. Se guardan en ~/.misyks/config, en este mismo ordenador —
// nunca se envian a maat ni a ningun otro sitio (ver src/local_config.rs).
use iced::widget::{button, column, text, text_input};
use iced::Element;

use crate::app::Message;
use crate::local_config::LocalConfig;

#[derive(Debug, Default)]
pub struct SettingsState {
    pub usuario: String,
    pub password: String,
    pub estado: EstadoGuardado,
}

#[derive(Debug, Default, Clone)]
pub enum EstadoGuardado {
    #[default]
    Ninguno,
    Guardado,
    Error(String),
}

impl SettingsState {
    pub fn cargar() -> Self {
        let config = LocalConfig::load();
        Self {
            usuario: config.get("gmail", "usuario").unwrap_or("").to_string(),
            // La contrasena no se recarga en la UI aunque ya este guardada:
            // un campo enmascarado que reaparece relleno es mala practica de
            // seguridad para poco beneficio (solo hace falta volver a
            // escribirla si se quiere cambiar).
            password: String::new(),
            estado: EstadoGuardado::default(),
        }
    }

    pub fn guardar(&mut self) {
        let mut config = LocalConfig::load();
        config.set("gmail", "usuario", self.usuario.trim());
        if !self.password.is_empty() {
            config.set("gmail", "password", self.password.trim());
        }
        self.estado = match config.save() {
            Ok(()) => EstadoGuardado::Guardado,
            Err(e) => EstadoGuardado::Error(format!("No se pudo guardar: {e}")),
        };
    }
}

pub fn view(state: &SettingsState) -> Element<'_, Message> {
    let mensaje: Element<'_, Message> = match &state.estado {
        EstadoGuardado::Ninguno => text("").into(),
        EstadoGuardado::Guardado => text("Guardado en ~/.misyks/config.").into(),
        EstadoGuardado::Error(e) => text(e).into(),
    };

    column![
        text("Credenciales de Gmail (sec.mail)").size(20),
        text("Se guardan solo en este ordenador. Usa una contrasena de aplicacion, no la de tu cuenta."),
        text_input("usuario@gmail.com", &state.usuario).on_input(Message::GmailUsuarioChanged),
        text_input("contrasena de aplicacion", &state.password)
            .secure(true)
            .on_input(Message::GmailPasswordChanged),
        button("Guardar").on_press(Message::GuardarCredenciales),
        mensaje,
    ]
    .spacing(12)
    .padding(10)
    .into()
}
