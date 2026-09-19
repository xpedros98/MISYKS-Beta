# Componentes: agentes IA y módulos

> Para qué sirve cada componente y qué no puede hacer. Nueve grupos, 56
> componentes. Solo dos tienen código; el resto es diseño.
> La arquitectura del sistema —cómo se componen los grupos, las rutas, los
> arquetipos— está en `ARQUITECTURA.md`. Última actualización: 2026-09-19

**Dos clases de componente, y no se confunden.** Un **agente IA** invoca un modelo
de lenguaje: su salida hay que acotarla y comprobarla porque puede inventar. Un
**módulo** es código determinista, sin LLM: la misma entrada da siempre la misma
salida y se audita leyéndolo. «Componente» es el término que los engloba cuando da
igual cuál de los dos sea; «agente», a secas, significa siempre agente IA. La
frontera no es de estilo: de ella dependen dónde corre cada uno (abajo) y qué
garantías hay que exigirle.

**Estado.** Implementados: `sec.mail` y `sec.agenda`, los dos módulos. A medias:
`pro.calendario`, del que existe el calendario de festivos y su recolector pero **no
el motor de días**, que es el módulo propiamente dicho. Los otros 53 son diseño, sin
código.

Cada entrada sigue la misma plantilla: qué hace, su contrato, las reglas de dominio
que debe respetar, cómo falla y de qué depende. Un componente está bien acotado
cuando puede fallar solo y verificarse solo.

`secretario` y `procesal` están detallados, y de `investigador` lo está
`inv.normativa`. Del resto hay todavía solo la tarea de cada componente, no su
contrato ni sus reglas: no es que no tengan restricciones, es que aún no están
escritas.

**Dónde corre cada uno.** Los agentes IA corren todos en el servidor `maat`,
porque ahí está el modelo. Los módulos corren donde están sus datos y sus
credenciales: `sec.mail` y `sec.agenda` en el PC del abogado --comparten cuenta y
tokens--, y `pro.calendario` también, porque el motor de días consulta expedientes. Su recolector es la excepción que confirma
la regla: solo lee boletines públicos, así que puede correr en el servidor. Ver
`ARQUITECTURA.md` §1, «Dónde corre cada componente».

---

## SECRETARIO · despacho — 6

La capa del despacho. Sabe recibir, clasificar, recordar y enviar; no sabe de plazos
ni de derecho, y no toca ningún canal procesal.

**`sec.mail`** — receptor · módulo, en local · **implementado** (lo que aún falta, en §8.3)
Gmail API o Microsoft Graph, **autenticadas por OAuth**, y base local cifrada con
SQLCipher. Corre en el ordenador del abogado, no en el servidor: tiene el acceso al
correo y lee el contenido sin anonimizar, así que ese contenido no sale de su
máquina. El «tercer mundo» —iCloud, Fastmail, servidores propios— seguirá siendo
IMAP con contraseña de aplicación, porque ahí no hay otra vía, pero **no está
escrito**: no hay adaptador (`ARQUITECTURA.md` §8.6).

- **Contrato:** `{cuenta, ventana}` → `{mensajes[], adjuntos[], resumen}`
- **Reglas:**
  - El módulo **lee, no vacía**: el correo permanece en el servidor y el abogado lo
    sigue viendo desde sus propios dispositivos. Tampoco marca como leído.
  - **La identidad del mensaje es `(proveedor, mensaje_id)`**, no el identificador a
    secas: dos proveedores pueden dar el mismo y no son el mismo correo. En Graph,
    además, **mover cambia el identificador**, así que la fila se queda con el nuevo.
  - **El cursor de sincronización es opaco** —`historyId` en Google, `deltaLink` en
    Graph— y se guarda sin interpretarlo. Si el proveedor lo rechaza por antiguo, se
    hace inventario completo en vez de fallar: repetir identificadores es inofensivo,
    perderlos sería un correo que el despacho no ve.
  - **El cursor no es la garantía de no perder nada; la cola sí.** Las dos APIs
    avanzan el cursor de golpe al final de la respuesta, no mensaje a mensaje. Lo
    anunciado se apunta en una cola *antes* de guardar el cursor, y cada correo sale
    de ella solo cuando está guardado. El cursor dice hasta dónde se ha *preguntado*;
    la cola, qué falta por *traer*.
  - Separa cuerpo y adjuntos como documentos distintos, y **desciende por los
    reenvíos anidados**: el documento relevante suele ir dentro de un forward, no en
    el primer nivel.
  - Conserva cabeceras como metadato probatorio: fecha de recepción y remitente.
  - Produce el **resumen** que consume `sec.clasificador`. Extraer adjuntos ocurre
    antes de resumir, nunca después.
- **Falla si:** guarda el cursor antes de encolar lo anunciado, y pierde los correos
  de una tanda interrumpida; identifica un mensaje sin su proveedor; pierde el
  adjunto anidado; resume antes de extraer.
- **Necesita:** tokens de OAuth (que se rotan, así que hay que poder reescribirlos) y,
  por carpeta, el cursor del proveedor más la cola de lo pendiente de descargar.

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

**`sec.agenda`** — reuniones, juicios y plazos · módulo, en local · **implementado**
(lo que aún falta, en §8.3)
Google Calendar API con el **mismo consentimiento OAuth que el correo** y base local
cifrada con SQLCipher. Corre junto a `sec.mail` porque usa sus tokens; §8.6 deja
abierto si debería vivir en `maat`, para poder avisar con el equipo del abogado
apagado.

