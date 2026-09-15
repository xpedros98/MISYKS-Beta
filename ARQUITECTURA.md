# Arquitectura de agentes y tipos documentales

> Modelo de organización del enrutado de MISYKS.
> Última actualización: 2026-09-15

**Naturaleza del documento.** Diseño completo del sistema de agentes. No se
distingue entre lo implementado y lo pendiente salvo en §8.3, que recoge el estado
real del código.

**Modelo.** Nueve grupos, no nueve agentes. Cada grupo es una familia de agentes muy
acotados, cada uno con una sola tarea y un contrato estrecho. El grupo define el
papel; los sub-agentes hacen el trabajo. Son 56 sub-agentes:

```
procesal 12 · redactor 6 · critico 6 · calculadora 6 · secretario 6
archivador 5 · investigador 5 · probatorio 5 · estratega 5
```

**Stack.** Backend Python, frontend Rust con `iced` (arquitectura Elm). Cada
sub-agente es un módulo bajo `Backend/<grupo>/<nombre>/`, con la misma anatomía:
`agent.py` expone la interfaz al resto del sistema, y detrás quedan el cliente del
canal, el parser, la base y la configuración.

**Convención de nombres.** `<grupo>.<nombre>` en el diseño, `Backend/sec/mail/` en
disco. El sub-agente de correo es **`sec.mail`**.

---

## 1 · Los nueve grupos

### Cuatro familias por naturaleza de la decisión

Lo que los diferencia no es el dominio jurídico sino **qué tipo de decisión toman**,
y eso determina si pueden equivocarse en silencio.

| familia | grupos | fallo típico |
|---|---|---|
| **Deterministas** | `procesal` · `calculadora` | ruidoso — se ve enseguida |
| **Extractivos** | `secretario` · `archivador` · `estratega` | **silencioso** — se propaga |
| **Evaluativos** | `probatorio` · `investigador` · `critico` | sesgado — cuesta detectar |
| **Generativo** | `redactor` | visible — lo lee un humano |

Los extractivos son los peligrosos: leen mal un dato y todo lo posterior hereda el
error sin avisar. De ahí la regla de diseño que comparten: **ante la duda devuelven
candidatos, no una respuesta**.

---

### SECRETARIO · despacho
El canal con **el mundo del despacho**: correo, agenda y avisos. No conoce los
canales procesales —LexNET, registro, notaría— que pertenecen a `procesal`. Su
competencia es lo que entra y sale por el correo del letrado, y lo que hay que
recordar.

| sub-agente | tarea |
|---|---|
| `sec.mail` | Gmail sobre IMAP. **Receptor**. Implementado |
| `sec.ocr` | procesa documentos fotografiados |
| `sec.clasificador` | a partir del resumen de `sec.mail`, determina clase y etiquetas |
| `sec.agenda` | reuniones, juicios y plazos; recibe estos últimos de `procesal` |
| `sec.notificador` | muestra avisos y los enumera en un log |
| `sec.entrega` | conexión al correo. **Emisor**: firma y envío a compañeros |

**Contrato entrada:** `{cuenta}` → `{documento, resumen, clase, etiquetas[]}`
**Contrato salida:** `{documento, destinatario, motivo}` → `{enviado, retorno_esperado?}`

`sec.mail` y `sec.entrega` son el mismo canal en direcciones opuestas, separados
porque fallan distinto: recibir mal cuesta una reclasificación, enviar mal puede
significar mandar el documento de un cliente a otro.

### ARCHIVADOR · estructura
Convierte un documento en una posición dentro del despacho.

| sub-agente | tarea |
|---|---|
| `arc.metadatos` | nº de procedimiento, órgano, autos, fecha |
| `arc.partes` | demandante, demandado, procurador, letrado contrario |
| `arc.emparejador` | ¿a qué expediente pertenece? devuelve candidatos |
| `arc.nomenclador` | nombra y ubica el fichero según convención del despacho |
| `arc.deduplicador` | hash — detecta el mismo documento llegado por dos vías |

**Contrato:** documento → `{expediente_id, metadatos, ruta, requiere_revision, candidatos[]}`

### PROCESAL · tiempo y forma
**Valida al entrar, verifica antes de salir y posee los canales procesales.** Decide si hay tiempo, si faltan requisitos y a qué destino corresponde;
el envío lo ejecuta el secretario. Determinista de punta a punta.

*Puerta — justo después de la entrada*

| sub-agente | tarea |
|---|---|
| `pro.calendario` | días hábiles, festivos locales, agosto |
| `pro.caducidad` | plazos perentorios por tipo de acto |
| `pro.prescripcion` | plazos sustantivos; en algunos tipos, por partida |
| `pro.procedibilidad` | requisitos previos: conciliación, vía administrativa, requerimiento |

*Verificación — justo antes de la salida*

| sub-agente | tarea |
|---|---|
| `pro.plazo-vivo` | ¿sigue en plazo ahora? el pipeline ha consumido días |
| `pro.forma` | requisitos formales de presentación para ese órgano y destino |
| `pro.destino` | determina por qué canal debe salir |

**Contrato puerta:** `{tipoActo, fechaActo}` → `{fecha_limite, franja, bloqueo, requisitos_pendientes}`
**Contrato verificación:** `{documento, expediente}` → `{en_plazo, defectos_formales[], destino}`

### INVESTIGADOR · derecho

| sub-agente | tarea |
|---|---|
| `inv.normativa` | BOE: artículo exacto y vigencia a la fecha del hecho |
| `inv.jurisprudencia` | CENDOJ, filtrado por órgano e instancia |
| `inv.convenio` | convenio colectivo aplicable por sector y provincia |
| `inv.doctrina` | criterio administrativo y doctrinal |
| `inv.citas` | ¿existe la referencia y dice lo que se le atribuye? |

**Contrato:** `{consulta, tipo_documento}` → `{artículos[], resoluciones[]}` con cita comprobable

### PROBATORIO · prueba

| sub-agente | tarea |
|---|---|
| `pru.inventario` | qué material hay y en qué soporte |
| `pru.admisibilidad` | licitud y forma de obtención |
| `pru.autenticidad` | acta notarial, cadena de custodia, metadatos |
| `pru.suficiencia` | ¿sostiene la pretensión o se queda corta? |
| `pru.carencias` | qué falta y cómo obtenerlo a tiempo |

**Contrato:** `{material, tipo_proceso}` → `{estrategia, señalar_al_letrado}`

Único grupo que **interrumpe al humano por iniciativa propia**.

### CALCULADORA · números
Determinista. Toda cifra que se defiende ante un juez sale de una función auditable;
el redactor escribe alrededor del número, nunca lo produce.

| sub-agente | tarea |
|---|---|
| `cal.antiguedad` | cómputo de la relación, con interrupciones |
| `cal.indemnizacion` | por tipo de extinción, con tramos y topes |
| `cal.cantidades` | nóminas, horas extra, finiquito, rentas |
| `cal.intereses` | legal, de mora, procesal |
| `cal.costas` | según cuantía y cauce |
| `cal.cuantia` | determina el cauce procesal y la postulación |

