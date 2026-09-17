"""Comprobación de los festivos antes de que entren en la base.

Esta es la pieza que permite que la lectura de los boletines la haga alguien
falible --hoy una persona o un modelo leyendo PDF en cuatro idiomas-- sin que
el error llegue al cálculo de un plazo. La idea es la misma que se adoptó con
`inv.normativa` el 16/09: **quien lee decide dónde mirar, pero el valor lo
produce y lo comprueba el código**.

Aquí no se llama a ningún modelo. Todo lo de este módulo es aritmética de
calendario y comparación de cadenas, así que se puede leer entero y se puede
probar sin red.

**El candidato tiene que traer su cita.** No basta con «el 25 de mayo es fiesta
en Barcelona»: hay que aportar el trozo de texto del boletín del que sale esa
afirmación, copiado tal cual. Esa exigencia es lo que hace verificable el
resto, porque convierte «me lo creo» en «el documento lo dice y aquí está
dónde». La cita va en el idioma del boletín, sin traducir: traducirla ya sería
interpretar, y la interpretación es justo lo que estamos comprobando.

Las cinco comprobaciones, y qué error caza cada una:

1. **El día aparece en la cita.** Caza el número cambiado --leer 14 donde pone
   15--, que es el error más probable y el más invisible.
2. **El mes de la cita coincide con el de la fecha.** Caza haberse ido de fila
   o de columna en una tabla por meses.
3. **El día de la semana cuadra.** Casi todos los boletines lo dicen. Es la
   comprobación más barata y la más potente: una fecha mal transcrita casi
   nunca cae en el día de la semana correcto.
4. **Como mucho dos fiestas locales por municipio y año.** Lo fija la ley: las
   propone el pleno del ayuntamiento y las aprueba la autoridad laboral.
5. **Una fiesta local no puede caer en un festivo autonómico o nacional.** No
   tendría sentido --el municipio gastaría una de sus dos fiestas en un día que
   ya era inhábil--, así que si coincide es que se ha leído mal la columna.
"""
import re
import unicodedata
from datetime import date

MAX_LOCALES = 2


