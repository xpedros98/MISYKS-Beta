# COMPETENCIA

Quién más está haciendo esto, qué tienen resuelto que nosotros no, y qué nos
dice eso sobre dónde conviene gastar el esfuerzo. Buscado el 17/09/2026.

**Para qué sirve este documento.** No es vigilancia comercial: es para no
reinventar piezas que ya están resueltas fuera y, sobre todo, para saber cuáles
de nuestras decisiones de diseño son de verdad nuestras y cuáles son lo que
hace todo el mundo. Cuando algo de aquí cambie de precio, de dueño o de
capacidades, se actualiza este fichero; si queda viejo, engaña más que informa.

**Aviso sobre las fuentes.** Los precios de Veredicta y Norbia salen de sus
propias páginas y son verificables. Las cifras de ROI y de horas ahorradas que
circulan en los blogs de consultoras españolas (Upliora, Flowmatic, Iazub) son
material de marketing sin metodología publicada: se recogen aquí porque marcan
el discurso con el que un cliente nos va a comparar, no porque las demos por
buenas.

---

## 1. Veredicta — el que más se nos parece

<https://veredicta.legal/>

Se define como «el sistema operativo para despachos en España». Quince «módulos» en
su terminología —áreas funcionales, no lo que aquí llamamos módulo— bajo un solo acceso, servidores en España, anonimización antes de pasar nada
por el modelo y traza de auditoría completa. Integra LexNET, CENDOJ,
Verifactu/SII, AutoFirma, FacturaE, Gmail y Stripe.

Lo relevante no es el producto sino que **sus tres agentes de primer nivel son
uno a uno los nuestros**:

| Veredicta | MISYKS |
| --- | --- |
| Triaje de correo: clasifica remitente, asunto y adjuntos, y propone expediente | `sec.mail` |
| Plazos: lee la resolución, calcula el plazo y aplica el calendario autonómico y local | `pro.calendario` |
| Investigación en CENDOJ: construye la consulta desde los hechos y ordena por relevancia | grupo de investigación |

**Lo que tienen y a nosotros nos falta: la autonomía como dial, no como
constante.** Cada agente corre en uno de cuatro niveles —`shadow` (observa y
calla), `suggest` (propone a una bandeja; es el de por defecto), `draft`
(genera el documento entero) y `execute` (solo acciones reversibles de bajo
riesgo)—. Nosotros tenemos lo mismo en COMPONENTES.md, pero escrito como
restricción fija por componente. La diferencia tiene consecuencia comercial: ellos
le dejan al despacho decidir cuánta correa suelta y pueden entrar en un cliente
desconfiado en modo `shadow`; nosotros obligamos a aceptar de entrada el nivel
que decidimos al diseñar. Merece una conversación, porque convertir nuestras
restricciones en un dial sin romper lo que protegen no es trivial: son
invariantes, y un dial mal puesto las deroga en silencio.

Precios: Solo 59 €/mes (1-2 usuarios, 200 expedientes), Despacho 149 €/mes
(hasta 5, expedientes ilimitados), Firma 299 €/mes (hasta 15), y Enterprise a
medida con opción de infraestructura privada. 17 % de descuento anual, 20 % a
colegiados. Está en producción, no en beta.

## 2. Norbia Legal — el que nos gana en `pro.calendario`

<https://norbialegal.com/>

Automatiza el circuito administrativo completo: del documento judicial recibido
hasta avisar al cliente y facturar. Backend en Supabase, infraestructura en la
UE, cifrado AES-256 con clave por despacho.

**Nos llevan ventaja justo en la pieza que más nos está costando.** Cubren más
de 93 municipios de las 17 comunidades más Ceuta y Melilla, con reglas por
jurisdicción (civil, penal, contencioso y social) y agosto inhábil por el art.
183 LOPJ. Dos detalles delatan que llevan tiempo peleándose con esto de verdad,
y los dos son cosas que nosotros no hemos escrito todavía:

- Avisan **a las 14:00 antes del corte de LexNET**, no solo a T-7, T-3 y T-1.
  Es el aviso que de verdad salva un plazo.
