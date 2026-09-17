# Agentes

> Para qué sirve cada sub-agente y qué no puede hacer. Nueve grupos, 56
> sub-agentes. Solo `sec.mail` existe en código; el resto es diseño.
> La arquitectura del sistema —cómo se componen los grupos, las rutas, los
> arquetipos— está en `ARQUITECTURA.md`. Última actualización: 2026-09-16

**Estado.** Implementado: `sec.mail`. Los otros 55 son diseño, sin código.

Cada entrada sigue la misma plantilla: qué hace, su contrato, las reglas de dominio
que debe respetar, cómo falla y de qué depende. Un sub-agente está bien acotado
cuando puede fallar solo y verificarse solo.

`secretario` y `procesal` están detallados, y de `investigador` lo está
`inv.normativa`. Del resto hay todavía solo la tarea de cada sub-agente, no su
contrato ni sus reglas: no es que no tengan restricciones, es que aún no están
escritas.

**Dónde corre cada uno.** Los agentes de IA —los que invocan un modelo de
lenguaje— corren todos en el servidor `maat`, porque ahí está el modelo. Los
agentes de software, deterministas y sin LLM, corren donde están sus datos y sus
credenciales: `sec.mail` en el PC del letrado. Ver `ARQUITECTURA.md` §1, «Dónde
corre cada agente».

---

## SECRETARIO · despacho — 6

La capa del despacho. Sabe recibir, clasificar, recordar y enviar; no sabe de plazos
ni de derecho, y no toca ningún canal procesal.

**`sec.mail`** — receptor · agente de software, en local · **implementado** (lo que aún falta, en §8.3)
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
El letrado no verifica las fechas de plazo (ver `pro.calendario`, en PROCESAL), así
que el riesgo se desplaza: ya no es tanto calcular mal como que un aviso pase
desapercibido. Este sub-agente es la mitad de la garantía; la otra mitad es la
validación del motor de días.

- **Contrato:** `{evento, prioridad}` → `{notificacion, log_entry, visto}`
- **Reglas:**
  - **Todo lo que notifica queda en el log.** Ese log es la prueba de qué se advirtió
    y cuándo: si un plazo se pierde, es lo que distingue un fallo del sistema de un
    aviso desatendido.
  - **Un aviso de plazo basta para actuar sin abrir nada más:** asunto, qué hay que
    hacer, órgano, último día, días que quedan y una **fecha recomendada** anterior al
    vencimiento, con el margen de seguridad de `pro.caducidad`. Si el plazo es
    `provisional`, lo dice.
  - La insistencia escala con la franja que le pasa `pro.caducidad`: aviso al entrar y
    recordatorios cada vez más seguidos según se acerca el vencimiento. Un aviso en
    franja crítica no puede pesar lo mismo que uno en franja holgada.
  - **Cambios de fecha:** si un plazo se **adelanta**, aviso inmediato con la fecha
    anterior y la nueva; si se **retrasa**, se actualiza sin interrumpir y queda en el
    log. Enterarse tarde de un adelanto puede costar el plazo; de un retraso, no.
  - **Comprueba que el aviso se ha visto.** Si un aviso importante no se abre, insiste
    y lo manda también por otra vía.
  - El log es enumerable y consultable, no un flujo efímero de notificaciones.
- **Falla si:** notifica sin registrar — y entonces no hay constancia de la
  advertencia; trata todos los avisos igual, y el letrado deja de leerlos; o da por
  avisado al letrado sin comprobar que ha visto un aviso crítico.

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

**El letrado no verifica las fechas que produce**: recibe el aviso y actúa. Es una
decisión de diseño, no un descuido: se diseña pensando en un despacho de un solo
abogado, y el sistema tiene que quitarle trabajo, no dárselo. La consecuencia es que
nadie más en la cadena va a detectar un error, así que la garantía se reparte en dos:
la **corrección**, antes de usarlo con clientes (validación, abajo), y la
**visibilidad**, después (`sec.notificador`).

