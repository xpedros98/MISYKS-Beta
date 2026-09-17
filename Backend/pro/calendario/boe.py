"""Extractor del BOE: las dos resoluciones estatales que fijan los festivos.

El BOE es la fuente más rentable con diferencia. Un solo documento —la
resolución anual de fiestas laborales— trae los festivos nacionales y los de
las diecinueve comunidades, que es el grueso de los días inhábiles. Solo las
locales quedan fuera, y esas van boletín por boletín (ver `fuentes.py`).

**Son dos resoluciones distintas, una por cómputo**, y confundirlas es uno de
los «falla si» del catálogo:

- *Judicial*: «relación de fiestas laborales», de la Dirección General de
  Trabajo. El art. 182 LOPJ no tiene lista propia: declara inhábiles los días
  de fiesta laboral en la comunidad o la localidad, así que esta resolución es
  la fuente del calendario judicial pese a llamarse laboral.
- *Administrativo*: «calendario de días inhábiles en el ámbito de la
  Administración General del Estado», de la Secretaría de Estado de Función
  Pública, publicada por separado y varias semanas después.

**El descubrimiento va por la API de sumarios, no por el buscador.** El
buscador del BOE rechaza las consultas GET que no vienen de su formulario, y
depender de su HTML sería atarse a una maquetación. La API de sumarios está
documentada, devuelve JSON y da el título y la URL del XML de cada documento
publicado ese día. El precio es recorrer los días del último trimestre del año
anterior, que es cuando salen las dos resoluciones: unas cien peticiones, una
vez al año, a cambio de no tener que tocar nada cuando el BOE rediseñe su web.
"""
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from . import certificados
from .fuentes import COMUNIDADES

AGENTE = "MISYKS/pro.calendario (despacho de abogados; lectura de calendario oficial)"

API_SUMARIO = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"
URL_XML = "https://www.boe.es/diario_boe/xml.php?id={id}"

# Cómo se reconoce cada resolución por su título. Se busca sobre el título
# normalizado (sin tildes, en minúsculas) porque el BOE no es consistente con
# los acentos entre el sumario y el documento.
PATRONES = {
    "judicial": "relacion de fiestas laborales para el ano {anio}",
    "administrativo": "calendario de dias inhabiles en el ambito de la administracion general del estado para el ano {anio}",
}

# Ventana de rastreo: las dos resoluciones se publican en el último trimestre
# del año anterior (fiestas laborales hacia finales de octubre, días inhábiles
# a finales de noviembre). Se arranca en septiembre por margen.
VENTANA = (9, 1, 12, 31)

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}