- **Contrato:** `{eventos[], plazos_de_procesal[]}` → `{agenda, conflictos[]}`
- **Reglas:**
  - **No calcula plazos: los recibe.** `procesal` computa, `sec.agenda` anota.
    Duplicar el cálculo aquí garantiza que las dos versiones diverjan. En el código
    no hay ni una suma de días, y es a propósito.
  - **Un plazo que se mueve no es un dato nuevo, es un aviso.** Al recibirlo otra vez
    se compara con la fecha anterior y se dice si se **adelanta** o se **retrasa**:
    lo primero exige aviso inmediato porque puede costar el plazo, lo segundo se
    actualiza sin interrumpir a nadie. Es lo que consume `sec.notificador`.
  - **Del calendario no viene qué es cada cosa.** La API no distingue un juicio de un
    café, así que todo entra como `sin_clasificar` y lo fija después una persona (o
    algún día `sec.clasificador`). Un evento sin clasificar **sí ocupa hora** a
    efectos de colisiones: la misma prudencia que aplica `pro.calendario` a los
    festivos que le faltan, porque una colisión de más se descarta en dos segundos y
    una de menos se descubre el día del señalamiento.
  - **Escribir en el calendario del abogado es a petición, nunca automático.** Una
    agenda que empieza a crear eventos sola deja de ser de fiar.
  - **La ventana la impone la agenda, no el proveedor.** Google, al preguntarle por lo
    que ha cambiado, contesta con la serie anual entera expandida hasta 2099 aunque se
    le haya pedido un año. Lo que cae fuera se descarta —salvo que ya estuviera
    guardado, que es como se sabe que algo se ha movido fuera—.
  - Tres clases de entrada con naturaleza distinta: reuniones (internas, movibles),
    juicios y vistas (externas, fijas) y plazos (derivados, con fecha dura).
  - Detecta **colisiones**: dos señalamientos del mismo abogado a la misma hora es la
    causa de suspensión más frecuente y se anticipa semanas antes.
  - Guarda obligaciones vivas de documentos ya cerrados —vencimientos de contrato,
    prórrogas, actualizaciones de renta—, que es lo que da vida posterior al
    arquetipo G.
  - **Los plazos no se guardan aquí: se proyectan.** Un plazo es un **hito del
    expediente** y vive donde vive el expediente; la agenda lo lee y lo enseña junto a
    las vistas y las reuniones, que es de donde sale el valor de tener agenda, pero no
    guarda copia de la fecha. Guardarla era duplicar el mismo dato en dos sitios, y eso
    acaba en dos fechas distintas sin forma de saber cuál vale.
  - **Recoge el «Hecho» del abogado.** Si presentó por su cuenta, fuera de MISYKS, un
    clic cierra el plazo como `cumplido`. Guarda la fecha de hoy, que puede cambiar
    —importa si la presentación abre plazos futuros, como el silencio
    administrativo—, se puede deshacer y queda en el log de `sec.notificador`. No es
    verificar nada: es informar de algo que el sistema no puede ver. Sin él, los avisos
    de un plazo ya cumplido seguirían sonando.
- **Falla si:** calcula plazos por su cuenta; solo mira el día siguiente; no cruza
  agendas entre abogados del despacho; cierra un plazo con «Hecho» sin guardar la
  fecha de presentación; concluye que un evento ya no existe a partir de una
  sincronización incremental, donde lo que no viene es lo que **no ha cambiado**
  —confundirlo vacía la agenda sin dar ningún error—; o compara horas locales en vez
  de instantes, que inventa colisiones entre zonas y silencia las reales.
- **Necesita:** la cuenta conectada por OAuth (la misma que `sec.mail`) y, de
  `procesal`, los plazos ya calculados.

**`sec.notificador`** — avisos y log
El abogado no verifica las fechas de plazo (ver `pro.calendario`, en PROCESAL), así
que el riesgo se desplaza: ya no es tanto calcular mal como que un aviso pase
desapercibido. Este componente es la mitad de la garantía; la otra mitad es la
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
  - **El estado del plazo manda.** Un plazo `cumplido` —por `pro.acuse` o por el
    «Hecho» del abogado— deja de generar avisos. Un plazo `vencido` y un **plazo no
    reconocido** generan aviso siempre, con su explicación.
  - El log es enumerable y consultable, no un flujo efímero de notificaciones.
- **Falla si:** notifica sin registrar — y entonces no hay constancia de la
  advertencia; trata todos los avisos igual, y el abogado deja de leerlos; da por
  avisado al abogado sin comprobar que ha visto un aviso crítico; o sigue avisando de
  un plazo ya cumplido.

**`sec.entrega`** — emisor
Misma conexión de correo, dirección contraria. Dos usos: mandar a firmar y compartir
con otro abogado.

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

Convierte un documento en una posición dentro del despacho. Grupo mixto: extraer e
identificar es trabajo de agente IA; nombrar según convención y deduplicar por hash
no necesita modelo. Cuál es cuál se fija al escribir sus contratos.

| componente | uso |
|---|---|
| `arc.metadatos` | nº de procedimiento, órgano, autos, fecha |
| `arc.partes` | demandante, demandado, procurador, abogado contrario, LAJ |
| `arc.emparejador` | a qué expediente pertenece; devuelve candidatos |
| `arc.nomenclador` | nombra y ubica el fichero según convención del despacho |
| `arc.deduplicador` | hash: el mismo documento llegado por dos vías |

## PROCESAL · tiempo y forma — 12

Justo después de la entrada y justo antes de la salida. **No toca canales**: no tiene
credenciales ni sabe enviar. Determinista de punta a punta: **los doce son módulos,
ninguno es agente IA**. Si alguno necesitara un LLM, está mal acotado: lo que falta
es una tabla mejor.

### Puerta

**`pro.calendario`** — el motor de días
Dependencia de todos los demás: ningún plazo se calcula sin pasar por él.

**El abogado no verifica las fechas que produce**: recibe el aviso y actúa. Es una
decisión de diseño, no un descuido: se diseña pensando en un despacho de un solo
abogado, y el sistema tiene que quitarle trabajo, no dárselo. La consecuencia es que
nadie más en la cadena va a detectar un error, así que la garantía se reparte en dos:
la **corrección**, antes de usarlo con clientes (validación, abajo), y la
**visibilidad**, después (`sec.notificador`).

