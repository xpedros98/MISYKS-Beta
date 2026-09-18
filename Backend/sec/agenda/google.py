"""Adaptador de la Google Calendar API. Autenticación por OAuth (ver sec.cuentas).

Scope `calendar.events` -- eventos, no la agenda completa --, que ya se pide en
el mismo consentimiento que el correo (ARQUITECTURA.md §8.6). Conectar la cuenta
desde `sec.mail` deja el calendario conectado también: no hay un segundo paso.

Dos decisiones que no son obvias al leer el código:

**`singleEvents=true`.** Se le pide a Google que expanda las series en
ocurrencias y que entregue cada una por separado, con su `recurringEventId`
apuntando a la serie. Una vista movida de día o anulada dentro de una serie
llega entonces como lo que es, una ocurrencia con su propia fecha o con estado
`cancelled`. La alternativa -- traer la regla de repetición y expandirla
nosotros -- es reescribir un calendario entero para equivocarnos justo en las
excepciones, que es donde están los señalamientos que se mueven.

**El `syncToken` no se puede acotar, y tampoco acota él.** En las llamadas
incrementales no se le pueden volver a mandar `timeMin` ni `timeMax` (responde
400), así que `db.py` guarda junto al cursor la ventana con la que se pidió y
lo descarta si se pide otra: reusarlo con otra ventana daría una agenda con
huecos que nadie notaría.

Lo que **no** hace es respetar esa ventana al contestar, aunque parezca lo
natural. Medido: dos eventos anuales sin fecha de fin, recién creados, y la
primera sincronización incremental devolvió **147 ocurrencias**, expandidas
hasta el año 2099. Por eso el filtrado por ventana lo hace `agent.py` sobre lo
recibido, y no se delega en la petición. Aquí se devuelve lo que manda Google
sin recortarlo: el adaptador no sabe qué hay guardado, y un evento que se ha
movido fuera de la ventana sí interesa a quien sí lo sabe.
"""
from datetime import datetime, timezone

from ..cuentas import oauth
from . import calendario

API = "https://www.googleapis.com/calendar/v3"

# El calendario principal de la cuenta. Que el abogado lleve el despacho en un
# calendario secundario es posible, y entonces esto tendrá que salir de la
# configuración; hoy no hay nada que lo pida.
CALENDARIO = "primary"


class GoogleCalendar(calendario.Calendario):
    proveedor = "google"

    def __init__(self, sesion=None, calendario_id=CALENDARIO):
        self.sesion = sesion or oauth.Sesion("google")
        self.cuenta = self.sesion.cuenta
        self.calendario_id = calendario_id

    def listar_eventos(self, desde, hasta, cursor=None):
        if cursor:
            try:
                # `showDeleted` solo aquí: en el incremental, una baja **es** la
                # noticia y llega como un evento con estado `cancelled`.
                eventos, cursor_nuevo = self._pedir({"syncToken": cursor}, borrados=True)
                return eventos, cursor_nuevo, False
            except oauth.ErrorApi as e:
                # 410: el cursor es demasiado antiguo y Google ya no sabe qué
                # ha cambiado desde entonces. Es el equivalente al 404 del
                # historyId de Gmail: se recorre la ventana entera.
                if e.codigo != 410:
                    raise
        eventos, cursor_nuevo = self._pedir(
            {
                "timeMin": _inicio_del_dia(desde),
                "timeMax": _fin_del_dia(hasta),
            }
        )
        return eventos, cursor_nuevo, True

    def _pedir(self, params_iniciales, borrados=False):
        """Recorre todas las páginas y devuelve (eventos, cursor nuevo).

        El `nextSyncToken` solo llega en la **última** página: si se guardara
        uno de una página intermedia, la sincronización siguiente empezaría por
        detrás de lo ya traído y se perdería lo que haya en medio.

        `borrados` solo vale la pena en el incremental. En un recorrido completo
        pedir los borrados **resucita lápidas**: Google guarda un tiempo los
        eventos eliminados y los devuelve con estado `cancelled`, así que cada
        recorrido completo volvía a crear la fila de algo borrado hace semanas.
        En el completo, una baja se detecta por ausencia, que es justo para lo
        que existe `marcar_ausentes_como_cancelados`.
        """
        eventos, pagina, cursor_nuevo = [], None, None
        while True:
            params = dict(params_iniciales)
            params.update(singleEvents="true", maxResults=2500)
            if borrados:
                params["showDeleted"] = "true"
            if pagina:
                params["pageToken"] = pagina
            respuesta = self.sesion.pedir(
                f"{API}/calendars/{self.calendario_id}/events", params=params
            )
            eventos += [_traducir(e) for e in respuesta.get("items", [])]
            pagina = respuesta.get("nextPageToken")
            if not pagina:
                cursor_nuevo = respuesta.get("nextSyncToken")
                break
        return eventos, cursor_nuevo

    def crear_evento(self, evento):
        creado = self.sesion.pedir(
            f"{API}/calendars/{self.calendario_id}/events",
            metodo="POST",
            cuerpo=_cuerpo(evento),
        )
        return creado["id"]

    def actualizar(self, evento_id, cambios):
        self.sesion.pedir(
            f"{API}/calendars/{self.calendario_id}/events/{evento_id}",
            metodo="PATCH",
            cuerpo=_cuerpo(cambios),
        )

    def borrar(self, evento_id):
        try:
            self.sesion.pedir(
                f"{API}/calendars/{self.calendario_id}/events/{evento_id}", metodo="DELETE"
            )
        except oauth.ErrorApi as e:
            # Ya no está: el resultado que se pedía es el que hay.
            if e.codigo not in (404, 410):
                raise


