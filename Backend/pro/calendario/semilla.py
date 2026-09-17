"""Carga de festivos establecidos a mano, con su prueba documental.

Esta es la fase de **establecimiento** del calendario: alguien lee los
boletines una vez, anota cada festivo con la cita literal del documento del que
sale, y este módulo lo verifica y lo mete en la base. La fase de
**actualización** --enterarse de que Andalucía ha rectificado en febrero-- es
otra cosa y no está escrita todavía.

Que lo lea una persona no es una carencia provisional a la espera de
automatizar. Para un trabajo que se hace una vez, escribir el automatismo cuesta
más que hacerlo. Lo que sí importa es que el resultado sea **auditable y
reproducible**, y de eso se ocupan tres cosas:

- El fichero de datos vive en el repositorio, con su historial. Cualquiera del
  despacho puede abrirlo y contrastar una fecha contra la URL que lleva al lado.
- Cada entrada trae la cita literal del boletín, en su idioma original. Sin
  cita no entra: es la regla que impide que una fecha «de memoria» acabe
  decidiendo un plazo.
- Nada se escribe sin pasar por `verificacion`, que no cree a nadie.

El fichero no necesita estar completo. Lo que falte queda `pendiente` en la
cobertura y el motor dará fecha prudente, que es la respuesta correcta a «no lo
sé» y la razón de que esto se pueda hacer municipio a municipio sin prisa.
"""
import json
from pathlib import Path

from . import verificacion

RUTA_DATOS = Path(__file__).parent / "datos" / "festivos_locales.json"

ESQUEMA = 1


def leer(ruta=RUTA_DATOS):
    """Lee el fichero de datos. Devuelve la lista de candidatos."""
    ruta = Path(ruta)
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if datos.get("esquema") != ESQUEMA:
        raise ValueError(
            f"{ruta.name} declara esquema {datos.get('esquema')} y este código "
            f"entiende el {ESQUEMA}."
        )
    return datos.get("festivos", [])


def cargar(cal, ruta=RUTA_DATOS, registro=print):
    """Verifica el fichero y escribe lo que pase. Devuelve un resumen.

    **Los rechazados no se escriben ni a medias.** Un candidato que no pasa la
    verificación deja su ámbito sin confirmar, y eso hace que el motor dé fecha
    prudente ahí. Es preferible a meter una fecha dudosa: lo peor que produce un
    hueco es un aviso de más; lo peor que produce un dato malo es un plazo
    perdido.
    """
    candidatos = leer(ruta)
    if not candidatos:
        registro(f"{Path(ruta).name} no tiene festivos todavía.")
        return {"aceptados": 0, "rechazados": [], "escritos": 0}

    aceptados, rechazados = verificacion.verificar_lote(candidatos, cal)
    for candidato, problemas in rechazados:
        registro(f"  ! {candidato.get('ambito')} {candidato.get('fecha')}: {'; '.join(problemas)}")

    version = cal.nueva_version(f"semilla de festivos locales ({len(aceptados)} entradas)")
    escritos = 0
    confirmados = set()
    for candidato in aceptados:
        fuente_id = cal.alta_fuente(
            candidato["ambito"],
            int(candidato["fecha"][:4]),
            candidato["fuente"],
            candidato["url"],
            candidato["url"],
        )
        if cal.anotar_festivo(
            candidato["ambito"], candidato["fecha"], candidato["computo"],
            candidato["nombre"], version, fuente_id,
        ):
            escritos += 1
        confirmados.add(
            (candidato["ambito"], int(candidato["fecha"][:4]), candidato["computo"], fuente_id)
        )

    # La cobertura se declara por ámbito, año y cómputo, y solo de lo que ha
    # entrado entero. Un municipio con un festivo aceptado y otro rechazado no
    # se confirma: lo que se sabe de él está incompleto.
    fallidos = {
        (c.get("ambito"), c.get("fecha", "0000")[:4], c.get("computo"))
        for c, _ in rechazados
    }
    motivos = {}
    for candidato, problemas in rechazados:
        clave = (candidato.get("ambito"), candidato.get("fecha", "0000")[:4],
                 candidato.get("computo"))
        motivos.setdefault(clave, []).extend(problemas)

    for ambito, anio, computo, fuente_id in confirmados:
        clave = (ambito, str(anio), computo)
        if clave in fallidos:
            # Una entrada rechazada es «se intento y no paso la verificacion»,
            # que no es lo mismo que «no se ha mirado»: queda `fallido` con el
            # motivo, para que se vea que hay algo que corregir en el fichero.
            registro(f"  · {ambito} {anio} {computo}: fallido, hay entradas rechazadas")
            cal.fijar_cobertura(ambito, anio, computo, "fallido", version, fuente_id,
                                detalle="; ".join(motivos.get(clave, [])[:3]))
            continue
        cal.fijar_cobertura(ambito, anio, computo, "confirmado", version, fuente_id)

    registro(
        f"{len(aceptados)} verificados, {len(rechazados)} rechazados, {escritos} nuevos "
        f"(versión {version})."
    )
    return {"aceptados": len(aceptados), "rechazados": rechazados, "escritos": escritos}