**Contrato:** `{campos, fechas}` → `{importe, desglose}`

### ESTRATEGA · adversario y decisión
Absorbe el análisis del escrito contrario y toda la capa de predicción. El análisis
del adversario es el medio; la recomendación es el fin.

| sub-agente | tarea |
|---|---|
| `est.contrario` | descompone el escrito ajeno en argumentos rebatibles |
| `est.citas-contrario` | verifica si las citas del adversario existen y sostienen lo que dice |
| `est.debilidades` | del caso propio, antes de que las encuentre el otro |
| `est.simulador` | escenarios y coste esperado de cada vía |
| `est.recomendador` | litigar, transigir o desistir |

**Contrato:** `{escrito_ajeno?, expediente}` → `{argumentos[], debilidades[], recomendación}`

El objeto de `est.contrario` cambia según la ruta —una demanda, una sentencia, un
acto administrativo— y eso son tres prompts distintos, no uno parametrizado.

### REDACTOR · producción

| sub-agente | tarea |
|---|---|
| `red.estructura` | esqueleto según tipo documental |
| `red.hechos` | relato numerado (PRIMERO.-, SEGUNDO.-) |
| `red.fundamentos` | con las citas que entrega el investigador |
| `red.petitorio` | SUPLICO según tipo |
| `red.contractual` | clausulado — documentos que no van a juzgado |
| `red.tramite` | escritos cortos de plantilla |

**Contrato:** `{contexto, tipo_documento, datos}` → documento

Regla dura: **nunca deja un placeholder vacío**. Si falta un dato, se pide.

### CRITICO · control

| sub-agente | tarea |
|---|---|
| `cri.formal` | requisitos tasados por tipo, como lista cerrada |
| `cri.citas` | ¿las citas del propio escrito existen? |
| `cri.coherencia` | hechos vs fundamentos vs suplico |
| `cri.cruzado` | coherencia **entre** documentos de un mismo expediente |
| `cri.abusividad` | cláusulas — pregunta distinta: no «¿convence?» sino «¿es válido?» |
| `cri.riesgo` | exposición del cliente y del letrado |

**Contrato:** `{contenido, tipo_documento}` → `{veto|visto_bueno, defectos[]}`

---

### Middleware transversal

`anonimizar` no es un grupo: es un filtro que atraviesa a todos. Seudonimiza antes
de que nada salga hacia un modelo externo y reinserta los datos reales en local al
redactar. Obligatorio en penal, familia y todo lo que toque salud.

### La capa de autoridad

Es lo que convierte nueve grupos en un sistema: no todos pesan igual, y alguno tiene
que poder parar a los demás.

| nivel | grupos | puede |
|---|---|---|
| **Bloquean** | `procesal`, `probatorio` | detener la ruta antes de gastar nada |
| **Interrumpen** | `probatorio`, `secretario` | crear tarea urgente para el letrado |
| **Condicionan** | `investigador`, `estratega`, `archivador` | alimentar a otros; su error se propaga |
| **Produce** | `redactor` | generar contenido, nunca decidir |
| **Veta** | `critico` | devolver el trabajo antes de la salida |

### Carga sobre el catálogo (89 tipos)

```
secretario 89 · procesal 89 · archivador 89 · redactor 89 · critico 89
investigador 77 · probatorio 72 · estratega 66 · calculadora 51
```
*(siempre + condicional)*

**Cinco grupos son universales y cuatro son enrutables** — y los cuatro enrutables
son exactamente el bloque de análisis. Entrada, tiempo, estructura, producción y
control ocurren siempre; lo que cambia de un tipo a otro es qué hay que analizar.
Ahí está todo el margen de coste.

---

## 2 · Detalle de sub-agentes

Cada entrada sigue la misma plantilla: qué hace, su contrato, las reglas de dominio
que debe respetar, cómo falla y de qué depende. Un sub-agente está bien acotado
cuando puede fallar solo y verificarse solo.

---

### 2.1 · SECRETARIO — 6 sub-agentes

La capa del despacho. Sabe recibir, clasificar, recordar y enviar; no sabe de plazos
ni de derecho, y no toca ningún canal procesal.

**`sec.mail`** — receptor · **implementado**
Gmail sobre IMAP, base local cifrada con SQLCipher.

- **Contrato:** `{cuenta_imap, ventana}` → `{mensajes[], adjuntos[], resumen}`
- **Reglas:**
  - IMAP y no POP: el correo permanece en el servidor y el letrado lo sigue viendo
    desde sus propios dispositivos. El agente lee, no vacía.
  - **Idempotencia por `Message-ID`**: al reconectar no puede reprocesar lo ya visto.
    Sin esto, una caída de red duplica expedientes.
  - Separa cuerpo y adjuntos como documentos distintos, y **desciende por los
    reenvíos anidados**: el documento relevante suele ir dentro de un forward, no en
    el primer nivel.
  - Conserva cabeceras como metadato probatorio: fecha de recepción y remitente.
  - Produce el **resumen** que consume `sec.clasificador`. Extraer adjuntos ocurre
    antes de resumir, nunca después.
- **Falla si:** reprocesa tras reconectar; pierde el adjunto anidado; resume antes de
  extraer.
- **Necesita:** credenciales (contraseña de aplicación u OAuth) e índice de
  `Message-ID` procesados.

**`sec.ocr`** — documentos fotografiados
No escaneados: **fotografiados**. El cliente manda la foto del burofax con el móvil,
torcida y con reflejo.

- **Contrato:** `{imagenes[]}` → `{texto, confianza_por_bloque, avisos[]}`
- **Reglas:**
  - Confianza **por bloque**, no global. Una media del 95 % puede esconder un número
    de autos ilegible, y ese dato contamina al `archivador` entero.
  - Umbral más estricto para **cifras y fechas** que para texto corrido: un dígito mal
    leído en un importe o en una fecha de notificación es un error caro.
  - Corrige perspectiva y detecta páginas fotografiadas **fuera de orden**.
  - Ante una zona ilegible, la marca. Nunca la completa por inferencia.
- **Falla si:** devuelve confianza global; adivina un dígito en silencio.

**`sec.clasificador`** — clase y etiquetas

- **Contrato:** `{resumen, metadatos_adjuntos}` → `{clase, etiquetas[], confianza, candidatos[]}`
- **Reglas:**
  - Trabaja sobre el **resumen** de `sec.mail`, no sobre el documento completo: es
    la decisión que lo hace barato. A cambio, cuando la confianza es baja debe poder
    **escalar y leer el original** antes de decidir.
  - Ante la duda devuelve `candidatos[]`, no una clase. Es la primera barrera contra
    el error silencioso, que es el modo de fallo característico de todo el bloque
    extractivo.
  - **Clase y etiquetas no son lo mismo:** la clase determina por qué ruta entra el
    documento; las etiquetas sirven para recuperarlo después. Una decide, la otra
    indexa.
- **Falla si:** clasifica con confianza desde un resumen que omitió el dato clave.

