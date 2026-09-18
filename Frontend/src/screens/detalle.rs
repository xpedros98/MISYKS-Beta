// La vista de un expediente: por donde va el caso.
//
// **Una pantalla limpia.** Ocupa el sitio de la lista en vez de abrirse encima:
// mirar un expediente es una tarea entera, no un vistazo, y lo que rodea
// distrae. Se sale por «Volver».
//
// La barra de nodos es lo unico que hay aqui, y se lee de izquierda a derecha:
// cada nodo es un hito del caso -- emplazamiento, contestacion, vista -- y
// debajo va su fecha. Los nodos son del **caso**, no del sistema: el letrado
// reconoce «audiencia previa», no `cri.coherencia`.
//
// Tres cosas que la barra tiene que distinguir o no sirve:
//
// 1. **Que clase de fecha es.** «2 de octubre» como tope propio y «2 de octubre»
//    como dia de vista no pueden parecer lo mismo. El tope lleva su matiz
//    («ultimo dia») y lo provisional lo dice.
// 2. **Lo que aun no tiene fecha.** Un senalamiento sin fijar no es un hueco ni
//    un error: es el estado normal, y puede durar meses. Se escribe.
// 3. **Lo que no esta revisado.** La plantilla de hitos de la que sale esto es
//    un borrador sin validar por un abogado. Mientras lo sea, se dice arriba:
//    una barra que parece definitiva y no lo es es peor que no tenerla.
use iced::widget::{button, column, row, scrollable, text, Space};
use iced::{Element, Length};

use crate::app::Message;
use crate::estilo;
use crate::expedientes::{Expediente, Hito};

// Ancho de cada nodo. Fijo para que los nombres no bailen y la barra se lea
// como una secuencia y no como una lista de cajas de tamanos distintos.
//
// Estrecho a proposito. Con 150 px y el contenido pegado a la izquierda, las
// marcas quedaban lejos unas de otras y el conector colgaba suelto entre dos
// bloques de texto: parecian seis fichas sueltas, no una linea de tiempo. Lo
// que une la barra es que las marcas esten cerca y el texto caiga **debajo de
// su marca**, centrado.
const ANCHO_NODO: f32 = 104.0;

// Cuanto baja el conector para quedar a la altura de las marcas. Es la mitad
// de la linea de la marca: si va a cero, la raya sale por encima de los
// circulos y la barra se ve rota.
const ALTURA_CONECTOR: u16 = 4;

pub fn view<'a>(expediente: &'a Expediente, hitos: &'a [Hito]) -> Element<'a, Message> {
    let volver = button("← Volver")
        .padding([4, 10])
        .on_press(Message::ExpedienteCerrarDetalle);

    let titulo = expediente
        .titulo
        .clone()
        .unwrap_or_else(|| expediente.tipo.replace('_', " "));

    let cabecera = row![
        volver,
        column![
            estilo::titulo(titulo),
            estilo::tenue(format!(
                "{}  ·  {}  ·  arquetipo {}  ·  salida por {}",
                expediente.referencia,
                expediente.tipo,
                expediente.arquetipo,
                expediente.destino.clone().unwrap_or_default()
            )),
        ]
        .spacing(2),
    ]
    .spacing(16)
    .align_y(iced::Alignment::Center);

    let cuerpo: Element<Message> = if hitos.is_empty() {
        // Un tipo sin plantilla no inventa nodos. Decir que no esta escrito es
        // informacion; dibujar una barra generica seria mentir sobre el caso.
        column![
            text("Este tipo documental todavia no tiene recorrido escrito."),
            estilo::tenue(
                "Hay plantilla de hitos para 5 de los 89 tipos. Se escribe en \
                 Backend/expedientes/datos/hitos.csv, con su articulo al lado."
            ),
        ]
        .spacing(8)
        .into()
    } else {
        let mut barra = row![].spacing(0).align_y(iced::Alignment::Start);
        for (i, h) in hitos.iter().enumerate() {
            if i > 0 {
                barra = barra.push(conector(hitos[i - 1].ocurrido));
            }
            barra = barra.push(nodo(h));
        }

        let sin_revisar = hitos.iter().any(|h| !h.revisado);
        let mut bloque = column![scrollable(barra).width(Length::Fill)].spacing(12);
        if sin_revisar {
            bloque = bloque.push(
                text("Borrador: estos hitos no los ha revisado todavia un abogado.")
                    .size(11)
                    .style(|_| text::Style {
                        color: Some(estilo::ALERTA),
                    }),
            );
        }
        bloque.push(normas(hitos)).push(leyenda()).into()
    };

    column![cabecera, estilo::tarjeta(cuerpo).width(Length::Fill)]
        .spacing(16)
        .height(Length::Fill)
        .into()
}

