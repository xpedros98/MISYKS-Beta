"""Línea de órdenes de expedientes. Se ejecuta desde la carpeta Backend:

    python -m expedientes tipos [--arquetipo A]   los 89 tipos documentales
    python -m expedientes abrir TIPO [--titulo T] [--cliente C] [--contrario X] [--organo O]
    python -m expedientes listar [--todos]        los abiertos, o todos
    python -m expedientes hitos ID                por dónde pasa: la barra, en texto
    python -m expedientes fechar ID ORDEN FECHA [--clase real|limite|provisional] [--ocurrido]
    python -m expedientes hecho ID HITO [--fecha F]   el abogado lo hizo por su cuenta
    python -m expedientes deshacer ID HITO           deshace un «hecho» dado sin querer
    python -m expedientes pausar ID HITO MOTIVO      suspende un plazo
    python -m expedientes reanudar ID HITO [FECHA]   lo reanuda con la fecha recalculada
    python -m expedientes prorrogar ID HITO FECHA [--resolucion R]   lo amplía el órgano
    python -m expedientes cancelar ID HITO MOTIVO    lo cancela; nunca se borra
    python -m expedientes acciones ID [N]            por qué las fechas son las que son
    python -m expedientes cerrar ID               lo saca de los abiertos, sin borrarlo
    python -m expedientes eliminar ID --si        lo borra de verdad
    python -m expedientes vaciar --si             los borra todos

`--si` no es una formalidad: borrar no deja rastro, así que la confirmación la
da quien llama. En la app la da una persona pulsando dos veces; aquí, este
parámetro. Sin él, la orden dice qué iba a borrar y no borra nada.
"""
import argparse
import sys

from sec.cuentas import consola

from .agent import Expedientes
from .catalogo import ARQUETIPOS
from .db import vida_efectiva


def main():
    p = argparse.ArgumentParser(prog="python -m expedientes", description="Expedientes de MISYKS.")
    sub = p.add_subparsers(dest="orden", required=True)

    s = sub.add_parser("tipos", help="los 89 tipos documentales del catálogo")
    s.add_argument("--arquetipo", choices=sorted(ARQUETIPOS), default=None)

    s = sub.add_parser("abrir", help="abre un expediente de un tipo")
    s.add_argument("tipo")
    s.add_argument("--titulo", default=None)
    s.add_argument("--cliente", default=None)
    s.add_argument("--contrario", default=None)
    s.add_argument("--organo", default=None)

    s = sub.add_parser("listar", help="los expedientes abiertos")
    s.add_argument("--todos", action="store_true", help="incluye los cerrados")

    s = sub.add_parser("hitos", help="los hitos del expediente, en orden")
    s.add_argument("id", type=int)

    s = sub.add_parser("fechar", help="pone fecha a un hito del expediente")
    s.add_argument("id", type=int)
    # `hito` y no `orden`: el subparser ya guarda el nombre de la orden en
    # `args.orden`, y un posicional con ese nombre lo pisaba -- la orden pasaba
    # a ser un numero y no entraba en ninguna rama.
    s.add_argument("hito", type=int, help="el numero de orden del hito")
    s.add_argument("fecha", help="ISO (2026-10-02)")
    s.add_argument("--clase", choices=("real", "limite", "provisional", "sin_senalar"),
                   default="real")
    s.add_argument("--ocurrido", action="store_true", help="darlo por cumplido")

    s = sub.add_parser("hecho", help="marca un hito como realizado")
    s.add_argument("id", type=int)
    s.add_argument("hito", type=int)
    s.add_argument("--fecha", default=None, help="fecha del hecho; por defecto, hoy")
    s.add_argument("--por", choices=("abogado", "acuse"), default="abogado")

    s = sub.add_parser("deshacer", help="deshace el marcado de un hito")
    s.add_argument("id", type=int)
    s.add_argument("hito", type=int)

    s = sub.add_parser("pausar", help="suspende un plazo por un hecho registrado")
    s.add_argument("id", type=int)
    s.add_argument("hito", type=int)
    s.add_argument("motivo")

    s = sub.add_parser("reanudar", help="reanuda un plazo pausado")
    s.add_argument("id", type=int)
    s.add_argument("hito", type=int)
    s.add_argument("fecha", nargs="?", default=None)

    s = sub.add_parser("prorrogar", help="el órgano amplía el plazo de un hito")
    s.add_argument("id", type=int)
    s.add_argument("hito", type=int)
    s.add_argument("fecha", help="la fecha nueva, la que concede la resolución")
    s.add_argument("--resolucion", default=None, help="referencia de la resolución que la concede")

    s = sub.add_parser("acciones", help="qué le ha pasado al expediente")
    s.add_argument("id", type=int)
    s.add_argument("n", nargs="?", type=int, default=30)

    s = sub.add_parser("cancelar", help="cancela un hito por un motivo registrado")
    s.add_argument("id", type=int)
    s.add_argument("hito", type=int)
    s.add_argument("motivo")

    s = sub.add_parser("cerrar", help="cierra un expediente sin borrarlo")
    s.add_argument("id", type=int)

    s = sub.add_parser("eliminar", help="borra un expediente de verdad")
    s.add_argument("id", type=int)
    s.add_argument("--si", action="store_true", help="confirma el borrado")

    s = sub.add_parser("vaciar", help="borra TODOS los expedientes")
    s.add_argument("--si", action="store_true", help="confirma el borrado")

    args = p.parse_args()
    consola.tolerante()
    try:
        ejecutar(args)
    except (RuntimeError, LookupError, ValueError) as e:
        sys.exit(f"Error: {e}")


