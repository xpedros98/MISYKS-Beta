use iced::widget::{button, column, row};
use iced::Element;

use crate::screens::{self, Screen};

#[derive(Debug, Default)]
pub struct State {
    current_screen: Screen,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Message {
    NavigateTo(Screen),
}

pub fn update(state: &mut State, message: Message) {
    match message {
        Message::NavigateTo(screen) => state.current_screen = screen,
    }
}

pub fn view(state: &State) -> Element<'_, Message> {
    let nav = row![
        nav_button(Screen::Home, state.current_screen),
        nav_button(Screen::Secretario, state.current_screen),
    ]
    .spacing(10);

    column![nav, screens::view(state.current_screen)]
        .spacing(20)
        .padding(20)
        .into()
}

fn nav_button(target: Screen, current: Screen) -> Element<'static, Message> {
    let label = target.label();
    if target == current {
        button(label).into()
    } else {
        button(label).on_press(Message::NavigateTo(target)).into()
    }
}
