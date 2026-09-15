use iced::widget::{column, container, scrollable, text};
use iced::{Element, Length};

use crate::app::Message;
use crate::secretario::{EmailSummary, SecMailError};

pub fn view(emails: &Result<Vec<EmailSummary>, SecMailError>) -> Element<'_, Message> {
    match emails {
        Err(err) => container(text(err.to_string()))
            .padding(20)
            .width(Length::Fill)
            .into(),
        Ok(emails) if emails.is_empty() => {
            text("Sin correos guardados todavia. Sincroniza con el agente Python primero.").into()
        }
        Ok(emails) => {
            let rows = emails.iter().map(email_row);
            scrollable(column(rows).spacing(4).width(Length::Fill))
                .height(Length::Fill)
                .into()
        }
    }
}

fn email_row(email: &EmailSummary) -> Element<'_, Message> {
    let estado = if email.leido { "leido" } else { "sin leer" };
    let remitente = email.remitente.as_deref().unwrap_or("(sin remitente)");
    let asunto = email.asunto.as_deref().unwrap_or("(sin asunto)");
    let fecha = email.fecha.as_deref().unwrap_or("");

    text(format!(
        "[{estado:>8}] {fecha:<20} {remitente:<30} {asunto} ({} adj.)",
        email.adjuntos
    ))
    .into()
}
