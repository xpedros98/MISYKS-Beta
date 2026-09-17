"""Confianza TLS para los boletines de la administración española.

Varias administraciones emiten con la CA del propio sector público --IZENPE en
el Gobierno Vasco, ACCV en la Generalitat Valenciana, Firmaprofesional en el
Ajuntament de Barcelona-- cuyas raíces no vienen con Python. Descargar de ellos
falla con `CERTIFICATE_VERIFY_FAILED`, aunque el certificado sea legítimo. El
BOE no da el problema porque la FNMT sí está incluida.

**Ese error no se calla desactivando la verificación.** Quien pudiera
interponerse en la conexión elegiría qué días son inhábiles, y no daría un
error sino un plazo mal calculado con apariencia de correcto. En su lugar se
añaden raíces concretas en `~/.misyks/ca/*.pem`: sigue habiendo verificación, y
sigue fallando si alguien se interpone. Si falta la raíz, la cobertura queda
`fallido` con el motivo y el sistema da fecha prudente.

Descargar esas raíces de la sede de su autoridad y comprobar su huella es
trabajo de instalación, no del programa: `RECOLECCION.md`.
"""
import ssl
from pathlib import Path

CA_DIR = Path.home() / ".misyks" / "ca"


def contexto():
    """Contexto TLS con el almacén del sistema más las raíces del despacho.

    Nunca devuelve un contexto sin verificar. Sin raíces añadidas se comporta
    como el de por defecto, que basta para el BOE y para cualquier boletín con
    CA comercial.
    """
    ctx = ssl.create_default_context()
    if CA_DIR.is_dir():
        for pem in sorted(CA_DIR.glob("*.pem")):
            try:
                ctx.load_verify_locations(cafile=str(pem))
            except ssl.SSLError as e:
                # Se para en seco en vez de saltarse el fichero: alguien puso
                # esa raíz ahí esperando cobertura, y seguir sin ella daría por
                # hecho que se tiene algo que no se tiene.
                raise ValueError(f"La raíz {pem.name} no se ha podido cargar: {e}") from e
    return ctx


def diagnostico(error):
    """Traduce un fallo de verificación a algo accionable, o None si es otra cosa.

    El mensaje de Python («self-signed certificate in certificate chain»)
    sugiere un servidor mal configurado, y casi nunca lo es.
    """
    if "CERTIFICATE_VERIFY_FAILED" not in str(error):
        return None
    return (
        "No se ha podido verificar el certificado del boletín. Casi siempre es "
        "que su autoridad de certificación es del sector público español "
        "(IZENPE, ACCV, Firmaprofesional) y su raíz no viene con Python. "
        f"Descárgala de la sede de la autoridad, comprueba su huella y déjala "
        f"en {CA_DIR}. No desactives la verificación."
    )