- **Contrato:** `{fecha_inicio, plazo, unidad, tipo_dia, sentido, tipo_computo, urgente, orden, municipio_organo, municipio_interesado?, ahora}` → `{fecha_limite, dias_restantes, estado, festivos_aplicados[], reglas_aplicadas[], version_calendario, avisos[]}`
  - `estado`: `firme · provisional`.
  - `tipo_computo`: `judicial · administrativo · civil`.
  - `urgente`: si es cierto, agosto y Navidad cuentan. Qué plazos son urgentes no lo
    decide este motor: lo dice la tabla de plazos de `pro.caducidad`.
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
  - **Civil** (plazos sustantivos del Código Civil): días naturales, sin excluir los
    inhábiles (art. 5.2 CC), así que no consulta festivos. Contarlos como hábiles
    alarga el plazo más allá del real.
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
  aplicaron y con qué versión del calendario. El abogado no tiene por qué leerla, pero
  si alguien pregunta «¿por qué esta fecha?» hay respuesta, y el cálculo se puede
  repetir aunque el calendario se haya corregido después.
- **Es un módulo**, sin LLM: corre donde estén los datos de los expedientes, según la
  regla de `ARQUITECTURA.md` §1, «Dónde corre cada componente». El calendario, en
  cambio, es dato público y puede vivir en el servidor sin reservas.
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
    es tarea de este módulo: lo llena el **recolector** (ver nota siguiente).
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
  - **Tres motivos distintos para no tener un dato, y no se mezclan.** `pendiente`
    es «no se ha intentado»: no hay extractor para esa fuente todavía, trabajo
    previsto. `sin_publicar` es «se miró y el boletín aún no ha sacado ese año»,
    normal entre enero y octubre. `fallido` es «se intentó y salió mal», y lleva el
    motivo guardado con la fila. Los tres dan fecha prudente igual, así que para el
    motor son lo mismo; la diferencia es para quien mantiene el calendario, y sin
    ella una fuente que se rompe se confunde con una que nunca se ha escrito y la
    regresión se queda ahí indefinidamente.
  - **No es de una sola pasada**, aunque lo parezca: las correcciones a mitad de año
    obligan a repetirla, y por eso guarda la huella de cada documento leído.
  - Es un **módulo**, sin LLM. Solo lee dato público, así que puede correr
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

**Cómo se lee el estado del calendario.** Tres cosas que se confunden con facilidad:

- **De los cuatro estados, solo `fallido` pide actuar.** `pendiente` es que aún no
  hay extractor para esa fuente, y `sin_publicar`, que el boletín no ha sacado ese
  año todavía. Los tres dan fecha prudente por igual: la distinción es para
  mantenimiento, no para el motor.
- **El último festivo guardado no es hasta cuándo se puede uno fiar.** Con 2026
  confirmado entero, el último es el 26 de diciembre y el calendario sirve hasta el
  31: los días sin festivo entre medias también son dato. Lo segundo es el
  *horizonte*, que se calcula por ámbito y cómputo contando años consecutivos
  confirmados y cortando en el primer hueco.
- **Un ámbito solo llega a firme si toda su cadena lo está** (`08019 → ES-CT → ES`).
  Un eslabón sin confirmar la invalida entera: sin las fiestas locales no se puede
  afirmar que un día sea hábil, y suponerlo adelantaría el vencimiento real. Por eso
  Madrid sale firme en judicial y no en administrativo — sus fiestas del ayuntamiento
  se tienen, el calendario administrativo de su comunidad no.

**Las dos bases viven en `~/.misyks/`**, fuera del repo: `sec_mail.db` cifrada con
SQLCipher, y `calendario.db` en SQLite a secas porque los festivos son dato público.
`recolectar` tarda un par de minutos y va escribiendo, así que consultarla mientras
corre exige abrirla en solo lectura.

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

**`pro.caducidad`** — plazos perentorios · módulo, en local · **diseñado, sin código**
El que puede matar un caso. Responde a una sola pregunta: **¿hasta cuándo se puede
hacer esto, y qué se pierde si no se hace?** Solo para los plazos cuyo vencimiento
hace perder algo sin remedio: ejercitar una acción (demandar un despido), contestar,
recurrir u oponerse dentro de un proceso, recurrir ante la Administración, y los
plazos que fija el propio órgano en una resolución. La prescripción es de
`pro.prescripcion`; las vistas y señalamientos, que son fechas fijas, van directos a
`sec.agenda`; contar días es de `pro.calendario`.

**No lee documentos.** Recibe ya extraídos, de los componentes que leen (secretario y
archivador), el tipo de acto, la fecha y el medio de notificación, el órgano y, si la
resolución lo fija, el plazo; cuando hay duda, varias opciones de cada cosa. A partir
de ahí todo es tabla y reglas fijas: con los mismos datos, el mismo resultado.

- **Contrato:** `{actos_candidatos[], notificacion: {fechas_candidatas[], medio}, orden, municipio_organo, municipio_interesado?, plazo_en_resolucion?, pausas_y_reinicios[], preparacion_ajustada?, ahora}` → `{plazos[]}`, y cada plazo `{tipo, fila_tabla, fecha_recomendada, ultimo_dia, ultimo_momento_legal?, franja, estado, bloqueo, explicacion}`
  - `estado`: `firme · provisional`. `franja`: `holgado · ajustado · crítico · vencido`.
  - Devuelve una **lista**: una misma notificación abre a menudo varios plazos (una
    sentencia, el de aclaración y el de recurso).
