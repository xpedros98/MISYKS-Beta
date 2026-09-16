"""Adaptador de Microsoft Graph. Autenticación por OAuth (ver oauth.py).

Cubre @outlook.com, @hotmail.com y cualquier dominio de Microsoft 365
(ARQUITECTURA.md 8.6). Graph es el único camino posible: la autenticación
básica de IMAP está eliminada en Exchange Online desde el 1 de octubre de
2022, y Exchange Web Services se bloquea desde el 1 de octubre de 2026.

**Escrito contra la interfaz, sin probar todavía.** El registro de la
aplicación en Entra está pendiente, así que esto no se ha ejecutado nunca
contra una cuenta real; lo probado de extremo a extremo es el camino de
Google. Lo que más papeletas tiene de necesitar ajuste es la paginación del
delta y el `@removed`.

Tres diferencias con Gmail que no son de estilo:

- **El identificador cambia al mover.** `POST /move` devuelve un mensaje
  nuevo, con `id` nuevo; el anterior deja de existir. De ahí que `mover`
  devuelva el identificador resultante -- en Gmail devuelve el mismo.
- **Las carpetas son carpetas.** Un mensaje está en una sola, no en varias
  como con las etiquetas de Gmail. `etiquetas` se rellena con las categorías,
  que es lo más parecido que hay.
- **El delta no es un número sino una URL.** El cursor que se guarda es el
  `@odata.deltaLink` entero, y se pide tal cual la vez siguiente.
"""
from . import correo, oauth

API = "https://graph.microsoft.com/v1.0/me"

# Nombres bien conocidos de Graph (no dependen del idioma de la cuenta),
# traducidos a las marcas de IMAP que usa el resto del sistema.
MARCAS = {
    "inbox": "\\Inbox",
    "sentitems": "\\Sent",
    "drafts": "\\Drafts",
    "deleteditems": "\\Trash",
    "junkemail": "\\Junk",
    "archive": "\\Archive",
}


class Graph(correo.Correo):
    proveedor = "microsoft"

    def __init__(self, sesion=None):
        self.sesion = sesion or oauth.Sesion("microsoft")
        self.cuenta = self.sesion.cuenta
        self._carpetas = None  # {nombre visible: id}

    def carpetas(self):
        return [
            {"nombre": c["displayName"], "marcas": _marcas(c)}
            for c in self._todas_las_carpetas()
        ]

    def listar_nuevos(self, carpeta, cursor):
        """Delta query sobre la carpeta.

        Sin cursor, la primera llamada recorre la carpeta entera paginando por
        `@odata.nextLink` y termina entregando un `@odata.deltaLink`; con
        cursor, se pide ese deltaLink y solo llegan los cambios.
        """
        if cursor:
            url, params = cursor, None
        else:
            url = f"{API}/mailFolders/{self._id_carpeta(carpeta)}/messages/delta"
            params = {"$select": "id,isRead", "$top": 100}

        ids, delta = [], cursor
        while url:
            try:
                respuesta = self.sesion.pedir(url, params=params)
            except oauth.ErrorApi as e:
                # 410 Gone: el token de delta ha caducado. Igual que un
                # UIDVALIDITY cambiado en IMAP: se recorre la carpeta entera
                # en vez de fallar y dejar de ver correos.
                if e.codigo == 410 and cursor:
                    return self.listar_nuevos(carpeta, None)
                raise
            params = None  # solo en la primera página; las siguientes ya la llevan
            for m in respuesta.get("value", []):
                # Un mensaje borrado o movido fuera llega como @removed: no es
                # un correo nuevo que descargar.
                if "@removed" not in m and m.get("id"):
                    ids.append(m["id"])
            url = respuesta.get("@odata.nextLink")
            delta = respuesta.get("@odata.deltaLink") or delta
        return ids, delta

    def descargar(self, mensaje_id):
        try:
            eml = self.sesion.pedir(f"{API}/messages/{mensaje_id}/$value", crudo=True)
            meta = self.sesion.pedir(
                f"{API}/messages/{mensaje_id}", params={"$select": "isRead,categories"}
            )
        except oauth.ErrorApi as e:
            if e.codigo == 404:  # borrado entre el listado y la descarga
                return None
            raise
        return {
            "mensaje_id": mensaje_id,
            "leido": bool(meta.get("isRead")),
            "etiquetas": meta.get("categories", []),
            "eml": eml,
        }

    def marcar_leido(self, mensaje_id):
        self.sesion.pedir(f"{API}/messages/{mensaje_id}", metodo="PATCH", cuerpo={"isRead": True})

    def mover(self, mensaje_id, destino, origen=None):
        respuesta = self.sesion.pedir(
            f"{API}/messages/{mensaje_id}/move",
            metodo="POST",
            cuerpo={"destinationId": self._id_carpeta(destino)},
        )
        # El identificador nuevo es obligatorio en la respuesta; si faltara,
        # quedarse con el viejo dejaría una fila apuntando a nada.
        return respuesta.get("id") or mensaje_id

    def _todas_las_carpetas(self):
        carpetas, url, params = [], f"{API}/mailFolders", {"$top": 100}
        while url:
            respuesta = self.sesion.pedir(url, params=params)
            params = None
            carpetas += respuesta.get("value", [])
            url = respuesta.get("@odata.nextLink")
        return carpetas

    def _mapa(self):
        if self._carpetas is None:
            self._carpetas = {c["displayName"]: c["id"] for c in self._todas_las_carpetas()}
        return self._carpetas

    def _id_carpeta(self, nombre):
        """Acepta el nombre visible, el bien conocido ('inbox') o la marca ('\\Inbox')."""
        mapa = self._mapa()
        if nombre in mapa:
            return mapa[nombre]
        if nombre.lower() in MARCAS:
            return nombre.lower()
        for conocido, marca in MARCAS.items():
            if marca.lower() == nombre.lower():
                return conocido
        raise correo.ErrorCorreo(
            f"No existe la carpeta '{nombre}' en la cuenta {self.cuenta}. "
            f"Las que hay: {', '.join(sorted(mapa))}"
        )


def _marcas(carpeta):
    """Graph no dice cuál es la bandeja de entrada en la lista de carpetas.

    El nombre bien conocido no viene como campo, así que se deduce del nombre
    visible en inglés cuando coincide. Es aproximado a propósito: quien
    necesita una carpeta concreta la pide por su nombre bien conocido, que
    `_id_carpeta` sí resuelve siempre.
    """
    clave = carpeta.get("displayName", "").lower().replace(" ", "")
    return [MARCAS[clave]] if clave in MARCAS else []
