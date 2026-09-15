use iced::widget::text;
use iced::Element;

use crate::app::Message;

pub fn view() -> Element<'static, Message> {
    text("MISYKS Beta").size(24).into()
}