**`sec.agenda`** — reuniones, juicios y plazos

- **Contrato:** `{eventos[], plazos_de_procesal[]}` → `{agenda, conflictos[]}`
- **Reglas:**
  - **No calcula plazos: los recibe.** `procesal` computa, `sec.agenda` anota.
    Duplicar el cálculo aquí garantiza que las dos versiones diverjan.
  - Tres clases de entrada con naturaleza distinta: reuniones (internas, movibles),
    juicios y vistas (externas, fijas) y plazos (derivados, con fecha dura).
  - Detecta **colisiones**: dos señalamientos del mismo letrado a la misma hora es la
    causa de suspensión más frecuente y se anticipa semanas antes.
  - Guarda obligaciones vivas de documentos ya cerrados —vencimientos de contrato,
    prórrogas, actualizaciones de renta—, que es lo que da vida posterior al
    arquetipo G.
- **Falla si:** calcula plazos por su cuenta; solo mira el día siguiente; no cruza
  agendas entre letrados del despacho.

**`sec.notificador`** — avisos y log

- **Contrato:** `{evento, prioridad}` → `{notificacion, log_entry}`
- **Reglas:**
  - **Todo lo que notifica queda en el log.** Ese log es la prueba de qué se advirtió
    y cuándo: si un plazo se pierde, es lo que distingue un fallo del sistema de un
    aviso desatendido.
  - La insistencia escala con la franja que le pasa `pro.caducidad`. Un aviso en
    franja crítica no puede pesar lo mismo que uno en franja holgada.
  - El log es enumerable y consultable, no un flujo efímero de notificaciones.
- **Falla si:** notifica sin registrar — y entonces no hay constancia de la
  advertencia; o trata todos los avisos igual, y el letrado deja de leerlos.

**`sec.entrega`** — emisor
Misma conexión de correo, dirección contraria. Dos usos: mandar a firmar y compartir
con otro letrado.

- **Contrato:** `{documento, destinatario, motivo}` → `{enviado, retorno_esperado?, version_firmada?}`
- **Reglas:**
  - Los dos usos no son iguales: **firma espera retorno**, compartir no. Cuando espera
    retorno, crea una entrada pendiente en `sec.agenda`; si no vuelve, alguien debe
    enterarse.
  - Vale la **versión firmada**, no la enviada. Archivar solo la que salió es el error
    típico y deja el expediente sin el documento que produce efectos.
  - Compartir con un compañero cruza la frontera del secreto profesional: el
    destinatario debe ser explícito, nunca autocompletado.
- **Falla si:** archiva la enviada y no la firmada; autocompleta el destinatario.

#### Notas de diseño del grupo

- **El secretario no sabe derecho y no debe aprender.** Detecta y reparte; no decide.
- **Es el grupo con credenciales de correo.** Por eso no toma decisiones jurídicas:
  separar canal de criterio permite auditar ambos por separado.
- **Entrada y salida no son simétricas en el riesgo.** Recibir mal cuesta una
  reclasificación; enviar mal puede significar mandar el documento de un cliente a
  otro. `sec.entrega` merece confirmación explícita de destinatario.

#### Pendiente de asignar

Con este alcance, los **canales procesales quedan sin dueño**: presentación en
LexNET, registro administrativo, burofax fehaciente, notaría, y el acuse que cierra
el plazo. No son correo ni agenda, así que no caben en `secretario`.

Recomendación: van a `procesal`, que ya determina el destino y los requisitos de
forma. Quedan recogidos en §2.2 como bloque de salida, marcado a la espera de
confirmación.

---

### 2.2 · PROCESAL — 12 sub-agentes

Justo después de la entrada y justo antes de la salida. **No toca canales**: no tiene
credenciales ni sabe enviar. Determinista de punta a punta — ningún sub-agente de
`procesal` debería invocar un LLM. Si alguno lo necesita, está mal acotado: lo que
falta es una tabla mejor.

#### Puerta

**`pro.calendario`** — el motor de días
Dependencia de todos los demás: ningún plazo se calcula sin pasar por él.

- **Contrato:** `{fecha_inicio, dias, tipo_dia, orden, municipio_organo}` → `{fecha_limite, dias_restantes, festivos_aplicados[]}`
- **Reglas:**
  - Sábados y domingos son inhábiles a efectos procesales.
  - El *dies a quo* es el día **siguiente** a la notificación, no el de la notificación.
  - Agosto es inhábil para actuaciones judiciales con excepciones tasadas; en el orden
    social varias modalidades urgentes siguen corriendo (despido, tutela de derechos
    fundamentales, conflicto colectivo).
  - **El cómputo administrativo no es el judicial**: los plazos por meses van de fecha
    a fecha y el calendario de festivos aplicable es distinto.
  - Festivos = nacionales + autonómicos + **locales del municipio del órgano**, no del
    municipio del despacho.
- **Falla si:** usa el calendario del despacho; trata agosto como uniforme; mezcla
  cómputo civil y administrativo.
- **Necesita:** calendario oficial por municipio, actualizado cada año. Dato externo
  con caducidad anual: si no se refresca, el sistema calcula mal **en silencio**.

**`pro.caducidad`** — plazos perentorios
El que puede matar un caso.

- **Contrato:** `{tipoActo, fechaActo, orden}` → `{fecha_limite, dias_restantes, franja, bloqueo}`
- **Reglas:**
  - La caducidad **no se interrumpe**; solo se suspende en supuestos tasados
    (conciliación previa, reclamación administrativa previa).
  - No devuelve un booleano sino una **franja**: `holgado · ajustado · crítico ·
    vencido`. Un plazo con dos días de margen no es lo mismo que uno con quince
    aunque ambos permitan presentar. La franja alimenta a `sec.notificador`.
  - Aplica **margen de seguridad**: la fecha objetivo interna es anterior al
    vencimiento real.
- **Falla si:** devuelve sí/no en vez de franja; ignora las suspensiones; computa
  desde la notificación en lugar del día siguiente.
- **Necesita:** `pro.calendario` + tabla `tipoActo → {plazo, dies_a_quo, norma}`.

**`pro.prescripcion`** — plazos sustantivos
Se comporta al revés que la caducidad, y por eso es un sub-agente distinto.

- **Contrato:** `{accion, partidas[], hechos_interruptivos[]}` → `{partidas_vivas[], partidas_prescritas[]}`
- **Reglas:**
  - **Sí se interrumpe**: reclamación extrajudicial, reconocimiento de deuda,
    interposición de demanda. Cada interrupción reinicia el cómputo entero.
  - En varios tipos corre **por partida**: cada mensualidad reclamada prescribe por
    separado.
  - No filtra el caso, **filtra conceptos**: la salida es una lista partida en dos.
  - El plazo depende de la acción ejercitada, que en la puerta puede no estar
    decidida. Marca el resultado como **provisional** y exige reevaluación.
- **Falla si:** lo tratan como puerta booleana; olvida un hecho interruptivo y
  descarta conceptos vivos.
