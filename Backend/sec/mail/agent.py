"""SecMail: la interfaz del sub-agente de correo para el resto de MISYKS."""
import json

from . import correo as correo_api
from . import db, parser


class SecMail:
    def __init__(self, base=None, buzon=None):
        self.db = base or db.abrir()
        self._buzon = buzon  # se abre al primer uso: `listar` no necesita red

    def cerrar(self):
        self.db.cerrar()

    @property
    def buzon(self):
        """El buzón OAuth de la cuenta conectada (Gmail API o Microsoft Graph)."""
        if self._buzon is None:
            self._buzon = correo_api.abrir()
        return self._buzon

    def carpetas(self):
        return self.buzon.carpetas()

    def sincronizar(self, carpeta="INBOX", limite=None):
        """Guarda los correos nuevos de una carpeta sin marcarlos como leídos.

        Dos pasos con propósitos distintos, y conviene no confundirlos:

        1. **Preguntar** al servidor qué hay de nuevo. Las dos APIs contestan
           con un cursor -- `historyId` en Google, `deltaLink` en Graph -- que
           avanza de golpe al final de la respuesta, no mensaje a mensaje como
           hacía el UID de IMAP. Lo anunciado se apunta en la cola de
           pendientes *antes* de guardar el cursor: si se guardara primero y
           el proceso muriera, esos correos no los volvería a anunciar nadie.
        2. **Traer** de la cola. `limite` corta la tanda a los N más antiguos
           pendientes; el resto sigue en la cola para la siguiente llamada.

        Que el cursor avance de golpe es el cambio real respecto a IMAP: lo
        que garantiza no perder ni duplicar ya no es el puntero, sino la cola
        (cada correo sale de ella solo cuando está guardado) más el índice
        único de `correos`, que ignora un mensaje ya descargado.

        Devuelve cuántos correos se guardaron por primera vez.
        """
        buzon = self.buzon
        cursor = self.db.cursor_sincronizacion(buzon.proveedor, carpeta)
        anunciados, cursor_nuevo = buzon.listar_nuevos(carpeta, cursor)
        self.db.encolar(buzon.proveedor, carpeta, anunciados)
        self.db.guardar_cursor(buzon.proveedor, carpeta, cursor_nuevo)

        nuevos = 0
        for mensaje_id in self.db.pendientes(buzon.proveedor, carpeta, limite):
            descarga = buzon.descargar(mensaje_id)
            if descarga is not None:
                correo = parser.parsear(descarga["eml"])
                correo.update(
                    proveedor=buzon.proveedor,
                    cuenta=buzon.cuenta,
                    mensaje_id=descarga["mensaje_id"],
                    carpeta=carpeta,
                    etiquetas=json.dumps(descarga["etiquetas"], ensure_ascii=False),
                    leido=int(descarga["leido"]),
                    eml=descarga["eml"],
                )
                if self.db.guardar_correo(correo) is not None:
                    nuevos += 1
            # Sale de la cola tanto si se guardó como si ya no existía en el
            # servidor; en los dos casos no hay nada más que hacer con él. Se
            # borra uno a uno: si esto se corta, la siguiente vez sigue aquí.
            self.db.desencolar(buzon.proveedor, carpeta, mensaje_id)
        return nuevos

    def pendientes(self, carpeta="INBOX"):
        """Cuántos correos hay anunciados y todavía sin descargar."""
        return self.db.cuantos_pendientes(self.buzon.proveedor, carpeta)

    def listar(self, limite=20):
        return self.db.listar(limite)

    def marcar_leido(self, correo_id):
        fila = self._fila(correo_id)
        self.buzon.marcar_leido(fila["mensaje_id"])
        self.db.marcar_leido(correo_id)

    def mover(self, correo_id, destino):
        fila = self._fila(correo_id)
        # En Graph el identificador cambia al mover; en Gmail no. El adaptador
        # devuelve el que vale a partir de ahora y la base se queda con ese.
        mensaje_id = self.buzon.mover(fila["mensaje_id"], destino, origen=fila["carpeta"])
        self.db.mover(
            correo_id,
            fila["carpeta"],
            destino,
            mensaje_id=mensaje_id if mensaje_id != fila["mensaje_id"] else None,
        )

    def _fila(self, correo_id):
        fila = self.db.correo(correo_id)
        if fila is None:
            raise LookupError(f"No hay ningún correo con id {correo_id} en la base.")
        return fila