- **Contrato:** `{fecha_inicio, plazo, unidad, tipo_dia, sentido, tipo_computo, orden, municipio_organo, municipio_interesado?, ahora}` → `{fecha_limite, dias_restantes, estado, festivos_aplicados[], reglas_aplicadas[], version_calendario, avisos[]}`
  - `estado`: `firme · provisional`.
  - `sentido`: hacia delante, o hacia atrás («X días antes de la vista»). Lo necesita
    la regla de la fecha prudente, porque un festivo que falta tiene efectos opuestos
    en cada caso.
- **Calculadora y calendario van separados.** El motor conoce las reglas pero no
  guarda festivos: los recibe de un calendario mantenido aparte. Los festivos cambian
  cada año, en cada municipio y a veces a mitad de año; si vivieran dentro del motor,
  cada corrección de un boletín obligaría a tocar el código que decide plazos.
- **Reglas:**
  - Sábados y domingos son inhábiles a efectos procesales.
  - El *dies a quo* es el día **siguiente** a la notificación, no el de la notificación.
  - Agosto es inhábil para actuaciones judiciales con excepciones tasadas; en el orden
    social varias modalidades urgentes siguen corriendo (despido, tutela de derechos
    fundamentales, conflicto colectivo).
  - Del **24 de diciembre al 6 de enero**, ambos inclusive, también es inhábil para
    actuaciones judiciales salvo las urgentes (art. 183 LOPJ, desde la LO 14/2022).
  - **El cómputo administrativo no es el judicial**: los plazos por meses van de fecha
    a fecha y el calendario de festivos aplicable es distinto.
  - En los plazos por meses, si el mes de vencimiento no tiene día equivalente, el
    plazo vence el último día del mes (art. 133.3 LEC, art. 30.4 Ley 39/2015). Si el
    último día es inhábil, se prorroga al siguiente hábil.
  - **Judicial:** festivos nacionales + autonómicos + **locales del municipio del
    órgano** (art. 182 LOPJ), no del municipio del despacho.
  - **Administrativo:** un día es inhábil si lo es en la sede del órgano **o** en el
    municipio donde reside el interesado (art. 30.6 Ley 39/2015). Mirar solo el del
    órgano da por hábil un día que la ley declara inhábil.
  - **Cada regla lleva su fecha de entrada en vigor.** Las normas procesales se
    reforman: un plazo de 2021 no conoce la inhabilidad de Navidad. Sin vigencia,
    recalcular un caso antiguo —o validar con sentencias de otros años— da resultados
    falsos.
- **Fecha prudente.** Cuando falta un dato, da la fecha que obliga a actuar **antes**,
  nunca después, y marca el resultado `provisional`. Lo peor que puede pasar es
  presentar un día antes de lo necesario.
  - Casos: festivos del año siguiente aún sin publicar (los locales salen entre agosto
    y diciembre, y un plazo que empieza en noviembre y vence en enero ya los necesita);
    varias fechas de inicio candidatas porque la notificación es dudosa (calcula con la
    más temprana).
  - Hacia delante, un festivo que falta hace vencer el plazo antes: basta con calcular
    sin él. Hacia atrás el efecto es el contrario: se supone que los locales que faltan
    —como mucho dos por municipio— caen dentro del plazo.
  - Cuando llega el dato, recalcula solo. Si la fecha se adelanta, `sec.notificador`
    avisa en el acto; si se retrasa, se actualiza sin interrumpir.
- **Cada fecha tiene su explicación.** El resultado guarda qué reglas y qué festivos se
  aplicaron y con qué versión del calendario. El letrado no tiene por qué leerla, pero
  si alguien pregunta «¿por qué esta fecha?» hay respuesta, y el cálculo se puede
  repetir aunque el calendario se haya corregido después.
- **Es un agente de software**, sin LLM: corre donde estén los datos de los
  expedientes, según la regla de `ARQUITECTURA.md` §1, «Dónde corre cada agente». El
  calendario, en cambio, es dato público y puede vivir en el servidor sin reservas.
