"""El recolector: lo que va a los boletines y llena el calendario.

`pro.calendario` calcula plazos y no sabe de dónde salen los festivos; esto es
lo que los trae. AGENTES.md deja el hueco escrito al decir que el calendario
oficial «se da por resuelto: mantenerlo no es tarea de este sub-agente». Va
aparte del motor por tres razones que no son de estilo:

- **Corren en sitios distintos.** El motor toca expedientes y vive en el PC del
  letrado; el recolector solo lee boletines públicos y puede vivir en `maat`.
- **Corren en momentos distintos.** El motor, cada vez que llega una
  notificación; el recolector, de tanto en tanto y en segundo plano.
- **Y sobre todo fallan distinto.** Si un boletín rediseña su web, el
  recolector se rompe y el motor tiene que seguir calculando con lo que haya,
  marcando `provisional`. Si fueran el mismo proceso, un cambio de maquetación
  en Aragón dejaría al despacho sin poder calcular ningún plazo.

**La regla que ordena todo esto: un fallo nunca se traga.** Si no se consigue
leer una publicación, su cobertura queda `fallido` con el motivo y se sigue con
la siguiente. Lo que no puede pasar es que un boletín ilegible deje huecos que
el motor confunda con días hábiles, porque entonces el error aparece semanas
después en forma de plazo perdido y sin nada que lo explique.
"""
import hashlib

from . import boe, fuentes, madrid
from .db import COMPUTOS, SinPublicar

# Qué sabe leer el recolector hoy. La clave es (ámbito, boletín). Lo que no
# está aquí queda registrado como fuente pero sin extractor, y su cobertura no
# pasa de `pendiente`: la base sabe entonces que no lo ha leído, en vez de
# aparentar que ese sitio no tiene fiestas.
#
# El BOE va aparte del resto porque es el único con descubrimiento --hay que
# encontrar la resolución de cada año-- y el único que cubre muchos ámbitos de
# una vez. Los locales son todos de la misma forma: una URL estable, un fichero
# que se compara por huella y una lista de fiestas municipales.
EXTRACTORES = {("ES", "BOE"): boe}

LOCALES = [madrid]


def sembrar(cal):
    """Crea el árbol de ámbitos y registra las publicaciones. Es idempotente.

    Se puede llamar en cada recolección: no borra nada y solo refresca nombres
    y URL de búsqueda, que es lo único de aquí que cambia con el tiempo.
    """
    for id, tipo, nombre, padre in fuentes.ambitos():
        cal.alta_ambito(id, tipo, nombre, padre)
    registradas = 0
    for ambito, boletin, url in fuentes.publicaciones():
        # `anio=None`: es la fuente de entrada, la que no depende del año. La
        # publicación concreta de cada año se registra al encontrarla.
        cal.alta_fuente(ambito, None, boletin, url)
        registradas += 1
    return registradas


def recolectar(cal, anios, registro=print):
    """Pasada completa. Devuelve un resumen de lo hecho.

    `anios` suele ser `db.ventana()`. `registro` recibe líneas de texto: en la
    línea de órdenes es `print`, y desde la app será lo que pinte el progreso.
    """
    sembrar(cal)
    version = cal.nueva_version(f"recolección de {', '.join(str(a) for a in anios)}")
    # `declarados` lleva la cuenta de cada (ámbito, año, cómputo) sobre el que
    # ya se ha dicho algo en esta pasada. Es lo que impide que el barrido final
    # pise un veredicto más preciso: la resolución del BOE deja las diecinueve
    # comunidades en `sin_publicar` cuando el año todavía no ha salido, y sin
    # esto el barrido las degradaba a `pendiente`, borrando la diferencia entre
    # «no toca aún» y «hay algo que arreglar» justo donde más importa.
    resumen = {
        "version": version, "anotados": 0, "retirados": 0,
        "confirmados": [], "declarados": set(), "fallos": [],
    }

    for anio in anios:
        # El judicial va primero y no es indiferente: el calendario
        # administrativo de Estado y comunidades se deriva de la rejilla de
        # fiestas laborales (ver `boe.dias_inhabiles_age`), así que necesita
        # tenerla ya extraída.
        laborales = {}
        for computo in COMPUTOS:
            try:
                _recolectar_boe(cal, anio, computo, version, resumen, registro, laborales)
            except Exception as e:
                # Un extractor roto no puede tumbar la pasada entera: lo que
                # se haya recogido antes sigue siendo válido y lo que falla
                # queda marcado como no sabido.
                registro(f"  ! {anio} {computo}: {type(e).__name__}: {e}")
                resumen["fallos"].append((f"ES/{computo}", anio, str(e)))
                # `fallido`, no `pendiente`: se intento y reventó. Marcarlo
                # como pendiente lo haria indistinguible de una fuente que
                # nunca se ha escrito, y una regresion se quedaria ahi.
                for ambito in _ambitos_que_cubre(computo):
                    _declarar(cal, resumen, ambito, anio, computo, "fallido",
                              version, detalle=f"{type(e).__name__}: {e}")

        for modulo in LOCALES:
            try:
                _recolectar_local(cal, modulo, anio, version, resumen, registro)
            except SinPublicar as e:
                # No es un fallo: el año todavía no está publicado.
                registro(f"  · {modulo.AMBITO} {anio}: {e}")
                for computo in modulo.COMPUTOS:
                    _declarar(cal, resumen, modulo.AMBITO, anio, computo,
                              "sin_publicar", version)
            except Exception as e:
                registro(f"  ! {modulo.AMBITO} {anio}: {type(e).__name__}: {e}")
                resumen["fallos"].append((modulo.AMBITO, anio, str(e)))
                for computo in modulo.COMPUTOS:
                    _declarar(cal, resumen, modulo.AMBITO, anio, computo, "fallido",
                              version, detalle=f"{type(e).__name__}: {e}")

    _marcar_lo_no_leido(cal, anios, version, resumen, registro)
    return resumen


