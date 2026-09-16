"""Línea de órdenes de sec.mail. Se ejecuta desde la carpeta Backend:

    python -m sec.mail carpetas                        lista las carpetas de Gmail
    python -m sec.mail sincronizar [CARPETA] [-n N]    guarda los correos nuevos (por defecto INBOX, sin limite)
    python -m sec.mail listar [N]                       muestra los últimos N correos guardados
    python -m sec.mail leido ID               marca un correo como leído en Gmail
    python -m sec.mail mover ID CARPETA       mueve un correo a otra carpeta de Gmail

Las credenciales de Gmail viven en ~/.misyks/config, seccion [gmail]. Normalmente
las escribe la pantalla de Ajustes de la app (Frontend), no se editan a mano.
"""
import argparse
import imaplib
import sys

from .agent import SecMail


def main():
    p = argparse.ArgumentParser(prog="python -m sec.mail", description="Sub-agente de correo de MISYKS.")
    sub = p.add_subparsers(dest="orden", required=True)
    sub.add_parser("carpetas", help="lista las carpetas de Gmail")
    s = sub.add_parser("sincronizar", help="guarda los correos nuevos de una carpeta")
    s.add_argument("carpeta", nargs="?", default="INBOX")
    s.add_argument("-n", "--limite", type=int, default=None, help="maximo de correos nuevos a traer en esta tanda")
    s = sub.add_parser("listar", help="muestra los últimos correos guardados")
    s.add_argument("n", nargs="?", type=int, default=20)
    s = sub.add_parser("leido", help="marca un correo como leído en Gmail")
    s.add_argument("id", type=int)
    s = sub.add_parser("mover", help="mueve un correo a otra carpeta de Gmail")
    s.add_argument("id", type=int)
    s.add_argument("carpeta")
    args = p.parse_args()

    try:
        ejecutar(args)
    except (RuntimeError, LookupError, ValueError, imaplib.IMAP4.error) as e:
        sys.exit(f"Error: {e}")


def ejecutar(args):
    agente = SecMail()
    try:
        if args.orden == "carpetas":
            for c in agente.carpetas():
                print(f"{c['nombre']:<30} {' '.join(c['marcas'])}")
        elif args.orden == "sincronizar":
            nuevos = agente.sincronizar(args.carpeta, limite=args.limite)
            print(f"{nuevos} correos nuevos guardados de {args.carpeta}.")
        elif args.orden == "listar":
            for f in agente.listar(args.n):
                estado = "leído   " if f["leido"] else "sin leer"
                print(
                    f"{f['id']:>4}  {(f['fecha'] or '')[:16]:<16}  {estado}  {f['carpeta']:<12}  "
                    f"{f['remitente']}  |  {f['asunto']}  ({f['adjuntos']} adj.)"
                )
        elif args.orden == "leido":
            agente.marcar_leido(args.id)
            print(f"Correo {args.id} marcado como leído.")
        elif args.orden == "mover":
            agente.mover(args.id, args.carpeta)
            print(f"Correo {args.id} movido a {args.carpeta}.")
    finally:
        agente.cerrar()


if __name__ == "__main__":
    main()
