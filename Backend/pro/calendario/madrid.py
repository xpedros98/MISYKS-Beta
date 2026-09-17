"""Festivos locales de la ciudad de Madrid, desde su portal de datos abiertos.

Primer extractor de nivel local, y el patrón que seguirán los demás. Tiene tres
decisiones que conviene entender antes de copiarlo para otro municipio.

**Se toman solo las filas de competencia municipal.** El fichero del
Ayuntamiento trae el calendario completo de la ciudad --nacionales,
autonómicos y locales-- y sería tentador cargarlo entero. No se hace, por dos
razones. La primera es estructural: los nacionales y autonómicos ya vienen del
BOE, y un festivo tiene que vivir en un solo ámbito; si Navidad estuviera
también en `28079`, retirarla tras una corrección exigiría dos cambios en vez
de uno y bastaría olvidar uno para que el día quedara inhábil a medias. La
segunda es que **la clasificación de este fichero no es de fiar fuera de lo
suyo**: en 2026 etiqueta el 3 de abril como «Jueves Santo» cuando es Viernes
Santo, y da por nacionales días que el BOE fija como autonómicos. En lo que sí
es competencia del pleno del ayuntamiento --sus dos fiestas locales-- es la
fuente autorizada; en el resto, no.

**Cubre el cómputo judicial, no el administrativo.** El art. 182 LOPJ declara
inhábiles las fiestas laborales de la localidad, así que estas dos fechas
cuentan para los plazos judiciales. Para el administrativo, en cambio, los días
inhábiles de un municipio son los que fije el calendario de su comunidad
(apartado segundo, c, de la resolución de la AGE), que no tiene por qué
coincidir. Ese dato sale del BOCM y aquí se deja como no sabido.

**No hay descubrimiento: la URL es estable.** A diferencia del BOE, donde cada
año publica un documento distinto, aquí el mismo fichero cubre de 2013 en
adelante y se actualiza en su sitio. Lo que cambia es su contenido, así que el
control no es encontrar la URL sino comparar la huella.
"""
import csv
import io
import urllib.error
import urllib.request

from . import certificados
from .db import SinPublicar

AMBITO = "28079"
BOLETIN = "datos.madrid.es"
COMPUTOS = ("judicial",)

URL = (
    "https://datos.madrid.es/dataset/300082-0-calendario_laboral/resource/"
    "300082-1-calendario_laboral-csv/download/300082-1-calendario_laboral-csv.csv"
)

AGENTE = "MISYKS/pro.calendario (despacho de abogados; lectura de calendario oficial)"

# Valor exacto de la columna «Tipo de Festivo» que marca competencia municipal.
TIPO_LOCAL = "festivo local de la ciudad de madrid"

# Hasta dos fiestas locales por municipio: las propone el pleno del
# ayuntamiento y las aprueba la autoridad laboral de la comunidad. Si salieran
# más, o ninguna, es que el fichero ha cambiado de forma y hay que mirarlo, no
# que Madrid haya decidido otra cosa.
LOCALES_ESPERADOS = (1, 2)


def descargar(anio=None):
    """Devuelve (bytes crudos, url). Los bytes sirven para el sha256."""
    req = urllib.request.Request(URL, headers={"User-Agent": AGENTE})
    try:
        crudo = urllib.request.urlopen(
            req, timeout=40, context=certificados.contexto()
        ).read()
    except urllib.error.URLError as e:
        pista = certificados.diagnostico(e.reason)
        if pista:
            raise RuntimeError(f"{URL}: {pista}") from e
        raise
    return crudo, URL


def locales(crudo, anio):
    """Fiestas locales de Madrid en ese año, como [(ámbito, fecha ISO, nombre)]."""
    texto = crudo.decode("utf-8-sig")
    filas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
    if not filas or "Tipo de Festivo" not in filas[0]:
        raise ValueError(
            "El CSV de datos.madrid.es no trae la columna «Tipo de Festivo»: "
            "ha cambiado de formato y no se puede distinguir lo local."
        )

    salida = []
    del_anio = 0
    for fila in filas:
        dia = (fila.get("Dia") or "").strip()
        if not dia.endswith(f"/{anio}"):
            continue
        del_anio += 1
        if (fila.get("Tipo de Festivo") or "").strip().lower() != TIPO_LOCAL:
            continue
        salida.append((AMBITO, _fecha(dia), (fila.get("Festividad") or "").strip()))

    # Sin ninguna fila de ese año, el fichero simplemente no lo cubre todavía:
    # el calendario municipal del año siguiente se aprueba en otoño. Eso no es
    # una avería, es «aún no toca», y hay que decirlo así -- si se tratara como
    # error, la cobertura quedaría `pendiente` y alguien se pondría a buscar un
    # problema que no existe.
    if del_anio == 0:
        raise SinPublicar(f"El fichero de datos.madrid.es todavía no cubre {anio}.")

    if len(salida) not in LOCALES_ESPERADOS:
        # Esto sí es una avería: el año está en el fichero pero sus fiestas
        # locales no aparecen o aparecen de más. Cero entraría en la base como
        # «Madrid no tiene fiestas propias», que es falso y no da ningún
        # síntoma hasta que alguien pierde un plazo el día de San Isidro.
        raise ValueError(
            f"Hay {del_anio} días de {anio} en el fichero pero {len(salida)} fiestas "
            f"locales, y se esperaban una o dos. ¿Ha cambiado el formato?"
        )
    return salida


def _fecha(dia):
    """De 'dd/mm/aaaa' a ISO."""
    d, m, a = dia.split("/")
    return f"{a}-{int(m):02d}-{int(d):02d}"
