// Estado y navegacion de la aplicacion de control.
//
// Una sola pantalla por ahora -- la cobertura del calendario de festivos --,
// pero la barra ya esta puesta: lo que falta por traer aqui esta escrito en
// ARQUITECTURA.md 8.5 (hitos sin revisar, registro de acciones, diagnostico de
// fuentes), y todo eso son secciones, no ventanas sueltas.
use iced::widget::{button, column, row};
use iced::{Element, Length, Task};

use nucleo::estilo;

use crate::screens::calendario::CalendarioState;
use crate::screens::{self, Screen};

pub struct State {
    current_screen: Screen,
    calendario: CalendarioState,
}

impl Default for State {
    fn default() -> Self {
        Self {
            current_screen: Screen::default(),
            // Lectura sincrona: es un fichero SQLite local, no una llamada de
            // red, asi que se resuelve en el arranque.
            calendario: CalendarioState::cargar(),
        }
    }
}

#[derive(Debug, Clone)]
pub enum Message {
    NavigateTo(Screen),
    CalendarioAmbito(String),
    CalendarioComputo(usize),
}

pub fn update(state: &mut State, message: Message) -> Task<Message> {
    match message {
        Message::NavigateTo(screen) => state.current_screen = screen,
        Message::CalendarioAmbito(ambito) => state.calendario.seleccionar(ambito),
        Message::CalendarioComputo(computo) => state.calendario.cambiar_computo(computo),
    }
    Task::none()
}

pub fn view(state: &State) -> Element<'_, Message> {
    let mut secciones = row![].spacing(4);
    for pantalla in Screen::TODAS {
        secciones = secciones.push(nav_button(*pantalla, state.current_screen));
    }
    let nav = estilo::barra(secciones).width(Length::Fill);

    let content = match state.current_screen {
        Screen::Calendario => screens::calendario::view(&state.calendario),
    };

    column![nav, content]
        .spacing(16)
        .padding(16)
        .height(Length::Fill)
        .into()
}

fn nav_button(target: Screen, current: Screen) -> Element<'static, Message> {
    let activa = target == current;
    let boton = button(target.label())
        .padding([6, 14])
        .style(estilo::pestana(target.color(), activa));
    if activa {
        boton.into()
    } else {
        boton.on_press(Message::NavigateTo(target)).into()
    }
}
