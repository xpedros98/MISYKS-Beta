// Paleta y piezas visuales compartidas.
//
// Dos reglas, aprendidas a base de hacerlo mal:
//
// **El texto no lleva color fijo.** La primera version clavaba un gris oscuro
// para los titulos, que sobre el fondo claro quedaba deslavado y sobre uno
// oscuro seria invisible. Los textos toman el color del tema (`palette.text`) y
// solo se apagan por *opacidad*, no cambiando de gris: asi siguen legibles
// aunque el tema cambie.
//
// **El color se reserva.** Si todo tiene color, nada destaca. El unico sitio
// donde el color identifica algo es la barra de navegacion --cada seccion tiene
// el suyo, para saber donde estas de un vistazo-- y el unico acento dentro de
// una pantalla es lo que pide accion. Las tablas van en un solo color.
use iced::widget::{button, container, text, Container, Text};
use iced::{Background, Border, Color, Font, Theme};

const fn rgb(r: u8, g: u8, b: u8) -> Color {
    Color::from_rgb(r as f32 / 255.0, g as f32 / 255.0, b as f32 / 255.0)
}

/// Color de cada seccion. Es lo unico que identifica por color en toda la app.
pub const SECCION_INICIO: Color = rgb(58, 110, 165);
pub const SECCION_SECRETARIO: Color = rgb(20, 130, 130);
pub const SECCION_CALENDARIO: Color = rgb(126, 74, 160);
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

/// Caja con un borde discreto, para separar bloques sin dibujar lineas.
///
/// El fondo sale del tema, no de un gris fijo: sobre tema oscuro, un `#f6f6f8`
/// clavado a mano seria una mancha blanca.
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