def _traducir(item):
    """Un evento de la API al diccionario de `calendario.evento_vacio()`."""
    evento = calendario.evento_vacio()
    inicio, fin = item.get("start", {}), item.get("end", {})
    todo_el_dia = "date" in inicio

    evento.update(
        evento_id=item.get("id", ""),
        serie_id=item.get("recurringEventId", ""),
        titulo=item.get("summary", ""),
        lugar=item.get("location", ""),
        descripcion=item.get("description", ""),
        zona=inicio.get("timeZone", ""),
        todo_el_dia=todo_el_dia,
        cancelado=item.get("status") == "cancelled",
        organizador=item.get("organizer", {}).get("email", ""),
        asistentes=", ".join(
            a.get("email", "") for a in item.get("attendees", []) if a.get("email")
        ),
    )
    if todo_el_dia:
        # Sin hora no hay instante. Google da el final en exclusiva (un evento
        # de un día termina «el día siguiente»), y así se guarda: quien compara
        # días no tiene que acordarse de sumar uno.
        evento.update(inicio_local=inicio.get("date", ""), fin_local=fin.get("date", ""))
    else:
        evento.update(
            inicio_local=_sin_desplazamiento(inicio.get("dateTime", "")),
            fin_local=_sin_desplazamiento(fin.get("dateTime", "")),
            inicio_utc=_a_utc(inicio.get("dateTime", "")),
            fin_utc=_a_utc(fin.get("dateTime", "")),
        )
    return evento


def _cuerpo(evento):
    """El diccionario propio traducido a lo que espera la API.

    Solo se mandan las claves presentes: `actualizar` hace PATCH y lo que no
    viaja se queda como estaba en el calendario del abogado.
    """
    cuerpo = {}
    if "titulo" in evento:
        cuerpo["summary"] = evento["titulo"]
    if "lugar" in evento:
        cuerpo["location"] = evento["lugar"]
    if "descripcion" in evento:
        cuerpo["description"] = evento["descripcion"]
    if evento.get("repeticion"):
        # Lista, porque la API admite varias reglas (RRULE, EXDATE, RDATE).
        cuerpo["recurrence"] = [evento["repeticion"]]
    zona = evento.get("zona") or ""
    if evento.get("todo_el_dia"):
        if evento.get("inicio_local"):
            cuerpo["start"] = {"date": evento["inicio_local"][:10]}
        if evento.get("fin_local"):
            cuerpo["end"] = {"date": evento["fin_local"][:10]}
    else:
        if evento.get("inicio_local"):
            cuerpo["start"] = {"dateTime": evento["inicio_local"]}
            if zona:
                cuerpo["start"]["timeZone"] = zona
        if evento.get("fin_local"):
            cuerpo["end"] = {"dateTime": evento["fin_local"]}
            if zona:
                cuerpo["end"]["timeZone"] = zona
    return cuerpo


def _sin_desplazamiento(rfc3339):
    """`2026-09-17T10:00:00+02:00` → `2026-09-17T10:00:00`, la hora que se lee.

    Es la que escribió quien creó el evento y la que el abogado reconoce en su
    propio calendario. No sirve para comparar dos eventos de zonas distintas:
    para eso está `_a_utc`.
    """
    return rfc3339[:19]


def _a_utc(rfc3339):
    """El instante, en UTC y con `Z`. Cadena vacía si no se puede leer.

    El desplazamiento viaja dentro del propio RFC 3339, así que no hace falta
    ninguna base de datos de zonas horarias: `fromisoformat` da un datetime con
    zona y de ahí sale el instante. Importa porque `zoneinfo` en Windows exige
    el paquete `tzdata`, y el Backend no tiene más dependencia que `sqlcipher3`.
    """
    try:
        momento = datetime.fromisoformat(rfc3339)
    except ValueError:
        return ""
    if momento.tzinfo is None:
        # Sin desplazamiento no hay instante que valga: es una hora local
        # suelta. Se deja vacío en vez de suponer UTC, que daría solapes
        # desplazados dos horas en verano y ninguno los inviernos.
        return ""
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _inicio_del_dia(fecha):
    return f"{fecha}T00:00:00Z"


def _fin_del_dia(fecha):
    return f"{fecha}T23:59:59Z"
