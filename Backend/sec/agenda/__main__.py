"""Línea de órdenes de sec.agenda. Se ejecuta desde la carpeta Backend:

    python -m sec.agenda sincronizar [--desde F] [--hasta F]   trae el calendario de la cuenta
    python -m sec.agenda agenda [--desde F] [--hasta F]        lo que hay, en orden
    python -m sec.agenda colisiones [--desde F] [--hasta F]    lo que se pisa
    python -m sec.agenda apuntar TITULO FECHA [--fin F] [--tipo T] [--dia-completo]
                                [--repetir-cada-anio] [--lugar L]
    python -m sec.agenda clasificar ID --tipo T [--abogado L] [--expediente E]
    python -m sec.agenda plazo ID FECHA ASUNTO [--expediente E] [--organo O]
                                [--estado firme|provisional] [--franja F]
    python -m sec.agenda publicar ID                           lo escribe en el calendario
    python -m sec.agenda acciones [N]                          qué se ha hecho y cuándo

La cuenta es la misma que la del correo y se conecta una sola vez, desde
`sec.mail` o desde Ajustes: el consentimiento trae correo y calendario juntos
(ARQUITECTURA.md §8.6). Si `python -m sec.mail estado` dice «conectado», la
agenda ya puede trabajar.

`plazo` está para lo que todavía no existe: cuando `pro.calendario` tenga motor
de días, será él quien llame a `anotar_plazo`. Mientras tanto se anota a mano,
que es también la forma de comprobar que los avisos de adelanto funcionan.
"""
import argparse
import sys

from ..cuentas import consola
from .agent import SecAgenda
from .db import TIPOS


def main():
    p = argparse.ArgumentParser(prog="python -m sec.agenda", description="Módulo de agenda de MISYKS.")
    sub = p.add_subparsers(dest="orden", required=True)

    def con_ventana(nombre, ayuda):
        s = sub.add_parser(nombre, help=ayuda)
        s.add_argument("--desde", default=None, help="fecha ISO (2026-09-17); por defecto, hace un mes")
        s.add_argument("--hasta", default=None, help="fecha ISO; por defecto, dentro de algo más de un año")
        return s

    con_ventana("sincronizar", "trae los eventos del calendario de la cuenta")
    s = con_ventana("agenda", "muestra lo que hay entre dos fechas")
    s.add_argument("--abogado", default=None)
    s.add_argument("--cancelados", action="store_true", help="incluye lo anulado")
    con_ventana("colisiones", "compromisos que se pisan")

    s = sub.add_parser("apuntar", help="crea un compromiso propio (no viene del calendario)")
    s.add_argument("titulo")
    s.add_argument("inicio", help="2026-11-30 para un día completo, o 2026-11-30T10:00:00")
    s.add_argument("--fin", default=None)
    s.add_argument("--tipo", choices=TIPOS, default="reunion")
    s.add_argument("--dia-completo", dest="dia_completo", action="store_true")
    s.add_argument("--repetir-cada-anio", dest="anual", action="store_true",
                   help="lo convierte en anual al publicarlo (RRULE:FREQ=YEARLY)")
    s.add_argument("--lugar", default=None)
    s.add_argument("--abogado", default=None)

    s = sub.add_parser("clasificar", help="dice qué es un evento traído del calendario")
    s.add_argument("id", type=int)
    s.add_argument("--tipo", choices=TIPOS, default=None)
    s.add_argument("--abogado", default=None)
    s.add_argument("--expediente", default=None)

    s = sub.add_parser("plazo", help="anota un plazo YA CALCULADO por procesal")
    s.add_argument("plazo_id", help="identificador del plazo en procesal")
    s.add_argument("fecha", help="fecha límite, ISO. Calculada fuera: aquí no se computa nada")
    s.add_argument("asunto")
    s.add_argument("--expediente", default=None)
    s.add_argument("--organo", default=None)
    s.add_argument("--estado", choices=("firme", "provisional"), default="firme")
    s.add_argument("--franja", choices=("holgado", "ajustado", "critico", "vencido"), default=None)
    s.add_argument("--abogado", default=None)

    s = sub.add_parser("publicar", help="escribe en el calendario del abogado un evento nacido aquí")
    s.add_argument("id", type=int)

    s = sub.add_parser("acciones", help="registro de lo hecho sobre cada evento")
    s.add_argument("n", nargs="?", type=int, default=20)

    args = p.parse_args()
    consola.tolerante()
    try:
        ejecutar(args)
    except (RuntimeError, LookupError, ValueError) as e:
        # ErrorOAuth, ConsentimientoRevocado, ErrorApi y ErrorCalendario son
        # todos RuntimeError: su mensaje ya dice qué hacer.
        sys.exit(f"Error: {e}")


