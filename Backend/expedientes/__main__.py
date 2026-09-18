"""Línea de órdenes de expedientes. Se ejecuta desde la carpeta Backend:

    python -m expedientes tipos [--arquetipo A]   los 89 tipos documentales
    python -m expedientes abrir TIPO [--titulo T] [--cliente C] [--contrario X] [--organo O]
    python -m expedientes listar [--todos]        los abiertos, o todos
    python -m expedientes hitos ID                por dónde pasa: la barra, en texto
    python -m expedientes fechar ID ORDEN FECHA [--clase real|limite|provisional] [--ocurrido]
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
                marca = "[x]" if h["estado"] == "ocurrido" else "[ ]"
                fecha = h["fecha"] or ("sin señalar" if h["clase"] == "senalamiento" else "—")
                clase = f"({h['clase_fecha']})" if h["clase_fecha"] else ""
                borrador = "" if h["revisado"] else "  · sin revisar"
                print(f"{marca} {h['orden']}. {h['nombre']:<44}  {fecha:<12} {clase:<14}"
                      f"  {h['norma'] or ''}{borrador}")
        elif args.orden == "fechar":
            expedientes.fechar(args.id, args.hito, args.fecha, args.clase, args.ocurrido)
            print(f"Hito {args.hito} del expediente {args.id}: {args.fecha} ({args.clase}).")
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