- Calculan solos el plazo de **tres días de acceso del art. 162.2 LEC**, que es
  el que convierte una notificación en una fecha.

Anonimizan once tipos de dato personal antes de que el texto llegue al modelo y
reidentifican solo en su servidor. Es exactamente el planteamiento de dos capas
que anotamos el 16/09.

Precio: 120 €/abogado/mes (tarifa fundador; la normal es 175 €) más 600 € de
implantación, +55 € el segundo abogado y +45 € del tercero en adelante. Sin
permanencia. **Cobran el doble que Veredicta por hacer menos cosas**, lo que
sugiere que lo que venden no es la IA sino la fiabilidad del cómputo. Es una
señal de mercado que nos conviene: el calendario es el activo, no el adorno.

## 3. El resto del mercado español

- **LexNetAI** (<https://www.lexnetai.com/>) y **Kmaleon / MN Program**
  (<https://www.mnprogram.com/funcionalidades/lexnet/>), además de los clásicos
  LexON y Kleos: gestión de expedientes con IA encima. No hay arquitectura de
  agentes, hay funciones.
- **Consultoras montando lo mismo sobre n8n**: Upliora
  (<https://www.upliora.es/blog/ia-para-procuradores-despachos-procuradoria-2026>),
  Flowmatic
  (<https://flowmatic.es/automatizacion/despachos-abogados-expedientes-ia/>).
  Venden el flujo «leer LexNET, extraer el plazo, avisar a los 7, 3 y 1 días»
  sin escribir código. **Es la alternativa barata contra la que nos van a
  comparar**, y conviene saber qué le falta: no hay verificación del dato ni
  procedencia, así que si el modelo lee mal una fecha el flujo la propaga tal
  cual. Ahí está la diferencia con lo que hace `verificacion.py`, y hay que
  saber contarla.
- **Cómputo de plazos ya regalado**: la calculadora de Estudia Derecho, **con
  API pública** (<https://estudiaderecho.es/calculadora-plazos-procesales/>),
  MetaJurídico y contadordias.net. El cómputo por sí solo no es producto.

## 4. Internacional

- **Legora** publicó en enero *2026: The Year of Agents in Legal AI*
  (<https://legora.com/blog/2026-the-year-of-agents-in-legal-ai>): misma tesis
  que la nuestra, a escala enterprise. En junio de 2026 pasó su nivel Agent Pro
  a precio por consumo.
- **Harvey**: no publica precios; la prensa del sector lo sitúa en 1.000-2.000
  $/usuario/mes en mid-market y 100-200 $ a escala Am Law 100. RAG contra
  LexisNexis, EDGAR y EUR-Lex.
- **Clio Duo**: 49-59 $/mes sobre la base de Clio (39-129 $). Ya trae
  extracción de plazos de documentos judiciales. Marca el techo de lo
  accesible: por debajo de 100 $/mes con todo incluido.

Ninguno toca España: ni LexNET, ni CENDOJ, ni festivos locales, ni cómputo
LOPJ. El derecho español es la barrera de entrada que nos protege de ellos y la
que protege a Veredicta y Norbia de nosotros.

## 5. Open source

- **anylegal-oss** (<https://github.com/anylegal-ai/anylegal-oss>) — el más
  interesante para nosotros: harness de agentes legales con licencia MIT que
  **carga ficheros `SKILL.md` en formato Anthropic sin modificar**. Multi-LLM
  vía OpenRouter o self-hosted por API compatible con OpenAI.
- **lawglance** (<https://github.com/lawglance/lawglance>) — RAG con LangGraph,
  hoy un solo agente con herramientas, con plan declarado de pasar a equipo
  multi-agente.
- **lq-ai** (<https://github.com/Flosters/lq-ai>) — self-hosted, expedientes
  como ámbito, citas verificables carácter a carácter, corre contra Ollama.
- **OpenContracts** (<https://github.com/Open-Source-Legal/OpenContracts>) —
  gestión documental para agentes, MIT.
- **local-legal-ai** (<https://github.com/jashankish/local-legal-ai>) — Q&A
  documental sin salir de la máquina.

Todos anglosajones y todos sobre contratos o consulta documental. Ninguno hace
plazos.

## 6. Dónde queda MISYKS

Lo que no hace nadie, y por tanto lo que hay que cuidar:

- **Frontend nativo.** Todos los demás son SaaS web sin excepción.
- **Local-first de verdad.** El ángulo de que el dato no salga de la máquina
  solo lo tocan los proyectos open source anglosajones, que ignoran España por
  completo. Veredicta y Norbia dicen «servidores en España», que es otra cosa.
- **Arquitectura publicada.** Nadie describe 56 componentes con restricciones
  declaradas uno a uno. Es nuestra ventaja de diseño y también nuestra deuda:
  hoy hay uno implementado.

Y dónde estamos en desventaja clara: **el calendario local**. Norbia y
Veredicta ya lo tienen, y eso es un foso de datos, no de código: no se salva
programando mejor, se salva recolectando. Por eso importa la sección siguiente.

## 7. ¿Se pueden aprovechar sus calendarios?

**Los de Norbia y Veredicta, no.** No hay API pública ni conjunto de datos de
ninguno de los dos. Sacar el calendario de dentro de su producto de pago choca
con sus condiciones de uso y con el derecho *sui generis* de base de datos del
art. 133 TRLPI, que protege exactamente la inversión en recopilar. No es vía.

**Las fuentes oficiales, sí, y más de lo que asume `fuentes.py`.** Ese fichero
da por supuesto que los festivos locales solo viven en 29 boletines que hay que
leer a mano. Era cierto de los boletines, pero varias comunidades publican
*además* el mismo calendario como dato abierto y estructurado:

- **Euskadi** es el caso ejemplar: los **tres niveles** —comunidad, territorio
  histórico y municipio— en JSON, ICS, CSV, XML y XLSX, licencia CC-BY-4.0,
  actualización anual y API propia. La URL del JSON es estable y solo cambia el
  año: `https://opendata.euskadi.eus/contenidos/ds_eventos/calendario_laboral_<año>/opendata/calendario_laboral_<año>.json`.
  **Sustituye por sí solo a nuestros tres extractores pendientes de BOTHA, BOB
  y BOG.**
- **Castilla-La Mancha**: 2020-2026 en CSV, ODS y JSON.
- **Galicia** y **Ayuntamiento de Madrid**: ICS; Madrid además CSV y XLSX.
- **BOE**: tiene API REST documentada con OpenAPI 3.1
  (<https://www.boe.es/datosabiertos/api/api.php>) para sumarios y legislación
  consolidada, más estable que entrar por `buscar/boe.php` como hace `boe.py`.
- **ApasPowre/calendario-laboral-espana**
  (<https://github.com/ApasPowre/calendario-laboral-espana>): raspa BOE y
  boletines autonómicos para más de 2.500 municipios. Referencia de cómo han
  resuelto boletines que a nosotros se nos atragantan.

**Dos cautelas antes de tocar nada.** La primera es jurídica: «calendario
laboral» no es «días inhábiles». Son cosas distintas —la resolución de días
inhábiles de la AGE computa a efectos de la Ley 39/2015 y el cómputo judicial
va por LOPJ y LEC—, así que un conjunto de datos de fiestas laborales es
*insumo* de nuestros cómputos y nunca la respuesta. La tabla `COMPUTOS` ya
distingue esto y la procedencia tiene que distinguirlo igual.

La segunda es de diseño y es la que de verdad frena: `verificacion.py` exige
que todo candidato traiga **la cita literal del boletín**, y un JSON de dato
abierto no trae cita. Enchufar un canal estructurado obliga a elegir entre
saltarse las cinco comprobaciones para esa fuente o fabricar una cita, que es
peor. La salida razonable es no tratar el dato abierto como origen sino como
**segunda opinión**: el festivo entra por el boletín con su cita, y el conjunto
de datos sirve para detectar discrepancias y huecos. Eso daría cobertura rápida
en Euskadi sin bajar el listón que nos hemos puesto.