- **Validación antes de usarlo con clientes.** Como nadie revisa después, no entra en
  uso hasta superar las tres comprobaciones. No hacen falta casos reales de un
  abogado, que hoy no existen:
  - **Sentencias** que resolvieron si algo se presentó a tiempo: recogen la fecha de
    notificación, los días excluidos y el último día, y el motor tiene que llegar a la
    misma fecha. Se eligen a mano en el CENDOJ, que no permite descargas masivas ni uso
    comercial de su base: de cada una se guarda el ECLI y las fechas, nunca el texto.
  - **Ejemplos sacados de la ley**, varios por regla, cada uno citando su artículo y
    cubriendo los casos límite: notificación en viernes, plazo que cruza agosto o
    Navidad, último día festivo, 31 de enero más un mes.
  - **Pruebas de sentido común repetidas miles de veces** con datos aleatorios: añadir
    un festivo nunca adelanta un plazo hacia delante; en N días hábiles hay exactamente
    N días hábiles; intercambiar los dos municipios del art. 30.6 no cambia el
    resultado.
- **Falla si:** usa el calendario del despacho; trata agosto como uniforme; mezcla
  cómputo civil y administrativo; ignora el municipio del interesado en lo
  administrativo; da una fecha posterior a la real cuando le falta un dato; da una
  fecha que no sabe explicar; se usa con clientes sin haber superado la validación.
- **Necesita:**
  - Calendario oficial de festivos por municipio, **fiable y al día**. Mantenerlo no
    es tarea de este sub-agente: lo llena el **recolector** (ver nota siguiente).
  - `municipio_organo`, de `pro.destino`; en cómputo administrativo, además, el
    municipio de residencia del interesado, de la ficha del cliente.

**`pro.calendario/recolector`** — quien llena el calendario
El hueco que la línea anterior daba por resuelto. No calcula nada: va a los boletines
oficiales, lee las publicaciones y escribe los festivos que el motor consume.

- **Contrato:** `{anios[]}` → `{version, anotados, retirados, confirmados[], fallos[]}`
- **Reglas:**
  - **Solo escribe; el motor solo lee.** Es lo que permite validar el motor contra
    datos fijos, y lo que evita que un boletín caído deje al despacho sin calcular.
  - **Un fallo nunca se traga.** Si no consigue leer una publicación, deja su
    cobertura en `pendiente` y sigue con la siguiente. Un hueco silencioso se
    confundiría con días hábiles y aparecería semanas después como un plazo perdido.
  - **Distingue `pendiente` de `sin_publicar`.** Lo primero hay que arreglarlo; lo
    segundo es normal —las locales salen entre agosto y diciembre del año anterior—.
    Los dos dan fecha prudente, pero solo uno pide intervención.
  - **No es de una sola pasada**, aunque lo parezca: las correcciones a mitad de año
    obligan a repetirla, y por eso guarda la huella de cada documento leído.
  - Es un **agente de software**, sin LLM. Solo lee dato público, así que puede correr
    en el servidor y replicarse.
- **Falla si:** deja un hueco sin marcar; borra un festivo en vez de retirarlo;
  aborta la pasada entera porque una fuente falló; confunde los dos cómputos.
- **Necesita:** acceso de red a los boletines. Nada más: ni credenciales ni datos de
  expedientes.

**Establecer y actualizar son dos trabajos, no uno.** *Establecer* los festivos que hoy
están publicados se hace una vez; *actualizar* —enterarse de que una comunidad ha
rectificado en febrero— es lo que de verdad tiene que correr solo. Automatizar lo
primero cuesta más que hacerlo, así que el establecimiento de lo que no tiene extractor
lo hace **una persona**, y el actualizador queda pendiente de diseño.

Que lo lea una persona no relaja nada, porque la garantía no está en quién lee sino en
lo que se exige de cada dato:

- **Sin cita literal del boletín, un festivo no entra.** Se copia el trozo de texto del
  que sale la fecha, en el idioma original y sin traducir: traducir ya es interpretar,
  y la interpretación es justo lo que se está comprobando. Es la misma línea que se
  trazó con `inv.normativa`: quien lee decide **dónde mirar**, pero el valor lo produce
  y lo comprueba el código.
- **Cinco comprobaciones deterministas**, sin modelo, antes de escribir: el día aparece
  en la cita; el mes que la cita nombra coincide con la fecha; el día de la semana
  cuadra, si el boletín lo dice; como mucho dos fiestas locales por municipio y año; y
  ninguna cae en un festivo autonómico o nacional —si coincide, se ha leído mal la
  columna—.