def _normaliza(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


# Raíces de los nombres de mes en las lenguas de los boletines: castellano,
# catalán/valenciano, gallego y euskera. Se guardan como raíz y se comparan por
# comienzo de palabra porque el euskera declina ('urtarrila' -> 'urtarrilaren')
# y el catalán a veces abrevia. Sin tildes, que es como las deja `_normaliza`.
MESES = {
    1: ("enero", "gener", "xaneiro", "urtarril"),
    2: ("febrero", "febrer", "febreiro", "otsail"),
    3: ("marzo", "marc", "martxo"),
    4: ("abril", "apiril"),
    5: ("mayo", "maig", "maio", "maiatz"),
    6: ("junio", "juny", "xuno", "ekain"),
    7: ("julio", "juliol", "xullo", "uztail"),
    8: ("agosto", "agost", "abuztu"),
    9: ("septiembre", "setembre", "setembro", "irail", "setiembre"),
    10: ("octubre", "outubro", "urri"),
    11: ("noviembre", "novembre", "novembro", "azaro"),
    12: ("diciembre", "desembre", "decembro", "abendu"),
}

DIAS_SEMANA = {
    0: ("lunes", "dilluns", "luns", "astelehen"),
    1: ("martes", "dimarts", "asteart"),
    2: ("miercoles", "dimecres", "mercores", "asteazken"),
    3: ("jueves", "dijous", "xoves", "ostegun"),
    4: ("viernes", "divendres", "venres", "ostiral"),
    5: ("sabado", "dissabte", "larunbat"),
    6: ("domingo", "diumenge", "igande"),
}

CAMPOS = ("ambito", "fecha", "computo", "nombre", "url", "cita")


def verificar(candidato):
    """Comprobaciones que solo necesitan el candidato. Devuelve lista de problemas.

    Lista vacía significa que pasa. No lanza excepción por un candidato malo:
    se recogen todos los problemas para poder enseñarlos juntos, que es lo útil
    cuando se está revisando un boletín entero.
    """
    problemas = []
    for campo in CAMPOS:
        if not (candidato.get(campo) or "").strip():
            problemas.append(f"falta el campo «{campo}»")
    if problemas:
        return problemas

    try:
        fecha = date.fromisoformat(candidato["fecha"])
    except ValueError:
        return [f"fecha no es ISO: {candidato['fecha']!r}"]

    cita = _normaliza(candidato["cita"])

    # 1 · el día aparece en la cita, como número suelto y no como parte de otro
    # (que '25' case dentro de '2025' sería aceptar cualquier cosa).
    if not re.search(rf"(?<!\d){fecha.day}(?!\d)", cita):
        problemas.append(f"el día {fecha.day} no aparece en la cita: {candidato['cita']!r}")

    # 2 · el mes. Si la cita no nombra ninguno --pasa en las tablas donde el mes
    # está en una cabecera aparte-- se exige que se cite también esa cabecera.
    meses_citados = _meses_en(cita)
    if not meses_citados:
        problemas.append(
            "la cita no nombra ningún mes; añade al contexto la cabecera de mes "
            f"del documento: {candidato['cita']!r}"
        )
    elif fecha.month not in meses_citados:
        nombres = ", ".join(MESES[m][0] for m in sorted(meses_citados))
        problemas.append(
            f"la fecha dice mes {fecha.month} pero la cita nombra: {nombres}"
        )

    # 3 · el día de la semana, si el boletín lo dice.
    dias_citados = _dias_semana_en(cita)
    if dias_citados and fecha.weekday() not in dias_citados:
        esperado = DIAS_SEMANA[fecha.weekday()][0]
        nombres = ", ".join(DIAS_SEMANA[d][0] for d in sorted(dias_citados))
        problemas.append(
            f"{candidato['fecha']} cae en {esperado} y la cita dice: {nombres}"
        )

    return problemas


def _meses_en(cita):
    """Números de mes cuyo nombre aparece en la cita, en cualquiera de las lenguas."""
    palabras = re.findall(r"[a-z]+", cita)
    return {
        numero
        for numero, raices in MESES.items()
        if any(p.startswith(r) for p in palabras for r in raices)
    }


def _dias_semana_en(cita):
    palabras = re.findall(r"[a-z]+", cita)
    return {
        numero
        for numero, raices in DIAS_SEMANA.items()
        if any(p.startswith(r) for p in palabras for r in raices)
    }


def verificar_lote(candidatos, cal=None, version=None):
    """Verifica una tanda entera. Devuelve (aceptados, rechazados).

    `rechazados` es [(candidato, [problemas])]. Con `cal` se añaden las dos
    comprobaciones que necesitan saber qué hay ya en la base: el tope de
    fiestas locales y el solape con niveles superiores.

    Nada se escribe aquí. Este módulo solo dictamina; escribir es de `db`.
    """
    aceptados, rechazados = [], []
    por_municipio = {}

    for candidato in candidatos:
        problemas = verificar(candidato)
        if not problemas:
            clave = (candidato["ambito"], candidato["fecha"][:4], candidato["computo"])
            por_municipio.setdefault(clave, []).append(candidato)
        else:
            rechazados.append((candidato, problemas))

    for (ambito, anio, computo), grupo in por_municipio.items():
        # 4 · tope legal de fiestas locales.
        if len(grupo) > MAX_LOCALES:
            fechas = ", ".join(c["fecha"] for c in grupo)
            for candidato in grupo:
                rechazados.append(
                    (candidato, [f"{len(grupo)} fiestas locales en {ambito}/{anio}: {fechas}"])
                )
            continue

        for candidato in grupo:
            problemas = []
            # 5 · solape con un festivo de nivel superior.
            if cal is not None:
                problemas += _comprueba_solape(cal, candidato, computo, version)
            if problemas:
                rechazados.append((candidato, problemas))
            else:
                aceptados.append(candidato)

    return aceptados, rechazados


def _comprueba_solape(cal, candidato, computo, version):
    """Una fiesta local que cae en festivo autonómico o nacional es un error de lectura.

    Se consulta la cadena del municipio y se descarta lo que aporte el propio
    municipio: si ya estaba anotada de una pasada anterior, no es un solape.
    """
    fecha = candidato["fecha"]
    try:
        dias = cal.inhabiles(candidato["ambito"], computo, fecha, fecha, version)
    except KeyError as e:
        return [f"ámbito desconocido: {e}"]
    except RuntimeError:
        return []  # calendario vacío: no hay con qué contrastar todavía
    de_arriba = [
        (ambito, nombre)
        for ambito, nombre in dias.get(fecha, [])
        if ambito != candidato["ambito"]
    ]
    if de_arriba:
        origen = ", ".join(f"{a}: {n}" for a, n in de_arriba)
        return [f"{fecha} ya es festivo de nivel superior ({origen}): ¿columna mal leída?"]
    return []