def _declarar(cal, resumen, ambito, anio, computo, estado, version,
              fuente_id=None, detalle=None):
    """Fija una cobertura y la apunta como ya dicha en esta pasada.

    Todo el recolector pasa por aquí en vez de llamar a `fijar_cobertura`
    directamente. La regla es «quien habla primero manda»: el extractor que
    llegó a mirar la publicación sabe más que el barrido final, que solo sabe
    que no hay extractor.
    """
    cal.fijar_cobertura(ambito, anio, computo, estado, version, fuente_id, detalle)
    resumen["declarados"].add((ambito, anio, computo))
    if estado == "confirmado":
        resumen["confirmados"].append((ambito, anio, computo))


def _recolectar_local(cal, modulo, anio, version, resumen, registro):
    """Una fuente de festivos locales: URL estable, se compara por huella.

    Los ámbitos que este módulo no declara cubrir no se tocan: se quedan como
    los deje `_marcar_lo_no_leido`. Que Madrid sepa sus fiestas judiciales no
    dice nada de su calendario administrativo, y darlo por confirmado sería
    afirmar algo que no se ha leído.
    """
    registro(f"{modulo.BOLETIN} {anio} ({modulo.AMBITO}): descargando...")
    crudo, url = modulo.descargar(anio)
    huella = hashlib.sha256(crudo).hexdigest()
    fuente_id = cal.alta_fuente(modulo.AMBITO, anio, modulo.BOLETIN, url, url, huella)

    extraidos = modulo.locales(crudo, anio)
    for computo in modulo.COMPUTOS:
        _sincronizar(
            cal, extraidos, computo, anio, version, fuente_id, resumen,
            alcance=[modulo.AMBITO],
        )
        _declarar(cal, resumen, modulo.AMBITO, anio, computo, "confirmado", version, fuente_id)
    registro(
        f"  · {len(extraidos)} fiestas locales: "
        + ", ".join(f"{f} {n}" for _, f, n in extraidos)
    )