def ejecutar(args):
    if args.orden == "tipos":
        # No necesita base: el catálogo es un fichero de datos, y listarlo no
        # debería exigir que exista ninguna base cifrada.
        from . import catalogo

        for t in catalogo.tipos():
            if args.arquetipo and t["arquetipo"] != args.arquetipo:
                continue
            print(f"{t['tipo']:<34}  {t['arquetipo']}  {ARQUETIPOS[t['arquetipo']]:<22}"
                  f"  origen: {t['origen']:<10}  destino: {t['destino']}")
        return

    expedientes = Expedientes()
    try:
        if args.orden == "abrir":
            e = expedientes.abrir(
                args.tipo,
                titulo=args.titulo,
                cliente=args.cliente,
                contrario=args.contrario,
                organo=args.organo,
            )
            print(f"Abierto {e['referencia']}  ({e['tipo']}, arquetipo {e['arquetipo']}, "
                  f"salida por {e['destino']}).")
        elif args.orden == "listar":
            filas = expedientes.listar(None if args.todos else "abierto")
            if not filas:
                print("No hay expedientes abiertos.")
            for f in filas:
                marca = "" if f["estado"] == "abierto" else "  [cerrado]"
                print(f"{f['id']:>4}  {f['referencia']:<14}  {f['tipo']:<32}  "
                      f"{(f['titulo'] or '')[:40]}{marca}")
        elif args.orden == "hitos":
            filas = expedientes.hitos(args.id)
            if not filas:
                print("Este tipo no tiene plantilla de hitos escrita todavía "
                      "(hay 5 de 89, en datos/hitos.csv).")
            for h in filas:
                vida = vida_efectiva(h)
                marca = {"ocurrido": "[x]", "en_pausa": "[=]",
                         "cancelado": "[-]", "vencido": "[!]"}.get(vida, "[ ]")
                fecha = h["fecha"] or ("sin señalar" if h["clase"] == "senalamiento" else "—")
                clase = f"({h['clase_fecha']})" if h["clase_fecha"] else ""
                # Quién lo dio por hecho importa tanto como que esté hecho.
                quien = ""
                if h["estado"] == "ocurrido":
                    quien = "  · acreditado" if h["cerrado_por"] == "acuse" else "  · declarado"
                elif vida == "vencido":
                    quien = "  · VENCIDO"
                elif h["prorroga"]:
                    quien = f"  · prorrogado ({h['prorroga']})"
                elif h["motivo"]:
                    quien = f"  · {h['motivo']}"
                borrador = "" if h["revisado"] else "  · sin revisar"
                print(f"{marca} {h['orden']}. {h['nombre']:<44}  {fecha:<12} {clase:<14}"
                      f"  {h['norma'] or ''}{quien}{borrador}")
        elif args.orden == "fechar":
            expedientes.fechar(args.id, args.hito, args.fecha, args.clase, args.ocurrido)
            print(f"Hito {args.hito} del expediente {args.id}: {args.fecha} ({args.clase}).")
        elif args.orden == "hecho":
            h = expedientes.hecho(args.id, args.hito, args.fecha, args.por)
            como = "acreditado, con justificante" if args.por == "acuse" else (
                "declarado por el abogado, sin justificante")
            print(f"Hito {args.hito} ({h['nombre']}) realizado el {h['cerrado_en']}: {como}.")
        elif args.orden == "deshacer":
            h = expedientes.deshacer(args.id, args.hito)
            print(f"Hito {args.hito} ({h['nombre']}) vuelve a estar pendiente.")
        elif args.orden == "pausar":
            h = expedientes.pausar(args.id, args.hito, args.motivo)
            print(f"Hito {args.hito} ({h['nombre']}) en pausa: {args.motivo}.")
        elif args.orden == "reanudar":
            h = expedientes.reanudar(args.id, args.hito, args.fecha)
            nueva = f" con fecha {args.fecha}" if args.fecha else " sin fecha nueva"
            print(f"Hito {args.hito} ({h['nombre']}) reanudado{nueva}.")
        elif args.orden == "prorrogar":
            h = expedientes.prorrogar(args.id, args.hito, args.fecha, args.resolucion)
            print(f"Hito {args.hito} ({h['nombre']}) prorrogado hasta {args.fecha}"
                  f"{' por ' + args.resolucion if args.resolucion else ''}.")
        elif args.orden == "acciones":
            filas = expedientes.acciones(args.id, args.n)
            if not filas:
                print("Todavía no le ha pasado nada a este expediente.")
            for a in filas:
                hito = f"hito {a['orden']}" if a["orden"] else "expediente"
                print(f"{a['fecha'][:16]}  {hito:<10}  {a['accion']:<16}  {a['detalle'] or ''}")
        elif args.orden == "cancelar":
            h = expedientes.cancelar(args.id, args.hito, args.motivo)
            print(f"Hito {args.hito} ({h['nombre']}) cancelado: {args.motivo}.")
        elif args.orden == "cerrar":
            expedientes.cerrar_expediente(args.id)
            print(f"Expediente {args.id} cerrado. Sigue estando; no aparece en los abiertos.")
        elif args.orden == "eliminar":
            if not args.si:
                sys.exit(f"Esto borra el expediente {args.id} sin dejar rastro. "
                         f"Si es lo que quieres: eliminar {args.id} --si")
            expedientes.eliminar(args.id)
            print(f"Expediente {args.id} borrado.")
        elif args.orden == "vaciar":
            cuantos = len(expedientes.listar(None))
            if not args.si:
                sys.exit(f"Esto borra los {cuantos} expedientes sin dejar rastro. "
                         f"Si es lo que quieres: vaciar --si")
            print(f"{expedientes.vaciar()} expedientes borrados.")
    finally:
        expedientes.cerrar()


if __name__ == "__main__":
    main()