- **Necesita:** historial de requerimientos, que produce `pro.burofax`.

**`pro.procedibilidad`** — requisitos previos
El único sub-agente que puede **desviar el pipeline a otro tipo documental**.

- **Contrato:** `{tipo_documento, expediente}` → `{cumplidos[], pendientes[], ruta_alternativa?}`
- **Reglas:**
  - Catálogo: conciliación previa (social), reclamación administrativa previa
    (Seguridad Social), agotamiento de la vía administrativa (contencioso),
    requerimiento previo fehaciente (desahucio, monitorio).
  - Cuando falta un requisito no devuelve error: devuelve **la ruta que hay que
    recorrer antes** y deja la actual suspendida.
  - Distingue **inadmisión** de **consecuencia**: en desahucio el requerimiento previo
    no impide demandar, pero condiciona la enervación.
- **Falla si:** confunde ambas; bloquea cuando solo debía advertir.
- **Necesita:** estado del expediente y salida de `pro.acuse`.

#### Verificación

Segundo paso del grupo, justo antes de que el secretario envíe. Existe porque
**entre la puerta y la salida ha pasado tiempo**.

**`pro.plazo-vivo`** — ¿sigue en plazo ahora?
- **Contrato:** `{expediente, plazo_id, ahora}` → `{en_plazo, dias_restantes, franja}`
- **Reglas:**
  - El pipeline consume días: investigación, prueba y revisión pueden llevar semanas.
    Un plazo holgado en la puerta puede estar crítico en la salida.
  - Si la franja ha empeorado, lo comunica a `sec.notificador` antes de presentar.
  - Si ha vencido, **bloquea la salida**. Es la última oportunidad de no presentar
    fuera de plazo.
- **Falla si:** no existe — y entonces el sistema presenta confiando en un cálculo
  que hizo semanas atrás.

**`pro.forma`** — requisitos formales de presentación
- **Contrato:** `{documento, organo, destino}` → `{conforme, defectos[]}`
- **Reglas:** otorgamiento de representación, firma, anexos exigidos, tasas si
  proceden, formato admitido por el destino.
- **Diferencia con `cri.formal`:** el crítico revisa el **contenido** jurídico; este
  revisa los requisitos de **presentación**. Un escrito impecable puede ser
  rechazado por un defecto de forma que el crítico no mira.

**`pro.destino`** — a dónde va
- **Contrato:** `{tipo_documento, organo, expediente}` → `{canal, destinatario}`
- **Reglas:**
  - Resuelve el canal que usará el secretario: `lexnet-out · registro · burofax ·
    notaria · entrega`.
  - Es el punto de traspaso limpio entre los dos grupos: **procesal decide dónde,
    secretario entrega**.
  - 30 de los 89 tipos no salen por LexNET. Sin este sub-agente, el destino se
    asumiría y un tercio del catálogo saldría por el canal equivocado.

#### Salida — canales procesales
*Bloque pendiente de confirmación: llega desde `secretario` al acotarse éste al
correo y la agenda.*

**`pro.lexnet`** — canal judicial, **bidireccional** · 59 tipos
- **Contrato entrada:** `{buzón}` → `{notificación, acuse_emitido, fecha_oficial}`
- **Contrato salida:** `{documento, anexos[], órgano}` → `{justificante, timestamp}`
- **Reglas:**
  - Recibir **también es actuar**: acusar recibo abre el cómputo del plazo. Es un
    hecho jurídico, no un trámite técnico, y debe quedar registrado en el instante.
  - La fecha que cuenta es la oficial del sistema, no la de lectura en el despacho.
  - Al presentar: nivel **ROJO**, doble confirmación con token, irreversible. El
    troceado de anexos por límite de tamaño debe ser explícito, nunca silencioso.
  - Recibido el documento, lo entrega a `sec.clasificador` como cualquier otra
    entrada.
- **Falla si:** acusa automáticamente sin registrarlo — el plazo corre y nadie lo
  sabe; da por presentado sin justificante.

**`pro.registro`** — registro administrativo · 12 tipos
El más complejo del bloque: no es un sistema, son decenas.

- **Contrato:** `{documento, administración, procedimiento}` → `{justificante, nº_registro, fecha_presentacion, fecha_entrada_competente, fecha_silencio_estimada, sentido_silencio}`
- **Reglas:**
  - **Dos fechas, no una.** La de presentación detiene *tu* plazo; la de entrada en el
    órgano competente arranca el de *ellos*. Sirven para cosas distintas y hay que
    guardar las dos.
  - Cabe presentar en un registro que no sea el competente: sigue deteniendo el plazo
    aunque el expediente tarde días en llegar a destino.
  - Calendario **administrativo**: los plazos por meses van de fecha a fecha, y el
    festivo aplicable es el de la Administración destinataria.
  - El registro electrónico está abierto 24/7; lo presentado en día inhábil se
    entiende hecho a primera hora del siguiente hábil, pero la fecha de presentación
    queda registrada.
  - **Genera trabajo futuro:** la entrega arranca un reloj que puede vencer en
    silencio. Esa fecha va a `sec.agenda` y, al vencer, dispara `recurso_alzada` o
    `recurso_contencioso`. Es el único sub-agente de salida cuya entrega **produce una
    entrada futura**.
  - Dada la fragmentación, conviene resolverlo con **drivers enchufables** por
    Administración (AEAT, Seguridad Social, extranjería, cada CCAA) más un driver
    genérico de registro interoperable como red de seguridad.
- **Falla si:** guarda una sola fecha; aplica calendario judicial; no programa el
  vencimiento del silencio; acepta un justificante sin número de registro.

**`pro.burofax`** — requerimiento fehaciente · 2 tipos, y medio catálogo depende de él
- **Contrato:** `{destinatario, contenido}` → `{acuse, certificacion_contenido, fecha}`
- **Reglas:** lo que da valor no es el envío sino el **acuse con certificación de
  contenido**; sin ella no prueba qué se requirió. Su acuse alimenta a
  `pro.prescripcion` (la interrumpe) y a `pro.procedibilidad` (requisito de desahucio
  y monitorio): produce hechos jurídicos, no solo entrega.
- **Falla si:** guarda el envío pero no la certificación de contenido.

**`pro.notaria`** — elevación a público · 6 tipos
- **Contrato:** `{minuta, comparecientes[]}` → `{cita, copia_autorizada}`
- **Reglas:** el despacho redacta la minuta, no el instrumento. La copia autorizada
  vuelve al expediente como documento nuevo y reentra por `sec.clasificador`.

**`pro.acuse`** — el cierre
- **Contrato:** `{justificante, expediente, plazo_id}` → `{hash, audit_entry, plazo_cerrado}`
- **Reglas:**
  - Hashea el justificante, lo escribe en `audit_log` y **marca el plazo cumplido**.
  - Sin él el sistema no sabe que se presentó: los avisos de `sec.notificador` siguen
    vivos y `pro.procedibilidad` bloquearía la siguiente ruta del mismo expediente.
  - Único punto donde presentación y plazo se reconcilian. **Idempotente**: reintentar
    no puede duplicar entradas de auditoría.
