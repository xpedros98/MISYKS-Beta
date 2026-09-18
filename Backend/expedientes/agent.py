"""La interfaz de expedientes para el resto de MISYKS.

Fina a propósito: hoy un expediente es una ficha con su tipo. Lo que le falta
—los hitos, la ruta, los documentos que cuelgan de él— se añade aquí cuando
exista, y entonces esta clase será lo que consulten `sec.agenda` para proyectar
la barra de nodos y `procesal` para saber qué plazos tocan.
"""
from . import catalogo, db


class Expedientes:
    def __init__(self, base=None):
        self.db = base or db.abrir_base()

    def cerrar(self):
        self.db.cerrar()

    def tipos(self):
        """Los 89 tipos documentales del catálogo."""
        return catalogo.tipos()

    def abrir(self, tipo, **datos):
        """Abre un expediente de un tipo. Devuelve su ficha, con la referencia."""
        return self.db.abrir_expediente(tipo, **datos)

    def hitos(self, expediente_id):
        """Por dónde pasa este expediente: la barra de nodos, en datos."""
        if self.db.expediente(expediente_id) is None:
            raise LookupError(f"No hay ningún expediente con id {expediente_id}.")
        return self.db.hitos(expediente_id)

    def fechar(self, expediente_id, orden, fecha, clase_fecha="real", ocurrido=False):
        """Pone fecha a un hito. Hoy lo hace una persona; mañana, `procesal`.

        Las fechas `limite` las tendrá que producir `pro.calendario` cuando
        exista el motor de días: aquí no se computa nada, igual que en
        `sec.agenda`.
        """
        if clase_fecha not in ("real", "limite", "provisional", "sin_senalar"):
            raise ValueError(
                f"Clase de fecha desconocida: {clase_fecha}. "
                "Las que hay: real, limite, provisional, sin_senalar."
            )
        self.db.fechar_hito(expediente_id, orden, fecha, clase_fecha, ocurrido)

    def listar(self, estado="abierto"):
        return self.db.listar(estado)

    def cerrar_expediente(self, expediente_id):
        if self.db.expediente(expediente_id) is None:
            raise LookupError(f"No hay ningún expediente con id {expediente_id}.")
        self.db.cerrar_expediente(expediente_id)

    def eliminar(self, expediente_id):
        if self.db.eliminar(expediente_id) == 0:
            raise LookupError(f"No hay ningún expediente con id {expediente_id}.")

    def vaciar(self):
        """Borra todos. Quien llama ya ha confirmado; aquí no se pregunta."""
        return self.db.vaciar()