def _normaliza(texto):
    """Minúsculas, sin tildes y con los espacios colapsados."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


# Nombre de comunidad tal como lo escribe la tabla del BOE -> código ISO. La
# tabla no usa los nombres oficiales completos ('Com. Madrid', 'Región
# Murcia'), así que el emparejamiento va por contención sobre el normalizado.
_CLAVES_COMUNIDAD = {
    "ES-AN": "andalucia", "ES-AR": "aragon", "ES-AS": "asturias",
    "ES-IB": "balears", "ES-CN": "canarias", "ES-CB": "cantabria",
    "ES-CM": "castilla-la mancha", "ES-CL": "castilla y leon",
    "ES-CT": "cataluna", "ES-EX": "extremadura", "ES-GA": "galicia",
    "ES-MD": "madrid", "ES-MC": "murcia", "ES-NC": "navarra",
    "ES-PV": "vasco", "ES-RI": "rioja", "ES-VC": "valencia",
    "ES-CE": "ceuta", "ES-ML": "melilla",
}


def _codigo_comunidad(cabecera):
    """Código ISO de la comunidad que encabeza una columna, o None."""
    n = _normaliza(cabecera)
    if not n:
        return None
    for codigo, clave in _CLAVES_COMUNIDAD.items():
        if clave in n:
            return codigo
    return None


def _descarga(url, cabeceras=None):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, **(cabeceras or {})})
    try:
        return urllib.request.urlopen(req, timeout=30, context=certificados.contexto()).read()
    except urllib.error.URLError as e:
        pista = certificados.diagnostico(e.reason)
        if pista:
            raise RuntimeError(f"{url}: {pista}") from e
        raise


def localizar(anio, computo, registro=None, hoy=None):
    """Busca en los sumarios del BOE la resolución de ese año y cómputo.

    Devuelve `{'id', 'url_xml', 'publicado'}` o None si no aparece. Que
    devuelva None **no es un fallo**: en septiembre, la resolución del año
    siguiente puede no estar publicada todavía. Por eso el recolector lo anota
    como `sin_publicar` y no como `fallido`: no hay nada que arreglar.

    `hoy` existe para poder probar el corte del rastreo sin depender de la
    fecha real de la máquina.
    """
    patron = PATRONES[computo].format(anio=anio)
    mes_i, dia_i, mes_f, dia_f = VENTANA
    dia = date(anio - 1, mes_i, dia_i)
    # El rastreo no pasa de hoy: un sumario de un día que todavía no ha
    # ocurrido no existe, y pedirlo son unas setenta y cinco peticiones
    # inútiles por cómputo cada vez que se busca el año que viene antes de
    # octubre. No cambia el resultado --sin hallazgo, la cobertura queda
    # `sin_publicar` igual--, solo lo que se tarda en llegar a él.
    fin = min(date(anio - 1, mes_f, dia_f), hoy or date.today())
    while dia <= fin:
        # Los sumarios de sábado y domingo no existen: el BOE no publica.
        if dia.weekday() < 5:
            hallazgo = _busca_en_sumario(dia, patron, registro)
            if hallazgo:
                return hallazgo
        dia += timedelta(days=1)
    return None


def _busca_en_sumario(dia, patron, registro=None):
    url = API_SUMARIO.format(fecha=dia.strftime("%Y%m%d"))
    try:
        datos = json.loads(_descarga(url, {"Accept": "application/json"}))
    except Exception as e:
        # Un día sin sumario (festivo, o fuera de rango) responde con error.
        # No es motivo para abortar el rastreo del trimestre entero.
        if registro:
            registro(f"sumario {dia.isoformat()}: {type(e).__name__}")
        return None
    encontrado = []

    def recorre(nodo):
        if isinstance(nodo, dict):
            if "identificador" in nodo and "titulo" in nodo:
                if patron in _normaliza(nodo["titulo"]):
                    encontrado.append(nodo)
                return
            for valor in nodo.values():
                recorre(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                recorre(valor)

    recorre(datos.get("data", {}))
    if not encontrado:
        return None
    doc = encontrado[0]
    return {
        "id": doc["identificador"],
        "url_xml": doc.get("url_xml") or URL_XML.format(id=doc["identificador"]),
        "publicado": dia.isoformat(),
    }


def descargar_xml(url_xml):
    """Devuelve (bytes crudos, árbol). Los bytes son para el sha256."""
    crudo = _descarga(url_xml)
    return crudo, ET.fromstring(crudo)


def fiestas_laborales(arbol, anio):
    """Extrae la rejilla de fiestas laborales (cómputo judicial).

    Devuelve [(ámbito, fecha ISO, nombre)]. Un día marcado en las diecinueve
    comunidades se anota **solo** en `ES`, no en cada una: es una fiesta
    nacional, y repetirla diecinueve veces haría que retirarla exigiera
    diecinueve correcciones en vez de una.
    """
    tabla = arbol.find(".//table")
    if tabla is None:
        raise ValueError("La resolución no trae tabla de fiestas: ¿ha cambiado el formato?")
    filas = tabla.findall(".//tr")

    columnas = _cabeceras(filas)
    if len(columnas) != len(COMUNIDADES):
        raise ValueError(
            f"Se han reconocido {len(columnas)} comunidades en la cabecera y se "
            f"esperaban {len(COMUNIDADES)}. El formato de la tabla ha cambiado."
        )

    salida = []
    mes = None
    for fila in filas:
        celdas = [_texto(c) for c in fila.findall(".//td") + fila.findall(".//th")]
        if not celdas:
            continue
        primera = _normaliza(celdas[0])
        if primera in MESES and not any(c.strip() for c in celdas[1:]):
            mes = MESES[primera]
            continue
        coincide = re.match(r"^(\d{1,2})\s+(.+?)\.?$", celdas[0].strip())
        if not coincide or mes is None:
            continue
        dia, nombre = int(coincide.group(1)), coincide.group(2).strip()
        try:
            fecha = date(anio, mes, dia).isoformat()
        except ValueError:
            continue  # un día que no existe en ese mes: fila mal formada
        # Las marcas van en las celdas que siguen a la de la fecha, y se
        # emparejan con la cabecera **por posición relativa**, no por índice
        # absoluto: la fila de cabecera empieza a nombrar comunidades en su
        # columna 0, mientras que en las filas de datos la columna 0 es la
        # fecha. Emparejar por índice desplazaba todo un puesto y cada
        # comunidad se quedaba con los festivos de la de al lado -- un error
        # que no da ningún síntoma, porque el número de festivos por comunidad
        # sigue pareciendo razonable.
        marcas = celdas[1:]
        if len(marcas) != len(columnas):
            raise ValueError(
                f"La fila «{celdas[0][:40]}» trae {len(marcas)} marcas y la cabecera "
                f"tiene {len(columnas)} comunidades. El formato ha cambiado."
            )
        marcadas = [codigo for codigo, marca in zip(columnas, marcas) if marca.strip()]
        if not marcadas:
            continue
        if len(marcadas) == len(columnas):
            salida.append(("ES", fecha, nombre))
        else:
            salida.extend((codigo, fecha, nombre) for codigo in marcadas)
    return salida


def _cabeceras(filas):
    """Códigos de comunidad **en el orden de las columnas**, leyendo la fila de nombres.

    Devuelve una lista, no un mapa por índice: lo que hay que conservar es el
    orden, porque es lo que empareja cada marca con su comunidad.

    Se toma la fila que más comunidades reconozca en vez de dar por hecho que
    es la segunda: el BOE ha movido esa fila entre años, y fijar el número de
    fila haría que el extractor devolviera cero festivos sin dar error.
    """
    mejor = []
    for fila in filas[:5]:
        celdas = [_texto(c) for c in fila.findall(".//td") + fila.findall(".//th")]
        orden = []
        for celda in celdas:
            codigo = _codigo_comunidad(celda)
            if codigo and codigo not in orden:
                orden.append(codigo)
        if len(orden) > len(mejor):
            mejor = orden
    return mejor


def dias_inhabiles_age(arbol, anio, laborales):
    """Días inhábiles de la AGE (cómputo administrativo) para Estado y comunidades.

    **No se extraen de este documento: se derivan del de fiestas laborales**, y
    conviene explicar por qué, porque la primera versión de esta función
    intentaba leerlos de aquí y devolvía basura convincente.

    La resolución de la AGE no trae el anexo en el XML del BOE --el cuerpo son
    solo párrafos; la rejilla existe únicamente en el PDF--. Lo que sí trae es
    la regla, en su apartado segundo: son inhábiles, en todo el territorio, las
    fiestas nacionales no sustituibles o sobre las que ninguna comunidad ejerció
    la sustitución, y en cada comunidad, los días que ella misma haya declarado
    festivos. Eso es, término a término, la rejilla de fiestas laborales que ya
    sabemos leer, y encaja con el art. 30.7 de la Ley 39/2015, que manda fijar
    este calendario «con sujeción al calendario laboral oficial».

    Derivarlo es además más seguro que parsear el anexo: si los dos documentos
    se contradijeran, la contradicción vendría de una errata de maquetación, no
    de dos voluntades distintas.

    Lo que **no** se deriva es el nivel local. Para el cómputo administrativo,
    los días inhábiles de un municipio son los que fije el calendario de su
    comunidad (apartado segundo, c), que no tiene por qué coincidir con sus
    fiestas patronales, y además el art. 30.6 obliga a mirar también el
    municipio del interesado. Eso sale del boletín autonómico y aquí se queda
    como no sabido.
    """
    _comprueba_anio(arbol, anio)
    return [(ambito, fecha, nombre) for ambito, fecha, nombre in laborales]


def _comprueba_anio(arbol, anio):
    """Confirma que la resolución descargada es la del año que se pide.

    Barato y vale la pena: si el rastreo del sumario cazara la resolución del
    año equivocado, los festivos entrarían con fechas de otro año y nadie lo
    notaría hasta que un plazo saliera absurdo.
    """
    titulo = arbol.findtext(".//titulo") or ""
    if str(anio) not in titulo:
        raise ValueError(f"La resolución descargada no menciona {anio}: «{titulo[:80]}»")


def _texto(celda):
    return "".join(celda.itertext()).strip()