- **Falla si:** no se ejecuta — y el fallo es invisible hasta que alguien pregunta si
  se presentó.

#### Notas de diseño del grupo

- **Ninguno usa LLM.** Es el bloque auditable del sistema; si deja de serlo, se pierde
  la única parte verificable a mano.
- **La tabla de plazos es el activo crítico.** `pro.caducidad` y `pro.prescripcion`
  valen exactamente lo que valga esa tabla. Debe versionarse, tener autoría y fecha de
  revisión, y ser un dato, no código.
- **Procesal decide, secretario ejecuta.** Separar criterio de canal es lo que permite
  que el que tiene credenciales no tome decisiones y el que decide no pueda enviar.

---

## 3 · La espina dorsal

```
sec.mail | pro.lexnet    llega algo — o el letrado abre el asunto
sec.ocr · sec.clasificador   normaliza y clasifica
pro.puerta     ¿hay tiempo? ¿faltan requisitos previos?      BLOQUEANTE
               ── archivador · estratega · probatorio ──
               ── calculadora · investigador ──
               ── redactor ──
               ── critico ──
pro.salida     ¿sigue en plazo? ¿forma correcta? ¿qué destino?
pro.<canal> → pro.acuse   presenta y cierra el plazo
sec.notificador · sec.agenda   avisa y anota lo que queda vivo
```

**Estructura de envoltorio.** El secretario envuelve al procesal, y el procesal
envuelve al trabajo:

