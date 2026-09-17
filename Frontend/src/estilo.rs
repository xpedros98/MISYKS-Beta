// Paleta y piezas visuales compartidas.
//
// Vive aparte para que el color signifique siempre lo mismo en toda la app: si
// `pendiente` es gris en una pantalla y ambar en otra, el color deja de
// informar y pasa a decorar. Aqui solo hay constantes y envoltorios pequenos;
// ninguna pantalla define su propio color.
//
// El criterio de la paleta no es estetico sino de urgencia: lo que va bien se
// apaga, lo que pide accion resalta. Por eso `confirmado` es verde sobrio y
// `fallido` es rojo, mientras que `pendiente` --que es trabajo previsto, no una
// averia-- se queda en gris y no compite por la atencion.
use iced::widget::{container, text, Container, Text};
use iced::{Color, Font};

const fn rgb(r: u8, g: u8, b: u8) -> Color {
    Color::from_rgb(r as f32 / 255.0, g as f32 / 255.0, b as f32 / 255.0)
}

// --- estados de cobertura ---
pub const CONFIRMADO: Color = rgb(56, 142, 60);
pub const PENDIENTE: Color = rgb(130, 130, 130);
pub const SIN_PUBLICAR: Color = rgb(25, 118, 210);
pub const FALLIDO: Color = rgb(198, 40, 40);

// --- niveles de ambito ---
// Distintos entre si y distintos de los de estado: un nivel no es un estado, y
// compartir color haria pensar que si.
pub const NACIONAL: Color = rgb(120, 60, 160);
pub const AUTONOMICO: Color = rgb(0, 131, 143);
pub const INSULAR: Color = rgb(191, 120, 0);
pub const LOCAL: Color = rgb(194, 60, 120);

// --- texto ---
pub const TENUE: Color = rgb(120, 120, 120);
pub const TITULO: Color = rgb(40, 40, 40);

pub fn color_estado(estado: &str) -> Color {
    match estado {
        "confirmado" => CONFIRMADO,
        "sin_publicar" => SIN_PUBLICAR,
        "fallido" => FALLIDO,
        _ => PENDIENTE,
    }
}

pub fn color_nivel(nivel: &str) -> Color {
    match nivel {
        "nacional" => NACIONAL,
        "autonomico" => AUTONOMICO,
        "insular" => INSULAR,
        _ => LOCAL,
    }
}

/// Letra que marca el nivel en una lista de dias: N, A, I o L.
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
    text(contenido.into()).size(16).color(TITULO)
}

pub fn tenue<'a>(contenido: impl Into<String>) -> Text<'a> {
    text(contenido.into()).size(11).color(TENUE)
}

/// Caja con fondo tenue y algo de aire, para separar bloques sin dibujar lineas.
pub fn tarjeta<'a, M: 'a>(contenido: impl Into<iced::Element<'a, M>>) -> Container<'a, M> {
    container(contenido).padding(12).style(|_theme| container::Style {
        background: Some(rgb(246, 246, 248).into()),
        border: iced::Border {
            color: rgb(222, 222, 228),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..container::Style::default()
    })
}
