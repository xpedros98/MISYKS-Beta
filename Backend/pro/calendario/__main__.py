"""Línea de órdenes de pro.calendario.

    python -m pro.calendario recolectar [AÑO...]   Lee los boletines y llena la base
    python -m pro.calendario semilla               Carga los festivos locales anotados a mano
    python -m pro.calendario comprobar URL [TEXTO] Por qué no se puede leer una fuente
    python -m pro.calendario estado                Qué se sabe y qué falta
    python -m pro.calendario festivos ÁMBITO [AÑO] Los días inhábiles de un sitio
    python -m pro.calendario calendario ÁMBITO [AÑO] El año entero en rejilla

El proceso de establecimiento está escrito en RECOLECCION.md, en la raíz del repo.
"""
import sys

from . import db, diagnostico, semilla
from .recolector import recolectar


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "ayuda"):
        print(__doc__)
        return 0
    orden, resto = argv[0], argv[1:]
    cal = db.abrir()
    try:
        if orden == "recolectar":
            anios = [int(a) for a in resto] or list(db.ventana())
            return _recolectar(cal, anios)
        if orden == "semilla":
            resumen = semilla.cargar(cal)
            # Las entradas rechazadas hacen fallar la orden: si alguien la
            # encadena en un script, tiene que enterarse de que el calendario
            # ha quedado incompleto a propósito.
            return 1 if resumen["rechazados"] else 0
        if orden == "comprobar":
            return _comprobar(resto)
        if orden == "estado":
            return _estado(cal)
        if orden == "festivos":
            if not resto:
                print("Falta el ámbito. Ejemplo: festivos 08019")
                return 2
            return _festivos(cal, resto[0], int(resto[1]) if len(resto) > 1 else None)
        if orden == "calendario":
            if not resto:
                print("Falta el ámbito. Ejemplo: calendario 28079")
                return 2
            return _calendario(cal, resto[0], int(resto[1]) if len(resto) > 1 else None)
        print(f"Orden desconocida: {orden}\n{__doc__}")
        return 2
    finally:
        cal.cerrar()


def _recolectar(cal, anios):
    resumen = recolectar(cal, anios)
    print(
        f"\nVersión {resumen['version']}: {resumen['anotados']} festivos anotados, "
        f"{resumen['retirados']} retirados."
    )
    if resumen["fallos"]:
        print(f"{len(resumen['fallos'])} fuentes han fallado:")
        for ambito, anio, error in resumen["fallos"]:
            print(f"  - {ambito} {anio}: {error}")
        # Las fuentes que fallan no hacen fracasar la orden: la base ha
        # quedado consistente y sabe lo que no sabe. Pero se avisa.
    return 0


def _comprobar(urls):
    """Interroga fuentes sin tocar la base. Sirve para decidir por dónde entrar."""
    if not urls:
        print("Falta la URL. Ejemplo: comprobar https://dogc.gencat.cat/... Barcelona")
        return 2
    # El segundo argumento es lo que tiene que aparecer si la descarga ha
    # servido de algo. Sin él no se puede afirmar que la fuente sirva.
    url, esperado = urls[0], (urls[1] if len(urls) > 1 else None)
    informe = diagnostico.revisar(url, esperado)
    print(f"\n{informe['url']}")
    print(f"  estado : {informe['estado']}")
    print(f"  detalle: {informe['detalle']}")
    if informe["emisor"]:
        print(f"  emisor : {informe['emisor']}")
    if informe["remedio"]:
        print(f"  remedio: {informe['remedio']}")
    return 0 if informe["estado"] == "ok" else 1


def _estado(cal):
    version = cal.version_actual()
    if version is None:
        print("El calendario está vacío. Ejecuta: python -m pro.calendario recolectar")
        return 1
    anios = list(db.ventana())
    print(f"Versión {version}. Años {anios[0]}-{anios[-1]}.\n")
    cuenta = {}
    for ambito, tipo, nombre, anio, computo, estado in cal.mapa_cobertura(anios):
        cuenta[(tipo, estado)] = cuenta.get((tipo, estado), 0) + 1
    print(f"{'nivel':<12} {'confirmado':>11} {'pendiente':>10} {'sin publicar':>13} {'FALLIDO':>8}")
    for tipo in db.TIPOS_AMBITO:
        fila = [cuenta.get((tipo, e), 0) for e in db.COBERTURA]
        if any(fila):
            print(f"{tipo:<12} {fila[0]:>11} {fila[1]:>10} {fila[2]:>13} {fila[3]:>8}")
    # Las cabeceras son los nombres que guarda la tabla, para que la pantalla y
    # la base hablen igual; lo que necesita explicacion va en la leyenda.
    print()
    print("  pendiente    = no se ha intentado: no hay extractor para esa fuente")
    print("  sin publicar = se miró y el boletín aún no ha sacado ese año")
    print("  FALLIDO      = se intentó y falló (lo único que pide actuar)")

    # Lo fallido se detalla siempre: es lo unico de esta pantalla que pide que
    # alguien haga algo. Lo demas es estado normal del trabajo pendiente.
    averias = cal.averias(anios)
    if averias:
        print(f"\n{len(averias)} fuentes se han intentado y han fallado:")
        for ambito, anio, computo, detalle in averias:
            print(f"  {ambito:10} {anio} {computo:15} {(detalle or '')[:70]}")
    else:
        print("\nNinguna fuente ha fallado.")

    _horizontes(cal, anios)
    return 0


