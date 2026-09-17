// Pantalla de calendario: que se sabe, que falta y que dias son inhabiles.
//
// Es la vista de **mantenimiento**, no la del dia a dia. El letrado no va a
// abrir esto: lo que el mirara son los plazos, y para eso hace falta el motor de
// dias, que todavia no existe. Lo que esta pantalla evita es el fallo que
// describe AGENTES.md -- que el calendario envejezca en silencio -- poniendo
// delante de alguien del equipo lo que falta y lo que se ha roto.
//
// Por eso lo fallido se separa del resto en vez de sumarse a un total: de los
// tres estados que no son `confirmado`, solo ese pide que alguien actue.
use iced::widget::{button, column, container, row, scrollable, text};
use iced::{Element, Length};

use crate::app::Message;
use crate::calendario::{Averia, CalendarioError, Festivo, Laguna};

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
        self.dias = crate::calendario::dias_inhabiles(&ambito, computo, self.anio)
            .unwrap_or_default();
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
}

pub fn view(state: &CalendarioState) -> Element<'_, Message> {
    let resumen = match &state.resumen {
        Err(err) => {
            // El error se cuenta entero, con la orden que lo arregla: quien abra
            // esto puede no saber que el calendario se llena desde un terminal.
            return container(text(err.to_string())).padding(20).into();
        }
        Ok(r) => r,
    };

    let mut bloque = column![
        text(format!(
            "Version {} · ultimo festivo guardado: {}",
            resumen.version,
            resumen.ultimo_festivo.as_deref().unwrap_or("ninguno")
        )),
        text(format!(
            "{:<12}{:>11}{:>11}{:>14}{:>9}",
            "nivel", "confirmado", "pendiente", "sin publicar", "FALLIDO"
        )),
    ]
    .spacing(2);

    for (nivel, confirmado, pendiente, sin_publicar, fallido) in &resumen.cobertura {
        bloque = bloque.push(text(format!(
            "{nivel:<12}{confirmado:>11}{pendiente:>11}{sin_publicar:>14}{fallido:>9}"
        )));
    }
    bloque = bloque
        .push(text("").size(6))
        .push(text("pendiente = no se ha intentado · sin publicar = el boletin aun no lo ha sacado").size(12))
        .push(averias(&resumen.averias));

    let selector = seleccion_municipio(state);
    let detalle = detalle_ambito(state);

    column![bloque, selector, detalle]
        .spacing(16)
        .padding(10)
        .into()
}

fn averias(averias: &[Averia]) -> Element<'_, Message> {
    if averias.is_empty() {
        return text("Ninguna fuente ha fallado.").size(12).into();
    }
    let mut bloque = column![text(format!(
        "{} fuentes se han intentado y han fallado:",
        averias.len()
    ))]
    .spacing(2);
    for a in averias {
        let detalle = a.detalle.as_deref().unwrap_or("");
        bloque = bloque.push(
            text(format!("  {} {} {} — {}", a.ambito, a.anio, a.computo, detalle)).size(12),
        );
    }
    bloque.into()
}

fn seleccion_municipio(state: &CalendarioState) -> Element<'_, Message> {
    let mut fila = row![].spacing(6);
    for m in &state.municipios {
        let seleccionado = state.seleccion.as_deref() == Some(m.id.as_str());
        let b = button(text(m.nombre.as_str()).size(12));
        fila = fila.push(if seleccionado {
            b
        } else {
            b.on_press(Message::CalendarioAmbito(m.id.clone()))
        });
    }

    let mut computos = row![].spacing(6);
    for (i, c) in crate::calendario::COMPUTOS.iter().enumerate() {
        let b = button(text(*c).size(12));
        computos = computos.push(if i == state.computo {
            b
        } else {
            b.on_press(Message::CalendarioComputo(i))
        });
    }

    column![scrollable(fila).width(Length::Fill), computos].spacing(6).into()
}

fn detalle_ambito(state: &CalendarioState) -> Element<'_, Message> {
    let Some(ambito) = &state.seleccion else {
        return text("Selecciona un municipio.").into();
    };
    // FIRME o PROVISIONAL es lo primero que hay que ver: es lo que decidira si
    // un plazo calculado sobre este sitio puede darse por bueno.
    let estado = if state.lagunas.is_empty() {
        "FIRME".to_string()
    } else {
        format!(
            "PROVISIONAL — faltan: {}",
            state
                .lagunas
                .iter()
                .map(|l| format!("{} ({})", l.ambito, l.estado))
                .collect::<Vec<_>>()
                .join(", ")
        )
    };

    let mut lista = column![].spacing(2);
    for d in &state.dias {
        // La marca dice de que nivel viene el dia, que es la pregunta que
        // surge al ver un festivo que no se esperaba.
        let marca = match d.tipo.as_str() {
            "nacional" => "N",
            "autonomico" => "A",
            "insular" => "I",
            _ => "L",
        };
        lista = lista.push(
            text(format!(
                "  {}  [{}] {:<10} {}",
                d.fecha,
                marca,
                d.ambito,
                d.nombre.as_deref().unwrap_or("")
            ))
            .size(12),
        );
    }

    column![
        text(format!(
            "{} · {} · {} · {} dias de boletin · {}",
            ambito,
            state.anio,
            crate::calendario::COMPUTOS[state.computo],
            state.dias.len(),
            estado
        )),
        // Los fines de semana no salen: son regla del motor, no dato de
        // boletin, y marcarlos aqui haria creer que el calendario los conoce.
        text("Sabados y domingos no aparecen: son regla del motor, no dato de boletin.").size(11),
        scrollable(lista).height(Length::Fill),
    ]
    .spacing(6)
    .into()
}