- **Reglas:**
  - **Una sola fuente de verdad: la tabla de plazos.** Nadie más calcula plazos: ni
    `sec.agenda` ni el secretario al leer un correo. El ecosistema antiguo tenía tres
    sitios que calculaban plazos, cada uno con su tabla, y la misma pregunta daba
    fechas distintas según por dónde entrara.
  - **Lo que no está en la tabla no se inventa.** Si la resolución fija el plazo («se
    concede un plazo de diez días»), se usa ese. Si no, aviso de **plazo no
    reconocido** al abogado, y la fila que falta se añade a la tabla. El ecosistema
    antiguo, a falta de fila, buscaba un número en el articulado: «un mes» acababa
    convertido en 30 días hábiles, unas seis semanas.
  - **El *dies a quo* sale de reglas, nunca de «hoy».** Depende del medio: una
    notificación de LexNET sin abrir se tiene por hecha a los tres días hábiles
    (art. 162.2 LEC, matizado por el Supremo en junio de 2026), y la notificación al
    procurador, la administrativa electrónica y la personal tienen reglas propias. El
    detector de plazos del ecosistema antiguo contaba desde el día en que leía el
    correo.
  - **Tres fechas, no una.**
    - *Fecha recomendada*: el último día menos un **margen que depende del tipo de
      escrito**, fijado en la tabla. Es la que recibe el abogado para organizarse.
    - *Último día* del plazo.
    - *Último momento legal*: ante los tribunales, hasta las 15:00 del día hábil
      siguiente (art. 135.5 LEC, que desde el RDL 6/2023 vale también para plazos
      sustantivos como el del despido). **Nunca se usa para planificar**: solo aparece
      como salida de emergencia. Ante la Administración no existe.
  - **Franja, no booleano, y calculada, no opinada.** Compara los días que quedan hasta
    la fecha recomendada con el **tiempo de preparación** de ese tipo de escrito: diez
    días sobran para una reposición y no alcanzan para una demanda compleja. MISYKS
    propone un tiempo aproximado por tipo y **el abogado puede ajustarlo**; el ajuste
    cambia cuándo empiezan los avisos y cuánto insisten, **nunca las fechas**. La
    franja alimenta a `sec.notificador`. En el ecosistema antiguo la prioridad la ponía
    un modelo.
  - **Y prórroga no es ninguna de las dos.** Una pausa detiene el reloj por un hecho
    tasado; un recálculo corrige una fecha que estaba mal o le faltaba un dato; una
    **prórroga** es el órgano ampliando un plazo que estaba bien. La fecha nueva no sale
    de ninguna regla nuestra: viene en una resolución, y se guarda con su referencia.
    Confundirlas deja un vencimiento que nadie sabe explicar.
  - **Pausa no es reinicio.** La caducidad sustantiva no se interrumpe, pero se
    suspende en supuestos tasados: la papeleta de conciliación para el plazo del
    despido, que se reanuda al día siguiente del acto o a los quince días hábiles si no
    se celebra (art. 65.1 LRJS). Otros plazos se **reinician** enteros: pedir
    aclaración de una sentencia reinicia el de recurrirla (art. 267.9 LOPJ). En los dos
    casos **la fecha se recalcula**, y cada pausa o reinicio queda con su fecha y su
    origen. En el ecosistema antiguo «suspender» solo ponía una marca y el vencimiento
    no se movía.
  - **Ante la duda, el plazo más corto.** Varios actos candidatos: calcula todos y se
    queda con el más corto. Varias fechas de notificación: la más temprana. La ley y la
    resolución no coinciden: el más corto, y lo señala. En los tres casos el resultado
    es `provisional` y se recalcula al llegar el dato aclarado. Reconocer el acto es el
    paso más peligroso: el ecosistema antiguo se quedaba con la primera palabra que
    coincidía, y a una «sentencia de despido» le daba los 20 días de la demanda en vez
    de los 5 para anunciar suplicación.
  - **La vida de un plazo:** `abierto` al detectarlo (se anota en `sec.agenda` y
    arrancan los avisos); `en_pausa` por un hecho registrado, y al reanudarse la fecha
    se recalcula; `cumplido` por `pro.acuse` si se presentó desde MISYKS, o por el
    **«Hecho» del abogado** si presentó por su cuenta; `vencido` por el paso del tiempo,
    siempre con aviso; `cancelado` por un motivo registrado, como un desistimiento, y
    nunca se borra.
  - **Vencido detiene el trabajo, pero nunca en silencio.** Bloquea la ruta —no se
    prepara un escrito caducado— y avisa al abogado explicando qué plazo era, desde
    cuándo contaba y qué pausas se tuvieron en cuenta: dar un asunto por perdido es
    demasiado grave para que falte un dato, como una conciliación que nadie registró.
    Con datos dudosos no hay `vencido`, hay `provisional`. Si aún cabe el último
    momento legal, lo dice. En el ecosistema antiguo un plazo pasaba a vencido al
    listarlo, sin avisar a nadie.
  - **Todo se puede explicar.** Cada plazo guarda su fila de la tabla, el artículo, las
    pausas aplicadas y la explicación de `pro.calendario`.
- **Validación antes de usarlo con clientes**, como `pro.calendario`: sentencias del
  CENDOJ, ejemplos sacados de la ley para cada fila de la tabla y pruebas de sentido
  común repetidas con datos aleatorios (una pausa nunca adelanta un plazo; la fecha
  recomendada nunca es posterior al último día). Con **casos obligatorios** tomados de
  los errores del ecosistema antiguo: la sentencia de despido (5 días, no 20); 31 de
  enero más un mes (no 3 de marzo); un recurso de alzada que cruza agosto (en lo
  administrativo agosto cuenta); y «un mes», que no puede acabar en 30 días hábiles.
- **Falla si:** devuelve sí/no en vez de franja; aplica el plazo de otro acto sin
  avisar o, entre dos candidatos, el más largo; cuenta desde «hoy», o desde la
  notificación en lugar del día siguiente; inventa un plazo que no está en la tabla;
  convierte meses en días o cuenta en hábiles un plazo de días naturales; pausa sin
  mover la fecha o confunde pausa y reinicio; planifica con el último momento legal;
  da un plazo por vencido sin avisar; usa una fila sin artículo o sin vigencia.
- **Necesita:** `pro.calendario`; la **tabla de plazos** (nota siguiente); los datos
  extraídos del documento, con varias opciones cuando haya duda; las pausas y
  reinicios, de `pro.procedibilidad` y `pro.acuse`; `municipio_organo`, de
  `pro.destino`; y el tiempo de preparación, si el abogado lo ha ajustado.

