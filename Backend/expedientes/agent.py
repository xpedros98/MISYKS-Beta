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

    def hecho(self, expediente_id, orden, fecha=None, por="abogado", documento_id=None):
        """El abogado marca un nodo como realizado, lo hiciera donde lo hiciera.

        Es el caso normal: presentó por su cuenta, fuera de MISYKS, y el sistema
        no tiene forma de verlo. No verifica nada; **informa**. Queda como
        realizado *declarado* -- lo dice quien lo hizo -- frente al *acreditado*,
        que llegará con el justificante de `pro.acuse`, y esa diferencia es lo
        que permite a la auditoría separar lo que consta de lo que se ha dicho.

        Sin esto la barra no avanzaría nunca salvo que todo el trabajo pasara
        por el sistema, que no es como trabaja un despacho.
        """
        return self.db.marcar_hecho(expediente_id, orden, por, fecha, documento_id)

    def deshacer(self, expediente_id, orden):
        """Devuelve a pendiente un hito marcado por error."""
        return self.db.deshacer_hito(expediente_id, orden)

    def pausar(self, expediente_id, orden, motivo):
        """Suspende un plazo por un hecho registrado (conciliación previa...)."""
        return self.db.pausar_hito(expediente_id, orden, motivo)

    def reanudar(self, expediente_id, orden, fecha=None):
        """Reanuda un plazo pausado con la fecha ya recalculada fuera."""
        return self.db.reanudar_hito(expediente_id, orden, fecha)

    def prorrogar(self, expediente_id, orden, nueva_fecha, resolucion=None):
        """El órgano amplía el plazo. Distinto de pausar y de recalcular.

        La fecha viene en una resolución, no de una regla nuestra, así que
        aquí tampoco se computa nada: se guarda la que llega y se anota de
        dónde sale.
        """
        return self.db.prorrogar_hito(expediente_id, orden, nueva_fecha, resolucion)

    def acciones(self, expediente_id, limite=100):
        """Todo lo que le ha pasado al expediente, para explicar una fecha."""
        if self.db.expediente(expediente_id) is None:
            raise LookupError(f"No hay ningún expediente con id {expediente_id}.")
        return self.db.acciones(expediente_id, limite)

    def cancelar(self, expediente_id, orden, motivo):
        """Cancela el hito por un motivo registrado. Nunca se borra."""
        return self.db.cancelar_hito(expediente_id, orden, motivo)

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
