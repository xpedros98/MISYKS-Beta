"""La interfaz `Correo`: lo único que `sec.mail` sabe de un buzón.

ARQUITECTURA.md 8.6: «`sec.mail` y `sec.agenda` no conocen el proveedor de
origen». El agente habla con esta interfaz y un adaptador por mundo la
implementa -- `google.Gmail` sobre la Gmail API, `microsoft.Graph` sobre
Microsoft Graph, y en su día uno sobre IMAP para iCloud, Fastmail y servidores
propios.

Tres cosas que los adaptadores resuelven de forma distinta y que conviene
tener presentes al leer sus implementaciones, porque cuando fallan no dan un
error sino correos que faltan:

- **Identidad estable del mensaje.** En Gmail el `id` del mensaje no cambia
  nunca, tampoco al moverlo de etiqueta. En Graph **sí cambia al mover**: la
  operación devuelve un mensaje nuevo con identificador nuevo. Por eso `mover`
  devuelve el identificador resultante y el agente lo guarda.
- **Sincronización incremental.** Cada proveedor trae el suyo: `historyId` en
  Google, `deltaLink` en Graph, `UIDVALIDITY` + UID en IMAP. Aquí se trata
  como un `cursor` opaco: el agente lo guarda y lo devuelve sin mirarlo.
- **Carpeta.** En Gmail son etiquetas y un mensaje puede tener varias; en
  Graph son carpetas de verdad y un mensaje está en una. Los dos aceptan el
  nombre visible y lo traducen a su identificador interno.
"""
from abc import ABC, abstractmethod

from . import config


class ErrorCorreo(RuntimeError):
    """Fallo hablando con el buzón que no es de autenticación."""


class Correo(ABC):
    """Un buzón ya autenticado. `proveedor` y `cuenta` identifican de quién es."""

    proveedor = ""
    cuenta = ""

    @abstractmethod
    def carpetas(self):
        """Lista de {"nombre", "marcas"}.

        Las marcas son las del proveedor normalizadas a las de IMAP
        (`\\Inbox`, `\\Sent`, `\\Trash`...), que no dependen del idioma de la
        cuenta: el nombre visible de la bandeja de entrada de una cuenta en
        español no es el de una en inglés, pero la marca sí.
        """

    @abstractmethod
    def listar_nuevos(self, carpeta, cursor):
        """(identificadores por orden de llegada, cursor nuevo).

        Con `cursor` a None hace inventario completo de la carpeta; con un
        cursor válido pide solo lo llegado desde entonces. Si el proveedor
        rechaza el cursor por antiguo, vuelve al inventario completo en vez de
        fallar: repetir identificadores no duplica nada (la base los ignora),
        perderlos sí sería un correo que el despacho no ve.

        No descarga nada: devolver solo identificadores es lo que permite
        encolarlos y bajarlos en tandas.
        """

    @abstractmethod
    def descargar(self, mensaje_id):
        """{"mensaje_id", "leido", "etiquetas", "eml"} o None si ya no existe.

        `eml` es el mensaje original completo en MIME, que es lo que guarda la
        base y lo que lee `parser.py`: el mismo formato en los tres mundos.
        Descargar no marca como leído -- el letrado sigue viendo su bandeja
        intacta desde sus propios dispositivos.
        """

    @abstractmethod
    def marcar_leido(self, mensaje_id):
        """Marca el mensaje como leído en el servidor."""

    @abstractmethod
    def mover(self, mensaje_id, destino, origen=None):
        """Mueve el mensaje. Devuelve su identificador después del movimiento.

        Puede ser el mismo (Gmail) u otro distinto (Graph). `origen` hace falta
        en Gmail, donde mover es quitar una etiqueta y poner otra.
        """


def abrir(proveedor=None):
    """El buzón configurado. Falla con un mensaje útil si no hay ninguno."""
    proveedor = proveedor or config.proveedor_activo()
    if proveedor == "google":
        from .google import Gmail

        return Gmail()
    if proveedor == "microsoft":
        from .microsoft import Graph

        return Graph()
    raise ErrorCorreo(
        f"Proveedor de correo desconocido: {proveedor}. Los implementados: google, microsoft."
    )
