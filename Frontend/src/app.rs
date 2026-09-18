use iced::widget::{button, column, row};
use iced::Element;
use iced::{Length, Task};

use crate::expedientes::TipoDoc;
use crate::screens::calendario::CalendarioState;
use crate::screens::expedientes::ExpedientesState;
use crate::screens::settings::SettingsState;
use crate::screens::{self, Screen};
use crate::secretario::{self, EmailSummary, SecMailError};

// Cuantos correos NUEVOS se bajan por cada pulsacion de Refrescar.
const TANDA_SINCRONIZACION: i64 = 5;
// Cuantos correos se muestran en la lista: -1 en SQLite es "sin limite" (ver
// secretario::list_emails) -- se quiere ver todo lo ya guardado, no solo la
// ultima tanda descargada.
const LIMITE_LISTA: i64 = -1;

pub struct State {
    current_screen: Screen,
    calendario: CalendarioState,
    expedientes: ExpedientesState,
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
            calendario: CalendarioState::cargar(),
            expedientes: ExpedientesState::cargar(),
            settings: SettingsState::cargar(),
        }
    }
}

#[derive(Debug, Clone)]
pub enum Message {
    NavigateTo(Screen),
    ConectarCuenta(String),
    CuentaConectada(Result<String, SecMailError>),
    DesconectarCuenta(String),
    RefrescarSecretario,
    CalendarioAmbito(String),
    CalendarioComputo(usize),
    ExpedienteTipo(TipoDoc),
    ExpedienteAbrir(i64),
    HitoHecho(i64, i64),
    HitoDeshacer(i64, i64),
    ExpedienteCerrarDetalle,
    ExpedienteCrear,
    ExpedienteEliminar(i64),
    // El borrado masivo va en tres mensajes a proposito: pedir, confirmar,
    // cancelar. Un solo mensaje seria una sola pulsacion, y esto no se deshace.
    ExpedienteVaciarPedir,
    ExpedienteVaciarConfirmar,
    ExpedienteVaciarCancelar,
}

/// `update` devuelve una `Task` porque conectar una cuenta **no puede
/// bloquear**: espera a que una persona acepte en el navegador, y eso tarda lo
/// que tarda. Todo lo demas sigue siendo sincrono y devuelve `Task::none()`.
pub fn update(state: &mut State, message: Message) -> Task<Message> {
    match message {
        Message::NavigateTo(screen) => state.current_screen = screen,
        Message::ConectarCuenta(proveedor) => {
            // Devuelve ya, con la pantalla diciendo que mire el navegador; la
            // respuesta llega luego como `CuentaConectada`.
            return state.settings.conectar(&proveedor);
        }
        Message::CuentaConectada(resultado) => {
            state.settings.conectada(resultado);
            if state.settings.hay_cuenta() {
                sincronizar_y_recargar(state);
            }
        }
        Message::DesconectarCuenta(proveedor) => state.settings.desconectar(&proveedor),
        Message::RefrescarSecretario => sincronizar_y_recargar(state),
        Message::CalendarioAmbito(ambito) => state.calendario.seleccionar(ambito),
        Message::CalendarioComputo(computo) => state.calendario.cambiar_computo(computo),
        Message::ExpedienteTipo(tipo) => state.expedientes.elegir_tipo(tipo),
        Message::ExpedienteAbrir(id) => state.expedientes.abrir_detalle(id),
        Message::HitoHecho(expediente, orden) => state.expedientes.marcar_hito(expediente, orden),
        Message::HitoDeshacer(expediente, orden) => {
            state.expedientes.deshacer_hito(expediente, orden)
        }
        Message::ExpedienteCerrarDetalle => state.expedientes.cerrar_detalle(),
        Message::ExpedienteCrear => state.expedientes.crear(),
        Message::ExpedienteEliminar(id) => state.expedientes.eliminar(id),
        Message::ExpedienteVaciarPedir => state.expedientes.pedir_vaciado(),
        Message::ExpedienteVaciarConfirmar => state.expedientes.vaciar(),
        Message::ExpedienteVaciarCancelar => state.expedientes.cancelar_vaciado(),
    }
    Task::none()
}

fn sincronizar_y_recargar(state: &mut State) {
    state.secretario_sync = Some(secretario::sincronizar(TANDA_SINCRONIZACION));
    state.secretario_emails = secretario::list_emails(LIMITE_LISTA);
}

pub fn view(state: &State) -> Element<'_, Message> {
    let nav = crate::estilo::barra(
        row![
            nav_button(Screen::Home, state.current_screen),
            nav_button(Screen::Secretario, state.current_screen),
            nav_button(Screen::Expedientes, state.current_screen),
            nav_button(Screen::Calendario, state.current_screen),
            nav_button(Screen::Ajustes, state.current_screen),
        ]
        .spacing(4),
    )
    .width(Length::Fill);

    let content = match state.current_screen {
        Screen::Home => screens::home::view(),
        Screen::Secretario => {
            screens::secretario::view(&state.secretario_emails, &state.secretario_sync)
        }
        Screen::Expedientes => screens::expedientes::view(&state.expedientes),
        Screen::Calendario => screens::calendario::view(&state.calendario),
        Screen::Ajustes => screens::settings::view(&state.settings),
    };

    column![nav, content].spacing(16).padding(16).height(Length::Fill).into()
}

fn nav_button(target: Screen, current: Screen) -> Element<'static, Message> {
    let activa = target == current;
    // Cada seccion tiene su color y solo se ve cuando esta activa: sirve para
    // saber donde estas sin leer, y no compite con nada porque las demas
    // pestanas quedan transparentes.
    let boton = button(target.label())
        .padding([6, 14])
        .style(crate::estilo::pestana(target.color(), activa));
    if activa {
        boton.into()
    } else {
        boton.on_press(Message::NavigateTo(target)).into()
    }
}