```
┌ secretario ─────────────────────────────────┐
│  ┌ procesal ─────────────────────────────┐  │
│  │   análisis · producción · control      │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

Tres consecuencias:

**El secretario está en las 89 rutas**, y en las dos puntas. Todo entra y sale por
él, incluso cuando el impulso es del letrado: entonces la entrada es el registro del
encargo y la salida sigue siendo una entrega.

**El procesal valida dos veces, y la segunda no es redundante.** Entre la puerta y la
salida el pipeline ha consumido días. Un plazo holgado al empezar puede estar crítico
al terminar, y `pro.plazo-vivo` es la última oportunidad de no presentar fuera de
plazo.

**Quien tiene credenciales no decide, y quien decide no puede enviar.** El secretario
sabe recibir y entregar, no sabe de plazos. El procesal calcula y determina destino,
pero no tiene acceso a ningún canal. La separación es lo que hace auditables a los
dos.

---

## 4 · Los diez arquetipos

Agrupar por rama del derecho junta documentos que no comparten nada operativo. Un
contrato de arrendamiento y una demanda de desahucio son ambos «Civil», pero uno no
pisa un juzgado y el otro vive de un plazo de enervación. El criterio útil es **qué
le exige el documento al pipeline**.

| | arquetipo | qué lo define |
|---|---|---|
| **A** | Reactivos | Analizan un documento ajeno antes de redactar |
| **B** | Caducidad + cálculo | Reloj corto y una cifra que defender con aritmética |
| **C** | Trámite previo | Su valor es el efecto sobre el plazo, no el texto |
| **D** | Penales | Anonimizar antes del LLM + elementos del tipo |
| **E** | Constructivo | Sin documento previo, pero la prueba precluye |
| **F** | Multi-documento | Coherencia cruzada entre piezas |
| **G** | No procesal | Nunca ve un juzgado |
| **H** | Extrajudicial previo | Arranca o interrumpe el reloj de otro tipo |
| **I** | Trámite | Dentro de un pleito vivo; sin investigador ni probatorio |
| **J** | Ejecución | Título, intereses y embargo; casi todo determinista |

A–G cubren el documento que **inicia** un procedimiento. H, I y J cubren lo que
ocurre **antes** del pleito, **durante** y **después**.

---

## 5 · Matriz de activación

89 tipos × 9 grupos, con disparador y destino de salida.
`1` siempre · `c` condicional · `0` no interviene

**Disparadores:** letrado 59 · secretario 22 · workflow 6 · agenda 2
**Destinos:** lexnet 59 · registro 12 · cliente 8 · notaría 6 · burofax 2 · smac 1 · comisaría 1

Tres lecturas:

- `archivador`, `procesal`, `redactor` y `critico` entran en los 89. Los otros cinco
  son enrutables.
- El **secretario dispara 22 rutas**, y **17 de esas 22** son justo las que activan
  `est.contrario`. Recibir y rebatir son la misma cadena.
- **LexNET sirve a 59 de 89.** Los otros 30 salen por los demás sub-agentes de
  `pro.salida`: tratarlo como destino único deja un tercio del catálogo sin camino.

```csv
tipo,arq,origen,secretario,archivador,procesal,estratega,probatorio,calculadora,investigador,redactor,critico,salida
demanda_laboral,B,letrado,1,1,1,c,1,1,1,1,1,lexnet
despido_objetivo,B,letrado,1,1,1,c,1,1,1,1,1,lexnet
despido_colectivo,F,letrado,1,1,1,c,1,1,1,1,1,lexnet
papeleta_conciliacion,C,workflow,1,1,1,0,0,c,0,1,c,smac
reclamacion_cantidad,B,letrado,1,1,1,c,1,1,1,1,1,lexnet
impugnacion_sancion,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
modificacion_sustancial,B,secretario,1,1,1,c,1,1,1,1,1,lexnet
extincion_art_50,E,letrado,1,1,1,c,1,1,1,1,1,lexnet
tutela_derechos_fundamentales,E,letrado,1,1,1,c,1,0,1,1,1,lexnet
demanda_seguridad_social,A,secretario,1,1,1,1,1,c,1,1,1,lexnet
reclamacion_previa_ss,H,secretario,1,1,1,c,0,0,c,1,c,admin
conflicto_colectivo,E,letrado,1,1,1,c,c,0,1,1,1,lexnet
recargo_prestaciones,A,letrado,1,1,1,1,1,1,1,1,1,lexnet
carta_despido,G,letrado,1,1,1,0,c,1,1,1,1,cliente
monitorio,B,letrado,1,1,1,c,1,1,c,1,1,lexnet
demanda_civil,E,letrado,1,1,1,c,1,c,1,1,1,lexnet
juicio_verbal,E,letrado,1,1,1,c,1,c,1,1,1,lexnet
contestacion_demanda,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
recurso_apelacion,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
juicio_cambiario,B,letrado,1,1,1,c,1,1,c,1,1,lexnet
nulidad_clausulas_abusivas,A,letrado,1,1,1,1,1,1,1,1,1,lexnet
reclamacion_danos,B,letrado,1,1,1,c,1,1,1,1,1,lexnet
division_cosa_comun,E,letrado,1,1,1,c,1,1,1,1,1,lexnet
demanda_desahucio,B,letrado,1,1,1,c,1,1,1,1,1,lexnet
desahucio_expiracion_plazo,E,letrado,1,1,1,c,1,c,1,1,1,lexnet
precario,E,letrado,1,1,1,c,1,0,1,1,1,lexnet
oposicion_ejecucion,A,secretario,1,1,1,1,1,1,1,1,1,lexnet
medidas_cautelares,I,letrado,1,1,1,c,1,c,1,1,1,lexnet
contrato_arrendamiento,G,letrado,1,1,1,0,0,c,1,1,1,cliente
divorcio_mutuo_acuerdo,E,letrado,1,1,1,c,c,1,1,1,1,lexnet
divorcio_contencioso,E,letrado,1,1,1,c,1,1,1,1,1,lexnet
convenio_regulador,G,letrado,1,1,1,0,0,1,1,1,1,cliente
medidas_paternofiliales,E,letrado,1,1,1,c,1,1,1,1,1,lexnet
modificacion_medidas,A,letrado,1,1,1,1,1,1,1,1,1,lexnet
reclamacion_alimentos,B,letrado,1,1,1,c,1,1,1,1,1,lexnet
liquidacion_gananciales,F,letrado,1,1,1,c,1,1,1,1,1,lexnet
medidas_apoyo,E,letrado,1,1,1,c,1,0,1,1,1,lexnet
orden_proteccion,D,letrado,1,1,1,c,1,0,1,1,1,lexnet
declaracion_herederos,E,letrado,1,1,1,0,1,0,1,1,1,notarial
cuaderno_particional,F,letrado,1,1,1,0,1,1,1,1,1,notarial
aceptacion_renuncia_herencia,G,letrado,1,1,1,0,c,c,1,1,1,notarial
impugnacion_testamento,A,letrado,1,1,1,1,1,0,1,1,1,lexnet
reclamacion_legitima,B,letrado,1,1,1,c,1,1,1,1,1,lexnet
denuncia_penal,D,letrado,1,1,1,0,1,0,1,1,1,policial
querella,D,letrado,1,1,1,c,1,0,1,1,1,lexnet
escrito_defensa,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
escrito_acusacion,A,workflow,1,1,1,1,1,0,1,1,1,lexnet
personacion_acusacion_particular,I,secretario,1,1,1,c,0,0,0,1,c,lexnet
recurso_reforma,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
recurso_apelacion_penal,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
juicio_leve,E,secretario,1,1,1,c,1,0,1,1,1,lexnet
conformidad,B,workflow,1,1,1,c,c,1,1,1,1,lexnet
habeas_corpus,I,letrado,1,1,1,c,0,0,c,1,c,lexnet
libertad_provisional,I,letrado,1,1,1,c,c,0,c,1,c,lexnet
recurso_alzada,A,secretario,1,1,1,1,c,0,1,1,1,admin
recurso_reposicion,A,secretario,1,1,1,1,c,0,1,1,1,admin
alegaciones_sancionador,A,secretario,1,1,1,1,c,0,1,1,1,admin
responsabilidad_patrimonial,B,letrado,1,1,1,0,1,1,1,1,1,admin
reclamacion_economico_administrativa,A,secretario,1,1,1,1,1,1,1,1,1,admin
recurso_contencioso,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
concurso_acreedores,F,letrado,1,1,1,c,1,1,1,1,1,lexnet
constitucion_sociedad,G,letrado,1,1,1,0,0,c,1,1,1,notarial
impugnacion_acuerdos_sociales,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
responsabilidad_administradores,E,letrado,1,1,1,c,1,1,1,1,1,lexnet
pacto_socios,G,letrado,1,1,1,0,0,0,1,1,1,cliente
compraventa_participaciones,G,letrado,1,1,1,0,c,1,1,1,1,notarial
disolucion_liquidacion,F,letrado,1,1,1,0,1,1,1,1,1,notarial
reclamacion_cambiaria,B,letrado,1,1,1,c,1,1,c,1,1,lexnet
arraigo,E,letrado,1,1,1,0,1,0,1,1,1,admin
nacionalidad,E,letrado,1,1,1,0,1,0,1,1,1,admin
recurso_denegacion,A,secretario,1,1,1,1,c,0,1,1,1,admin
recurso_expulsion,A,secretario,1,1,1,1,c,0,1,1,1,admin
burofax_requerimiento,H,letrado,1,1,1,0,c,c,c,1,c,burofax
reclamacion_extrajudicial,H,letrado,1,1,1,0,c,c,c,1,c,burofax
acuerdo_transaccional,H,letrado,1,1,1,0,0,1,1,1,1,cliente
solicitud_mediacion,H,letrado,1,1,1,0,0,0,0,1,c,admin
suspension_vista,I,agenda,1,1,1,c,0,0,0,1,c,lexnet
aportacion_documental,I,workflow,1,1,1,c,c,0,0,1,c,lexnet
subsanacion_defectos,I,secretario,1,1,1,c,0,0,c,1,c,lexnet
proposicion_prueba,I,agenda,1,1,1,c,1,0,c,1,c,lexnet
desistimiento,I,letrado,1,1,1,c,0,0,0,1,c,lexnet
justicia_gratuita,I,letrado,1,1,1,0,c,c,0,1,c,admin
recurso_reposicion_procesal,I,secretario,1,1,1,1,0,0,c,1,c,lexnet
ejecucion_titulo_judicial,J,workflow,1,1,1,c,c,1,0,1,c,lexnet
ejecucion_hipotecaria,J,letrado,1,1,1,c,1,1,c,1,c,lexnet
ejecucion_familia,J,letrado,1,1,1,c,c,1,0,1,c,lexnet
hoja_encargo,G,letrado,1,1,1,0,0,1,0,1,c,cliente
minuta_honorarios,G,workflow,1,1,1,0,0,1,0,1,c,cliente
provision_fondos,G,letrado,1,1,1,0,0,1,0,1,c,cliente
```

---

## 6 · Doce rutas de referencia

Una por patrón, nombrando sub-agentes. Cada uno de los 89 tipos hereda la ruta de su
arquetipo.

### A · Reactivos

Regla: **nada se redacta antes de analizar el documento recibido.**

**`contestacion_demanda`**
```
pro.lexnet (acuse) → sec.clasificador        llega el emplazamiento
arc.metadatos · arc.partes · arc.emparejador
pro.caducidad        PUERTA — 20 días desde emplazamiento (art. 404 LEC) → rebeldía
est.contrario
   ├─ hechos que se admiten / niegan (art. 405 LEC)
   ├─ excepciones procesales oponibles
   └─ ¿procede reconvención?
est.citas-contrario  ¿sostienen las citas del actor lo que dice?
est.debilidades      dónde es vulnerable la posición propia
pru.suficiencia · pru.carencias   prueba de descargo — precluye si no acompaña
inv.jurisprudencia   resoluciones que CONTRADIGAN la tesis del actor
red.estructura · red.hechos · red.fundamentos · red.petitorio
cri.coherencia       el silencio sobre un hecho puede leerse como admisión tácita
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

