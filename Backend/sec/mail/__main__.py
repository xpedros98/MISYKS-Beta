"""Línea de órdenes de sec.mail. Se ejecuta desde la carpeta Backend:

    python -m sec.mail conectar [google|microsoft]     autoriza una cuenta en el navegador
    python -m sec.mail estado                          dice si la cuenta sigue autorizada
    python -m sec.mail desconectar [PROVEEDOR]         revoca el acceso y borra los tokens
    python -m sec.mail carpetas                        lista las carpetas del buzón
    python -m sec.mail sincronizar [CARPETA] [-n N]    guarda los correos nuevos (por defecto INBOX, sin limite)
    python -m sec.mail listar [N]                      muestra los últimos N correos guardados
    python -m sec.mail leido ID                        marca un correo como leído en el buzón
    python -m sec.mail mover ID CARPETA                mueve un correo a otra carpeta del buzón

El acceso al correo es por OAuth (ARQUITECTURA.md 8.6): no hay contraseña que
escribir en ningún sitio. Los tokens viven en ~/.misyks/config, en la sección
[oauth.google] o [oauth.microsoft]; normalmente los escribe `conectar` o la
pantalla de Ajustes de la app (Frontend), no se editan a mano.
"""
import argparse
import sys

from ..cuentas import consola, oauth
from . import config
from .agent import SecMail


def main():
    p = argparse.ArgumentParser(prog="python -m sec.mail", description="Módulo de correo de MISYKS.")
    sub = p.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("conectar", help="autoriza una cuenta de correo en el navegador")
    s.add_argument("proveedor", nargs="?", default=config.PROVEEDOR_POR_DEFECTO, choices=sorted(oauth.PROVEEDORES))
    sub.add_parser("estado", help="dice si la cuenta conectada sigue autorizada")
    s = sub.add_parser("desconectar", help="revoca el acceso y borra los tokens locales")
    s.add_argument("proveedor", nargs="?", default=None, choices=sorted(oauth.PROVEEDORES))
    sub.add_parser("carpetas", help="lista las carpetas del buzón")
    s = sub.add_parser("sincronizar", help="guarda los correos nuevos de una carpeta")
    s.add_argument("carpeta", nargs="?", default="INBOX")
    s.add_argument("-n", "--limite", type=int, default=None, help="maximo de correos nuevos a traer en esta tanda")
    s = sub.add_parser("listar", help="muestra los últimos correos guardados")
    s.add_argument("n", nargs="?", type=int, default=20)
    s = sub.add_parser("leido", help="marca un correo como leído en el buzón")
    s.add_argument("id", type=int)
    s = sub.add_parser("mover", help="mueve un correo a otra carpeta del buzón")
    s.add_argument("id", type=int)
    s.add_argument("carpeta")
    args = p.parse_args()
    # Un asunto con un emoji no puede tumbar `listar` entero (ver consola.py).
    consola.tolerante()

    try:
        ejecutar(args)
    except (RuntimeError, LookupError, ValueError) as e:
        # ErrorOAuth, ConsentimientoRevocado, ErrorApi y ErrorCorreo son todos
        # RuntimeError: su mensaje ya dice qué hacer, así que se muestra tal
        # cual. El Frontend lo recoge de stderr y lo enseña en Ajustes.
        sys.exit(f"Error: {e}")


def ejecutar(args):
    # Conectar y desconectar no tocan la base: no deben exigir que exista la
    # clave de cifrado para poder autorizar una cuenta.
    if args.orden == "conectar":
        cuenta = oauth.conectar(args.proveedor)
        print(f"Cuenta conectada: {cuenta or '(sin dirección)'} ({args.proveedor}).")
        return
    if args.orden == "desconectar":
        for proveedor in [args.proveedor] if args.proveedor else sorted(oauth.PROVEEDORES):
            oauth.desconectar(proveedor)
            print(f"Acceso a {proveedor} revocado y tokens borrados.")
        return
    if args.orden == "estado":
        for proveedor in sorted(oauth.PROVEEDORES):
            estado, detalle = oauth.estado_conexion(proveedor)
            print(f"{proveedor:<10} {estado:<13} {detalle}")
        return

    agente = SecMail()
    try:
        if args.orden == "carpetas":
            for c in agente.carpetas():
                print(f"{c['nombre']:<30} {' '.join(c['marcas'])}")
        elif args.orden == "sincronizar":
            nuevos = agente.sincronizar(args.carpeta, limite=args.limite)
            quedan = agente.pendientes(args.carpeta)
            cola = f" Quedan {quedan} por descargar." if quedan else ""
            print(f"{nuevos} correos nuevos guardados de {args.carpeta}.{cola}")
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
