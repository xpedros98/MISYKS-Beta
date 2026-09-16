"""Adaptador de la Gmail API. Autenticación por OAuth (ver oauth.py).

Sustituye al acceso por IMAP con contraseña de aplicación. Lo que se pierde al
dejar IMAP es poco -- `X-GM-MSGID` era una extensión propia de Gmail y aquí el
`id` del mensaje cumple lo mismo, además de ser el identificador natural de la
API -- y lo que se gana es el `historyId`, una sincronización incremental de
verdad: en vez de preguntar por los UID posteriores al último visto, el
servidor dice qué ha cambiado desde la última vez.

El `id` de la Gmail API y el `X-GM-MSGID` de IMAP son el mismo número, uno en
hexadecimal y el otro en decimal. De ahí que la migración de la base
(`db.py`) pueda convertir los correos ya guardados sin volver a descargarlos.
"""
import base64

from . import correo, oauth

API = "https://gmail.googleapis.com/gmail/v1/users/me"

# Las etiquetas de sistema de Gmail, traducidas a las marcas de IMAP, que es
# lo que entiende el resto del sistema y no depende del idioma de la cuenta.
MARCAS = {
    "INBOX": "\\Inbox",
    "SENT": "\\Sent",
    "DRAFT": "\\Drafts",
    "TRASH": "\\Trash",
    "SPAM": "\\Junk",
    "STARRED": "\\Flagged",
    "IMPORTANT": "\\Important",
}


class Gmail(correo.Correo):
    proveedor = "google"

    def __init__(self, sesion=None):
        self.sesion = sesion or oauth.Sesion("google")
        self.cuenta = self.sesion.cuenta
        self._etiquetas = None  # {nombre visible: id}, se pide una vez por proceso

    def carpetas(self):
        return [
            {"nombre": e["name"], "marcas": [MARCAS[e["id"]]] if e["id"] in MARCAS else []}
            for e in self._todas_las_etiquetas()
        ]

    def listar_nuevos(self, carpeta, cursor):
        etiqueta = self._id_etiqueta(carpeta)
        if cursor:
            try:
                return self._incremental(etiqueta, cursor)
            except oauth.ErrorApi as e:
                # 404: el historial pedido ya no está en el servidor (Gmail
                # guarda una semana larga, no siempre). Es lo mismo que un
                # UIDVALIDITY cambiado en IMAP: se recorre la carpeta entera.
                if e.codigo != 404:
                    raise
        return self._inventario(etiqueta)

    def _inventario(self, etiqueta):
        """Todos los mensajes de la etiqueta, del más antiguo al más reciente.

        El `historyId` se pide **antes** de listar, no después: si se pidiera
        al final, los mensajes llegados durante el recorrido quedarían por
        debajo del cursor y no los vería nadie nunca. Pedirlo antes puede hacer
        que alguno se repita, y repetir es inofensivo.
        """
        historia = self.sesion.pedir(f"{API}/profile")["historyId"]
        ids, pagina = [], None
        while True:
            params = {"labelIds": etiqueta, "maxResults": 500, "includeSpamTrash": "true"}
            if pagina:
                params["pageToken"] = pagina
            respuesta = self.sesion.pedir(f"{API}/messages", params=params)
            ids += [m["id"] for m in respuesta.get("messages", [])]
            pagina = respuesta.get("nextPageToken")
            if not pagina:
                break
        # La API los da del más reciente al más antiguo; el agente los procesa
        # en orden de llegada para que una tanda cortada siga por donde iba.
        return list(reversed(ids)), historia

    def _incremental(self, etiqueta, cursor):
        ids, pagina, ultimo = [], None, cursor
        while True:
            params = {"startHistoryId": cursor, "labelId": etiqueta, "historyTypes": "messageAdded"}
            if pagina:
                params["pageToken"] = pagina
            respuesta = self.sesion.pedir(f"{API}/history", params=params)
            for entrada in respuesta.get("history", []):
                ids += [m["message"]["id"] for m in entrada.get("messagesAdded", [])]
            ultimo = respuesta.get("historyId", ultimo)
            pagina = respuesta.get("nextPageToken")
            if not pagina:
                break
        return ids, ultimo

    def descargar(self, mensaje_id):
        try:
            mensaje = self.sesion.pedir(f"{API}/messages/{mensaje_id}", params={"format": "raw"})
        except oauth.ErrorApi as e:
            if e.codigo == 404:  # borrado entre el listado y la descarga
                return None
            raise
        etiquetas = mensaje.get("labelIds", [])
        return {
            "mensaje_id": mensaje["id"],
            "leido": "UNREAD" not in etiquetas,
            "etiquetas": [self._nombre_etiqueta(e) for e in etiquetas],
            # `raw` viene en base64url; el resto del sistema trabaja con el
            # MIME original, igual que cuando lo traía IMAP.
            "eml": base64.urlsafe_b64decode(mensaje["raw"] + "=" * (-len(mensaje["raw"]) % 4)),
        }

    def marcar_leido(self, mensaje_id):
        self.sesion.pedir(
            f"{API}/messages/{mensaje_id}/modify", metodo="POST", cuerpo={"removeLabelIds": ["UNREAD"]}
        )

    def mover(self, mensaje_id, destino, origen=None):
        """En Gmail mover es poner una etiqueta y quitar la anterior.

        Sin quitar la de origen el correo quedaría en las dos, que es
        exactamente lo que el letrado no espera de un «mover». El `id` no
        cambia, así que se devuelve el mismo.
        """
        cambio = {"addLabelIds": [self._id_etiqueta(destino)]}
        if origen:
            cambio["removeLabelIds"] = [self._id_etiqueta(origen)]
        self.sesion.pedir(f"{API}/messages/{mensaje_id}/modify", metodo="POST", cuerpo=cambio)
        return mensaje_id

    def _todas_las_etiquetas(self):
        return self.sesion.pedir(f"{API}/labels").get("labels", [])

    def _mapa(self):
        if self._etiquetas is None:
            self._etiquetas = {e["name"]: e["id"] for e in self._todas_las_etiquetas()}
        return self._etiquetas

    def _id_etiqueta(self, nombre):
        """Acepta el nombre visible ('Recibidos'), el interno ('INBOX') o la marca ('\\Inbox')."""
        mapa = self._mapa()
        if nombre in mapa:
            return mapa[nombre]
        if nombre.upper() in MARCAS:
            return nombre.upper()
        for interno, marca in MARCAS.items():
            if marca.lower() == nombre.lower():
                return interno
        raise correo.ErrorCorreo(
            f"No existe la etiqueta '{nombre}' en la cuenta {self.cuenta}. "
            f"Las que hay: {', '.join(sorted(mapa))}"
        )

    def _nombre_etiqueta(self, id_etiqueta):
        for nombre, identificador in self._mapa().items():
            if identificador == id_etiqueta:
                return nombre
        return id_etiqueta