*La tabla de plazos.* Una fila por tipo de plazo, con: acto y orden jurisdiccional;
duración y **cómo se cuenta** (días hábiles procesales, días naturales civiles o meses
de fecha a fecha); desde cuándo corre; si es **urgente** —entonces agosto y Navidad
cuentan, y `pro.calendario` necesita saberlo—; qué lo pausa o lo reinicia; si admite el
último momento legal; qué se pierde si vence; el **margen** de la fecha recomendada;
el **tiempo de preparación** propuesto; y el artículo, con su identificador BOE, su
**cita literal** y su vigencia. La mantiene el equipo, no el abogado, con la misma
exigencia que los festivos: sin cita literal, la fila no entra. Primera versión: los 12
tipos revisados con detalle y los 6 de mayor volumen (`ARQUITECTURA.md` §9 y §8.2).

**`pro.prescripcion`** — plazos sustantivos · módulo, en local · **diseñado, sin código**
Se comporta al revés que la caducidad, y por eso es un módulo aparte y no una opción de
`pro.caducidad`. Responde a otra pregunta: **¿qué de lo que se reclama está todavía
vivo?** No mira el caso, mira los conceptos.

**Nunca bloquea, ni en penal.** Es la diferencia de fondo con `pro.caducidad`, que sí
puede cerrar una ruta: aquí **no hay campo `bloqueo`** en la salida, y quien lea los dos
contratos seguidos no debe esperar simetría. El motivo es jurídico, no de diseño: la
prescripción civil solo existe si el demandado la alega, así que reclamar una partida
prescrita es una jugada legítima del abogado y no un error del sistema. Como el módulo no
puede parar nada, todo su valor está en que el aviso llegue y se pueda discutir: de ahí
que cada partida salga con su explicación y que el resultado quede registrado en
`sec.notificador`. Lo que protege al despacho no es el bloqueo, es la constancia de que
se avisó.

**Dos clases de hecho, y no se comportan igual.** Interrumpir devuelve el plazo a cero y
lo hace empezar completo (art. 1973 CC: reclamación judicial, reclamación extrajudicial,
reconocimiento del deudor). Suspender para el reloj y lo reanuda donde estaba, sin perder
lo corrido. Confundirlas regala o quita un plazo entero. Y hay actos que hacen las dos
cosas a la vez sobre plazos distintos —la solicitud de conciliación suspende la caducidad
e interrumpe la prescripción—, así que el mismo documento alimenta a los dos módulos con
efectos opuestos. El ecosistema antiguo no distinguía ninguna de las dos: marcaba el
plazo como suspendido sin mover la fecha de vencimiento.

- **Contrato:** `{accion, partidas[], hechos[], ahora}` → `{partidas[], avisos[], version_tabla}`
  - `hechos[]`: cada uno con `clase` (`interrumpe · suspende`), fecha, fecha de fin si
    suspende, el acto del que sale y **quién lo sostiene**: `acuse` si consta con
    justificante, `abogado` si lo dice quien lo hizo por su cuenta. Es el mismo eje que
    `expedientes` guarda en sus hitos, y aquí pesa más: de un hecho declarado depende un
    año entero de cómputo.
  - Cada partida de salida: `{concepto, fecha_nacimiento, plazo_aplicado, fila_tabla, fecha_prescripcion, estado, firmeza, franja, hechos_aplicados[], explicacion}`
  - `estado`: `viva · prescrita`. `firmeza`: `firme · provisional`. **Son dos ejes, no
    uno**: una partida puede estar viva y ser provisional a la vez.
  - **`prescrita` se deriva al leer, nunca se guarda**, por la misma razón por la que
    `expedientes` no guarda `vencido`: escribirlo sería el módulo decidiendo que un
    derecho ha muerto, y este módulo no decide, informa. Y **solo prescribe lo firme**:
    con una suspensión abierta o una acción sin decidir no hay prescrita, hay
    provisional.
  - `franja`: `holgado · ajustado · crítico · vencido`, **la misma escala que
    `pro.caducidad`**, para que `sec.notificador` no tenga que aprender dos.
  - `ahora` es obligatorio y la salida lleva la versión de la tabla usada: sin las dos
    cosas, un resultado de hace tres meses no se puede volver a explicar.
- **Reglas:**
  - **Los hechos se aplican en orden cronológico.** Una interrupción posterior a una
    suspensión borra lo acumulado; aplicarlos en el orden en que llegan, y no en el que
    ocurrieron, da otra fecha.
  - **Una suspensión sin fecha de fin deja la partida provisional.** Mientras el reloj
    está parado no hay fecha de prescripción que dar, y darla firme es inventarla.
  - **Corre por partida**, y qué es una partida lo fija el tipo: una mensualidad de
    nómina, una factura, un concepto reclamado. En varios tipos son decenas.
  - **No filtra el caso, filtra conceptos**: la salida es la lista entera, cada partida
    con su estado, nunca un sí/no sobre el asunto.
  - **Años y meses van de fecha a fecha** (art. 5.1 CC), nunca convertidos a días. Cinco
    años no son 1825 días: el ecosistema antiguo lo hacía así y se quedaba un día corto,
    dos en los plazos de diez años, porque ignoraba los bisiestos. Corto significa
    declarar muerto lo que todavía vive.
  - **Cada regla lleva su vigencia.** El plazo general de las acciones personales pasó de
    quince años a cinco en 2015 y tiene régimen transitorio: un hecho anterior no se
    computa con la regla de hoy, por lo mismo que un plazo de 2021 no conoce la
    inhabilidad de Navidad.
  - **Lo que no está en la tabla no se inventa**: aviso de **acción no reconocida**, y la
    fila que falta se añade a la tabla.
  - **El plazo depende de la acción ejercitada**, que en la puerta puede no estar
    decidida —en penal sale de la pena en abstracto, que exige una calificación que aún
    no se ha hecho—. Entonces el resultado es `provisional` y exige reevaluación.
  - **Toda partida prescrita lleva su explicación**: qué fila, qué artículo y qué hechos
    se aplicaron, en qué orden. Es lo único con lo que el abogado puede contradecir al
    módulo, y como este no bloquea, contradecirlo es todo lo que hay.
  - **No llama a ningún modelo.**