/// Un nodo: la marca, el nombre, la fecha y de donde sale.
fn nodo(h: &Hito) -> Element<'_, Message> {
    // Relleno si ya ocurrio, hueco si no. Es la unica diferencia que hace falta
    // para leer de un vistazo por donde va el caso.
    let marca = if h.ocurrido { "●" } else { "○" };

    let fecha = h.fecha_legible();
    let fecha_widget: Element<Message> = if h.fecha.is_some() {
        text(fecha).size(12).into()
    } else {
        // Sin fecha se atenua: esta ahi para decir que no la hay, no para que
        // el ojo se pare en ella.
        estilo::tenue(fecha).into()
    };

    let matiz = h.matiz();
    let matiz_widget: Element<Message> = if matiz.is_empty() {
        Space::new().height(0).into()
    } else {
        estilo::tenue(matiz).into()
    };

    column![
        text(marca).size(16),
        // El numero no es decoracion: es con el que se le pone fecha al hito
        // desde la CLI (`expedientes fechar ID ORDEN FECHA`) mientras no haya
        // forma de hacerlo desde aqui.
        text(format!("{}. {}", h.orden, h.nombre))
            .size(11)
            .align_x(iced::alignment::Horizontal::Center),
        fecha_widget,
        matiz_widget,
    ]
    // Todo centrado bajo su marca: es lo que hace que el texto se lea como
    // «lo que pasa en este nodo» y no como una columna de una tabla.
    .align_x(iced::Alignment::Center)
    .spacing(2)
    .width(ANCHO_NODO)
    .into()
}

/// La linea entre dos nodos. Se atenua cuando el tramo aun no se ha recorrido.
fn conector(anterior_ocurrido: bool) -> Element<'static, Message> {
    let linea = text("──").size(13);
    let linea: Element<Message> = if anterior_ocurrido {
        linea.into()
    } else {
        linea
            .style(|theme: &iced::Theme| text::Style {
                color: Some(estilo::tenue_color(theme)),
            })
            .into()
    };
    // A la altura de las marcas, no del bloque entero.
    column![linea].padding([ALTURA_CONECTOR, 0]).into()
}

/// El fundamento de cada hito, debajo de la barra y no dentro de cada nodo.
///
/// Estaba en el nodo y era lo que mas lo ensanchaba: «art. 404 LEC — 20 dias
/// habiles» no cabe en 104 px y obligaba a columnas del doble de ancho. Ademas
/// no es lo que se mira de un vistazo -- se consulta cuando alguien pregunta
/// por que --, asi que baja a una lista y deja la barra limpia.
fn normas(hitos: &[Hito]) -> Element<'_, Message> {
    let mut lista = column![].spacing(1);
    for h in hitos {
        let Some(norma) = h.norma.clone().filter(|n| !n.is_empty() && n != "—") else {
            continue;
        };
        lista = lista.push(estilo::tenue(format!("{}. {}  ·  {}", h.orden, h.nombre, norma)));
    }
    lista.into()
}

fn leyenda() -> Element<'static, Message> {
    estilo::tenue(
        "● ocurrido   ○ pendiente   ·   «ultimo dia» = plazo propio   \
         ·   «sin senalar» = lo fija el juzgado",
    )
    .into()
}
