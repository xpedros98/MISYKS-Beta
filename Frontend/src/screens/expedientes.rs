// Pantalla de expedientes: elegir un tipo documental y abrir el expediente.
//
// El expediente es la unidad a la que se subordina el resto -- las fechas, los
// plazos, los documentos --, asi que empieza por lo unico que no se puede
// deducir: **de que tipo es**. El tipo determina la ruta, los plazos y el canal
// de salida, y por eso se elige antes que nada y ya no se cambia.
//
// Lo que falta aqui, y se notara: la barra de nodos con los hitos del caso y sus
// fechas debajo. Necesita la lista de hitos por tipo, que es conocimiento
// juridico por escribir (ARQUITECTURA.md 8.3). Hasta entonces, un expediente
// sabe que es pero no por donde va.
use iced::widget::{button, column, pick_list, row, scrollable, text, Space};
use iced::{Element, Length};

use crate::app::Message;
use crate::estilo;
use crate::expedientes::{self, Expediente, ExpedientesError, Hito, TipoDoc};

pub struct ExpedientesState {
    pub tipos: Result<Vec<TipoDoc>, ExpedientesError>,
    pub seleccion: Option<TipoDoc>,
    pub abiertos: Result<Vec<Expediente>, ExpedientesError>,
    pub aviso: Option<Result<String, ExpedientesError>>,
    /// El expediente que se esta mirando, con sus hitos ya leidos. Mientras
    /// hay uno, la pantalla es la suya: `view` devuelve el detalle en vez de la
    /// lista. Los hitos se cargan al abrirlo y no en cada `view`, que se llama
    /// en cada fotograma.
    pub detalle: Option<(Expediente, Vec<Hito>)>,
    /// Segundo paso del borrado masivo. Mientras esta en `true`, el boton
    /// cambia de texto y pide confirmar: borrar todos los expedientes no puede
    /// ser una sola pulsacion.
    pub confirmando_vaciado: bool,
}

impl ExpedientesState {
    pub fn cargar() -> Self {
        Self {
            tipos: expedientes::tipos(),
            seleccion: None,
            abiertos: expedientes::abiertos(),
            aviso: None,
            detalle: None,
            confirmando_vaciado: false,
        }
    }

    pub fn abrir_detalle(&mut self, id: i64) {
        let Ok(filas) = &self.abiertos else { return };
        let Some(expediente) = filas.iter().find(|e| e.id == id).cloned() else {
            return;
        };
        let hitos = expedientes::hitos(id).unwrap_or_default();
        self.detalle = Some((expediente, hitos));
    }

    pub fn cerrar_detalle(&mut self) {
        self.detalle = None;
    }

    pub fn marcar_hito(&mut self, expediente_id: i64, orden: i64) {
        self.aviso = Some(expedientes::hito_hecho(expediente_id, orden));
        self.recargar_detalle(expediente_id);
    }

    pub fn deshacer_hito(&mut self, expediente_id: i64, orden: i64) {
        self.aviso = Some(expedientes::hito_deshacer(expediente_id, orden));
        self.recargar_detalle(expediente_id);
    }

    /// Relee los hitos del expediente abierto. El estado vive en la base, no
    /// aqui: tras cambiarlo hay que volver a preguntarlo, no adivinarlo.
    fn recargar_detalle(&mut self, expediente_id: i64) {
        if let Some((expediente, _)) = &self.detalle {
            if expediente.id == expediente_id {
                let hitos = expedientes::hitos(expediente_id).unwrap_or_default();
                let expediente = expediente.clone();
                self.detalle = Some((expediente, hitos));
            }
        }
    }

    pub fn elegir_tipo(&mut self, tipo: TipoDoc) {
        self.seleccion = Some(tipo);
        self.aviso = None;
    }

    pub fn crear(&mut self) {
        let Some(tipo) = self.seleccion.clone() else {
            return;
        };
        self.aviso = Some(expedientes::abrir(&tipo.tipo));
        self.recargar();
    }

    pub fn pedir_vaciado(&mut self) {
        self.confirmando_vaciado = true;
        self.aviso = None;
    }

    pub fn cancelar_vaciado(&mut self) {
        self.confirmando_vaciado = false;
    }

    pub fn vaciar(&mut self) {
        self.confirmando_vaciado = false;
        self.aviso = Some(expedientes::vaciar());
        self.recargar();
    }

    pub fn eliminar(&mut self, id: i64) {
        self.aviso = Some(expedientes::eliminar(id));
        self.recargar();
    }

    fn recargar(&mut self) {
        self.abiertos = expedientes::abiertos();
        // Si lo que se estaba mirando ya no existe -- se acaba de borrar --, la
        // pantalla vuelve a la lista en vez de quedarse ensenando un expediente
        // fantasma.
        if let Some((abierto, _)) = &self.detalle {
            let sigue = self
                .abiertos
                .as_ref()
                .map(|f| f.iter().any(|e| e.id == abierto.id))
                .unwrap_or(false);
            if !sigue {
                self.detalle = None;
            }
        }
    }
}

