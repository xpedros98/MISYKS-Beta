use iced::widget::{button, column, row};
use iced::Element;

use crate::screens::settings::SettingsState;
use crate::screens::{self, Screen};
use crate::secretario::{self, EmailSummary, SecMailError};

pub struct State {
    current_screen: Screen,
    secretario_emails: Result<Vec<EmailSummary>, SecMailError>,
    settings: SettingsState,
}

impl Default for State {
    fn default() -> Self {
        Self {
            current_screen: Screen::default(),
            // Lectura sincrona: es un fichero SQLite local, no una llamada de
            // red, asi que se resuelve en el arranque sin necesitar un Task
            // async todavia.
            secretario_emails: secretario::list_emails(50),
            settings: SettingsState::cargar(),
        }
    }
}

#[derive(Debug, Clone)]
pub enum Message {
    NavigateTo(Screen),
    GmailUsuarioChanged(String),
    GmailPasswordChanged(String),
    GuardarCredenciales,
}

pub fn update(state: &mut State, message: Message) {
    match message {
        Message::NavigateTo(screen) => {
            state.current_screen = screen;
            if screen == Screen::Secretario {
                // Recarga por si se acaba de sincronizar desde el CLI de
                // Python o de guardar credenciales nuevas en Ajustes.
                state.secretario_emails = secretario::list_emails(50);
            }
        }
        Message::GmailUsuarioChanged(valor) => state.settings.usuario = valor,
        Message::GmailPasswordChanged(valor) => state.settings.password = valor,
        Message::GuardarCredenciales => state.settings.guardar(),
    }
}

pub fn view(state: &State) -> Element<'_, Message> {
    let nav = row![
        nav_button(Screen::Home, state.current_screen),
        nav_button(Screen::Secretario, state.current_screen),
        nav_button(Screen::Ajustes, state.current_screen),
    ]
    .spacing(10);

    let content = match state.current_screen {
        Screen::Home => screens::home::view(),
        Screen::Secretario => screens::secretario::view(&state.secretario_emails),
        Screen::Ajustes => screens::settings::view(&state.settings),
    };

    column![nav, content].spacing(20).padding(20).into()
}

fn nav_button(target: Screen, current: Screen) -> Element<'static, Message> {
    let label = target.label();
    if target == current {
        button(label).into()
    } else {
        button(label).on_press(Message::NavigateTo(target)).into()
    }
}