def _horizontes(cal, anios):
    """Hasta dónde llegan los datos, y hasta dónde se puede uno fiar.

    Son dos cosas distintas y por eso van separadas. La última fecha anotada
    solo dice dónde acaban las filas; el horizonte dice hasta cuándo una fecha
    puede salir firme, que es lo que decide un plazo. Con 2026 confirmado
    entero, el último festivo es el 26 de diciembre pero el horizonte llega al
    31: el año está completo, y los días sin festivo también son dato.
    """
    print(f"\nÚltimo festivo guardado: {cal.ultimo_festivo() or 'ninguno'}")
    print("Firme hasta — un ámbito sale aquí solo si toda su cadena está confirmada:")
    por_fecha = {}
    for fila in cal.conn.execute("SELECT id FROM ambitos ORDER BY id"):
        for computo in db.COMPUTOS:
            clave = (cal.horizonte(fila["id"], computo, desde=anios[0]), computo)
            por_fecha.setdefault(clave, []).append(fila["id"])
    for (fecha, computo), ambitos in sorted(
        por_fecha.items(), key=lambda x: (x[0][0] is None, x[0][0] or "", x[0][1])
    ):
        muestra = ", ".join(ambitos[:5]) + ("..." if len(ambitos) > 5 else "")
        print(f"  {fecha or 'nada firme':12} {computo:15} {len(ambitos):3} ámbitos  {muestra}")


def _festivos(cal, ambito, anio):
    anio = anio or db.ventana()[0]
    for computo in db.COMPUTOS:
        dias = cal.inhabiles(ambito, computo, f"{anio}-01-01", f"{anio}-12-31")
        lagunas = cal.lagunas(ambito, computo, [anio])
        print(f"\n{ambito} · {anio} · cómputo {computo} · {len(dias)} días")
        for fecha in sorted(dias):
            origen = ", ".join(f"{a}: {n}" for a, n in dias[fecha])
            print(f"  {fecha}  {origen}")
        if lagunas:
            # Esto es lo que el motor convertiría en `provisional`.
            print(f"  ! faltan datos de: {', '.join(f'{a} ({e})' for a, _, e in lagunas)}")
    return 0


MESES_NOMBRE = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# Marca de cada día en la rejilla. El nivel se ve de un vistazo porque es lo
# que suele estar en duda: que el 25 de diciembre sea inhábil no lo discute
# nadie, pero si un día sale festivo y no se sabe de dónde viene, el nivel es
# la primera pregunta.
MARCAS = {"nacional": "N", "autonomico": "A", "insular": "I", "local": "L"}


def _calendario(cal, ambito, anio):
    """El año entero en rejilla, dos meses por fila.

    Es la vista de comprobación a ojo: sirve para que alguien del despacho mire
    un mes y diga «aquí falta el Corpus». Los fines de semana no se marcan
    porque no son dato de boletín sino regla del motor, y mezclarlos aquí daría
    a entender que el calendario sabe algo que no sabe.
    """
    import calendar as cal_py

    anio = anio or db.ventana()[0]
    niveles = {a["id"]: a["tipo"] for a in cal.cadena(ambito)}
    nombre_sitio = cal.cadena(ambito)[0]["nombre"]

    for computo in db.COMPUTOS:
        dias = cal.inhabiles(ambito, computo, f"{anio}-01-01", f"{anio}-12-31")
        lagunas = cal.lagunas(ambito, computo, [anio])
        estado = "FIRME" if not lagunas else "PROVISIONAL"
        print(f"\n{nombre_sitio} ({ambito}) · {anio} · cómputo {computo} · {estado}")
        print("=" * 68)

        marcado = {}
        for fecha, origenes in dias.items():
            dia = int(fecha[8:10])
            mes = int(fecha[5:7])
            # Si un día viene de dos capas se enseña la más concreta, que es la
            # que explica por qué ese sitio y no el de al lado.
            tipo = min(
                (niveles.get(a, "nacional") for a, _ in origenes),
                key=lambda t: list(MARCAS).index(t) if t in MARCAS else 0,
                default="nacional",
            )
            marcado[(mes, dia)] = MARCAS.get(tipo, "*")

        # Dos meses por fila y celdas de cuatro caracteres. Con tres meses y
        # celdas de tres cabía todo más apretado, pero dos días marcados
        # seguidos se pegaban («12N13») y esta vista existe precisamente para
        # leerla despacio.
        for fila in range(6):
            meses = [fila * 2 + 1, fila * 2 + 2]
            print("  ".join(f"{MESES_NOMBRE[m - 1]:^27}" for m in meses))
            print("  ".join(["lu  ma  mi  ju  vi  sa  do"] * 2))
            semanas = [cal_py.Calendar().monthdayscalendar(anio, m) for m in meses]
            for i in range(max(len(s) for s in semanas)):
                linea = []
                for mes, semanas_mes in zip(meses, semanas):
                    if i < len(semanas_mes):
                        celdas = [
                            "    " if d == 0 else f"{d:2d}{marcado.get((mes, d), ' ')} "
                            for d in semanas_mes[i]
                        ]
                        linea.append("".join(celdas).rstrip().ljust(27))
                    else:
                        linea.append(" " * 27)
                print("  ".join(linea).rstrip())
            print()

        print("  N nacional   A autonómico   I insular   L local")
        print(f"  {len(dias)} días de boletín (los sábados y domingos no salen: son regla del motor)")
        if lagunas:
            print("  ! sin datos de: " + ", ".join(f"{a} ({e})" for a, _, e in lagunas))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
