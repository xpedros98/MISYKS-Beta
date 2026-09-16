// Pantalla de Ajustes: conectar la cuenta de correo de sec.mail.
//
// Ya no hay contrasena que escribir aqui. El acceso es por OAuth
// (ARQUITECTURA.md 8.6): «Conectar cuenta» abre el navegador en el dominio
// del proveedor, la persona elige cuenta y acepta los permisos, y lo unico
// que vuelve a esta maquina es un refresh token, que se guarda en
// ~/.misyks/config — nunca se envia a maat ni a ningun otro sitio (ver
// src/local_config.rs).
//
// Los tres estados que puede tener una cuenta se pintan distinto a proposito:
// «conectado» y «sin conectar» son obvios, pero «revocado» es el que importa,
// porque el sistema deja de recibir correo sin que nadie haya tocado nada
// (contrasena cambiada, administrador que bloquea la app, o los 7 dias que
// dura un refresh token mientras la app de Google siga en estado *Testing*).
use iced::widget::{button, column, row, text};
use iced::Element;

use crate::app::Message;
use crate::secretario;

pub const PROVEEDORES: [&str; 2] = ["google", "microsoft"];

#[derive(Debug, Default)]
pub struct SettingsState {
    /// (proveedor, estado, detalle) tal como los da `sec.mail estado`.
    pub cuentas: Vec<(String, String, String)>,
    pub estado: EstadoGuardado,
}

#[derive(Debug, Default, Clone)]
pub enum EstadoGuardado {
    #[default]
    Ninguno,
    Conectado(String),
    Error(String),
}

impl SettingsState {
    pub fn cargar() -> Self {
        let mut estado = Self::default();
        estado.refrescar();
        estado
    }

    /// Relee el estado de las cuentas preguntandoselo al Backend.
    ///
    /// Si el Backend no contesta (no esta el venv, falta el client_id) no se
    /// deja la lista vacia, que pareceria «no hay nada conectado»: se enseña
    /// el error, que es lo que de verdad pasa.
    pub fn refrescar(&mut self) {
        match secretario::estado_oauth() {
            Ok(cuentas) => self.cuentas = cuentas,
            Err(e) => {
                self.cuentas.clear();
                self.estado = EstadoGuardado::Error(e.to_string());
            }
        }
    }

    /// Abre el navegador y espera al consentimiento. Bloqueante: puede tardar
    /// minutos, porque depende de que una persona acepte en otra ventana.
    pub fn conectar(&mut self, proveedor: &str) {
        self.estado = match secretario::conectar(proveedor) {
            Ok(salida) => EstadoGuardado::Conectado(salida),
            Err(e) => EstadoGuardado::Error(e.to_string()),
        };
        self.refrescar();
    }

    pub fn desconectar(&mut self, proveedor: &str) {
        self.estado = match secretario::desconectar(proveedor) {
            Ok(salida) => EstadoGuardado::Conectado(salida),
            Err(e) => EstadoGuardado::Error(e.to_string()),
        };
        self.refrescar();
    }

    /// Si hay al menos una cuenta usable, para saber si tiene sentido
    /// sincronizar nada mas volver de Ajustes.
    pub fn hay_cuenta(&self) -> bool {
        self.cuentas.iter().any(|(_, estado, _)| estado == "conectado")
    }
}

pub fn view(state: &SettingsState) -> Element<'_, Message> {
    let mut contenido = column![
        text("Cuentas de correo (sec.mail)").size(20),
        text(
            "La autorizacion se hace en el navegador, en la pagina del proveedor. \
             MISYKS no ve tu contrasena: guarda solo el permiso de acceso, y solo \
             en este ordenador."
        ),
    ]
    .spacing(12)
    .padding(10);

    for proveedor in PROVEEDORES {
        let (estado, detalle) = state
            .cuentas
            .iter()
            .find(|(p, _, _)| p == proveedor)
            .map(|(_, e, d)| (e.as_str(), d.as_str()))
            .unwrap_or(("sin_conectar", ""));

        let conectado = estado == "conectado";
        let descripcion = match estado {
            "conectado" => format!("conectada: {detalle}"),
            "revocado" => "el permiso ya no vale: vuelve a conectarla".to_string(),
            _ => "sin conectar".to_string(),
        };

        let accion = if conectado {
            button("Desconectar").on_press(Message::DesconectarCuenta(proveedor.to_string()))
        } else {
            button("Conectar cuenta").on_press(Message::ConectarCuenta(proveedor.to_string()))
        };

        contenido = contenido.push(
            row![
                text(etiqueta(proveedor)).size(16),
                text(descripcion),
                accion,
            ]
            .spacing(12),
        );
    }

    let mensaje: Element<'_, Message> = match &state.estado {
        EstadoGuardado::Ninguno => text("").into(),
        EstadoGuardado::Conectado(s) => text(s.clone()).into(),
        EstadoGuardado::Error(e) => text(e.clone()).into(),
    };

    contenido.push(mensaje).into()
}

fn etiqueta(proveedor: &str) -> &'static str {
    match proveedor {
        "google" => "Google (Gmail, Workspace)",
        "microsoft" => "Microsoft (Outlook, Microsoft 365)",
        _ => "Otro proveedor",
    }
}