**`recurso_apelacion`**
```
pro.lexnet (acuse) → sec.clasificador   llega la sentencia
pro.caducidad        PUERTA — 20 días desde notificación (art. 458 LEC)
est.contrario        objeto = LA SENTENCIA, no un escrito de parte
   ├─ extraer la ratio decidendi
   ├─ motivos apelables: error en valoración de prueba / infracción de norma
   └─ FILTRO: descartar cuestiones nuevas no planteadas en primera instancia
inv.jurisprudencia   resoluciones que contradigan la ratio, por cada motivo
red.fundamentos
cri.formal           no es segunda instancia plena: cada motivo, fundado por separado
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

**`recurso_contencioso`**
```
sec.mail | pro.lexnet            llega la resolución
pro.caducidad        PUERTA — 2 meses (art. 46 LJCA)
                     si hubo silencio administrativo, el cómputo cambia de régimen
pro.procedibilidad   PUERTA 2 — ¿vía administrativa agotada?
                       └─ si no → desviar a recurso_alzada / recurso_reposicion
est.contrario        objeto = EL ACTO ADMINISTRATIVO
   ├─ ¿está motivado?
   ├─ vicio: nulidad / anulabilidad (arts. 47 y 48 Ley 39/2015)
   └─ ¿desviación de poder?
inv.normativa → red.fundamentos → red.petitorio    (art. 71 LJCA)
cri.coherencia
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

### B · Caducidad y cálculo

**`demanda_laboral`**
```
sec.mail              el letrado abre el asunto
pro.calendario · pro.caducidad
                     PUERTA — 20 días HÁBILES desde el despido (art. 59.3 ET)
                     caducidad, no prescripción: no se interrumpe, solo se suspende
                     por la conciliación previa; excluir festivos locales
pro.procedibilidad   PUERTA 2 — ¿papeleta SMAC presentada?
                       └─ si no → desviar a papeleta_conciliacion y suspender
pru.inventario · pru.carencias    carta de despido, contrato, nóminas, vida laboral
cal.antiguedad · cal.indemnizacion
                     salario/día con prorrata, doble tramo pre-2012, tope
inv.normativa · inv.jurisprudencia   calificación + jurisprudencia de la causa
red.estructura · red.hechos · red.fundamentos · red.petitorio
cri.citas · cri.coherencia
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

**`reclamacion_cantidad`**
```
sec.mail              el letrado abre el asunto
pro.prescripcion     PUERTA — 1 año (art. 59 ET), CORRE POR PARTIDA
                     no es sí/no: filtra los conceptos ya prescritos
pru.inventario       nóminas, convenio, registro de jornada
                     (la ausencia de registro horario favorece al trabajador)
inv.convenio         localizar el aplicable por sector y provincia
cal.cantidades · cal.intereses    desglose concepto a concepto + mora (art. 29.3 ET)
red.hechos · red.petitorio
cri.coherencia       que la cifra del suplico case con el desglose
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

**`demanda_desahucio`**
```
sec.mail              el letrado abre el asunto
pro.procedibilidad   PUERTA — ¿hubo requerimiento previo fehaciente?
                     de ello depende que el arrendatario pueda ENERVAR (art. 22.4 LEC)
pru.autenticidad     contrato, impagos, burofax con acuse
                     (el acuse es lo que sostiene la no-enervación)
cal.cantidades · cal.intereses    rentas vencidas, asimiladas e intereses
inv.normativa
red.estructura       ACUMULAR desahucio + reclamación de rentas en un solo escrito
cri.coherencia
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

### C · Trámite previo

**`papeleta_conciliacion`**
```
sec.mail              el letrado abre el asunto
pro.caducidad        PUERTA — comparte el reloj de la demanda; presentarla SUSPENDE
red.tramite          plantilla ligera, SIN investigador
cri.formal           mínimo: partes y coherencia con la demanda futura
pro.forma · pro.destino → pro.registro → pro.acuse          SMAC
sec.agenda           el paso que importa:
   ├─ reanudación del plazo de 20 días tras el acto
   ├─ tarea «preparar demanda» en el mismo expediente
   └─ recordatorio de la fecha del acto
```

### D · Penales

Dos exigencias que no aparecen en ningún otro arquetipo: **anonimizar antes de
llamar al modelo** —datos de infracciones penales, con régimen reforzado en RGPD— y
verificar que los hechos colman TODOS los elementos del tipo.

**`denuncia_penal`**
```
sec.mail              el letrado abre el asunto
pro.prescripcion     PUERTA — según pena en abstracto (art. 131 CP)
                     depende de una calificación que aún no se ha hecho → reevaluar
[anonimizar]         middleware, antes de cualquier LLM
pru.inventario · pru.autenticidad     indicios y cadena de custodia
inv.normativa        tipo penal + DESGLOSE DE SUS ELEMENTOS
red.hechos           relato fáctico; la denuncia no vincula calificación
cri.riesgo           no afirmar más de lo que los indicios sostienen
pro.forma · pro.destino → pro.registro → pro.acuse          juzgado o comisaría — no siempre LexNET
```

**`querella`**
```
sec.mail              el letrado abre el asunto
pro.prescripcion · pro.procedibilidad
                     PUERTA — prescripción + legitimación + poder especial
[anonimizar]
pru.suficiencia      UMBRAL REFORZADO — si no lo alcanza,
                     PROPONER DEGRADAR A DENUNCIA en vez de seguir
est.recomendador     querellarse o denunciar: es una decisión, no un trámite
inv.normativa → red.hechos → red.petitorio
cri.formal           checklist cerrado del art. 277 LECrim
   ├─ órgano competente · identidad de querellante y querellado
   ├─ relato circunstanciado de los hechos
   └─ diligencias solicitadas · firma y postulación
cri.riesgo           querella infundada → acusación o denuncia falsa (art. 456 CP)
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

### E · Constructivo

**`demanda_civil`**
```
sec.mail              el letrado abre el asunto
pro.prescripcion     PUERTA — prescripción de la acción ejercitada
cal.cuantia          PUERTA 2 — la cuantía decide cauce y postulación:
                     resolverla ANTES de redactar, no después
arc.metadatos · arc.partes
pru.suficiencia      PRECLUSIÓN: los documentos fundamentadores acompañan la demanda.
                     Debe BLOQUEAR, no advertir, si falta uno esencial
inv.normativa · inv.jurisprudencia
red.estructura · red.hechos · red.fundamentos · red.petitorio   (art. 399 LEC)
cal.costas · cri.coherencia
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse                                            [ROJO]
```

### F · Multi-documento

**`concurso_acreedores`**
```
sec.mail              el letrado abre el asunto
pro.caducidad        PUERTA — 2 meses desde conocida la insolvencia
                     el plazo NO protege al cliente, LE OBLIGA: incumplirlo abre la
                     puerta a calificación culpable y responsabilidad personal
                     del administrador. La puerta debe advertir de esa exposición.
red.estructura       reparte en paralelo:
   ├─ memoria (historia económica y jurídica)
   ├─ inventario de bienes y derechos
   ├─ lista de acreedores con clasificación
   ├─ relación de trabajadores
   └─ cuentas anuales
pru.inventario · cal.cantidades   contabilidad; masa activa y pasiva se calculan
cri.cruzado          coherencia ENTRE documentos: inventario vs cuentas,
                     lista de acreedores vs pasivo de la memoria.
                     Revisar cada pieza por separado no detecta la contradicción,
                     que es justo lo que mira la administración concursal.
pro.plazo-vivo · pro.forma → pro.lexnet → pro.acuse            Juzgado de lo Mercantil         [ROJO]
```