pub fn view(state: &ExpedientesState) -> Element<'_, Message> {
    // Con un expediente abierto, la pantalla es la suya y nada mas: mirar un
    // caso es una tarea entera, no un vistazo.
    if let Some((expediente, hitos)) = &state.detalle {
        return crate::screens::detalle::view(expediente, hitos);
    }

    let mut contenido = column![estilo::titulo("Expedientes")].spacing(16);

    // --- alta -------------------------------------------------------------
    let alta: Element<Message> = match &state.tipos {
        Ok(tipos) => {
            let selector = pick_list(
                tipos.as_slice(),
                state.seleccion.as_ref(),
                Message::ExpedienteTipo,
            )
            .placeholder("Elige un tipo documental...")
            .width(Length::Fill);

            let crear = {
                let boton = button("Abrir expediente").padding([6, 14]);
                // Sin tipo elegido no hay nada que abrir: el boton se deja
                // muerto en vez de abrir un expediente sin tipo, que es un
                // expediente sin ruta ni plazos.
                if state.seleccion.is_some() {
                    boton.on_press(Message::ExpedienteCrear)
                } else {
                    boton
                }
            };

            let detalle: Element<Message> = match &state.seleccion {
                Some(t) => estilo::tenue(format!(
                    "Arquetipo {} · salida por {}",
                    t.arquetipo, t.destino
                ))
                .into(),
                None => estilo::tenue(format!("{} tipos en el catalogo", tipos.len())).into(),
            };

            column![row![selector, crear].spacing(8), detalle].spacing(6).into()
        }
        Err(e) => estilo::tenue(e.to_string()).into(),
    };
    contenido = contenido.push(estilo::tarjeta(alta));

    // --- aviso de la ultima operacion -------------------------------------
    if let Some(resultado) = &state.aviso {
        let linea = match resultado {
            Ok(mensaje) => text(mensaje.clone()),
            Err(e) => text(e.to_string()),
        };
        contenido = contenido.push(estilo::tarjeta(linea));
    }

    // --- lista ------------------------------------------------------------
    let lista: Element<Message> = match &state.abiertos {
        Err(e) => estilo::tenue(e.to_string()).into(),
        Ok(filas) if filas.is_empty() => {
            estilo::tenue("No hay ningun expediente abierto todavia.").into()
        }
        Ok(filas) => {
            let mut columna = column![].spacing(6);
            for e in filas {
                columna = columna.push(fila(e));
            }
            scrollable(columna).height(Length::Fill).into()
        }
    };

    let cabecera = row![
        estilo::titulo("Abiertos"),
        Space::new().width(Length::Fill),
        vaciado(state),
    ]
    .spacing(8)
    .align_y(iced::Alignment::Center);

    contenido = contenido.push(cabecera).push(lista);
    contenido.height(Length::Fill).into()
}

fn fila(e: &Expediente) -> Element<'_, Message> {
    let titulo = e.titulo.clone().unwrap_or_else(|| e.tipo.replace('_', " "));
    // La fila entera abre el expediente. El boton de eliminar queda fuera de
    // ese boton y no dentro: una pulsacion que puede borrar no puede compartir
    // superficie con la que solo mira.
    let abrir = button(
        row![
            estilo::mono(e.referencia.clone()),
            column![
                text(titulo),
                estilo::tenue(format!(
                    "{}  ·  arquetipo {}  ·  {}",
                    e.tipo,
                    e.arquetipo,
                    e.destino.clone().unwrap_or_default()
                )),
            ]
            .spacing(2)
            .width(Length::Fill),
        ]
        .spacing(12)
        .align_y(iced::Alignment::Center),
    )
    .padding(0)
    .width(Length::Fill)
    .style(estilo::fila_clicable())
    .on_press(Message::ExpedienteAbrir(e.id));

    estilo::tarjeta(
        row![
            abrir,
            button("Eliminar")
                .padding([4, 10])
                .on_press(Message::ExpedienteEliminar(e.id)),
        ]
        .spacing(12)
        .align_y(iced::Alignment::Center),
    )
    .into()
}

/// El boton de borrado masivo, en sus dos estados.
///
/// Dos pulsaciones y no una, y la segunda dice **cuantos** se va a llevar: es
/// una accion que no se puede deshacer y que no avisa de nada cuando acierta.
/// Al lado queda siempre la salida -- Cancelar --, para que confirmar no sea el
/// unico camino hacia delante.
fn vaciado(state: &ExpedientesState) -> Element<'_, Message> {
    let cuantos = state.abiertos.as_ref().map(|f| f.len()).unwrap_or(0);
    if cuantos == 0 {
        return Space::new().width(Length::Shrink).into();
    }
    if state.confirmando_vaciado {
        row![
            text(format!("¿Eliminar los {cuantos}? No se puede deshacer.")),
            button("Si, eliminar todo")
                .padding([4, 10])
                .on_press(Message::ExpedienteVaciarConfirmar),
            button("Cancelar")
                .padding([4, 10])
                .on_press(Message::ExpedienteVaciarCancelar),
        ]
        .spacing(8)
        .align_y(iced::Alignment::Center)
        .into()
    } else {
        button("Eliminar todos")
            .padding([4, 10])
            .on_press(Message::ExpedienteVaciarPedir)
            .into()
    }
}