def ejecutar(args):
    agente = SecAgenda()
    try:
        if args.orden == "sincronizar":
            r = agente.sincronizar(args.desde, args.hasta)
            recorrido = "completo" if r["completo"] else "incremental"
            fuera = f", {r['fuera']} fuera de la ventana" if r.get("fuera") else ""
            print(
                f"{r['nuevos']} nuevos, {r['actualizados']} actualizados, "
                f"{r['cancelados']} cancelados{fuera} (recorrido {recorrido})."
            )
        elif args.orden == "agenda":
            filas = agente.agenda(args.desde, args.hasta, args.abogado, args.cancelados)
            if not filas:
                print("No hay nada anotado en esa ventana.")
            for f in filas:
                print(_linea(f))
        elif args.orden == "colisiones":
            choques = agente.colisiones(args.desde, args.hasta)
            if not choques:
                print("Sin colisiones en esa ventana.")
            for c in choques:
                marca = "MISMO ABOGADO" if c["ambito"] == "mismo_abogado" else "despacho"
                print(
                    f"[{marca}] {c['a_inicio'][:16]}  {c['a_titulo']}  ({c['a_tipo']}, {c['a_abogado']})\n"
                    f"{'':<16}  choca con {c['b_inicio'][:16]}  {c['b_titulo']}  "
                    f"({c['b_tipo']}, {c['b_abogado']})"
                )
        elif args.orden == "apuntar":
            fila_id = agente.apuntar(
                args.titulo,
                args.inicio,
                fin=args.fin,
                tipo=args.tipo,
                todo_el_dia=args.dia_completo or len(args.inicio) <= 10,
                lugar=args.lugar,
                repeticion="RRULE:FREQ=YEARLY" if args.anual else None,
                abogado=args.abogado,
            )
            print(f"Apuntado con id {fila_id}. Para que salga en el calendario: publicar {fila_id}.")
        elif args.orden == "clasificar":
            agente.clasificar(args.id, args.tipo, args.abogado, args.expediente)
            print(f"Evento {args.id} clasificado.")
        elif args.orden == "plazo":
            que_paso, anterior = agente.anotar_plazo(
                args.plazo_id,
                args.fecha,
                args.asunto,
                expediente=args.expediente,
                organo=args.organo,
                estado=args.estado,
                franja=args.franja,
                abogado=args.abogado,
            )
            if que_paso == "adelantado":
                print(f"AVISO: el plazo {args.plazo_id} se ADELANTA de {anterior} a {args.fecha}.")
            elif que_paso == "retrasado":
                print(f"El plazo {args.plazo_id} se retrasa de {anterior} a {args.fecha}.")
            elif que_paso == "igual":
                print(f"El plazo {args.plazo_id} sigue en {args.fecha}.")
            else:
                print(f"Plazo {args.plazo_id} anotado para el {args.fecha} ({args.estado}).")
        elif args.orden == "publicar":
            identificador = agente.publicar(args.id)
            print(f"Evento {args.id} publicado en el calendario ({identificador}).")
        elif args.orden == "acciones":
            for a in agente.acciones(args.n):
                print(f"{a['fecha'][:16]}  {a['accion']:<18}  {a['titulo']}  {a['detalle'] or ''}")
    finally:
        agente.cerrar()


def _linea(f):
    cuando = f["inicio_local"][:10] if f["todo_el_dia"] else f["inicio_local"][:16].replace("T", " ")
    estado = ""
    if f["cancelado"]:
        estado = "  [ANULADO]"
    elif f["estado"] == "provisional":
        estado = "  [provisional]"
    return (
        f"{f['id']:>4}  {cuando:<16}  {f['tipo']:<14}  {(f['titulo'] or '(sin título)')[:48]:<48}"
        f"  {f['lugar'] or ''}{estado}"
    )


if __name__ == "__main__":
    main()