- **Un ámbito con una entrada rechazada no se confirma entero.** Lo que se sabe de él
  está incompleto, así que sigue dando fecha prudente. Media verdad no es mejor que
  ninguna cuando de ahí sale un plazo.
- **El dato establecido vive en el repositorio**, con su URL y su cita al lado, no en
  el resultado de una llamada a un modelo. Así cualquiera del despacho puede
  contrastarlo, y no depende de que una API siga respondiendo igual dentro de dos años.
- **Se descartó usar un modelo externo** para esta fase. No por calidad: por coste —
  sería gasto nuevo del despacho— y porque lo que aportaría se consigue igual
  escribiendo el dato una vez. La decisión se reabrirá al diseñar el actualizador.

El procedimiento, escrito para las personas del equipo, está en `RECOLECCION.md`.

**Ninguna fuente se lee sin verificar el certificado.** Varias administraciones emiten
con autoridades del sector público español que no vienen en los almacenes de confianza
habituales (IZENPE, Firmaprofesional). La salida es añadir esa raíz concreta y
comprobada, nunca desactivar la comprobación: quien pudiera interponerse elegiría qué
días son inhábiles, y no daría error sino una fecha equivocada con aspecto de correcta.
Si una fuente no se puede leer, su cobertura queda `pendiente` y ya está.

*Origen del calendario.* No existe una fuente única de festivos por municipio. Se forma
en tres capas: las **nacionales**, las **autonómicas**, que fija cada comunidad, y hasta
dos **locales** por municipio, que propone el pleno del ayuntamiento y aprueba y
publica la autoridad laboral de la comunidad. El BOE publica cada año (hacia octubre)
las nacionales y autonómicas, pero **no las locales**. Casi todas las comunidades
publican las locales en su boletín, con dos excepciones: Castilla y León, en los nueve
boletines provinciales, y el País Vasco, en los boletines de Álava, Bizkaia y Gipuzkoa.
Canarias añade fiestas insulares. En total, unas 29 publicaciones distintas solo para
las locales, que a menudo se corrigen con el año ya empezado (en 2026, Andalucía en
febrero y abril; Aragón, en marzo). Por eso no basta con refrescar el calendario una
vez al año: si no se vigila, el sistema calcula mal **en silencio**.

*Y son dos calendarios, no uno.* El judicial sale de la resolución anual de **fiestas
laborales**: el art. 182 LOPJ no tiene lista propia, declara inhábiles los días de
fiesta laboral en la comunidad o la localidad. El administrativo sale de la resolución
de **días inhábiles de la AGE** y de los acuerdos equivalentes de cada comunidad. A
nivel estatal y autonómico coinciden —el apartado segundo de la de la AGE remite a los
mismos días, como manda el art. 30.7 de la Ley 39/2015—, pero **a nivel local no
tienen por qué**: para el cómputo administrativo los días de un municipio son los que
fije el calendario de su comunidad, no sus fiestas patronales. Por eso cada festivo se
guarda con el cómputo al que sirve, y pedir días inhábiles sin decir cuál es un error,
no un descuido con valor por defecto.

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
- **Contrato:** `{tipo_documento, organo, expediente}` → `{canal, destinatario, municipio_sede}`
- **Reglas:**
  - Resuelve el canal que usará el secretario: `lexnet-out · registro · burofax ·
    notaria · entrega`.
  - **Resuelve también el municipio de la sede del órgano**, a partir de una tabla de
    órganos y sedes. `pro.calendario` lo necesita para aplicar los festivos locales, y
    este es el sub-agente que ya conoce el órgano; sin esta resolución el calendario
    tendría que adivinarlo o caería en el municipio del despacho. Esta consulta se usa
    **ya en la puerta**, no solo en la salida: el primer cálculo del plazo la necesita.
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
  - Calendario **administrativo**: los plazos por meses van de fecha a fecha, y un día
    es inhábil si lo es en la sede de la Administración destinataria **o** en el
    municipio donde reside el interesado (art. 30.6 Ley 39/2015).
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

**`inv.normativa`** — artículo y vigencia · agente de IA, en `maat` · **diseñado, sin código**

Único sub-agente diseñado con **bucle de herramienta** en vez de una sola llamada:
localizar un artículo exige a veces reintentar con otro identificador, y eso es
iterativo por naturaleza. Los demás sub-agentes siguen siendo de una llamada; ver
las notas del grupo.