### G · No procesal

**`contrato_arrendamiento`**
```
sec.mail              el letrado abre el asunto
— sin puerta de plazo —           no hay tipoActo que casar contra la tabla
inv.normativa        LAU 29/1994 y sus LÍMITES IMPERATIVOS: duración mínima,
                     prórrogas, fianza legal, actualización, zonas tensionadas
red.contractual      clausulado
cri.abusividad       otra pregunta: no «¿convence?» sino «¿es válido?»
   ├─ ¿renuncia a derechos irrenunciables del arrendatario?
   ├─ ¿duración mínima y prórroga respetadas?
   ├─ ¿fianza ajustada a la legal?
   └─ ¿índice de actualización admisible?
pro.forma → sec.entrega   PDF / DOCX al cliente — NUNCA LexNET
sec.agenda           avisos de vencimiento, prórroga y actualización anual
```

---

## 7 · Tabla de puertas

| tipo | puerta | plazo | referencia | si expira |
|---|---|---|---|---|
| `demanda_laboral` | caducidad | 20 días hábiles | art. 59.3 ET | acción perdida |
| `papeleta_conciliacion` | heredada | suspende los 20 d. | LRJS | bloquea la demanda |
| `reclamacion_cantidad` | prescripción | 1 año por partida | art. 59 ET | filtra conceptos |
| `demanda_civil` | prescripción + cuantía | según acción | CC · LEC | excepción del demandado |
| `contestacion_demanda` | caducidad | 20 días | art. 404 LEC | rebeldía |
| `recurso_apelacion` | caducidad | 20 días | art. 458 LEC | sentencia firme |
| `demanda_desahucio` | procedibilidad | requerimiento previo | art. 22.4 LEC | permite enervar |
| `contrato_arrendamiento` | ninguna | — | LAU 29/1994 | — |
| `denuncia_penal` | prescripción | según pena | art. 131 CP | extinción de la acción |
| `querella` | prescripción + legitimación | según pena | art. 277 LECrim | inadmisión a trámite |
| `recurso_contencioso` | caducidad + vía previa | 2 meses | art. 46 LJCA | acto firme y consentido |
| `concurso_acreedores` | deber legal | 2 meses | TRLC | riesgo de concurso culpable |

---

## 8 · Notas de implementación

### 8.1 · Cuatro decisiones que vertebran el diseño

1. **`procesal` abre y cierra.** El plazo condiciona si merece la pena arrancar, y el
   mismo grupo certifica que se terminó en forma. Ponerlo solo al final invierte la
   economía del pipeline.
2. **`estratega` alimenta la redacción.** Los tres arquetipos reactivos no pueden
   redactarse sin él, y el objeto de `est.contrario` cambia en cada uno: demanda,
   sentencia, acto administrativo. Son tres prompts, no uno parametrizado.
3. **`calculadora` separada del LLM.** Toda cifra que se defiende ante un juez sale
   de una función auditable.
4. **Sub-agentes acotados, no agentes generalistas.** Un `cri.formal` que recorre el
   art. 277 LECrim como lista cerrada es verificable; un «crítico» que opina sobre
   todo, no. La granularidad es lo que hace auditable el sistema.

### 8.2 · Seis tipos de mayor volumen real

`burofax_requerimiento` · `monitorio` · `escrito_defensa` ·
`divorcio_mutuo_acuerdo` · `recurso_alzada` · `suspension_vista`

### 8.3 · Estado del código

**Implementado — `sec.mail`**

Primer sub-agente en producción. Gmail sobre IMAP con almacenamiento local cifrado.

| pieza | fichero |
|---|---|
| interfaz al resto del sistema | `sec/mail/agent.py` |
| cliente IMAP | `sec/mail/imap.py` |
| parser de `.eml` | `sec/mail/parser.py` |
| base SQLCipher | `sec/mail/db.py` |
| credenciales y llavero | `sec/mail/config.py` |
| CLI | `sec/mail/__main__.py` |

Superficie: `carpetas · sincronizar · listar · marcar_leido · mover`.
Tablas: `correos · adjuntos · sincronizacion · acciones`.

Decisiones que conviene no perder:

- **Idempotencia por `UIDVALIDITY` + último UID.** Si el servidor reinicia los UID,
  se recorre la carpeta entera; si no, se sigue desde donde se quedó. Resuelve el
  modo de fallo clásico: reprocesar y duplicar tras una reconexión.
- **`X-GM-MSGID` como identidad estable.** Los UID cambian al mover un correo de
  carpeta; el identificador de Gmail no. Todas las acciones posteriores resuelven el
  UID actual a partir de él.
- **Sincronización en solo lectura.** El agente lee sin marcar como leído: el letrado
  sigue viendo su bandeja intacta desde sus propios dispositivos.
- **Avance correo a correo.** El puntero se guarda tras cada mensaje, así que una
  interrupción no pierde trabajo ni lo repite.
- **Secretos repartidos.** Usuario y contraseña de aplicación en `.config`, fuera de
  git; la clave de la base la genera el agente y vive en el **Llavero de macOS**. El
  valor se pasa a `security` por entrada estándar para que no aparezca en la lista de
  procesos.
- **Registro de acciones** en tabla propia: todo lo que el agente hace sobre un correo
  queda anotado.

**Pendiente**

Los otros cinco de `secretario`: `sec.ocr`, `sec.clasificador`, `sec.agenda`,
`sec.notificador`, `sec.entrega`. Después, grupo a grupo, según vaya funcionando cada
uno.

**Decidido por el código**

La duda entre IMAP y API de Gmail queda resuelta: **IMAP**. Sirve para cualquier
proveedor y no ata el sistema a Google, a cambio de gestionar las credenciales, que
es lo que resuelven el `.config` y el Llavero.

---

## 9 · Alcance

**Sobre las citas.** Los preceptos y plazos orientan el enrutado, no son un dictamen.
Antes de codificar la puerta conviene contrastarlos con la práctica del despacho: el
cómputo real depende de festivos locales, de suspensiones y, en varios tipos, de la
calificación que aún no se ha hecho cuando la puerta se ejecuta.

**Sobre el catálogo.** Los 89 tipos están verificados como cobertura —qué maneja de
verdad un despacho generalista— pero solo 12 se revisaron con detalle de plazos y
preceptos. Alguna asignación de arquetipo es discutible: `monitorio` figura en B por
el peso del cálculo, pero tiene tanto de H por el requerimiento previo.

**Sobre los sub-agentes.** Los 54 son una propuesta de granularidad, no un contrato
cerrado. El criterio aplicado: un sub-agente por tarea que pueda fallar de forma
independiente y verificarse por separado.
