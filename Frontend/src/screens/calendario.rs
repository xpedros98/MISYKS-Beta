// Pantalla de calendario: que se sabe, que falta y que dias son inhabiles.
//
// Es la vista de **mantenimiento**, no la del dia a dia. El letrado no va a
// abrir esto: lo que el mirara son los plazos, y para eso hace falta el motor de
// dias, que todavia no existe. Lo que esta pantalla evita es el fallo que
// describe COMPONENTES.md -- que el calendario envejezca en silencio -- poniendo
// delante de alguien del equipo lo que falta y lo que se ha roto.
//
// La tabla va en un solo color: con varios compitiendo, el ojo no sabe donde
// mirar y no destaca ninguno. El unico acento es lo que pide accion -- una
// averia, o una cifra distinta de cero en FALLIDO --; lo que esta bien se
// atenua. El color que identifica vive en la barra de navegacion, no aqui.
use iced::widget::{button, column, container, row, scrollable, text, Space};
use iced::{Element, Length};

use crate::app::Message;
use crate::calendario::{Averia, CalendarioError, Festivo, Laguna};
use crate::estilo;

// Anchuras de la tabla de cobertura. Fijas y en un solo sitio, porque cabecera
// y filas tienen que coincidir o la tabla deja de leerse en columna.
const ANCHO_NIVEL: f32 = 110.0;
const ANCHO_CIFRA: f32 = 92.0;

pub struct CalendarioState {
    pub resumen: Result<crate::calendario::Resumen, CalendarioError>,
    pub municipios: Vec<crate::calendario::Ambito>,
    pub seleccion: Option<String>,
    pub anio: i32,
    pub computo: usize,
    pub dias: Vec<Festivo>,
    pub lagunas: Vec<Laguna>,
}

impl CalendarioState {
    pub fn cargar() -> Self {
        // Si la base no existe todavia, el ano da igual: la pantalla mostrara
        // el error de `resumen` con la orden que hay que ejecutar.
        let anio = crate::calendario::anio_base().unwrap_or(0);
        let resumen = crate::calendario::resumen();
        let municipios = crate::calendario::municipios().unwrap_or_default();
        let mut estado = Self {
            resumen,
            municipios,
            seleccion: None,
            anio,
            computo: 0,
            dias: Vec::new(),
            lagunas: Vec::new(),
        };
        // Se arranca con el primer municipio para que la pantalla no salga
        // vacia: sin nada seleccionado no se entiende para que sirve.
        if let Some(primero) = estado.municipios.first().map(|m| m.id.clone()) {
            estado.seleccionar(primero);
        }
        estado
    }

    pub fn seleccionar(&mut self, ambito: String) {
        let computo = crate::calendario::COMPUTOS[self.computo];
        self.dias =
            crate::calendario::dias_inhabiles(&ambito, computo, self.anio).unwrap_or_default();
        self.lagunas =
            crate::calendario::lagunas(&ambito, computo, self.anio).unwrap_or_default();
        self.seleccion = Some(ambito);
    }

    pub fn cambiar_computo(&mut self, computo: usize) {
        self.computo = computo;
        if let Some(ambito) = self.seleccion.clone() {
            self.seleccionar(ambito);
        }
    }

    fn nombre_seleccion(&self) -> &str {
        self.seleccion
            .as_deref()
            .and_then(|id| {
                self.municipios
                    .iter()
                    .find(|m| m.id == id)
                    .map(|m| m.nombre.as_str())
            })
            .unwrap_or("")
    }
}

pub fn view(state: &CalendarioState) -> Element<'_, Message> {
    let resumen = match &state.resumen {
        Err(err) => {
            // El error se cuenta entero, con la orden que lo arregla: quien abra
            // esto puede no saber que el calendario se llena desde un terminal.
            return container(
                column![
                    estilo::titulo("No se puede leer el calendario"),
                    text(err.to_string()).size(13),
                ]
                .spacing(8),
            )
            .padding(20)
            .into();
        }
        Ok(r) => r,
    };

    scrollable(
        column![
            cabecera(resumen),
            tabla_cobertura(resumen),
            averias(&resumen.averias),
            selector(state),
            detalle(state),
        ]
        .spacing(14)
        .padding(4),
    )
    .height(Length::Fill)
    .into()
}

