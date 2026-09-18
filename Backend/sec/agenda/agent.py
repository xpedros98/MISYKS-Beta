"""SecAgenda: la interfaz del módulo de agenda para el resto de MISYKS.

Contrato (COMPONENTES.md): `{eventos[], plazos_de_procesal[]}` →
`{agenda, conflictos[]}`.

La regla que manda sobre todas las demás está en la primera línea de su ficha:
**no calcula plazos, los recibe.** `procesal` computa y `sec.agenda` anota. En
este archivo no hay ni una suma de días, y no es un descuido: duplicar el
cálculo aquí garantiza que las dos versiones acaben divergiendo, y entonces hay
dos fechas y ninguna forma de saber cuál vale.
"""
from datetime import date, datetime, timedelta, timezone

from . import calendario as calendario_api
from . import config, db


class SecAgenda:
    def __init__(self, base=None, calendario=None):
        self.db = base or db.abrir()
        # Se abre al primer uso: `agenda` y `colisiones` no necesitan red, y
        # exigir conexión para mirar lo ya guardado sería una avería nueva.
        self._calendario = calendario

    def cerrar(self):
        self.db.cerrar()

    @property
    def calendario(self):
        """El calendario de la cuenta conectada (hoy, Google Calendar)."""
        if self._calendario is None:
            self._calendario = calendario_api.abrir()
        return self._calendario

    # --- entrada: el calendario del abogado -------------------------------

    def sincronizar(self, desde=None, hasta=None):
        """Trae los eventos del calendario de la cuenta y los guarda.

        Dos caminos, y la diferencia entre ellos es lo único delicado de aquí:

        - **Incremental**, con cursor: el proveedor manda solo lo que ha
          cambiado. Lo que no viene es que sigue igual.
        - **Completo**, sin cursor o con uno que el proveedor ha rechazado por
          antiguo: viene la ventana entera. Solo entonces se puede concluir que
          lo que no ha venido **ya no existe**, y cancelarlo.

        Confundir los dos casos vacía la agenda de golpe, y sin dar ningún
        error: simplemente, un día no hay señalamientos.

        Devuelve un resumen: `{nuevos, actualizados, cancelados, completo}`.
        """
        desde, hasta = self._ventana(desde, hasta)
        calendario = self.calendario
        cursor = self.db.cursor_sincronizacion(calendario.proveedor, calendario.cuenta, desde, hasta)
        eventos, cursor_nuevo, completo = calendario.listar_eventos(desde, hasta, cursor)

        resumen = {"nuevos": 0, "actualizados": 0, "cancelados": 0, "fuera": 0,
                   "completo": completo}
        vistos = set()
        for evento in eventos:
            # En el recorrido incremental, Google **no** respeta la ventana: una
            # serie anual sin fecha de fin llega expandida hasta 2099. Medido con
            # dos eventos anuales recién creados: 147 ocurrencias en una sola
            # sincronización. Lo de fuera se descarta aquí, salvo que ya esté
            # guardado -- si un evento nuestro se ha movido fuera de la ventana,
            # hay que enterarse, y descartarlo dejaría la fila vieja mintiendo.
            if not self._interesa(evento, desde, hasta, calendario.proveedor):
                resumen["fuera"] += 1
                continue
            vistos.add(evento["evento_id"])
            evento = dict(evento)
            evento.update(
                proveedor=calendario.proveedor,
                cuenta=calendario.cuenta,
                origen="calendario",
                # Del calendario no viene qué es cada cosa: un evento llamado
                # «Juicio Pérez» es una vista y «Café con Marta» no, y la API
                # no distingue. Entra sin clasificar y lo fija `clasificar`.
                tipo="sin_clasificar",
                # La cuenta es, hoy, el abogado: una máquina, una agenda. Con
                # varios abogados esto saldrá de la ficha de cada uno.
                abogado=calendario.cuenta,
            )
            que_paso, _ = self.db.guardar_evento(evento)
            if que_paso == "nuevo":
                resumen["nuevos"] += 1
            elif que_paso == "actualizado":
                resumen["actualizados"] += 1

        if completo:
            desaparecidos = self.db.marcar_ausentes_como_cancelados(
                calendario.proveedor, calendario.cuenta, desde, hasta, vistos
            )
            resumen["cancelados"] = len(desaparecidos)

        # El cursor se guarda al final, cuando ya está todo escrito. Al revés
        # que en `sec.mail` no hace falta cola: aquí listar ya trae el evento
        # entero, así que no existe el hueco entre anunciar y traer.
        if cursor_nuevo:
            self.db.guardar_cursor(calendario.proveedor, calendario.cuenta, cursor_nuevo, desde, hasta)
        return resumen

    # --- entrada: los plazos que entrega procesal --------------------------

    def anotar_plazo(self, plazo_id, fecha_limite, asunto, **datos):
        """Recibe un plazo ya calculado por `procesal` y lo pone en la agenda.

        Devuelve (`qué pasó`, `fecha anterior`): 'nuevo', 'adelantado',
        'retrasado' o 'igual'. Quien llama necesita esa distinción porque un
        plazo **adelantado** exige aviso inmediato -- enterarse tarde puede
        costar el plazo -- y uno retrasado no interrumpe a nadie.

        `fecha_limite` llega calculada. Aquí no se toca.
        """
        return self.db.anotar_plazo(plazo_id, fecha_limite, asunto, **datos)

    def apuntar(self, titulo, inicio, fin=None, tipo="reunion", todo_el_dia=False,
                lugar=None, descripcion=None, zona=None, repeticion=None, abogado=None,
                expediente=None):
        """Crea un compromiso propio, que no vino del calendario ni de procesal.

        Una reunión que alguien acuerda por teléfono, un cumpleaños, una
        obligación viva de un contrato ya cerrado (el arquetipo G). Se guarda
        **solo aquí**: para que aparezca en el calendario del abogado hay que
        `publicar`, y eso es otra decisión y otro momento.

        `repeticion` es una RRULE (`RRULE:FREQ=YEARLY`) y solo viaja al
        publicar. La agenda no la expande: cuando el evento esté en el
        proveedor, será él quien devuelva cada ocurrencia por separado.

        Devuelve el id de la fila.
        """
        if todo_el_dia:
            # Google da el final de un evento de día completo en exclusiva: uno
            # de un solo día termina «el día siguiente». Se guarda con ese
            # criterio para no tener dos convenios distintos en la misma tabla.
            fin = fin or _dia_siguiente(inicio)
        identidad = f"propio:{_marca_de_tiempo()}"
        _, fila_id = self.db.guardar_evento(
            {
                "proveedor": "",
                "cuenta": "",
                "evento_id": identidad,
                "tipo": tipo,
                "origen": "manual",
                "abogado": abogado,
                "titulo": titulo,
                "lugar": lugar,
                "descripcion": descripcion,
                "inicio_local": inicio,
                "fin_local": fin or inicio,
                "zona": zona,
                "todo_el_dia": todo_el_dia,
                "repeticion": repeticion,
                "expediente": expediente,
            }
        )
        self.db.registrar(fila_id, "apuntado", titulo)
        return fila_id

    def hecho(self, plazo_id, fecha_presentacion=None):
        """El «Hecho» del abogado: presentó por su cuenta, fuera de MISYKS.

        No verifica nada ni comprueba nada: **informa de algo que el sistema no
        puede ver**. Queda como cumplido *declarado*, no acreditado —no hay
        justificante—, y `pro.acuse` necesita esa distinción para que la
        auditoría separe lo que consta de lo que se ha dicho.

        Sin esto, los avisos de un plazo ya presentado seguirían sonando, que es
        la forma más rápida de que alguien deje de leerlos.
        """
        return self.db.cerrar_plazo(plazo_id, "abogado", fecha_presentacion)

    def acusar(self, plazo_id, fecha_presentacion=None, justificante=None):
        """Cierra el plazo con justificante. Lo llamará `pro.acuse`."""
        return self.db.cerrar_plazo(plazo_id, "acuse", fecha_presentacion, justificante)

    def deshacer(self, plazo_id):
        """Devuelve a abierto un plazo cerrado por error."""
        return self.db.deshacer_cierre(plazo_id)

    def pausar(self, plazo_id, motivo):
        """Suspende el plazo por un hecho registrado (conciliación previa, etc.)."""
        return self.db.pausar_plazo(plazo_id, motivo)

    def reanudar(self, plazo_id, fecha_limite=None):
        """Reanuda el plazo con la fecha que trae quien reanuda, ya recalculada."""
        return self.db.reanudar_plazo(plazo_id, fecha_limite)

    def cancelar(self, plazo_id, motivo):
        """Cancela el plazo por un motivo registrado. Nunca se borra."""
        return self.db.cancelar_plazo(plazo_id, motivo)

    def clasificar(self, evento_id, tipo=None, abogado=None, expediente=None):
        """Dice qué es un evento del calendario: reunión, vista, obligación."""
        if self.db.evento(evento_id) is None:
            raise LookupError(f"No hay ningún evento con id {evento_id} en la agenda.")
        self.db.clasificar(evento_id, tipo=tipo, abogado=abogado, expediente=expediente)
        self.db.registrar(evento_id, "clasificado", tipo or abogado or expediente)

    # --- salida ------------------------------------------------------------

    def agenda(self, desde=None, hasta=None, abogado=None, incluir_cancelados=False):
        """Lo que hay entre dos fechas: reuniones, vistas, plazos y obligaciones."""
        desde, hasta = self._ventana(desde, hasta)
        return self.db.agenda(desde, hasta, abogado=abogado, incluir_cancelados=incluir_cancelados)

    def colisiones(self, desde=None, hasta=None):
        """Compromisos que se pisan. Es la mitad del valor de tener agenda.

        Dos señalamientos del mismo abogado a la misma hora son la causa de
        suspensión más frecuente, y se ven con semanas de antelación si alguien
        mira. Mirar es esto.
        """
        desde, hasta = self._ventana(desde, hasta)
        return self.db.colisiones(desde, hasta)

    def publicar(self, evento_id):
        """Escribe en el calendario del abogado un evento que nació aquí.

        Solo a petición explícita, nunca durante una sincronización: escribir
        en el calendario de alguien es una acción hacia fuera, y una agenda que
        empieza a poner eventos sola por su cuenta deja de ser de fiar. Los
        plazos se publican así, uno a uno, cuando alguien lo pide.
        """
        fila = self.db.evento(evento_id)
        if fila is None:
            raise LookupError(f"No hay ningún evento con id {evento_id} en la agenda.")
        if fila["origen"] == "calendario":
            raise ValueError(
                f"El evento {evento_id} ya vino del calendario del abogado: publicarlo lo duplicaría."
            )
        identificador = self.calendario.crear_evento(dict(fila))
        self.db.registrar(evento_id, "publicado", f"{self.calendario.proveedor}:{identificador}")
        self._publicado(evento_id, self.calendario.proveedor, identificador)
        return identificador

    def acciones(self, limite=50):
        """El registro de lo que la agenda ha hecho sobre cada evento."""
        return self.db.acciones(limite)

    def _interesa(self, evento, desde, hasta, proveedor):
        """Si este evento entra en la agenda o se descarta.

        Un evento sin fecha legible no se puede situar en la ventana: llega así
        alguna baja de una ocurrencia. Se acepta solo si ya lo teníamos, que es
        cuando significa algo.
        """
        dia = (evento.get("inicio_local") or "")[:10]
        if dia and desde <= dia <= hasta:
            return True
        return self.db.evento_por_identidad(proveedor, evento["evento_id"]) is not None

    def _publicado(self, fila_id, proveedor, identificador):
        """Deja constancia de con qué identificador quedó en el proveedor.

        Sin esto, la siguiente sincronización traería el evento recién
        publicado como uno nuevo del calendario y habría dos filas para el
        mismo compromiso: la de aquí y la de allí.
        """
        self.db.conn.execute(
            "UPDATE eventos SET proveedor = ?, evento_id = ?, origen = 'calendario' WHERE id = ?",
            (proveedor, identificador, fila_id),
        )
        self.db.conn.commit()

    def _ventana(self, desde, hasta):
        """La ventana por defecto, cuadrada a meses enteros.

        Cuadrarla es lo que permite que el cursor sobreviva de un día para otro
        (ver `config.MESES_ATRAS`): una ventana que se mueve cada día obliga a
        un recorrido completo cada día.
        """
        hoy = date.today()
        return (
            desde or _primero_de_mes(hoy, -config.MESES_ATRAS).isoformat(),
            hasta or (_primero_de_mes(hoy, config.MESES_ADELANTE + 1) - timedelta(days=1)).isoformat(),
        )


def _primero_de_mes(dia, desplazamiento):
    """El día 1 del mes que está a `desplazamiento` meses de `dia`."""
    mes = dia.month - 1 + desplazamiento
    return date(dia.year + mes // 12, mes % 12 + 1, 1)


def _dia_siguiente(fecha):
    return (date.fromisoformat(fecha[:10]) + timedelta(days=1)).isoformat()


def _marca_de_tiempo():
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
