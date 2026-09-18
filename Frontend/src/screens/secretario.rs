use iced::widget::{button, column, container, row, scrollable, text};
use iced::{Element, Length};

use crate::app::Message;
use nucleo::secretario::{EmailSummary, SecMailError};

pub fn view<'a>(
    emails: &'a Result<Vec<EmailSummary>, SecMailError>,
    sync: &'a Option<Result<String, SecMailError>>,
) -> Element<'a, Message> {
    let barra = row![
        button("Refrescar").on_press(Message::RefrescarSecretario),
        sync_status(sync),
    ]
    .spacing(10);

    let lista: Element<'_, Message> = match emails {
        Err(err) => container(text(err.to_string())).padding(20).into(),
        Ok(emails) if emails.is_empty() => {
            text("Sin correos guardados todavia. Pulsa Refrescar.").into()
        }
        Ok(emails) => {
            let filas = emails.iter().map(email_row);
            scrollable(column(filas).spacing(4).width(Length::Fill))
                .height(Length::Fill)
                .into()
        }
    };

    column![barra, lista].spacing(16).padding(10).into()
}

fn sync_status(sync: &Option<Result<String, SecMailError>>) -> Element<'_, Message> {
    match sync {
        None => text("").into(),
        Some(Ok(salida)) if salida.is_empty() => text("Sincronizado.").into(),
        Some(Ok(salida)) => text(salida.clone()).into(),
        Some(Err(err)) => text(err.to_string()).into(),
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