- **No confundir con prórroga ni con recálculo.** `expedientes` ya distingue las dos:
  la prórroga es el órgano ampliando un plazo que estaba bien, y su fecha viene en una
  resolución; el recálculo corrige una fecha que estaba mal. La interrupción y la
  suspensión no son ninguna de las dos: la fecha cambia porque **el derecho se ha
  movido**, no porque nadie la conceda ni porque estuviera equivocada.
- **Falla si:** devuelve un booleano, o bloquea; olvida un hecho y descarta conceptos
  vivos; convierte años o meses en días; trata una suspensión como interrupción, o al
  revés; aplica los hechos fuera de orden; da fecha firme con una suspensión abierta;
  computa con la regla vigente hoy un hecho anterior a la reforma; o devuelve una partida
  prescrita sin explicación con la que discutirla.
- **Necesita:** la **tabla de plazos sustantivos** y el **catálogo de hechos** (nota
  siguiente); el historial de requerimientos con su acuse y su certificación de
  contenido, que produce `pro.burofax` —mientras no exista, los hechos se anotan a mano,
  como hoy se anotan los plazos en `sec.agenda`—; y `pro.calendario` **solo** para los
  plazos cortos en días: los de años y meses son naturales de fecha a fecha y no
  consultan festivos, así que este módulo no espera al motor de días para existir.

*La tabla de plazos sustantivos y el catálogo de hechos.* Dos datos revisables, no
código, con la misma exigencia que los festivos: sin cita literal, la fila no entra. La
tabla, una fila por acción: plazo, unidad, desde cuándo corre, si se aprecia de oficio,
el artículo con su identificador BOE, su cita literal, su vigencia y el régimen
transitorio si lo tiene. El catálogo, una fila por acto: si interrumpe o suspende, su
artículo y qué prueba exige. Primera versión: **laboral y civil** —el año de las acciones
derivadas del contrato de trabajo, donde la partida se ve con más claridad, y el plazo
general de las acciones personales con su transitorio—. **Penal queda fuera de la primera
versión**, porque su plazo depende de la pena en abstracto y eso exige una calificación
que en la puerta no existe. Las citas de esta ficha **están sin comprobar contra el
BOE**: son la pista por donde empezar, no la fuente.

*Dónde vive la fecha, y qué ve el abogado.* No se publica nada en la agenda: desde que el
plazo es un **hito del expediente** y `sec.agenda` lo proyecta, publicar sería volver a
tener el mismo dato en dos sitios. La fecha vive en el expediente y la agenda la enseña
sola. De las partidas se lleva **una sola, la primera en prescribir**: un expediente de
reclamación de cantidad con dieciocho mensualidades llenaría la barra de dieciocho nodos
del mismo asunto, y las demás se consultan en el módulo. **Queda por decidir si ese nodo
entra en la barra de hitos**, porque la barra está definida como el recorrido procesal
—lo que pasa en el juzgado— y una fecha de prescripción no es un paso del procedimiento
sino un límite que corre por fuera.

**`pro.procedibilidad`** — requisitos previos
El único módulo que puede **desviar el pipeline a otro tipo documental**.

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

**`pro.destino`** — a dónde va · módulo, en local · **diseñado, sin código**
Responde a tres preguntas: **por qué canal sale esto, a quién, y en qué municipio está
la sede del órgano.** La tercera es la que lo mete en la puerta: `pro.calendario` no
puede aplicar festivos locales sin ella, y quien conoce el órgano es este módulo. Es
además el punto de traspaso limpio entre los dos grupos: **procesal decide dónde,
secretario entrega**.

**Se le llama en dos momentos y es la misma llamada.** En la puerta, antes de calcular
el plazo, donde solo se consume `municipio_sede`; y en la salida, antes de entregar,
donde se consumen el canal y el destinatario. Que sea una sola resolución es
deliberado: dos resoluciones del mismo órgano en momentos distintos pueden divergir, y
entonces el plazo se calculó con un municipio y el escrito sale hacia otro.

- **Contrato:** `{tipo_documento, organo?, expediente, momento}` → `{canal_preferente, canales_candidatos[], destinatario, municipio_sede, firmeza, avisos[]}`
  - `organo` entra como **identificador** si se conoce, o como el texto tal cual consta
    para que el módulo intente resolverlo.
  - `municipio_sede`: código INE de cinco dígitos como texto, o vacío. Vale igual para
    un juzgado y para una Administración, porque el cómputo administrativo también
    necesita la sede de su destinatario.
  - `firmeza`: `firme · provisional`, el mismo vocabulario que `pro.calendario`,
    `pro.caducidad` y `pro.prescripcion`. Provisional cuando el órgano no se ha
    resuelto o cuando el canal depende de una decisión no tomada.
