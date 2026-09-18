"""Los expedientes: la unidad a la que se subordina todo lo demás.

**No es un componente.** No hace trabajo del despacho: no clasifica, no calcula
ni redacta. Es el almacén de lo que los componentes miran y anotan, igual que
`sec.cuentas` es el almacén de las credenciales. Por eso vive fuera de los nueve
grupos.

Un expediente es **una instancia de un tipo documental** (`contestacion_demanda`,
`monitorio`, `hoja_encargo`...), y el tipo es lo que determina su ruta, sus
plazos y su canal de salida. El catálogo de los 89 tipos está en
`datos/tipos.csv`, sacado de la matriz de activación de `ARQUITECTURA.md` §5.

Lo que todavía **no** hay: los hitos. La barra de nodos con fechas que da sentido
a todo esto necesita, por cada tipo, la lista de hitos procesales que atraviesa
—emplazamiento, contestación, audiencia previa, vista, sentencia— y eso es
conocimiento jurídico que hay que escribir y revisar, no deducirlo del código.
Sin esa lista, un expediente sabe qué es pero no por dónde va.
"""
from .agent import Expedientes

__all__ = ["Expedientes"]
