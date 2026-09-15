use iced::widget::{button, column, row};
use iced::Element;

use crate::screens::settings::{EstadoGuardado, SettingsState};
use crate::screens::{self, Screen};
use crate::secretario::{self, EmailSummary, SecMailError};

// Cuantos correos NUEVOS se piden a Gmail por cada pulsacion de Refrescar.
const TANDA_SINCRONIZACION: i64 = 5;
// Cuantos correos se muestran en la lista: -1 en SQLite es "sin limite" (ver
// secretario::list_emails) -- se quiere ver todo lo ya guardado, no solo la
// ultima tanda descargada.
const LIMITE_LISTA: i64 = -1;

pub struct State {
    current_screen: Screen,
    secretario_emails: Result<Vec<EmailSummary>, SecMailError>,
    secretario_sync: Option<Result<String, SecMailError>>,
    settings: SettingsState,
}

impl Default for State {
    fn default() -> Self {
        Self {
            current_screen: Screen::default(),
            // Lectura sincrona: es un fichero SQLite local, no una llamada de
            // red, asi que se resuelve en el arranque sin necesitar un Task
            // async todavia.
            secretario_emails: secretario::list_emails(LIMITE_LISTA),
            secretario_sync: None,
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
    RefrescarSecretario,
}

pub fn update(state: &mut State, message: Message) {
    match message {
        Message::NavigateTo(screen) => state.current_screen = screen,
        Message::GmailUsuarioChanged(valor) => state.settings.usuario = valor,
        Message::GmailPasswordChanged(valor) => state.settings.password = valor,
        Message::GuardarCredenciales => {
            state.settings.guardar();
            // Bloqueante (llama a IMAP por red): aceptable ahora mismo por
            // simplicidad, pero un candidato claro a Task async si la espera
            // se nota en la UI.
            if matches!(state.settings.estado, EstadoGuardado::Guardado) {
                sincronizar_y_recargar(state);
            }
        }
        Message::RefrescarSecretario => sincronizar_y_recargar(state),
    }
}

fn sincronizar_y_recargar(state: &mut State) {
    state.secretario_sync = Some(secretario::sincronizar(TANDA_SINCRONIZACION));
    state.secretario_emails = secretario::list_emails(LIMITE_LISTA);
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
        Screen::Secretario => {
            screens::secretario::view(&state.secretario_emails, &state.secretario_sync)
        }
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
