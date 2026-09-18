"""Que un carácter raro no tumbe una orden entera.

La consola de Windows es cp1252 y no sabe escribir ni «→» ni «—» ni un emoji.
Con la configuración por defecto de Python, un `print` con uno de esos
caracteres no imprime un signo raro: lanza `UnicodeEncodeError` y se lleva por
delante la orden completa. Y no es un caso rebuscado: el asunto de un correo o
el título de un evento del calendario los escribe cualquiera.

macOS, que es donde trabaja el equipo, es UTF-8 y no sufre esto. El Backend se
desarrolla también en Windows, así que los dos tienen que funcionar.

Se aplica solo en las CLI, no en las bibliotecas: es una decisión sobre cómo se
muestra algo, y quien llame a `sec.agenda` desde otro sitio decidirá la suya.
"""
import sys


def tolerante():
    """Deja stdout y stderr sustituyendo lo que no sepan escribir.

    `errors="replace"` cambia el carácter por un interrogante en vez de fallar.
    Se pierde un signo de puntuación; la alternativa es perder la salida entera.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            # Salida redirigida a algo que no admite reconfiguración: no es
            # motivo para no ejecutar la orden.
            pass
