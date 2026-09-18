// Paleta y piezas visuales compartidas.
//
// Dos reglas:
//
// **El texto no lleva color fijo.** Sale del tema (`palette.text`), y lo que se
// quiere atenuar baja la opacidad en vez de cambiar a otro gris. Un gris fijo
// deja de funcionar en cuanto cambia el fondo: deslavado sobre claro,
// invisible sobre oscuro.
//
// **El color se reserva.** Si todo tiene color, nada destaca. Solo identifica
// en la barra de navegacion, donde cada seccion tiene el suyo; dentro de una
// pantalla, el unico acento es lo que pide accion.
use iced::widget::{button, container, text, Container, Text};
use iced::theme::Palette;
use iced::{Background, Border, Color, Font, Theme};

const fn rgb(r: u8, g: u8, b: u8) -> Color {
    Color::from_rgb(r as f32 / 255.0, g as f32 / 255.0, b as f32 / 255.0)
}

/// El tema de cada aplicacion: **fondo claro la del abogado, negro la de
/// administrador**.
///
/// Es la senal mas barata y mas dificil de ignorar de en cual estas. Las dos se
/// parecen -- misma barra, mismas tarjetas, misma tipografia -- y van a estar
/// abiertas a la vez en la misma pantalla; confundirlas es tocar el
/// mantenimiento creyendo que trabajas, o al reves.
///
/// Funciona porque en este proyecto **el texto no lleva color fijo**: sale del
/// tema, y lo atenuado baja la opacidad en vez de elegir un gris. Un gris fijo
/// habria quedado invisible sobre negro, que es justo el motivo por el que esa
/// regla esta escrita arriba.
pub fn tema_usuario() -> Theme {
    Theme::Light
}

pub fn tema_administrador() -> Theme {
    // Negro de verdad, no un gris oscuro: tiene que distinguirse de un tema
    // oscuro cualquiera del sistema. El acento es el de Ajustes, que es la
    // seccion de la que nacio esta aplicacion.
    Theme::custom(
        "Administrador".to_string(),
        Palette {
            background: rgb(12, 12, 14),
            text: rgb(228, 228, 232),
            primary: SECCION_CALENDARIO,
            success: rgb(60, 150, 90),
            warning: rgb(200, 150, 40),
            danger: ALERTA,
        },
    )
}

/// Color de cada seccion. Es lo unico que identifica por color en toda la app.
pub const SECCION_INICIO: Color = rgb(58, 110, 165);
pub const SECCION_SECRETARIO: Color = rgb(20, 130, 130);
pub const SECCION_CALENDARIO: Color = rgb(126, 74, 160);
pub const SECCION_EXPEDIENTES: Color = rgb(176, 108, 44);
pub const SECCION_AJUSTES: Color = rgb(120, 120, 130);

/// Lo unico que pide accion dentro de una pantalla.
pub const ALERTA: Color = rgb(198, 40, 40);

/// Texto del tema, atenuado. Se apaga bajando la opacidad en vez de elegir un
/// gris: un gris fijo deja de funcionar en cuanto cambia el fondo.
pub fn tenue_color(theme: &Theme) -> Color {
    let mut c = theme.palette().text;
    c.a = 0.55;
    c
}

/// Letra que marca el nivel de un dia en una lista: N, A, I o L.
///
/// En letra y no en color a proposito: una lista corta con cuatro colores se
/// lee peor que con cuatro iniciales.
pub fn marca_nivel(nivel: &str) -> &'static str {
    match nivel {
        "nacional" => "N",
        "autonomico" => "A",
        "insular" => "I",
        _ => "L",
    }
}

/// Texto de anchura fija. Las cifras de una tabla solo se leen en columna si
/// todas ocupan lo mismo, y con fuente proporcional no lo hacen.
pub fn mono<'a>(contenido: String) -> Text<'a> {
    text(contenido).font(Font::MONOSPACE).size(13)
}

pub fn titulo<'a>(contenido: impl Into<String>) -> Text<'a> {
    text(contenido.into()).size(16)
}

pub fn tenue<'a>(contenido: impl Into<String>) -> Text<'a> {
    text(contenido.into()).size(11).style(|theme: &Theme| text::Style {
        color: Some(tenue_color(theme)),
    })
}

/// Boton que no parece un boton: una fila de lista que se puede pulsar.
///
/// Sin fondo ni borde en reposo, con un realce apenas perceptible al pasar por
/// encima. Un boton con relieve por cada fila convertiria la lista en una
/// botonera y el ojo no sabria donde mirar.
pub fn fila_clicable() -> impl Fn(&Theme, button::Status) -> button::Style {
    move |theme: &Theme, status: button::Status| {
        let resaltada = matches!(
            status,
            button::Status::Hovered | button::Status::Pressed
        );
        let mut fondo = theme.palette().text;
        fondo.a = if resaltada { 0.06 } else { 0.0 };
        button::Style {
            background: Some(Background::Color(fondo)),
            text_color: theme.palette().text,
            border: Border::default().rounded(4),
            ..button::Style::default()
        }
    }
}

/// Caja con un borde discreto, para separar bloques sin dibujar lineas.
/// El fondo sale del tema; un gris fijo seria una mancha sobre tema oscuro.
pub fn tarjeta<'a, M: 'a>(contenido: impl Into<iced::Element<'a, M>>) -> Container<'a, M> {
    container(contenido).padding(12).style(|theme: &Theme| {
        let paleta = theme.extended_palette();
        container::Style {
            background: Some(Background::Color(paleta.background.weak.color)),
            border: Border {
                color: paleta.background.strong.color,
                width: 1.0,
                radius: 6.0.into(),
            },
            ..container::Style::default()
        }
    })
}

/// La barra que aloja las pestanas.
pub fn barra<'a, M: 'a>(contenido: impl Into<iced::Element<'a, M>>) -> Container<'a, M> {
    container(contenido).padding([6, 8]).style(|theme: &Theme| {
        let paleta = theme.extended_palette();
        container::Style {
            background: Some(Background::Color(paleta.background.weak.color)),
            border: Border {
                color: paleta.background.strong.color,
                width: 1.0,
                radius: 8.0.into(),
            },
            ..container::Style::default()
        }
    })
}

/// Estilo de una pestana de la barra de navegacion.
///
/// Activa: rellena con el color de su seccion. Inactiva: transparente, con el
/// texto del tema, y al pasar el raton se insinua con el mismo color a baja
/// opacidad -- para que se vea que es pulsable antes de pulsarla.
pub fn pestana(color: Color, activa: bool) -> impl Fn(&Theme, button::Status) -> button::Style {
    move |theme: &Theme, status: button::Status| {
        let texto = theme.palette().text;
        if activa {
            return button::Style {
                background: Some(Background::Color(color)),
                text_color: Color::WHITE,
                border: Border { radius: 6.0.into(), ..Border::default() },
                ..button::Style::default()
            };
        }
        let fondo = match status {
            button::Status::Hovered | button::Status::Pressed => {
                Some(Background::Color(Color { a: 0.15, ..color }))
            }
            _ => None,
        };
        button::Style {
            background: fondo,
            text_color: texto,
            border: Border { radius: 6.0.into(), ..Border::default() },
            ..button::Style::default()
        }
    }
}
