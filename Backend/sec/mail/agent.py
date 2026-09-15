"""SecMail: la interfaz del sub-agente de correo para el resto de MISYKS."""
import json

from . import config, db, parser
from .imap import Gmail


class SecMail:
    def __init__(self, base=None):
        self.db = base or db.abrir()

    def cerrar(self):
        self.db.cerrar()

    def carpetas(self):
        with self._gmail() as gmail:
            return gmail.carpetas()

    def sincronizar(self, carpeta="INBOX"):
        """Guarda los correos nuevos de una carpeta sin marcarlos como leídos.

        Devuelve cuántos correos se guardaron por primera vez.
        """
        nuevos = 0
        with self._gmail() as gmail:
            uidvalidity = gmail.seleccionar(carpeta, solo_lectura=True)
            validez_guardada, ultimo_uid = self.db.estado(carpeta)
            if validez_guardada != uidvalidity:  # UIDs reiniciados en el servidor: se recorre entera
                ultimo_uid = 0
            for uid in gmail.uids_desde(ultimo_uid):
                descarga = gmail.descargar(uid)
                if descarga is not None:
                    correo = parser.parsear(descarga["eml"])
                    correo.update(
                        gmail_msgid=descarga["gmail_msgid"],
                        carpeta=carpeta,
                        etiquetas=json.dumps(descarga["etiquetas"], ensure_ascii=False),
                        leido=int(descarga["leido"]),
                        eml=descarga["eml"],
                    )
                    if self.db.guardar_correo(correo) is not None:
                        nuevos += 1
                # Se avanza correo a correo: si se corta, la siguiente vez sigue desde aquí.
                self.db.avanzar(carpeta, uidvalidity, uid)
        return nuevos

    def listar(self, limite=20):
        return self.db.listar(limite)

    def marcar_leido(self, correo_id):
        fila = self._fila(correo_id)
        with self._gmail() as gmail:
            gmail.seleccionar(fila["carpeta"], solo_lectura=False)
            gmail.marcar_leido(_uid_actual(gmail, fila))
        self.db.marcar_leido(correo_id)

    def mover(self, correo_id, destino):
        fila = self._fila(correo_id)
        with self._gmail() as gmail:
            gmail.seleccionar(fila["carpeta"], solo_lectura=False)
            gmail.mover(_uid_actual(gmail, fila), destino)
        self.db.mover(correo_id, fila["carpeta"], destino)

    def _gmail(self):
        return Gmail(*config.credenciales_gmail())

    def _fila(self, correo_id):
        fila = self.db.correo(correo_id)
        if fila is None:
            raise LookupError(f"No hay ningún correo con id {correo_id} en la base.")
        return fila


def _uid_actual(gmail, fila):
    # Los UIDs cambian al mover correos; X-GM-MSGID no.
    uid = gmail.buscar_msgid(fila["gmail_msgid"])
    if uid is None:
        raise LookupError(f"El correo {fila['id']} ya no está en la carpeta {fila['carpeta']} de Gmail.")
    return uid