- **Contrato:** `{consulta, fecha_del_hecho}` → `{norma, articulo, vigente_en, texto, url}`
  o `{no_encontrado, motivo}`
- **Herramienta — la única que se le ofrece:**

  ```
  consultar_boe(norma, articulo, fecha) → {texto, url, ...} | {error}
  ```

  `norma` es el identificador BOE (`BOE-A-1889-4763`), nunca un nombre: un nombre es
  ambiguo y un identificador es verificable. `fecha` es obligatoria — el contrato del
  grupo exige vigencia a la fecha del hecho, así que sin fecha no hay respuesta
  correcta posible.

- **Reglas:**
  - **El texto legal no pasa por el modelo de vuelta.** El modelo decide *qué*
    consultar; el texto lo devuelve la herramienta y lo ensambla el código, literal.
    Medido en `maat` con `qwen2.5:7b`: al pedirle que reprodujera el art. 1124 CC
    convirtió «no **cumpliere**» en «no **cumpla**» dentro de una cita entrecomillada.
    Es correcto en castellano, nadie lo nota al leer, y destruye la comprobabilidad
    que `AGENTES.md` exige a todo el grupo. No se corrige con el prompt: un 7B que
    regenera texto siempre puede deslizar una palabra. Se corrige no dejándole
    regenerarlo.
  - **La parada la decide el código, no el modelo.** Éxito = `consultar_boe` devolvió
    texto. No se para porque el modelo diga que ha terminado: eso es una opinión suya
    sobre su propio trabajo, y este es el agente que existe para no fiarse de eso.
  - **Tres intentos, y detección de llamada repetida.** Si repite nombre y argumentos
    idénticos, se corta: es el modo de fallo típico de un modelo pequeño en bucle.
    Agotados los intentos, el resultado es `no_encontrado` — nunca una respuesta
    redactada de memoria.
  - **El error de la herramienta enseña.** `ERROR: norma "CC" no reconocida. Formato
    BOE-A-AAAA-NNNN. Código Civil = BOE-A-1889-4763` permitió la corrección en la
    iteración siguiente; un `400 Bad Request` no habría enseñado nada. La calidad del
    mensaje de error es la mitad del resultado, no un detalle de implementación.
  - **Prefijo estable.** System prompt y esquema de la herramienta, fijos y primero;
    lo variable, al final. La caché de prefijo de Ollama bajó el procesado de 21,8 s a
    0,13 s en la misma petición repetida. Meter la fecha de hoy en el system prompt
    cuesta ~20 s por iteración.
  - **Devuelve siempre `url`.** Es lo que hace la cita comprobable de verdad: el
    letrado pincha y ve el original.

- **Falla si:** deja que el modelo reproduzca el texto legal; deriva la parada del
  modelo en vez de del resultado de la herramienta; devuelve una cita sin `url`;
  responde sin fecha de vigencia; o acepta un nombre de norma en vez de un
  identificador BOE.

- **Medido** (`maat`, `qwen2.5:7b`, 12 núcleos, sin GPU, 2026-09-16): emite
  `tool_calls` bien formados y normaliza fechas por su cuenta; se corrige ante un
  error explicativo; para al recibir datos. Generación ~7,4 tok/s. Bucle de tres
  vueltas, 92 s; con la salida directa desde la herramienta, ~41 s. Contra un
  `consultar_boe` simulado y un solo artículo: **la fuente real del BOE y los casos
  de artículo modificado siguen sin medir.**

### Notas de diseño del grupo

- **`inv.normativa` es la excepción, no el patrón.** Lleva bucle porque localizar un
  artículo puede exigir reintentar; los otros cuatro sub-agentes del grupo son de una
  llamada y no deben ganar herramientas «por coherencia». Un bucle añade modos de
  fallo, y solo se paga donde la tarea es genuinamente iterativa.
- **La superficie de herramientas es cerrada y de lectura.** Al modelo se le ofrece
  exactamente una función, definida por nosotros, contra una fuente pública. No tiene
  disco, ni shell, ni forma de pedir nada que no esté en ese array. Es lo que hace
  admisible un bucle dentro de un sistema que debe poder auditarse.

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
