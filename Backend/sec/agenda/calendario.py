"""La interfaz `Calendario`: lo único que `sec.agenda` sabe de un calendario.

ARQUITECTURA.md §8.6: «`sec.mail` y `sec.agenda` no conocen el proveedor de
origen. Hablan con `Correo` y `Calendario` -- esta última con
`listar_eventos(desde, hasta)`, `crear_evento`, `actualizar` y `borrar` --,
implementadas por un adaptador por mundo.»

§8.6 nombra además los tres puntos donde los proveedores divergen, y avisa de
que **sus fallos no dan error sino plazos incorrectos**. Así se resuelve cada
uno aquí:

- **Eventos recurrentes.** Una ocurrencia movida o cancelada dentro de una
  serie se representa de forma distinta en cada proveedor. No se interpreta la
  regla de repetición: se le pide al proveedor que **expanda la serie** y se
  guarda cada ocurrencia como un evento con su `serie_id`. Interpretar RRULE
  por nuestra cuenta sería reimplementar un calendario, y equivocarse en una
  excepción es perder un señalamiento.
- **Zonas horarias.** Un evento es una hora local con una zona asociada, no un
  instante. Se guardan **las dos cosas**: la hora local tal como la escribió
  quien creó el evento (es la que el abogado reconoce) y el instante UTC que
  sale del desplazamiento que trae el propio proveedor (es con el que se
  comparan solapes). El desplazamiento viene dentro del RFC 3339, así que no
  hace falta base de datos de zonas horarias -- que en Windows exigiría el
  paquete `tzdata`, y el Backend no tiene más dependencia que `sqlcipher3`.
- **Sincronización incremental.** Cursor opaco, igual que en `sec.mail`:
  `syncToken` en Google, `deltaLink` en Graph. `sec.agenda` lo guarda y lo
  devuelve sin mirarlo, y si el proveedor lo rechaza por antiguo se vuelve a
  recorrer la ventana entera.

Y una diferencia con `Correo` que conviene no pasar por alto: aquí **listar ya
trae el evento entero**, no un identificador que haya que descargar después.
Por eso no hay cola de pendientes como en el correo: no existe el hueco entre
anunciar y traer que la cola venía a cubrir.
"""
from abc import ABC, abstractmethod

from ..cuentas import ajustes


class ErrorCalendario(RuntimeError):
    """Fallo hablando con el calendario que no es de autenticación."""


class Calendario(ABC):
    """Un calendario ya autenticado. `proveedor` y `cuenta` dicen de quién es."""

    proveedor = ""
    cuenta = ""

    @abstractmethod
    def listar_eventos(self, desde, hasta, cursor=None):
        """(eventos[], cursor nuevo, hubo_reinicio).

        `desde` y `hasta` son fechas ISO (`2026-09-17`) y acotan la ventana.
        Con `cursor` a None recorre la ventana entera; con un cursor válido
        pide solo lo cambiado desde entonces, incluidas las **bajas** -- un
        señalamiento anulado tiene que desaparecer de la agenda, y si solo se
        pidieran las altas seguiría ahí para siempre.

        `hubo_reinicio` es True cuando el proveedor rechazó el cursor y se ha
        recorrido la ventana entera. Quien llama lo necesita: en un recorrido
        completo, lo que no aparece es que ya no existe, y eso solo se puede
        concluir cuando la respuesta es completa.

        Cada evento es un diccionario con las claves que describe
        `evento_vacio()`.
        """

    @abstractmethod
    def crear_evento(self, evento):
        """Crea el evento en el calendario del proveedor. Devuelve su identificador."""

    @abstractmethod
    def actualizar(self, evento_id, cambios):
        """Cambia un evento ya creado. `cambios` usa las mismas claves que `crear_evento`."""

    @abstractmethod
    def borrar(self, evento_id):
        """Quita el evento del calendario del proveedor."""


def evento_vacio():
    """La forma de un evento tal como lo entrega un adaptador.

    - `evento_id`   identificador en el proveedor; estable entre llamadas.
    - `serie_id`    identificador de la serie, si es una ocurrencia de una
                    repetición. Vacío si el evento es único.
    - `repeticion`  regla de repetición en RRULE (`RRULE:FREQ=YEARLY`), **solo
                    de salida**: se manda al crear un evento que se repite. De
                    vuelta no llega, porque se piden las ocurrencias ya
                    expandidas; lo que identifica a una ocurrencia como parte
                    de una serie es `serie_id`.
    - `titulo`, `lugar`, `descripcion`
    - `inicio_local`, `fin_local`   `2026-09-17T10:00:00` tal como lo ve quien
                    creó el evento, sin desplazamiento. Es lo que se enseña.
    - `zona`        nombre de la zona del proveedor (`Europe/Madrid`), como
                    texto opaco: no se resuelve contra ninguna tabla.
    - `inicio_utc`, `fin_utc`   el instante, en UTC y con `Z`. Es lo único con
                    lo que se comparan solapes; comparar horas locales de dos
                    zonas distintas da colisiones que no existen y, peor,
                    silencia las que sí.
    - `todo_el_dia` True cuando el proveedor da fecha sin hora. Entonces no hay
                    instante y `inicio_utc`/`fin_utc` van vacíos.
    - `cancelado`   True si el proveedor lo da como anulado. No se borra la
                    fila: un señalamiento que se cae es información.
    - `organizador`, `asistentes`
    """
    return {
        "evento_id": "",
        "serie_id": "",
        "repeticion": "",
        "titulo": "",
        "lugar": "",
        "descripcion": "",
        "inicio_local": "",
        "fin_local": "",
        "zona": "",
        "inicio_utc": "",
        "fin_utc": "",
        "todo_el_dia": False,
        "cancelado": False,
        "organizador": "",
        "asistentes": "",
    }


def abrir(proveedor=None):
    """El calendario configurado. Falla con un mensaje útil si no hay ninguno."""
    proveedor = proveedor or ajustes.proveedor_activo("calendario")
    if proveedor == "google":
        from .google import GoogleCalendar

        return GoogleCalendar()
    if proveedor == "microsoft":
        raise ErrorCalendario(
            "El adaptador de Microsoft Graph para calendario no está escrito todavía "
            "(ARQUITECTURA.md §8.3). Hoy sec.agenda solo habla con Google Calendar."
        )
    raise ErrorCalendario(
        f"Proveedor de calendario desconocido: {proveedor}. El implementado: google."
    )