- **Reglas:**
  - **El órgano se resuelve por identificador, nunca por el nombre.** El nombre solo
    sirve para encontrar la fila, y las formas en que ese órgano aparece de verdad en
    una notificación se guardan como **alias**, que son dato con su fuente, no
    heurística. Normalizar —mayúsculas, tildes, abreviaturas— sirve para buscar el
    alias, no para inventarlo. Es el criterio de `inv.normativa`, que rechaza «CC» y
    exige `BOE-A-1889-4763`.
  - **Nunca resuelve por parecido.** «Juzgado de Primera Instancia nº 4 de San
    Sebastián de los Reyes» y «…de Donostia-San Sebastián» se parecen mucho y están en
    provincias, comunidades y calendarios distintos. Un acierto por similitud no da un
    error visible: da una fecha límite calculada con el calendario de otra comunidad.
    Sin alias, la respuesta es `organo_no_reconocido`.
  - **La clave para el calendario es el municipio, no el partido judicial.** Las
    fiestas locales son municipales y un partido judicial agrupa municipios con fiestas
    distintas, así que usarlo como clave —como hacía el ecosistema antiguo, y además
    como texto libre— mete los festivos de la cabecera en todos los demás.
  - **Cada órgano lleva vigencia.** Se reorganizan: la reforma que convierte los
    juzgados en Tribunales de Instancia cambia los nombres y no las sedes. Con
    vigencia, una resolución de 2024 sigue resolviendo; sin ella deja de resolver el
    día que se actualiza la tabla. Mismo criterio que las reglas de `pro.calendario`.
  - **Distingue dos fallos que no se arreglan igual.** `organo_no_reconocido` —no
    sabemos qué juzgado es, así que no hay municipio— se arregla añadiendo el órgano o
    el alias a la tabla; `municipio_sin_cobertura` —sabemos que es Getafe, pero el
    calendario no tiene sus fiestas locales— se arregla añadiendo el municipio al árbol
    de ámbitos y recolectando sus festivos. Confundirlos deja a quien lo lee sin saber
    qué hay que hacer.
  - **Cuando no resuelve: fecha prudente y `provisional`**, con el aviso en texto para
    el abogado. **Nunca el municipio del despacho ni solo los festivos nacionales**, que
    es lo que hacía el ecosistema antiguo: el número salía, parecía firme y nadie se
    enteraba nunca de que se había calculado con el calendario de otra ciudad.
  - **Los dos avisos son enumerables**, como la cobertura `pendiente` del calendario:
    una lista de órganos por resolver y otra de municipios sin cobertura. Es el
    mecanismo por el que los diez municipios de prueba crecen hacia los que el despacho
    usa de verdad, empujados por casos reales, en vez de cargar por delante 8.131
    municipios y todos los juzgados de España.
  - **El canal se devuelve con candidatos y un preferente, y nunca se asume por
    descarte.** El `destino` del catálogo es el preferente, no el único: la
    `denuncia_penal` puede presentarse en comisaría (`presencial`) o en el juzgado de
    guardia, donde el abogado sí podría presentarla por vía electrónica (`lexnet`). No
    son dos tipos documentales, es un tipo con dos salidas, y cuál se usa lo decide
    quien lleva el caso; la elección se registra. **30 de los 89 tipos no salen por
    LexNET**: tratarlo como destino único deja un tercio del catálogo saliendo por el
    canal equivocado.
  - **Un justificante presencial es declarado, no acreditado**, y eso viaja a
    `pro.acuse` para que la auditoría distinga lo que consta de lo que se ha dicho.
  - **No llama a ningún modelo.**
- **Falla si:** resuelve un municipio por parecido de nombre; cae al municipio del
  despacho o a los festivos nacionales cuando no resuelve; confunde órgano no
  reconocido con municipio sin cobertura, y entonces nadie sabe qué hay que arreglar;
  devuelve `firme` con el órgano sin resolver; cierra el canal a un único valor en un
  tipo que admite dos; deja pasar un justificante presencial como acreditado; o asume
  LexNET por descarte.
- **Necesita:** la **tabla de órganos y sedes** (nota siguiente), que es dato nuevo; el
  catálogo de los 89 tipos, que ya existe, para el canal preferente; el árbol de
  ámbitos de `pro.calendario`, para comprobar que el municipio existe antes de
  devolverlo; y del expediente, el órgano tal como consta y los datos del destinatario.

*La tabla de órganos y sedes.* Dato revisable, no código, con una fila por órgano:
identificador, nombre oficial, **alias[]**, tipo y número, orden jurisdiccional,
**municipio de la sede** en código INE, partido judicial y vigencia desde/hasta. La
mantiene el equipo. Primera versión: los órganos de los **diez municipios ya sembrados**
en `pro.calendario`, más los que vayan apareciendo en expedientes reales. Queda por
comprobar si el identificador puede ser el **código de órgano que ya viaja en las
notificaciones** —el de LexNET y el NIG—: si consta siempre y es estable, es mejor que
inventar uno, por lo mismo que `inv.normativa` usa el del BOE.

*Los siete canales, y quién sirve cada uno.* El vocabulario es el del catálogo, que ya
es dato en uso, no uno propio de esta ficha.

| canal | tipos | lo sirve | qué vuelve |
|---|---|---|---|
| `lexnet` | 59 | `pro.lexnet` | justificante con hora oficial |
| `admin` | 12 | `pro.registro` | nº de registro y **dos fechas** |
| `cliente` | 8 | `sec.entrega` | nada que registrar |
| `notarial` | 6 | `pro.notaria` | cita y copia autorizada |
| `burofax` | 2 | `pro.burofax` | acuse **con certificación de contenido** |
| `smac` | 1 | `pro.registro` | papeleta sellada; además **suspende** el plazo de la demanda |
| `presencial` | 1 | **nadie** | copia sellada, **sin nº de registro** |

**`presencial` no tiene módulo, y eso es la respuesta, no un hueco.** Un módulo de canal
se define por tener credenciales y transmitir, y aquí el sistema no transmite nada: la
cadena termina en `pro.forma`, el documento se le entrega al abogado y `pro.acuse` lo
cierra como cumplido **declarado**. El canal sigue haciendo falta para lo único
importante, que es impedir que ese tipo salga por LexNET por descarte. Se llama
`presencial` y no `policial` porque nombra la propiedad —no hay registro que devuelva
identificador y fecha oficial— en vez de la institución, y así cubre los tres sitios
donde la misma denuncia puede acabar: comisaría, juzgado de guardia y Fiscalía. Con el
nombre viejo, además, el único tipo `policial` del catálogo incumplía una regla de
`pro.registro`, que falla si acepta un justificante sin número de registro.

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

