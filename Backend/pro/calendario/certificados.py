"""Confianza TLS para los boletines de la administración española.

Varias administraciones no usan una CA comercial sino la del propio sector
público: el Gobierno Vasco emite con **IZENPE**, la Generalitat Valenciana con
**ACCV**, y hay más. Esos certificados son legítimos, pero sus raíces no están
en el almacén que trae Python, así que descargar de ellos falla con
`CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`. El
BOE no da el problema porque la FNMT sí está incluida.

**El atajo que no se toma.** Ese error se calla en una línea, desactivando la
verificación. En cualquier otro módulo sería una decisión discutible; aquí es
inadmisible, y conviene dejar escrito por qué: quien pudiera interponerse en
esa conexión elegiría qué días son inhábiles. No provocaría un error ni un
aviso, provocaría un plazo mal calculado con toda la apariencia de estar bien,
que es exactamente el fallo contra el que está diseñado el resto del módulo.
Un calendario que se descarga sin verificar no es un calendario fiable, y el
sub-agente entero se apoya en que lo sea.

**Lo que se hace en su lugar.** Se parte del almacén del sistema y se le añaden
las raíces que el despacho haya puesto en `~/.misyks/ca/*.pem`. Añadir una raíz
concreta y comprobable es muy distinto de aceptar cualquiera: sigue habiendo
verificación, y sigue fallando si alguien se interpone. Si falta la raíz, la
descarga falla, la cobertura queda `fallido` con el motivo y el sistema da
fecha prudente en vez de datos de origen dudoso.

Las raíces se descargan de la sede de cada autoridad y se comprueba su huella
antes de dejarlas aquí; eso es trabajo de instalación, no del programa, y está
en `INSTALACION.md`.
"""
import ssl
from pathlib import Path

CA_DIR = Path.home() / ".misyks" / "ca"


def contexto():
    """Contexto TLS con el almacén del sistema más las raíces del despacho.

    Nunca devuelve un contexto sin verificar: si no hay raíces añadidas, se
    comporta como el de por defecto, que es lo correcto para el BOE y para
    cualquier boletín con CA comercial.
    """
    ctx = ssl.create_default_context()
    if CA_DIR.is_dir():
        for pem in sorted(CA_DIR.glob("*.pem")):
            try:
                ctx.load_verify_locations(cafile=str(pem))
            except ssl.SSLError as e:
                # Un PEM corrupto no puede impedir que se lean los boletines
                # que sí funcionan con el almacén del sistema.
                raise ValueError(f"La raíz {pem.name} no se ha podido cargar: {e}") from e
    return ctx


def diagnostico(error):
    """Traduce un fallo de verificación a algo accionable.

    El mensaje de Python («self-signed certificate in certificate chain»)
    sugiere que el servidor está mal configurado, que casi nunca es el caso:
    lo normal es que falte la raíz de una CA pública española.
    """
    if "CERTIFICATE_VERIFY_FAILED" not in str(error):
        return None
    return (
        "No se ha podido verificar el certificado del boletín. Casi siempre es "
        "que su autoridad de certificación es del sector público español "
        "(IZENPE en Euskadi, ACCV en la Comunitat Valenciana) y su raíz no "
        f"viene con Python. Descárgala de la sede de la autoridad, comprueba su "
        f"huella y déjala en {CA_DIR}. No desactives la verificación."
    )