def _recolectar_boe(cal, anio, computo, version, resumen, registro, laborales):
    registro(f"BOE {anio} ({computo}): buscando la resolución...")
    hallazgo = boe.localizar(anio, computo)
    if hallazgo is None:
        # No encontrarla no es un fallo si el año aún no ha llegado: las dos
        # resoluciones salen en el último trimestre del año anterior. Esa
        # diferencia es la que separa «hay que arreglar algo» de «todavía no
        # toca», y las dos dan fecha prudente igualmente.
        estado = "sin_publicar"
        registro(f"  · sin publicar todavía")
        for ambito in _ambitos_que_cubre(computo):
            _declarar(cal, resumen, ambito, anio, computo, estado, version)
        return

    crudo, arbol = boe.descargar_xml(hallazgo["url_xml"])
    huella = hashlib.sha256(crudo).hexdigest()
    fuente_id = cal.alta_fuente(
        "ES", anio, "BOE", fuentes.BOLETINES["ES"][0][1], hallazgo["url_xml"], huella
    )
    registro(f"  · {hallazgo['id']} publicado el {hallazgo['publicado']}")

    if computo == "judicial":
        extraidos = boe.fiestas_laborales(arbol, anio)
        laborales[anio] = extraidos
    else:
        if anio not in laborales:
            # Sin la rejilla laboral no se puede derivar el administrativo, y
            # inventarlo sería peor que no tenerlo.
            raise ValueError(
                "No hay rejilla de fiestas laborales de la que derivar el "
                "calendario administrativo: la resolución judicial no se leyó."
            )
        extraidos = boe.dias_inhabiles_age(arbol, anio, laborales[anio])

    _sincronizar(
        cal, extraidos, computo, anio, version, fuente_id, resumen,
        alcance=_ambitos_que_cubre(computo),
    )
    for ambito in _ambitos_que_cubre(computo):
        _declarar(cal, resumen, ambito, anio, computo, "confirmado", version, fuente_id)
    registro(f"  · {len(extraidos)} festivos")


def _ambitos_que_cubre(computo):
    """Qué ámbitos deja confirmados la resolución estatal de cada cómputo.

    Las dos confirman el Estado y las diecinueve comunidades: la de fiestas
    laborales porque trae su rejilla, y la de la AGE porque su apartado segundo
    remite a esos mismos días. Lo que ninguna de las dos cubre es el nivel
    local, que va boletín por boletín.
    """
    return ["ES"] + list(fuentes.COMUNIDADES)


def _sincronizar(cal, extraidos, computo, anio, version, fuente_id, resumen, alcance):
    """Escribe lo extraído y retira lo que la publicación ya no trae.

    Retirar importa tanto como anotar: cuando una comunidad rectifica, el día
    que se cae tiene que dejar de contar, pero sin borrarse, para que un plazo
    calculado antes de la corrección se pueda seguir explicando.

    `alcance` son los ámbitos sobre los que esta publicación tiene autoridad, y
    es obligatorio pasarlo. Una fuente solo puede retirar festivos de lo que
    ella misma publica: si el fichero de Madrid pudiera retirar en `ES`, su
    lista de dos fiestas locales borraría el calendario nacional entero, y lo
    haría en silencio, porque retirar no es un error.
    """
    vigentes = set()
    for ambito, fecha, nombre in extraidos:
        if cal.anotar_festivo(ambito, fecha, computo, nombre, version, fuente_id):
            resumen["anotados"] += 1
        vigentes.add((ambito, fecha))

    desde, hasta = f"{anio}-01-01", f"{anio}-12-31"
    for ambito in set(alcance):
        for fecha in cal.festivos_de(ambito, computo, desde, hasta, version):
            if (ambito, fecha) not in vigentes:
                if cal.retirar_festivo(ambito, fecha, computo, version):
                    resumen["retirados"] += 1


def _marcar_lo_no_leido(cal, anios, version, resumen, registro):
    """Deja constancia de las publicaciones que aún no se saben leer.

    Es la mitad honesta del recolector. Sin esto, los diez municipios y el
    calendario administrativo de las comunidades quedarían sin fila de
    cobertura y, aunque el motor los trataría igual de provisionales, nadie
    vería en la pantalla de mantenimiento *cuántas* fuentes faltan ni cuáles.
    """
    sin_extractor = [
        (ambito, boletin)
        for ambito, boletin, _ in fuentes.publicaciones()
        if (ambito, boletin) not in EXTRACTORES
    ]
    # Un ámbito puede tener varias publicaciones (Castilla y León, nueve), y
    # su cobertura se declara una sola vez.
    ambitos_sin_leer = sorted({ambito for ambito, _ in sin_extractor})
    municipios = list(fuentes.MUNICIPIOS) + list(fuentes.ISLAS)
    for anio in anios:
        for computo in COMPUTOS:
            for ambito in municipios + ambitos_sin_leer:
                # Solo lo que nadie ha dictaminado ya: `pendiente` significa
                # aqui «no se ha intentado», que es lo cierto -- no hay
                # extractor para esa fuente todavia.
                if (ambito, anio, computo) not in resumen["declarados"]:
                    _declarar(cal, resumen, ambito, anio, computo, "pendiente", version)
    registro(
        f"{len(sin_extractor)} publicaciones registradas sin extractor todavía; "
        f"{len(municipios)} municipios e islas sin festivos locales."
    )
