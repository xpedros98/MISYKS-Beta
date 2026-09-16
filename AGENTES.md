# Agentes

> Para qué sirve cada sub-agente y qué no puede hacer. Nueve grupos, 56
> sub-agentes. Solo `sec.mail` existe en código; el resto es diseño.
> La arquitectura del sistema —cómo se componen los grupos, las rutas, los
> arquetipos— está en `ARQUITECTURA.md`. Última actualización: 2026-09-16

Cada entrada sigue la misma plantilla: qué hace, su contrato, las reglas de dominio
que debe respetar, cómo falla y de qué depende. Un sub-agente está bien acotado
cuando puede fallar solo y verificarse solo.

`secretario` y `procesal` están detallados. De los otros siete grupos hay todavía
solo la tarea de cada sub-agente, no su contrato ni sus reglas: no es que no tengan
restricciones, es que aún no están escritas.

---

## SECRETARIO · despacho — 6

La capa del despacho. Sabe recibir, clasificar, recordar y enviar; no sabe de plazos
ni de derecho, y no toca ningún canal procesal.

**`sec.mail`** — receptor · **implementado** (lo que aún falta, en §8.3)
Gmail sobre IMAP, base local cifrada con SQLCipher. Corre en el ordenador del
letrado, no en el servidor: tiene la contraseña del correo y lee el contenido sin
anonimizar, así que ese contenido no sale de su máquina.

- **Contrato:** `{cuenta_imap, ventana}` → `{mensajes[], adjuntos[], resumen}`
- **Reglas:**
  - IMAP y no POP: el correo permanece en el servidor y el letrado lo sigue viendo
    desde sus propios dispositivos. El agente lee, no vacía.
  - **Idempotencia por identidad estable del mensaje** (en Gmail, `X-GM-MSGID`) y,
    por carpeta, por `UIDVALIDITY` + último UID: al reconectar no puede reprocesar lo
    ya visto. Sin esto, una caída de red duplica expedientes.
  - Separa cuerpo y adjuntos como documentos distintos, y **desciende por los
    reenvíos anidados**: el documento relevante suele ir dentro de un forward, no en
    el primer nivel.
  - Conserva cabeceras como metadato probatorio: fecha de recepción y remitente.
  - Produce el **resumen** que consume `sec.clasificador`. Extraer adjuntos ocurre
    antes de resumir, nunca después.
- **Falla si:** reprocesa tras reconectar; pierde el adjunto anidado; resume antes de
  extraer.
- **Necesita:** credenciales (contraseña de aplicación u OAuth) y el estado de
  sincronización de cada carpeta (`UIDVALIDITY` + último UID).

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

### Notas de diseño del grupo

- **El secretario no sabe derecho y no debe aprender.** Detecta y reparte; no decide.
- **Es el grupo con credenciales de correo.** Por eso no toma decisiones jurídicas:
  separar canal de criterio permite auditar ambos por separado.
- **Entrada y salida no son simétricas en el riesgo.** Recibir mal cuesta una
  reclasificación; enviar mal puede significar mandar el documento de un cliente a
  otro. `sec.entrega` merece confirmación explícita de destinatario.

### Pendiente de asignar

Con este alcance, los **canales procesales quedan sin dueño**: presentación en
LexNET, registro administrativo, burofax fehaciente, notaría, y el acuse que cierra
el plazo. No son correo ni agenda, así que no caben en `secretario`.

Recomendación: van a `procesal`, que ya determina el destino y los requisitos de
forma. Quedan recogidos en `procesal` como bloque de salida (mas
abajo), marcado a la espera de confirmación.

## ARCHIVADOR · estructura — 5

Convierte un documento en una posición dentro del despacho.

| sub-agente | uso |
|---|---|
| `arc.metadatos` | nº de procedimiento, órgano, autos, fecha |
| `arc.partes` | demandante, demandado, procurador, letrado contrario |
| `arc.emparejador` | a qué expediente pertenece; devuelve candidatos |
| `arc.nomenclador` | nombra y ubica el fichero según convención del despacho |
| `arc.deduplicador` | hash: el mismo documento llegado por dos vías |

## PROCESAL · tiempo y forma — 12