fn cabecera(resumen: &crate::calendario::Resumen) -> Element<'_, Message> {
    row![
        estilo::titulo("Calendario de festivos"),
        Space::new().width(Length::Fill),
        estilo::tenue(format!(
            "version {} · ultimo festivo guardado {}",
            resumen.version,
            resumen.ultimo_festivo.as_deref().unwrap_or("ninguno")
        )),
    ]
    .align_y(iced::Alignment::Center)
    .into()
}

fn tabla_cobertura(resumen: &crate::calendario::Resumen) -> Element<'_, Message> {
    let encabezado = row![
        estilo::tenue("nivel").width(Length::Fixed(ANCHO_NIVEL)),
        celda_cabecera("confirmado"),
        celda_cabecera("pendiente"),
        celda_cabecera("sin publicar"),
        celda_cabecera("FALLIDO"),
    ];

    let mut tabla = column![encabezado].spacing(4);
    for (nivel, confirmado, pendiente, sin_publicar, fallido) in &resumen.cobertura {
        tabla = tabla.push(
            row![
                text(nivel.clone()).size(13).width(Length::Fixed(ANCHO_NIVEL)),
                celda(*confirmado, false),
                celda(*pendiente, false),
                celda(*sin_publicar, false),
                // La unica columna que puede pedir accion.
                celda(*fallido, true),
            ]
            .align_y(iced::Alignment::Center),
        );
    }

    tabla = tabla.push(Space::new().height(Length::Fixed(4.0))).push(
        estilo::tenue(
            "pendiente = no se ha intentado  ·  sin publicar = el boletin aun no lo ha sacado  \
             ·  FALLIDO = se intento y fallo",
        ),
    );

    estilo::tarjeta(tabla).width(Length::Fill).into()
}

fn celda_cabecera<'a>(etiqueta: &'a str) -> Element<'a, Message> {
    estilo::tenue(etiqueta)
        .width(Length::Fixed(ANCHO_CIFRA))
        .align_x(iced::alignment::Horizontal::Right)
        .into()
}

fn celda<'a>(valor: i64, alerta: bool) -> Element<'a, Message> {
    // Un cero se atenua siempre, tambien en la columna de alerta: una columna
    // que resalta aunque no haya nada que mirar deja de avisar de nada, y esta
    // pantalla existe justamente para avisar.
    let destacar = alerta && valor > 0;
    let celda = estilo::mono(valor.to_string())
        .width(Length::Fixed(ANCHO_CIFRA))
        .align_x(iced::alignment::Horizontal::Right);
    if destacar {
        celda.color(estilo::ALERTA).into()
    } else if valor == 0 {
        celda
            .style(|theme: &iced::Theme| text::Style {
                color: Some(estilo::tenue_color(theme)),
            })
            .into()
    } else {
        celda.into()
    }
}

fn averias(averias: &[Averia]) -> Element<'_, Message> {
    if averias.is_empty() {
        return estilo::tenue("Ninguna fuente ha fallado.").into();
    }
    let mut bloque = column![text(format!(
        "{} fuentes se han intentado y han fallado",
        averias.len()
    ))
    .size(14)
    .color(estilo::ALERTA)]
    .spacing(3);
    for a in averias {
        bloque = bloque.push(
            estilo::mono(format!(
                "{:<10} {} {:<15} {}",
                a.ambito,
                a.anio,
                a.computo,
                a.detalle.as_deref().unwrap_or("")
            ))
            .size(12),
        );
    }
    estilo::tarjeta(bloque).width(Length::Fill).into()
}