**`pro.registro`** — registro administrativo · 13 tipos: los 12 de canal `admin` y la
papeleta del SMAC, que se registra igual aunque su efecto sea suspender un plazo
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
    `recurso_contencioso`. Es el único módulo de salida cuya entrega **produce una
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
  - **Cumplido acreditado no es cumplido declarado.** Si el abogado presentó por su
    cuenta, fuera de MISYKS, el plazo se cierra con su «Hecho» (`sec.agenda`) y no hay
    justificante: queda como cumplido **por declaración del abogado**, no por acuse,
    para que la auditoría distinga lo que consta de lo que se ha dicho.
  - Sin él el sistema no sabe que se presentó: los avisos de `sec.notificador` siguen
    vivos y `pro.procedibilidad` bloquearía la siguiente ruta del mismo expediente.
  - Único punto donde presentación y plazo se reconcilian. **Idempotente**: reintentar
    no puede duplicar entradas de auditoría.
- **Falla si:** no se ejecuta — y el fallo es invisible hasta que alguien pregunta si
  se presentó.

### Notas de diseño del grupo

- **Ninguno usa LLM: son módulos, no agentes.** Es el bloque auditable del sistema;
  si deja de serlo, se pierde la única parte verificable a mano.
- **Las tablas de plazos son el activo crítico, y son dos.** La procesal, de
  `pro.caducidad`, y la sustantiva de `pro.prescripcion` con su catálogo de hechos. No
  se mezclan, porque no responden a lo mismo: una dice hasta cuándo se puede actuar
  dentro de un procedimiento, la otra hasta cuándo sigue vivo un derecho. Cada módulo
  vale exactamente lo que valga su tabla. Las dos deben versionarse, tener autoría y
  fecha de revisión, y ser un dato, no código. **Las mantiene el equipo, no el abogado, y
  se vigilan:** cada cierto tiempo se consulta en el BOE el texto vigente de cada
  artículo citado y se compara con la cita guardada; si ha cambiado, se avisa al equipo
  para revisar la fila. Es una consulta y una comparación de textos, sin modelo, y no
  forma parte de ninguno de los dos módulos. Sin esa vigilancia la tabla envejece en
  silencio: la del ecosistema antiguo seguía ofreciendo la «preparación» del recurso de
  apelación, un trámite suprimido en 2011, y computaba cinco años de prescripción como
  1825 días naturales.
- **Procesal decide, secretario ejecuta.** Separar criterio de canal es lo que permite
  que el que tiene credenciales no tome decisiones y el que decide no pueda enviar.

## INVESTIGADOR · derecho — 5

Toda cita que produce debe ser **comprobable**.

| agente IA | uso |
|---|---|
| `inv.normativa` | BOE: artículo exacto y vigencia a la fecha del hecho |
| `inv.jurisprudencia` | CENDOJ, filtrado por órgano e instancia |
| `inv.convenio` | convenio colectivo por sector y provincia |
| `inv.doctrina` | criterio administrativo y doctrinal |
| `inv.citas` | ¿existe la referencia y dice lo que se le atribuye? |

**`inv.normativa`** — artículo y vigencia · agente IA, en `maat` · **diseñado, sin código**

Único agente IA diseñado con **bucle de herramienta** en vez de una sola llamada:
localizar un artículo exige a veces reintentar con otro identificador, y eso es
iterativo por naturaleza. Los demás agentes IA siguen siendo de una llamada; ver
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
    que `COMPONENTES.md` exige a todo el grupo. No se corrige con el prompt: un 7B que
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
    abogado pincha y ve el original.

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
  artículo puede exigir reintentar; los otros cuatro agentes IA del grupo son de una
  llamada y no deben ganar herramientas «por coherencia». Un bucle añade modos de
  fallo, y solo se paga donde la tarea es genuinamente iterativa.
- **La superficie de herramientas es cerrada y de lectura.** Al modelo se le ofrece
  exactamente una función, definida por nosotros, contra una fuente pública. No tiene
  disco, ni shell, ni forma de pedir nada que no esté en ese array. Es lo que hace
  admisible un bucle dentro de un sistema que debe poder auditarse.

## PROBATORIO · prueba — 5

Único grupo que **interrumpe al humano por iniciativa propia**.

| agente IA | uso |
|---|---|
| `pru.inventario` | qué material hay y en qué soporte |
| `pru.admisibilidad` | licitud y forma de obtención |
| `pru.autenticidad` | acta notarial, cadena de custodia, metadatos |
| `pru.suficiencia` | ¿sostiene la pretensión o se queda corta? |
| `pru.carencias` | qué falta y cómo obtenerlo a tiempo |

## CALCULADORA · números — 6

Determinista: **seis módulos, ningún agente IA**. Toda cifra que se defiende ante un
juez sale de una función auditable:
**el redactor escribe alrededor del número, nunca lo produce**.

| módulo | uso |
|---|---|
| `cal.antiguedad` | cómputo de la relación, con interrupciones |
| `cal.indemnizacion` | por tipo de extinción, con tramos y topes |
| `cal.cantidades` | nóminas, horas extra, finiquito, rentas |
| `cal.intereses` | legal, de mora, procesal |
| `cal.costas` | según cuantía y cauce |
| `cal.cuantia` | determina el cauce procesal y la postulación |

## ESTRATEGA · adversario y decisión — 5

El análisis del adversario es el medio; **la recomendación es el fin**.

| agente IA | uso |
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

| agente IA | uso |
|---|---|
| `red.estructura` | esqueleto según tipo documental |
| `red.hechos` | relato numerado (PRIMERO.-, SEGUNDO.-) |
| `red.fundamentos` | con las citas que entrega el investigador |
| `red.petitorio` | SUPLICO según tipo |
| `red.contractual` | clausulado: documentos que no van a juzgado |
| `red.tramite` | escritos cortos de plantilla |

## CRITICO · control — 6

Devuelve `veto` o `visto_bueno`, con los defectos encontrados.

| agente IA | uso |
|---|---|
| `cri.formal` | requisitos tasados por tipo, como lista cerrada |
| `cri.citas` | ¿las citas del propio escrito existen? |
| `cri.coherencia` | hechos vs fundamentos vs suplico |
| `cri.cruzado` | coherencia **entre** documentos de un mismo expediente |
| `cri.abusividad` | cláusulas: no «¿convence?» sino «¿es válido?» |
| `cri.riesgo` | exposición del cliente y del abogado |
