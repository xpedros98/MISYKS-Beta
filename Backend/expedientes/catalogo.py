"""Los 89 tipos documentales: qué son y de dónde salen.

**Dato, no código.** El catálogo vive en `datos/tipos.csv` y no en un literal de
Python, por lo mismo que COMPONENTES.md exige de la tabla de plazos: es un
activo que se revisa, se versiona y lo tiene que poder leer alguien que no
programa. Añadir un tipo es añadir una línea.

El fichero se extrajo de la **matriz de activación** de `ARQUITECTURA.md` §5,
que sigue siendo la fuente: si los dos se separan, manda el documento. De las
doce columnas de la matriz aquí se guardan cuatro, que son las que necesita un
expediente para existir; el resto —qué grupo interviene en cada ruta— lo usa el
pipeline, que todavía no está escrito.

Cada tipo trae:

- `tipo`       identificador (`contestacion_demanda`), que es como se nombra en
               todo el sistema.
- `arquetipo`  A–J, qué le exige el documento al pipeline (§4). Es lo que
               determina la ruta, no la rama del derecho: un arrendamiento y un
               desahucio son los dos «Civil» y no comparten nada operativo.
- `origen`     quién dispara: `abogado` (59), `secretario` (22), `workflow` (6),
               `agenda` (2).
- `destino`    por dónde sale: `lexnet` (59), `admin` (12), `cliente` (8),
               `notarial` (6), `burofax` (2), `smac` (1), `policial` (1).
"""
import csv
from pathlib import Path

RUTA = Path(__file__).parent / "datos" / "tipos.csv"
RUTA_HITOS = Path(__file__).parent / "datos" / "hitos.csv"

ARQUETIPOS = {
    "A": "Reactivos",
    "B": "Caducidad y cálculo",
    "C": "Trámite previo",
    "D": "Penales",
    "E": "Constructivo",
    "F": "Multi-documento",
    "G": "No procesal",
    "H": "Extrajudicial previo",
    "I": "Trámite",
    "J": "Ejecución",
}

_cache = None
_cache_hitos = None


def tipos():
    """Los 89, en el orden del catálogo, que agrupa por rama y no por nombre.

    Ese orden importa para la interfaz: alfabetizarlos mezclaría lo laboral con
    lo penal y obligaría a leer la lista entera para encontrar algo.
    """
    global _cache
    if _cache is None:
        with open(RUTA, encoding="utf-8", newline="") as f:
            _cache = [dict(fila) for fila in csv.DictReader(f)]
    return _cache


def tipo(nombre):
    """Un tipo por su identificador. Falla nombrando el error, no devuelve None.

    Abrir un expediente de un tipo que no existe es un error de quien llama, y
    dejarlo pasar daría un expediente sin ruta, sin plazos y sin canal de
    salida: un expediente que parece estar bien y no puede avanzar.
    """
    for t in tipos():
        if t["tipo"] == nombre:
            return t
    raise ValueError(
        f"No existe el tipo documental '{nombre}'. Son {len(tipos())} y están en "
        f"{RUTA.name}; para verlos: python -m expedientes tipos"
    )


def por_arquetipo():
    """{arquetipo: [tipos]}, para agrupar en una lista larga."""
    grupos = {}
    for t in tipos():
        grupos.setdefault(t["arquetipo"], []).append(t)
    return grupos


# --- hitos -----------------------------------------------------------------
#
# La plantilla de hitos de cada tipo: por dónde pasa un caso de esa clase. Es
# lo que da la barra de nodos, y es **conocimiento jurídico**, no una estructura
# de datos: por eso vive en `datos/hitos.csv`, con su artículo al lado y una
# columna `revisado` que hoy dice `no` en todas las filas.
#
# `revisado` no es decorativo. Un hito de menos es un trámite que nadie espera;
# un plazo mal atribuido es un plazo perdido. Mientras diga `no`, la interfaz lo
# enseña como borrador, y quien lo mire sabe que aún no lo ha validado un
# abogado.
#
# Hay plantilla para cinco tipos de los 89. Un tipo sin plantilla no inventa
# nada: abre el expediente sin hitos y lo dice.

# Qué clase de fecha lleva cada hito, que es lo que decide cómo se pinta:
#
# - `acto`          algo que ocurre y se fecha cuando ocurre (un emplazamiento).
# - `limite`        un plazo: la fecha es el último día, y la calcula `procesal`.
# - `senalamiento`  lo fija el juzgado; hasta que lo haga, no hay fecha y eso es
#                   normal, no un hueco.
# - `resolucion`    llega cuando llega; no se puede prever.
CLASES = ("acto", "limite", "senalamiento", "resolucion")


def hitos(tipo):
    """La plantilla de hitos de un tipo. Lista vacía si no tiene todavía.

    Vacía **no** es un error: hay plantilla para cinco de los 89 tipos. Un
    expediente sin hitos es un expediente cuyo recorrido aún no ha escrito
    nadie, y es mejor decirlo que inventar nodos.
    """
    global _cache_hitos
    if _cache_hitos is None:
        with open(RUTA_HITOS, encoding="utf-8", newline="") as f:
            _cache_hitos = [dict(fila) for fila in csv.DictReader(f)]
    propios = [h for h in _cache_hitos if h["tipo"] == tipo]
    return sorted(propios, key=lambda h: int(h["orden"]))


def tipos_con_hitos():
    """Los tipos para los que hay plantilla escrita."""
    if _cache_hitos is None:
        hitos("")
    return sorted({h["tipo"] for h in _cache_hitos})