Justo después de la entrada y justo antes de la salida. **No toca canales**: no tiene
credenciales ni sabe enviar. Determinista de punta a punta — ningún sub-agente de
`procesal` debería invocar un LLM. Si alguno lo necesita, está mal acotado: lo que
falta es una tabla mejor.

### Puerta

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

### Verificación

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

### Salida — canales procesales
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

### Notas de diseño del grupo

- **Ninguno usa LLM.** Es el bloque auditable del sistema; si deja de serlo, se pierde
  la única parte verificable a mano.
- **La tabla de plazos es el activo crítico.** `pro.caducidad` y `pro.prescripcion`
  valen exactamente lo que valga esa tabla. Debe versionarse, tener autoría y fecha de
  revisión, y ser un dato, no código.
- **Procesal decide, secretario ejecuta.** Separar criterio de canal es lo que permite
  que el que tiene credenciales no tome decisiones y el que decide no pueda enviar.

## INVESTIGADOR · derecho — 5

Toda cita que produce debe ser **comprobable**.

| sub-agente | uso |
|---|---|
| `inv.normativa` | BOE: artículo exacto y vigencia a la fecha del hecho |
| `inv.jurisprudencia` | CENDOJ, filtrado por órgano e instancia |
| `inv.convenio` | convenio colectivo por sector y provincia |
| `inv.doctrina` | criterio administrativo y doctrinal |
| `inv.citas` | ¿existe la referencia y dice lo que se le atribuye? |

## PROBATORIO · prueba — 5

Único grupo que **interrumpe al humano por iniciativa propia**.

| sub-agente | uso |
|---|---|
| `pru.inventario` | qué material hay y en qué soporte |
| `pru.admisibilidad` | licitud y forma de obtención |
| `pru.autenticidad` | acta notarial, cadena de custodia, metadatos |
| `pru.suficiencia` | ¿sostiene la pretensión o se queda corta? |
| `pru.carencias` | qué falta y cómo obtenerlo a tiempo |

## CALCULADORA · números — 6

Determinista. Toda cifra que se defiende ante un juez sale de una función auditable:
**el redactor escribe alrededor del número, nunca lo produce**.

| sub-agente | uso |
|---|---|
| `cal.antiguedad` | cómputo de la relación, con interrupciones |
| `cal.indemnizacion` | por tipo de extinción, con tramos y topes |
| `cal.cantidades` | nóminas, horas extra, finiquito, rentas |
| `cal.intereses` | legal, de mora, procesal |
| `cal.costas` | según cuantía y cauce |
| `cal.cuantia` | determina el cauce procesal y la postulación |

## ESTRATEGA · adversario y decisión — 5

El análisis del adversario es el medio; **la recomendación es el fin**.

| sub-agente | uso |
|---|---|
| `est.contrario` | descompone el escrito ajeno en argumentos rebatibles |
| `est.citas-contrario` | ¿las citas del adversario existen y sostienen lo que dice? |
| `est.debilidades` | del caso propio, antes de que las encuentre el otro |
| `est.simulador` | escenarios y coste esperado de cada vía |
| `est.recomendador` | litigar, transigir o desistir |

El objeto de `est.contrario` cambia según la ruta (demanda, sentencia, acto
administrativo): son tres prompts distintos, no uno parametrizado.

## REDACTOR · producción — 6

Regla dura: **nunca deja un placeholder vacío**. Si falta un dato, se pide.

| sub-agente | uso |
|---|---|
| `red.estructura` | esqueleto según tipo documental |
| `red.hechos` | relato numerado (PRIMERO.-, SEGUNDO.-) |
| `red.fundamentos` | con las citas que entrega el investigador |
| `red.petitorio` | SUPLICO según tipo |
| `red.contractual` | clausulado: documentos que no van a juzgado |
| `red.tramite` | escritos cortos de plantilla |

## CRITICO · control — 6

Devuelve `veto` o `visto_bueno`, con los defectos encontrados.

| sub-agente | uso |
|---|---|
| `cri.formal` | requisitos tasados por tipo, como lista cerrada |
| `cri.citas` | ¿las citas del propio escrito existen? |
| `cri.coherencia` | hechos vs fundamentos vs suplico |
| `cri.cruzado` | coherencia **entre** documentos de un mismo expediente |
| `cri.abusividad` | cláusulas: no «¿convence?» sino «¿es válido?» |
| `cri.riesgo` | exposición del cliente y del letrado |