fn selector(state: &CalendarioState) -> Element<'_, Message> {
    let mut municipios = row![].spacing(6);
    for m in &state.municipios {
        let elegido = state.seleccion.as_deref() == Some(m.id.as_str());
        // Mismo lenguaje que la barra de navegacion y con el color de esta
        // seccion: dos formas distintas de decir «esto esta seleccionado» en la
        // misma pantalla obligan a aprender dos cosas en vez de una.
        let boton = button(text(m.nombre.as_str()).size(12))
            .padding([4, 10])
            .style(estilo::pestana(estilo::SECCION_CALENDARIO, elegido));
        municipios = municipios.push(if elegido {
            boton
        } else {
            boton.on_press(Message::CalendarioAmbito(m.id.clone()))
        });
    }

    let mut computos = row![].spacing(6);
    for (i, c) in crate::calendario::COMPUTOS.iter().enumerate() {
        let elegido = i == state.computo;
        let boton = button(text(*c).size(12))
            .padding([4, 10])
            .style(estilo::pestana(estilo::SECCION_CALENDARIO, elegido));
        computos = computos.push(if elegido {
            boton
        } else {
            boton.on_press(Message::CalendarioComputo(i))
        });
    }

    column![
        scrollable(municipios).width(Length::Fill),
        row![estilo::tenue("computo:"), computos]
            .spacing(8)
            .align_y(iced::Alignment::Center),
    ]
    .spacing(8)
    .into()
}

fn detalle(state: &CalendarioState) -> Element<'_, Message> {
    let Some(ambito) = &state.seleccion else {
        return estilo::tenue("Selecciona un municipio.").into();
    };

    // FIRME o PROVISIONAL es lo primero que hay que ver: es lo que decide si un
    // plazo calculado sobre este sitio puede darse por bueno.
    let mut veredicto = row![].spacing(6).align_y(iced::Alignment::Center);
    // FIRME no se colorea: que algo este bien no necesita llamar la atencion.
    // Lo que se marca es que una laguna venga de una averia, porque eso si pide
    // que alguien haga algo hoy.
    if state.lagunas.is_empty() {
        veredicto = veredicto.push(text("FIRME").size(13));
    } else {
        veredicto = veredicto.push(text("PROVISIONAL").size(13));
        veredicto = veredicto.push(estilo::tenue("le falta"));
        for l in &state.lagunas {
            let etiqueta = estilo::mono(format!("{} ({})", l.ambito, l.estado)).size(12);
            veredicto = veredicto.push(if l.estado == "fallido" {
                etiqueta.color(estilo::ALERTA)
            } else {
                etiqueta
            });
        }
    }

    let cabecera = row![
        estilo::titulo(format!("{} · {}", state.nombre_seleccion(), ambito)),
        estilo::tenue(format!(
            "{} · {} dias de boletin",
            state.anio,
            state.dias.len()
        )),
        Space::new().width(Length::Fill),
        veredicto,
    ]
    .spacing(10)
    .align_y(iced::Alignment::Center);

    let mut lista = column![].spacing(3);
    for d in &state.dias {
        lista = lista.push(
            row![
                estilo::mono(d.fecha.clone()).width(Length::Fixed(100.0)),
                // La marca dice de que nivel viene el dia -- N nacional, A
                // autonomico, I insular, L local --, que es la pregunta que
                // surge al ver un festivo inesperado. Va en letra, no en color:
                // una lista de doce dias con cuatro colores se lee peor.
                estilo::mono(estilo::marca_nivel(&d.tipo).to_string())
                    .width(Length::Fixed(18.0)),
                estilo::mono(d.ambito.clone())
                    .style(|theme: &iced::Theme| text::Style {
                        color: Some(estilo::tenue_color(theme)),
                    })
                    .width(Length::Fixed(80.0)),
                text(d.nombre.clone().unwrap_or_default()).size(13),
            ]
            .align_y(iced::Alignment::Center),
        );
    }

    column![
        cabecera,
        estilo::tenue(
            "Sabados y domingos no aparecen: son regla del motor, no dato de boletin."
        ),
        estilo::tarjeta(lista).width(Length::Fill),
    ]
    .spacing(6)
    .into()
}
