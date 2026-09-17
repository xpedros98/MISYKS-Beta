"""Catálogo de sitios y de publicaciones: qué ámbitos existen y dónde se busca cada festivo.

Esto son datos, no lógica. Va aparte del recolector porque cambia por motivos
distintos: el recolector cambia cuando cambia *cómo* se lee un boletín, y este
fichero cambia cuando el despacho empieza a litigar en otro partido judicial o
cuando una comunidad se muda de dominio.

**El árbol arranca con diez municipios, no con los 8.131 del INE.** No es
pereza: la cobertura de festivos locales de un municipio que nadie consulta
quedaría «pendiente» para siempre y llenaría de ruido la pantalla de
mantenimiento, que es justo la que tiene que dejar ver lo que falta de verdad.
El árbol crece cuando `pro.destino` resuelve un órgano nuevo.

**Las 29 publicaciones sí están todas**, aunque solo unas pocas se sepan leer
todavía. Registrarlas desde el principio es lo que hace que la base sepa lo que
*no* tiene: una fuente sin extractor deja su cobertura en `pendiente`, y el
motor da fecha prudente en vez de suponer que ese municipio no tiene fiestas.
"""

# Las 19 comunidades y ciudades autónomas, con el código ISO 3166-2:ES. Son
# exactamente las 19 columnas de la tabla de fiestas laborales del BOE.
COMUNIDADES = {
    "ES-AN": "Andalucía",
    "ES-AR": "Aragón",
    "ES-AS": "Asturias",
    "ES-IB": "Illes Balears",
    "ES-CN": "Canarias",
    "ES-CB": "Cantabria",
    "ES-CM": "Castilla-La Mancha",
    "ES-CL": "Castilla y León",
    "ES-CT": "Cataluña",
    "ES-EX": "Extremadura",
    "ES-GA": "Galicia",
    "ES-MD": "Comunidad de Madrid",
    "ES-MC": "Región de Murcia",
    "ES-NC": "Comunidad Foral de Navarra",
    "ES-PV": "País Vasco",
    "ES-RI": "La Rioja",
    "ES-VC": "Comunitat Valenciana",
    "ES-CE": "Ceuta",
    "ES-ML": "Melilla",
}

# Nivel insular, entre la comunidad y el municipio. Solo existe donde lo hay:
# Canarias tiene fiestas por isla, y Baleares también.
ISLAS = {
    "ES-CN-GC": ("Gran Canaria", "ES-CN"),
    "ES-IB-MA": ("Mallorca", "ES-IB"),
}

# Los diez municipios más poblados, como banco de pruebas. El código es el del
# INE, cinco dígitos, con la provincia en los dos primeros.
MUNICIPIOS = {
    "28079": ("Madrid", "ES-MD"),
    "08019": ("Barcelona", "ES-CT"),
    "46250": ("València", "ES-VC"),
    "41091": ("Sevilla", "ES-AN"),
    "50297": ("Zaragoza", "ES-AR"),
    "29067": ("Málaga", "ES-AN"),
    "30030": ("Murcia", "ES-MC"),
    "07040": ("Palma", "ES-IB-MA"),
    "35016": ("Las Palmas de Gran Canaria", "ES-CN-GC"),
    "48020": ("Bilbao", "ES-PV"),
}

# Las publicaciones donde viven los festivos, por ámbito.
#
# Lo que hace incómodo esto no es el número sino la irregularidad: el BOE trae
# las nacionales y las autonómicas de todas las comunidades en un solo
# documento, pero **las locales no las publica nadie de forma centralizada**.
# Casi todas las comunidades las sacan en su boletín, con dos excepciones que
# son las que disparan la cuenta a 29: Castilla y León las reparte en los nueve
# boletines provinciales y el País Vasco en los tres de territorio histórico.
#
# `url_busqueda` es estable y es por donde se entra cada año; el documento
# concreto cambia de URL y se guarda en la base al encontrarlo.
BOLETINES = {
    # Estatal: cubre ES y, para el cómputo judicial, las 19 comunidades.
    "ES": [("BOE", "https://www.boe.es/buscar/boe.php")],
    "ES-AN": [("BOJA", "https://www.juntadeandalucia.es/boja")],
    "ES-AR": [("BOA", "https://www.boa.aragon.es/")],
    "ES-AS": [("BOPA", "https://sede.asturias.es/bopa")],
    "ES-IB": [("BOIB", "https://www.caib.es/eboibfront/")],
    "ES-CN": [("BOC-CN", "https://www.gobiernodecanarias.org/boc/")],
    "ES-CB": [("BOC-CB", "https://boc.cantabria.es/")],
    "ES-CM": [("DOCM", "https://docm.jccm.es/")],
    "ES-CT": [("DOGC", "https://dogc.gencat.cat/")],
    "ES-EX": [("DOE", "https://doe.juntaex.es/")],
    "ES-GA": [("DOG", "https://www.xunta.gal/diario-oficial-galicia")],
    "ES-MD": [("BOCM", "https://www.bocm.es/")],
    "ES-MC": [("BORM", "https://www.borm.es/")],
    "ES-NC": [("BON", "https://bon.navarra.es/")],
    "ES-RI": [("BOR", "https://web.larioja.org/bor")],
    "ES-VC": [("DOGV", "https://dogv.gva.es/")],
    "ES-CE": [("BOCCE", "https://www.ceuta.es/ceuta/boletin-oficial")],
    "ES-ML": [("BOME", "https://www.melilla.es/bome")],
    # Castilla y León no publica las locales en su boletín autonómico: van una
    # por una en los nueve boletines provinciales.
    "ES-CL": [
        ("BOP-AV", "https://www.diputacionavila.es/bop/"),
        ("BOP-BU", "https://bop.burgos.es/"),
        ("BOP-LE", "https://bop.dipuleon.es/"),
        ("BOP-P", "https://bop.diputaciondepalencia.es/"),
        ("BOP-SA", "https://bop.diputaciondesalamanca.com/"),
        ("BOP-SG", "https://bop.dipsegovia.es/"),
        ("BOP-SO", "https://bop.dipsoria.es/"),
        ("BOP-VA", "https://bop.diputaciondevalladolid.es/"),
        ("BOP-ZA", "https://bop.diputaciondezamora.es/"),
    ],
    # El País Vasco, en los tres de territorio histórico.
    "ES-PV": [
        ("BOTHA", "https://www.araba.eus/botha/"),
        ("BOB", "https://www.bizkaia.eus/bao/"),
        ("BOG", "https://egoitza.gipuzkoa.eus/gao/"),
    ],
}


def ambitos():
    """El árbol completo, en orden de creación: un padre antes que sus hijos.

    El orden importa porque `ambitos.padre` es clave ajena: dar de alta un
    municipio cuya comunidad no existe todavía falla, y eso es deliberado --
    impide que entre un festivo colgado de un código mal tecleado.
    """
    arbol = [("ES", "nacional", "España", None)]
    arbol += [(id, "autonomico", nombre, "ES") for id, nombre in COMUNIDADES.items()]
    arbol += [(id, "insular", nombre, padre) for id, (nombre, padre) in ISLAS.items()]
    arbol += [(id, "local", nombre, padre) for id, (nombre, padre) in MUNICIPIOS.items()]
    return arbol


def publicaciones():
    """Las 29 publicaciones como [(ámbito, boletín, url_busqueda)]."""
    return [
        (ambito, boletin, url)
        for ambito, lista in BOLETINES.items()
        for boletin, url in lista
    ]
