# Arquitectura de componentes y tipos documentales

> Modelo de organización del enrutado de MISYKS.
> Última actualización: 2026-09-17

**Naturaleza del documento.** Diseño completo del sistema de componentes —agentes
IA y módulos—. No se
distingue entre lo implementado y lo pendiente salvo en §8.3, que recoge el estado
real del código.

**Normas de trabajo.**

- **Nada de branches.** Se trabaja siempre directo sobre `main`. Sin ramas de
  feature, sin PRs pendientes de fusionar: cada commit que llega a `main` ya
  se considera el estado real del proyecto.
- **Este documento se actualiza en el mismo cambio que lo motiva, no después.**
  Cualquier commit que altere una decisión de arquitectura, el estado de un
  componente (§8.3) o el contrato de un grupo debe traer también el ajuste
  correspondiente aquí. Un `ARQUITECTURA.md` desactualizado es peor que no
  tenerlo: alguien lo lee y confía en algo que ya no es cierto.
- **Detalle, no titulares.** Cuando algo cambie, se explica el porqué y las
  consecuencias (qué se rompía antes, qué falla si se deshace), no solo el
  qué. Un `Cambió X` sin contexto no ayuda a quien lo lea dentro de tres
  meses.
- **El ecosistema antiguo (`misyks-repo`, `~/maat/` en el servidor, y cualquier
  cosa del "MAAT" que este proyecto viene a reemplazar) es referencia, no
  autoridad.** Sirve para ver cómo se resolvió algo antes (un patrón, un
  script, una decisión), pero nunca se copia ni se aplica a MISYKS-Beta sin
  consultarlo antes con el equipo. Que algo ya exista ahí no lo convierte en
  el diseño correcto para este proyecto.

**Modelo.** Nueve grupos, no nueve agentes generalistas. Cada grupo es una familia de
piezas muy acotadas, cada una con una sola tarea y un contrato estrecho. El grupo define el
papel; los componentes hacen el trabajo. Son 56 componentes:

```
procesal 12 · redactor 6 · critico 6 · calculadora 6 · secretario 6
archivador 5 · investigador 5 · probatorio 5 · estratega 5
```

**Vocabulario.** Dos clases de componente, y la distinción manda en el diseño:

| término | qué es |
|---|---|
| **agente IA**, o **agente** a secas | invoca un modelo de lenguaje; su salida se acota y se comprueba porque puede inventar |
| **módulo** | código determinista, sin LLM; misma entrada, misma salida, y se audita leyéndolo |
| **componente** | cualquiera de los dos, cuando da igual cuál |

«Agente» sin más **siempre** significa agente IA. Cuando haga falta hablar del
módulo de Python, este documento dirá *paquete*.

**Stack.** Backend Python, frontend Rust con `iced` (arquitectura Elm). Cada
componente es un paquete bajo `Backend/<grupo>/<nombre>/`, con la misma anatomía:
`agent.py` expone la interfaz al resto del sistema —el nombre del fichero es
histórico y sirve igual para un módulo—, y detrás quedan el cliente del canal, el
parser, la base y la configuración.

**Convención de nombres.** `<grupo>.<nombre>` en el diseño, `Backend/sec/mail/` en
disco. El componente de correo es **`sec.mail`**, y es un módulo.

---

## 1 · Los nueve grupos

Qué grupos hay, qué decide cada uno y cómo se componen. Los componentes de cada
grupo —56 en total, con sus reglas y contratos— están en **`COMPONENTES.md`**.

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

### Dónde corre cada componente

Eje de diseño distinto del anterior, y el que decide la infraestructura: **no todo
componente es un agente IA**.

| tipo | qué es | dónde corre | por qué |
|---|---|---|---|
| **Módulo** | código determinista, sin LLM | donde están sus datos y sus credenciales | `sec.mail` tiene los tokens de acceso al buzón y lee contenido sin anonimizar: corre en el PC del abogado y eso no sale de ahí |
| **Agente IA** | invoca un modelo de lenguaje | **siempre en el servidor (`maat`)** | ahí está el modelo. Ollama con `qwen2.5:7b`, 12 núcleos y 62 GB de RAM; el portátil del abogado no sostiene eso, y replicarlo en cada equipo no tiene sentido |

Los nueve grupos de arriba describen **qué decide** cada componente, no dónde se
ejecuta. Son módulos los doce de `procesal`, los seis de `calculadora` y los que
tocan un canal con credenciales (`sec.mail`, y más adelante `sec.entrega`), que
corren en local; el resto son agentes IA y viven en `maat`.

Que un módulo dependa de un paso de IA no lo convierte en agente: `sec.mail`
descarga y almacena en local sin tocar el modelo, y el **resumen** que consume
`sec.clasificador` lo produce una llamada aparte, en `maat` (§8.4). La frontera no es
la pieza, es quién hace la llamada: lo que decide un modelo se comprueba, lo que
decide el código se lee.

### SECRETARIO · despacho
El canal con **el mundo del despacho**: correo, agenda y avisos. No conoce los
canales procesales —LexNET, registro, notaría— que pertenecen a `procesal`. Su
competencia es lo que entra y sale por el correo del abogado, y lo que hay que
recordar.

**Contrato entrada:** `{cuenta}` → `{documento, resumen, clase, etiquetas[]}`
**Contrato salida:** `{documento, destinatario, motivo}` → `{enviado, retorno_esperado?}`

### ARCHIVADOR · estructura
Convierte un documento en una posición dentro del despacho.

**Contrato:** documento → `{expediente_id, metadatos, ruta, requiere_revision, candidatos[]}`

### PROCESAL · tiempo y forma
**Valida al entrar, verifica antes de salir y posee los canales procesales.** Decide si hay tiempo, si faltan requisitos y a qué destino corresponde;
el envío lo ejecuta el secretario. Determinista de punta a punta.

**Contrato puerta:** `{actos_candidatos[], notificacion, organo, expediente}` → `{plazos[], requisitos_pendientes[], bloqueo}`, y cada plazo `{fecha_recomendada, ultimo_dia, franja, estado}`

La puerta no lee documentos: recibe los datos ya extraídos por `secretario` y
`archivador`, con varias opciones cuando hay duda, y ante la duda se queda con el plazo
más corto y marca el resultado `provisional`. Devuelve una **lista** porque una misma
notificación abre a menudo varios plazos (una sentencia, el de aclaración y el de
recurso). Si alguno ha vencido, bloquea la ruta y avisa al abogado con la explicación,
nunca en silencio. Detalle en `COMPONENTES.md`, `pro.caducidad`.
**Contrato verificación:** `{documento, expediente}` → `{en_plazo, defectos_formales[], destino}`

### INVESTIGADOR · derecho

**Contrato:** `{consulta, tipo_documento}` → `{artículos[], resoluciones[]}` con cita comprobable

### PROBATORIO · prueba

**Contrato:** `{material, tipo_proceso}` → `{estrategia, señalar_al_abogado}`

Único grupo que **interrumpe al humano por iniciativa propia**.

### CALCULADORA · números
Determinista. Toda cifra que se defiende ante un juez sale de una función auditable;
el redactor escribe alrededor del número, nunca lo produce.

**Contrato:** `{campos, fechas}` → `{importe, desglose}`

### ESTRATEGA · adversario y decisión
Absorbe el análisis del escrito contrario y toda la capa de predicción. El análisis
del adversario es el medio; la recomendación es el fin.

**Contrato:** `{escrito_ajeno?, expediente}` → `{argumentos[], debilidades[], recomendación}`

El objeto de `est.contrario` cambia según la ruta —una demanda, una sentencia, un
acto administrativo— y eso son tres prompts distintos, no uno parametrizado.

### REDACTOR · producción

**Contrato:** `{contexto, tipo_documento, datos}` → documento

Regla dura: **nunca deja un placeholder vacío**. Si falta un dato, se pide.

### CRITICO · control

**Contrato:** `{contenido, tipo_documento}` → `{veto|visto_bueno, defectos[]}`

---

### Middleware transversal — `anonimizar`, diseñado, sin implementar

`anonimizar` no es un grupo: es un filtro transversal que seudonimiza antes de
cualquier llamada a un modelo y reinserta los datos reales en local al redactar.
**No está implementado.** Donde las rutas de §6 escriben `[anonimizar]`, hay un
hueco, no un paso que ocurra. Lo que sigue es el diseño acordado; hasta que exista
código, cualquier ruta que lo invoque está incompleta y no debe darse por segura.

#### Dos capas, y la primera no lleva modelo

El error de partida sería tratar la anonimización como un problema de NER. En un
documento de despacho, lo que de verdad identifica a una persona suele tener forma
fija, y eso se resuelve con expresiones regulares y validación de dígito de control:
recall del 100 %, auditable, sin modelo y sin GPU.

```
capa 1 · determinista        identificadores y referencias de forma fija
capa 2 · NER                 lo que no tiene forma fija
```

**Capa 1 — determinista.** Cubre DNI, NIE, CIF, NUSS, IBAN, tarjetas, matrículas,
número de procedimiento y NIG, teléfonos, correos, direcciones postales y fechas de
nacimiento. Todos esos formatos admiten validación —letra del DNI, IBAN mod 97, NIG
por composición— así que un acierto es comprobable y un fallo es un `False` explícito,
no una probabilidad baja que nadie mira.

**Capa 2 — NER.** Nombres de persona, organizaciones y topónimos, que no tienen
forma reconocible. Aquí sí hace falta un modelo de clasificación de tokens, y aquí
es donde el sistema puede fallar en silencio.

El orden importa: la capa 1 va primero y su resultado no lo revisa el modelo. Si la
capa 2 se equivoca, la 1 ya ha retirado los identificadores fuertes; si se invirtiera
el orden, un fallo del modelo podría arrastrar un DNI entero al exterior.

La consecuencia práctica es que **la capa 1 es entregable por sí sola** y ya reduce
la mayor parte del riesgo real. La capa 2 es el proyecto de verdad.

#### El modelo de la capa 2

**Decisión: se usa un modelo que ya viene con cabeza de NER entrenada.** Hoy,
`PlanTL-GOB-ES/roberta-base-bne-capitel-ner` (BSC/SEDIA, Apache 2.0): clasificación
de tokens lista para usar, en español, corriendo en local como exige §8.4. Está
entrenado sobre español general y no jurídico, así que se espera que falle más en
denominaciones societarias, órganos judiciales y topónimos poco frecuentes. Se acepta
ese coste a cambio de tener la capa 2 funcionando sin una fase previa de
entrenamiento.

**Opción futura: RoBERTalex fine-tuneado por nosotros.** `PlanTL-GOB-ES/RoBERTalex`
(mismo origen y licencia) es RoBERTa-base entrenado sobre 8,9 GB de corpus jurídico
español — el dominio exacto del despacho. No se puede usar tal cual: es un modelo
base de *masked language modeling*, da representaciones y no etiquetas, y su propia
ficha dice que está listo solo para eso. Convertirlo en un anonimizador exige
fine-tunearlo sobre un corpus de NER jurídico anotado que hay que conseguir o
construir; de dónde sale ese corpus sigue abierto (más abajo).

Cuando exista, se sustituye **midiendo contra el modelo en uso**, no por ser del
dominio: si el fine-tuneado no mejora el recall medido, no entra.

#### El mapa de seudónimos

La estructura de datos es trivial —un diccionario `real ↔ seudónimo`— y da igual que
haya tres personas o cuarenta. La dificultad no está en guardar las sustituciones,
está en decidir **cuáles son las claves** y en que el texto vuelva del modelo en
condiciones de deshacerlas.

**Qué cuenta como la misma persona.** En un mismo expediente, Juan Pérez García
aparece como «Juan Pérez García», «Juan Pérez», «el Sr. Pérez», «D. Juan» y
«J. Pérez». Si cada forma es una entrada distinta, el modelo lee cinco personas donde
hay una y todo su razonamiento sobre el caso queda mal; si son una sola entrada,
alguien tiene que decidir que lo son, y eso es resolución de entidades, no un
diccionario. Peor cuando hay dos Pérez en el mismo procedimiento: ahí la forma corta
es genuinamente ambigua y al reinsertar no hay manera de saber a cuál volvía.

**Que el texto vuelva entero.** La sustitución de ida es controlada; la vuelta no. El
modelo redacta libremente y puede escribir `[PERSONA_4]` cuando solo se enviaron tres,
partir una marca, o referirse a alguien sin usar la marca. Un `dict` invertido
solo funciona si las marcas vuelven intactas, y eso no está garantizado: hay que
validarlo, no suponerlo.

**Concordancia gramatical.** Un seudónimo neutro obliga al modelo a adivinar el género
—«[PERSONA_1] fue detenida» o «detenido», «del [PERSONA_1]» o «de la»— y al reinsertar
el nombre real la concordancia equivocada se queda escrita. Los seudónimos deben
llevar el género de la persona real.

**Alcance — propuesta, sin decidir: por expediente y persistente.** No por documento.
El argumento a favor: si `[PERSONA_1]` no significa lo mismo en dos escritos del mismo
caso, el modelo no puede razonar sobre el expediente —no sabría que el demandado del
escrito A y el del B son la misma persona— y se pierde justo lo que justifica mandarle
contexto. El argumento en contra: un mapa que sobrevive a la sesión hay que cifrarlo
y custodiarlo, y concentra en un fichero lo que el resto del diseño se dedica a
dispersar. **El equipo no lo ha decidido**; hasta que lo haga, el alcance del mapa
queda abierto y con él la vida útil del fichero.

**Vive en local, nunca en `maat`.** Si el mapa llegara al servidor, la seudonimización
no protegería de nada: quien accediera al servidor tendría el texto y la clave para
deshacerlo.

**Reinsertar es la mitad difícil.** Un fallo ahí no se ve: produce un escrito
coherente con el nombre equivocado, que es peor que un escrito roto porque pasa la
lectura. La reinserción debe ser total o fallar: si al redactar queda un
`[PERSONA_n]` sin correspondencia en el mapa, el paso aborta y avisa al abogado. No
se entrega un documento con seudónimos dentro ni se adivina a quién se refería.

#### Verificación — propuesta de condición de uso

Un middleware de anonimización sin una medida de su recall es un sello de confianza
sin nada detrás: nadie sabe cuánto se le escapa, y la seguridad que aporta es una
suposición.

**Propuesta, pendiente de que el equipo la asuma o la rechace:** que `anonimizar` no
autorice ninguna llamada a una API externa mientras no exista un conjunto de prueba
con documentos reales anotados y una cifra de recall publicada en este documento. Si
esa cifra no se puede dar, la consecuencia sería usar solo el modelo local de `maat`
— que es donde está el proyecto hoy, así que adoptarla no cambia nada a corto plazo;
lo que hace es fijar por adelantado qué haría falta para cambiarlo.

Si se adopta, las dos capas se medirían por separado: la 1 debe dar recall 1,0 sobre
sus formatos (si no, es un bug, no una métrica), y la 2 se reporta con su número
real.

**Mientras no se decida, no hay condición escrita** — y conviene saberlo: el hueco no
es que falte la medición, es que nadie ha fijado quién autoriza la salida de datos ni
con qué criterio.

#### Qué no resuelve

- **No desbloquea un cambio de arquitectura de componentes.** Que la seudonimización
  funcione permite *llamar a un modelo externo*; no cambia que los contratos de los
  56 componentes sean de una llamada, entrada estructurada → salida estructurada.
  Adoptar un framework de agentes con bucle propio, herramientas de disco y shell
  sigue siendo un desajuste de forma, y sigue rompiendo el carácter auditable que
  `COMPONENTES.md` exige al bloque determinista.
- **No sostiene el argumento RGPD de §8.4.** `maat` está en la UE, así que enviarle
  datos no es transferencia internacional con o sin seudonimización. Anonimizar
  reduce el impacto de un acceso indebido al servidor; no cambia la base legal.
  Conviene no apoyarse en él para justificar la infraestructura.
- **No reabre por sí solo la decisión de §8.4** (resumen con Ollama en `maat` frente
  a API externa). Esa decisión se tomó comparando calidad, coste y confidencialidad;
  `anonimizar` solo retira uno de los tres obstáculos.

#### Decisiones abiertas

- **El alcance sigue sin decidir.** Se planteó como obligatorio en penal, familia y
  lo que toque salud. Eso deja fuera el correo ordinario, que es el volumen real. Si
  el criterio acaba siendo «antes de cualquier llamada al modelo», entonces es
  universal y no por materia — y son dos sistemas distintos, no el mismo con más
  casos. Mientras no se decida, las rutas de §6 marcan `[anonimizar]` solo en el
  arquetipo D.
- **De dónde sale el corpus anotado** para el fine-tuning de RoBERTalex: anotación
  interna sobre expedientes propios —que no pueden salir del despacho— frente a
  corpus público, que existe para español general y no para jurídico.
- **Si la verificación es vinculante** (arriba): sin regla escrita, la decisión de
  mandar datos fuera queda al criterio de quien lo implemente, que es peor sitio que
  este documento.
- **El alcance del mapa de seudónimos** (por expediente y persistente, o por
  documento y efímero): el primero permite razonar sobre el caso, el segundo reduce
  lo que hay que custodiar. Propuesto arriba el primero, sin acordar.
- **Qué hacer con los falsos positivos.** Seudonimizar de más degrada el texto que
  lee el modelo y puede volverlo incomprensible. Nadie ha fijado todavía el umbral
  ni si se prefiere errar por exceso.

### La capa de autoridad

Es lo que convierte nueve grupos en un sistema: no todos pesan igual, y alguno tiene
que poder parar a los demás.

| nivel | grupos | puede |
|---|---|---|
| **Bloquean** | `procesal`, `probatorio` | detener la ruta antes de gastar nada |
| **Interrumpen** | `probatorio`, `secretario` | crear tarea urgente para el abogado |
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

## 2 · Detalle de componentes

Movido a **`COMPONENTES.md`**: qué hace cada componente, su contrato, las reglas de
dominio que respeta, cómo falla y de qué depende. Aquí solo queda la arquitectura
—cómo se componen los grupos, no el interior de cada uno.

La numeración de secciones se conserva a propósito: hay referencias a `§8.3` y
`§8.5` en comentarios del código y en otros documentos.

## 3 · La espina dorsal

```
sec.mail | pro.lexnet    llega algo — o el abogado abre el asunto
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

Cuatro consecuencias:

**El secretario está en las 89 rutas**, y en las dos puntas. Todo entra y sale por
él, incluso cuando el impulso es del abogado: entonces la entrada es el registro del
encargo y la salida sigue siendo una entrega.

**El procesal valida dos veces, y la segunda no es redundante.** Entre la puerta y la
salida el pipeline ha consumido días. Un plazo holgado al empezar puede estar crítico
al terminar, y `pro.plazo-vivo` es la última oportunidad de no presentar fuera de
plazo.

**Quien tiene credenciales no decide, y quien decide no puede enviar.** El secretario
sabe recibir y entregar, no sabe de plazos. El procesal calcula y determina destino,
pero no tiene acceso a ningún canal. La separación es lo que hace auditables a los
dos.

**El abogado no verifica los plazos: los recibe.** Se diseña pensando en un despacho
de un solo abogado, al que el sistema tiene que quitar trabajo, no dárselo. Como nadie
revisa después las fechas que calcula `procesal`, la garantía se reparte entre las dos
capas del envoltorio. `procesal` responde de la **corrección**: `pro.calendario` no se
usa con clientes hasta superar su validación, y cuando le falta un dato da la fecha que
obliga a actuar antes. `secretario` responde de la **visibilidad**: `sec.notificador`
comprueba que los avisos se ven e insiste si no. Si falla cualquiera de las dos mitades,
el plazo se pierde sin que nadie lo detecte. Detalle de ambos en `COMPONENTES.md`.

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

**Disparadores:** abogado 59 · secretario 22 · workflow 6 · agenda 2
**Destinos:** lexnet 59 · admin 12 · cliente 8 · notarial 6 · burofax 2 · smac 1 · policial 1

Tres lecturas:

- `secretario`, `archivador`, `procesal`, `redactor` y `critico` entran en los 89.
  Los otros cuatro son enrutables.
- El **secretario dispara 22 rutas**, y **17 de esas 22** son justo las que activan
  `est.contrario`. Recibir y rebatir son la misma cadena.
- **LexNET sirve a 59 de 89.** Los otros 30 salen por los demás módulos de
  `pro.salida`: tratarlo como destino único deja un tercio del catálogo sin camino.

```csv
tipo,arq,origen,secretario,archivador,procesal,estratega,probatorio,calculadora,investigador,redactor,critico,salida
demanda_laboral,B,abogado,1,1,1,c,1,1,1,1,1,lexnet
despido_objetivo,B,abogado,1,1,1,c,1,1,1,1,1,lexnet
despido_colectivo,F,abogado,1,1,1,c,1,1,1,1,1,lexnet
papeleta_conciliacion,C,workflow,1,1,1,0,0,c,0,1,c,smac
reclamacion_cantidad,B,abogado,1,1,1,c,1,1,1,1,1,lexnet
impugnacion_sancion,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
modificacion_sustancial,B,secretario,1,1,1,c,1,1,1,1,1,lexnet
extincion_art_50,E,abogado,1,1,1,c,1,1,1,1,1,lexnet
tutela_derechos_fundamentales,E,abogado,1,1,1,c,1,0,1,1,1,lexnet
demanda_seguridad_social,A,secretario,1,1,1,1,1,c,1,1,1,lexnet
reclamacion_previa_ss,H,secretario,1,1,1,c,0,0,c,1,c,admin
conflicto_colectivo,E,abogado,1,1,1,c,c,0,1,1,1,lexnet
recargo_prestaciones,A,abogado,1,1,1,1,1,1,1,1,1,lexnet
carta_despido,G,abogado,1,1,1,0,c,1,1,1,1,cliente
monitorio,B,abogado,1,1,1,c,1,1,c,1,1,lexnet
demanda_civil,E,abogado,1,1,1,c,1,c,1,1,1,lexnet
juicio_verbal,E,abogado,1,1,1,c,1,c,1,1,1,lexnet
contestacion_demanda,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
recurso_apelacion,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
juicio_cambiario,B,abogado,1,1,1,c,1,1,c,1,1,lexnet
nulidad_clausulas_abusivas,A,abogado,1,1,1,1,1,1,1,1,1,lexnet
reclamacion_danos,B,abogado,1,1,1,c,1,1,1,1,1,lexnet
division_cosa_comun,E,abogado,1,1,1,c,1,1,1,1,1,lexnet
demanda_desahucio,B,abogado,1,1,1,c,1,1,1,1,1,lexnet
desahucio_expiracion_plazo,E,abogado,1,1,1,c,1,c,1,1,1,lexnet
precario,E,abogado,1,1,1,c,1,0,1,1,1,lexnet
oposicion_ejecucion,A,secretario,1,1,1,1,1,1,1,1,1,lexnet
medidas_cautelares,I,abogado,1,1,1,c,1,c,1,1,1,lexnet
contrato_arrendamiento,G,abogado,1,1,1,0,0,c,1,1,1,cliente
divorcio_mutuo_acuerdo,E,abogado,1,1,1,c,c,1,1,1,1,lexnet
divorcio_contencioso,E,abogado,1,1,1,c,1,1,1,1,1,lexnet
convenio_regulador,G,abogado,1,1,1,0,0,1,1,1,1,cliente
medidas_paternofiliales,E,abogado,1,1,1,c,1,1,1,1,1,lexnet
modificacion_medidas,A,abogado,1,1,1,1,1,1,1,1,1,lexnet
reclamacion_alimentos,B,abogado,1,1,1,c,1,1,1,1,1,lexnet
liquidacion_gananciales,F,abogado,1,1,1,c,1,1,1,1,1,lexnet
medidas_apoyo,E,abogado,1,1,1,c,1,0,1,1,1,lexnet
orden_proteccion,D,abogado,1,1,1,c,1,0,1,1,1,lexnet
declaracion_herederos,E,abogado,1,1,1,0,1,0,1,1,1,notarial
cuaderno_particional,F,abogado,1,1,1,0,1,1,1,1,1,notarial
aceptacion_renuncia_herencia,G,abogado,1,1,1,0,c,c,1,1,1,notarial
impugnacion_testamento,A,abogado,1,1,1,1,1,0,1,1,1,lexnet
reclamacion_legitima,B,abogado,1,1,1,c,1,1,1,1,1,lexnet
denuncia_penal,D,abogado,1,1,1,0,1,0,1,1,1,policial
querella,D,abogado,1,1,1,c,1,0,1,1,1,lexnet
escrito_defensa,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
escrito_acusacion,A,workflow,1,1,1,1,1,0,1,1,1,lexnet
personacion_acusacion_particular,I,secretario,1,1,1,c,0,0,0,1,c,lexnet
recurso_reforma,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
recurso_apelacion_penal,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
juicio_leve,E,secretario,1,1,1,c,1,0,1,1,1,lexnet
conformidad,B,workflow,1,1,1,c,c,1,1,1,1,lexnet
habeas_corpus,I,abogado,1,1,1,c,0,0,c,1,c,lexnet
libertad_provisional,I,abogado,1,1,1,c,c,0,c,1,c,lexnet
recurso_alzada,A,secretario,1,1,1,1,c,0,1,1,1,admin
recurso_reposicion,A,secretario,1,1,1,1,c,0,1,1,1,admin
alegaciones_sancionador,A,secretario,1,1,1,1,c,0,1,1,1,admin
responsabilidad_patrimonial,B,abogado,1,1,1,0,1,1,1,1,1,admin
reclamacion_economico_administrativa,A,secretario,1,1,1,1,1,1,1,1,1,admin
recurso_contencioso,A,secretario,1,1,1,1,c,0,1,1,1,lexnet
concurso_acreedores,F,abogado,1,1,1,c,1,1,1,1,1,lexnet
constitucion_sociedad,G,abogado,1,1,1,0,0,c,1,1,1,notarial
impugnacion_acuerdos_sociales,A,secretario,1,1,1,1,1,0,1,1,1,lexnet
responsabilidad_administradores,E,abogado,1,1,1,c,1,1,1,1,1,lexnet
pacto_socios,G,abogado,1,1,1,0,0,0,1,1,1,cliente
compraventa_participaciones,G,abogado,1,1,1,0,c,1,1,1,1,notarial
disolucion_liquidacion,F,abogado,1,1,1,0,1,1,1,1,1,notarial
reclamacion_cambiaria,B,abogado,1,1,1,c,1,1,c,1,1,lexnet
arraigo,E,abogado,1,1,1,0,1,0,1,1,1,admin
nacionalidad,E,abogado,1,1,1,0,1,0,1,1,1,admin
recurso_denegacion,A,secretario,1,1,1,1,c,0,1,1,1,admin
recurso_expulsion,A,secretario,1,1,1,1,c,0,1,1,1,admin
burofax_requerimiento,H,abogado,1,1,1,0,c,c,c,1,c,burofax
reclamacion_extrajudicial,H,abogado,1,1,1,0,c,c,c,1,c,burofax
acuerdo_transaccional,H,abogado,1,1,1,0,0,1,1,1,1,cliente
solicitud_mediacion,H,abogado,1,1,1,0,0,0,0,1,c,admin
suspension_vista,I,agenda,1,1,1,c,0,0,0,1,c,lexnet
aportacion_documental,I,workflow,1,1,1,c,c,0,0,1,c,lexnet
subsanacion_defectos,I,secretario,1,1,1,c,0,0,c,1,c,lexnet
proposicion_prueba,I,agenda,1,1,1,c,1,0,c,1,c,lexnet
desistimiento,I,abogado,1,1,1,c,0,0,0,1,c,lexnet
justicia_gratuita,I,abogado,1,1,1,0,c,c,0,1,c,admin
recurso_reposicion_procesal,I,secretario,1,1,1,1,0,0,c,1,c,lexnet
ejecucion_titulo_judicial,J,workflow,1,1,1,c,c,1,0,1,c,lexnet
ejecucion_hipotecaria,J,abogado,1,1,1,c,1,1,c,1,c,lexnet
ejecucion_familia,J,abogado,1,1,1,c,c,1,0,1,c,lexnet
hoja_encargo,G,abogado,1,1,1,0,0,1,0,1,c,cliente
minuta_honorarios,G,workflow,1,1,1,0,0,1,0,1,c,cliente
provision_fondos,G,abogado,1,1,1,0,0,1,0,1,c,cliente
```

---

## 6 · Doce rutas de referencia

Una por patrón, nombrando componentes. Cubren los arquetipos A–G: cada tipo de esos
arquetipos hereda la ruta del suyo. Los 19 tipos de H, I y J aún no tienen ruta de
referencia.

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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
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
sec.mail              el abogado abre el asunto
— sin puerta de plazo —           no hay acto que buscar en la tabla de plazos
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
4. **Componentes acotados, no agentes generalistas.** Un `cri.formal` que recorre el
   art. 277 LECrim como lista cerrada es verificable; un «crítico» que opina sobre
   todo, no. La granularidad es lo que hace auditable el sistema.

### 8.2 · Seis tipos de mayor volumen real

`burofax_requerimiento` · `monitorio` · `escrito_defensa` ·
`divorcio_mutuo_acuerdo` · `recurso_alzada` · `suspension_vista`

### 8.3 · Estado del código

**Implementado — `sec.mail`**

Primer componente implementado, y es un módulo. Correo por **Gmail API autenticada
con OAuth** (§8.6) y almacenamiento local cifrado. Corre en el ordenador del abogado. **Hoy no
sube nada al servidor**: el resumen que lo haría sigue pendiente (más abajo). Cuando
exista, subirá sin filtrar — `anonimizar` no está implementado (§1).

| pieza | fichero |
|---|---|
| interfaz al resto del sistema | `sec/mail/agent.py` |
| interfaz `Correo`, común a los tres mundos | `sec/mail/correo.py` |
| flujo OAuth (PKCE + loopback), tokens y renovación | `sec/cuentas/oauth.py` (compartido) |
| adaptador de Gmail API | `sec/mail/google.py` |
| adaptador de Microsoft Graph | `sec/mail/microsoft.py` |
| parser de `.eml` | `sec/mail/parser.py` |
| base SQLCipher | `sec/mail/db.py` |
| credenciales, tokens y claves de las bases | `sec/cuentas/ajustes.py` (compartido) |
| IMAP y ruta de su base | `sec/mail/config.py` |
| CLI | `sec/mail/__main__.py` |

Superficie: `conectar · estado · desconectar · carpetas · sincronizar [--limite N] ·
listar · leido · mover`. Tablas: `correos · adjuntos · sincronizacion · pendientes ·
acciones`.

El Backend sigue sin más dependencia que `sqlcipher3`: el flujo OAuth y las dos APIs
van con la librería estándar (`urllib`, `http.server`).

Frontend (`iced`): pantalla **Calendario** nueva (`src/calendario.rs` +
`src/screens/calendario.rs`), que lee `calendario.db` en **solo lectura** y sin clave
--no está cifrada-- y muestra la cobertura por nivel, las averías con su motivo y los
días inhábiles de un municipio con la marca de qué nivel aporta cada uno. Es vista de
mantenimiento, no del día a día: existe para que el calendario no envejezca en
silencio. La cadena de ámbitos se resuelve con un **CTE recursivo** en SQL, así que el
frontend no necesita saber cuántos niveles hay.

Sobre el **acoplamiento de esquema**: `secretario.rs` y `calendario.rs` conocen el
esquema de las bases que escribe el Backend, y nada ata las dos mitades. Mitigación en
`calendario.rs`: `comprobar_esquema` verifica las columnas que usa y falla nombrando
la que falte, en vez de devolver una lista vacía que parece un calendario sin
festivos. Las consultas de Rust y Python se han contrastado sobre la base real --doce
casos, mismos días y mismas lagunas-- pero eso es una comprobación puntual, no un
mecanismo; si el acoplamiento crece, la alternativa es que el frontend pida los datos
por la CLI.

**Dos caras en dos pestañas: Despacho y Control.** Arriba se elige la cara, debajo
aparecen solo sus secciones. **Despacho** es el trabajo del día —Inicio, Expedientes,
Secretario—; **Control** es mirar cómo está el sistema —Calendario, Ajustes—. El reparto
no lo decidió esta pantalla: `calendario.rs` ya decía en su cabecera «el abogado no va a
abrir esto», porque enseña la cobertura del calendario de festivos y sus averías, no los
plazos de nadie.

**No es seguridad, es atención.** La base y la configuración están en la misma máquina y
quien edite un fichero de texto ve lo que quiera. Lo que se gana es que una pantalla de
mantenimiento no se cruce en medio del trabajo, y que una de trabajo no esconda lo que se
ha roto.

Cada cara recuerda dónde se estaba, o cruzar a mirar algo costaría tres clics de vuelta.
Y hay una excepción deliberada al reparto: **una cuenta revocada se avisa en Despacho**,
con un botón que lleva a Ajustes. Esconder Ajustes en Control dejaba al abogado sin saber
que su permiso había caducado —y eso no da ningún error: simplemente deja de entrar
correo, cada siete días mientras la app de Google siga en *Testing*—. Lo que se ha roto
se enseña donde se está trabajando, no donde habría que ir a mirarlo.

**Conectar cuenta ya no bloquea la ventana.** Era el último bloqueo síncrono dentro de
`update`, y el peor: espera a que una persona elija cuenta en el navegador, hasta cinco
minutos. Mientras tanto el bucle de eventos de `iced` estaba parado, la ventana no
repintaba y el navegador podía abrirse **detrás** de ella; desde fuera parecía que el
botón no hacía nada, y así se vio en macOS. Ahora `update` devuelve `Task`, el
consentimiento corre en un hilo aparte —es una espera bloqueante de un subproceso, no
trabajo asíncrono: meterlo en el ejecutor ocuparía un hilo igual, disimulado— y la
pantalla dice **«Abriendo el navegador… si no lo ves, búscalo detrás de esta
ventana»**. El botón queda muerto mientras tanto: dos consentimientos a la vez abren dos
navegadores y solo uno guarda el token. `Refrescar` sigue siendo síncrono, pero eso
tarda medio segundo, no minutos.

Frontend (`iced`): botón **Refrescar** en la pantalla Secretario invoca
`sincronizar --limite 5` como subproceso y recarga la lista. Ajustes ya no tiene
campos de texto sino **Conectar cuenta** por proveedor, con el estado de cada una;
conectar dispara una sincronización. El límite de la tanda de descarga (5) y el
límite de la lista mostrada (sin límite: se ve todo lo ya guardado) son valores
independientes -- confundirlos fue un bug real, ya corregido.

Decisiones que conviene no perder:

- **La identidad del mensaje es `(proveedor, mensaje_id)`.** El identificador de la
  Gmail API no cambia nunca, tampoco al mover de etiqueta. En Graph **sí cambia al
  mover**: la operación devuelve un mensaje nuevo, así que `mover` devuelve el
  identificador resultante y la base se queda con ese. Una fila que apunte al
  identificador viejo no da error, simplemente deja de resolver.
- **Cursor opaco por proveedor.** `historyId` en Google, `deltaLink` en Graph. El
  módulo lo guarda y lo devuelve sin interpretarlo. Si el proveedor lo rechaza por
  antiguo (404 en Google, 410 en Graph) se hace inventario completo de la carpeta en
  vez de fallar: repetir identificadores es inofensivo, perderlos sería un correo que
  el despacho no ve.
- **Cola de pendientes.** Es lo que sustituye al puntero de UID de IMAP, y el punto
  más delicado del cambio. Las dos APIs avanzan el cursor **de golpe** al final de la
  respuesta, no mensaje a mensaje, así que el cursor ya no puede ser la garantía de
  no perder nada. Lo anunciado por el servidor se apunta en `pendientes` *antes* de
  guardar el cursor; cada correo sale de la cola solo cuando está guardado. Una
  interrupción a mitad de tanda no pierde trabajo ni lo repite, que es la propiedad
  que había que conservar.
- **Inventario: el cursor se pide antes de listar.** Si se pidiera después, los
  correos llegados durante el recorrido quedarían por debajo del cursor y no los
  vería nadie nunca.
- **Sincronización en solo lectura.** El módulo lee sin marcar como leído: el abogado
  sigue viendo su bandeja intacta desde sus propios dispositivos.
- **Sincronización en tandas.** `--limite N` corta la descarga a los N pendientes más
  antiguos; el resto se queda en la cola para la llamada siguiente.
- **Secretos en local, sin llavero del sistema.** Los tokens de OAuth (sección
  `[oauth.google]`) y la clave de la base (`[secmail]`) viven en `~/.misyks/config`,
  junto a la base `~/.misyks/sec_mail.db`. Fuera del repo, para que sigan funcionando
  cuando la app se distribuya como binario.
- **Escribir el archivo de secretos vuelve a abrirlo.** El reemplazo atómico deja en
  su sitio el archivo temporal, que heredó los permisos del directorio y no los del
  archivo al que sustituye. Cada renovación de token deshacía así, en silencio, el
  endurecimiento que aplica el Frontend, dejando el refresh token y la clave de la
  base legibles para `SYSTEM` y `Administrators` (comprobado con `icacls`). Quien
  escribe el archivo lo cierra: `config._restringir_permisos` repite en Python lo que
  `local_config.rs` hace en Rust.
- **`config.py` ya escribe, no solo lee.** Con contraseña de aplicación bastaba con
  leer, porque la escribía la persona desde Ajustes. Con OAuth el access token caduca
  cada hora y Microsoft rota el refresh token en cada renovación: quien renueva tiene
  que poder guardar. Escribe solo su sección, con archivo temporal y reemplazo
  atómico, para que un corte no deje la configuración sin la clave de la base -- que
  dejaría la base ilegible.
- **Registro de acciones** en tabla propia: todo lo que el módulo hace sobre un correo
  queda anotado.

**Migración desde la versión IMAP.** Las bases ya existentes se convierten al abrirlas
y los correos descargados no se vuelven a bajar: el `id` de la Gmail API y el
`X-GM-MSGID` de IMAP son el mismo número, en hexadecimal y en decimal, así que el
identificador se traduce en sitio. Lo que no tiene traducción es el puntero
`UIDVALIDITY` + último UID, que se descarta; la primera sincronización tras migrar
hace inventario completo, que lista identificadores sin descargar nada, y descarta
contra la base los que ya están.

Con una trampa que costó un fallo real: desde SQLite 3.25, `ALTER TABLE ... RENAME`
reescribe las referencias que otras tablas hacen a la renombrada, así que `adjuntos`
y `acciones` pasaban a apuntar a la tabla temporal que la migración borraba después.
La base seguía abriendo y leyendo con normalidad; el error (`no such table:
correos_imap`) solo aparecía al guardar el primer adjunto, muy lejos de su causa. La
migración usa ahora `PRAGMA legacy_alter_table`, y `_reparar_referencias` reconstruye
las tablas de las bases que ya pasaron por la versión defectuosa.

**Pendiente**

En `sec.mail`, respecto a lo descrito en `COMPONENTES.md`:

- el **resumen** que consume `sec.clasificador` y el parámetro **ventana** del contrato;
- **descender por los reenvíos**: hoy un correo reenviado como adjunto se guarda entero
  como `.eml`, sin extraer sus adjuntos como documentos propios;
- la **fecha de recepción**: se guarda la cabecera `Date` (la que declara el remitente)
  y la hora de guardado, no la fecha de llegada al buzón.

Del paso a OAuth:

- **Microsoft sin probar.** `microsoft.py` está escrito contra la interfaz `Correo`
  pero no se ha ejecutado nunca contra una cuenta real: falta el registro de la
  aplicación en Entra. Lo más probable que necesite ajuste es la paginación del delta.
- **Registro y verificación de las apps.** Hoy cada máquina usa su propio `client_id`
  en estado *Testing*, donde Google caduca el refresh token a los siete días. La app
  publicada y verificada es trámite aparte (§8.6).
- **Determinación del mundo por MX.** No está implementada: hoy el proveedor sale de
  `[correo] proveedor` en la configuración, o se deduce cuando hay una sola cuenta
  conectada. Basta mientras la conexión la hace una persona en Ajustes, eligiendo
  Google o Microsoft; hará falta cuando se quiera acertar solo a partir de la
  dirección.
- **Una cuenta por proveedor.** El esquema ya guarda `cuenta` en cada correo, pero
  `config` elige un único proveedor activo: varias cuentas a la vez no están
  resueltas.
- **Adaptador del tercer mundo: no existe, y ya no hay esqueleto.** `imap.py` se ha
  borrado. No lo importaba nadie —`correo.abrir()` solo conoce `google` y
  `microsoft`— y lo que contenía era el Gmail de antes de OAuth: host fijo
  `imap.gmail.com`, identidad por `X-GM-MSGID`, etiquetas propias de Gmail. Es decir,
  justo las tres cosas que un adaptador de iCloud o Fastmail tendría que sustituir
  —host configurable, `Message-ID` o UID como identidad, sin etiquetas—, así que
  conservarlo no adelantaba trabajo y sí inducia a error a quien lo leyera. Cuando
  toque ese mundo se escribe contra la interfaz `Correo`; el archivo está en el
  historial de git. Con él se han ido `config.credenciales_imap`, `IMAP_HOST` y
  `IMAP_PORT`; la sección `[imap]` de `~/.misyks/config` ya no la lee nadie.

**Implementado — `sec.agenda`**

Tercer componente con código, también módulo. Calendario por **Google Calendar API**
con el mismo consentimiento OAuth que el correo (§8.6) y base local cifrada. Corre
donde `sec.mail`, porque usa sus tokens.

| pieza | fichero |
|---|---|
| interfaz al resto del sistema | `sec/agenda/agent.py` |
| interfaz `Calendario`, común a los tres mundos | `sec/agenda/calendario.py` |
| adaptador de Google Calendar | `sec/agenda/google.py` |
| base SQLCipher | `sec/agenda/db.py` |
| ruta de la base y ventana por defecto | `sec/agenda/config.py` |
| CLI | `sec/agenda/__main__.py` |

Superficie: `sincronizar · agenda · colisiones · clasificar · plazo · publicar ·
acciones`. Tablas: `eventos · sincronizacion · acciones`, en `~/.misyks/sec_agenda.db`.

**Lo compartido se ha separado: `sec/cuentas/`.** El consentimiento es uno por cuenta
y trae correo y calendario juntos, así que la sección `[oauth.google]` no es de
`sec.mail`. `oauth.py` y la parte genérica de su `config.py` (ahora `ajustes.py`)
salen de dentro de `sec.mail` para que `sec.agenda` no tenga que importarlo solo para
leer un token. `sec/mail/config.py` se queda con lo suyo —IMAP y la ruta de su base—
y reexporta el resto, así que el código que lo usaba no cambia. `sec.mail` sigue
funcionando igual: se ha comprobado contra la cuenta real después de moverlo.

Decisiones que conviene no perder:

- **Una sola tabla de eventos, con `tipo` y `origen`.** Una vista del calendario, una
  reunión escrita a mano y un plazo que entrega `procesal` se miran juntos o no
  sirven de nada. Lo que los diferencia —si se pueden mover, quién los produjo, si
  son firmes— son columnas.
- **Incremental y completo no son lo mismo, y confundirlos vacía la agenda.** En un
  recorrido incremental, que un evento no venga significa que **no ha cambiado**;
  solo tras un recorrido completo se puede concluir que ya no existe y cancelarlo.
  Por eso `listar_eventos` devuelve también si hubo reinicio, y no basta con mirar si
  había cursor: Google puede rechazarlo por antiguo (410) y responder completo.
- **El cursor no se puede acotar, y tampoco acota él.** Al `syncToken` de Google no
  se le pueden volver a mandar `timeMin`/`timeMax` (400), así que se guarda junto a la
  ventana con la que se pidió y se descarta si se pide otra: reusarlo con otra ventana
  daría una agenda con huecos que nadie notaría. Lo que **no** hace es respetar esa
  ventana al contestar, aunque lo parezca. **Medido contra la API real:** dos eventos
  anuales sin fecha de fin, y la primera sincronización incremental devolvió **147
  ocurrencias**, expandidas hasta el año 2099. Aquí se había supuesto lo contrario, y
  con el calendario vacío no se veía. El recorte por ventana lo hace ahora `agent.py`
  sobre lo recibido, con una excepción necesaria: un evento que cae fuera **pero ya
  está guardado** sí se acepta, porque es como se entera la agenda de que algo suyo se
  ha movido fuera; descartarlo dejaría la fila vieja mintiendo. El adaptador no
  recorta: no sabe qué hay guardado.
- **Hora local e instante, los dos.** Un evento es una hora local con una zona, no un
  instante (§8.6). Se guarda la hora que el abogado reconoce **y** el instante en UTC
  que sale del desplazamiento del propio RFC 3339. Los solapes se comparan por
  instante: hacerlo por hora local inventa colisiones entre zonas y silencia las
  reales. El desplazamiento viene en el dato, así que no hace falta `zoneinfo` ni el
  paquete `tzdata`, que en Windows habría sido una dependencia nueva.
- **Las series las expande el proveedor** (`singleEvents=true`). Interpretar la regla
  de repetición por nuestra cuenta es reescribir un calendario para equivocarse justo
  en las excepciones, que es donde están los señalamientos que se mueven.
- **Lo cancelado no se borra.** Un señalamiento que se cae es información; se marca y
  queda en el registro de acciones.
- **Lo clasificado a mano no se pisa.** Una sincronización posterior actualiza el
  título o la hora, pero no el `tipo` ni el `abogado`: eso lo puso alguien que sabía
  algo que la API no dice.
- **Los plazos no viven aquí: se proyectan del expediente.** Estuvieron un día en
  `sec.agenda` con su propia vida y su propia fecha, hasta que se vio que un plazo y un
  hito de clase `limite` del expediente **son la misma cosa guardada dos veces**, que
  es exactamente el fallo contra el que avisa el resto de este documento. Ahora la
  verdad es el hito; `agent.agenda()` lee los expedientes abiertos y devuelve sus hitos
  con fecha mezclados con lo propio, cada fila con su `origen_fila`. Marcar un hito
  como hecho se ve en la agenda al instante porque no hay nada que copiar.
- **Lo que ponen las personas no se pisa.** `tipo` y `abogado` están protegidos: una
  sincronización del calendario cambia la hora y el título de un evento, pero no lo
  que alguien clasificó a mano.
- **Escribir en el calendario es a petición.** `publicar` existe y `sincronizar` no
  escribe nunca. Publicar algo que vino del calendario se rechaza: lo duplicaría.
- **Publicar adopta el identificador del proveedor.** Al crear el evento allí, la fila
  pasa a `origen = 'calendario'` con el identificador que devuelve la API. Sin eso, la
  sincronización siguiente traería el evento recién publicado como uno nuevo y
  habría dos filas para el mismo compromiso.
- **La ventana por defecto se cuadra a meses enteros, y no es cosmético.** El cursor
  se guarda con la ventana que lo pidió y se descarta si se pide otra. Con una ventana
  de «hoy ± N días», mañana la ventana ya es otra: el cursor no vale nunca y **todas
  las sincronizaciones son completas**, con lo que el camino incremental existiría sin
  llegar a usarse jamás. Se vio al día siguiente de escribirlo, midiendo tiempos.
  Cuadrada al mes, cambia una vez cada treinta días: un recorrido completo al mes y el
  resto incrementales.
- **`showDeleted` solo en el incremental.** Ahí una baja *es* la noticia y llega como
  un evento `cancelled`. En un recorrido completo, pedir los borrados **resucita
  lápidas**: Google guarda un tiempo lo eliminado y lo devuelve igualmente, así que
  cada recorrido completo volvía a crear la fila de algo borrado hace semanas
  —comprobado con el evento de prueba—. En el completo, la baja se detecta por
  ausencia, que es para lo que existe `marcar_ausentes_como_cancelados`.
- **`apuntar` es la tercera entrada.** Ni del calendario ni de `procesal`: una reunión
  acordada por teléfono, un cumpleaños, una obligación viva de un contrato ya cerrado
  (arquetipo G). Admite `RRULE` para lo que se repite cada año, que solo viaja al
  publicar: la agenda no expande series, eso lo hace el proveedor.
- **Las columnas que faltan se añaden al abrir.** `CREATE TABLE IF NOT EXISTS` no toca
  una tabla que ya existe, así que una columna añadida después no aparecería y la
  primera escritura fallaría con `no such column`. `_anadir_columnas_que_falten` las
  compara y añade lo que falte.
- **La clave de `sec_agenda.db` la genera el Backend.** La de `sec.mail` la crea el
  Frontend antes de invocarlo; la agenda no tiene pantalla todavía, y fallar
  obligaría a pegar a mano un hexadecimal de 64 caracteres para poder guardar una
  reunión. Cuando haya pantalla, esto pasa a leerse como el otro.
- **Salida de consola tolerante (`sec/cuentas/consola.py`).** La consola de Windows es
  cp1252: un título con un emoji o una flecha no imprimía un signo raro, lanzaba
  `UnicodeEncodeError` y se llevaba la orden entera. Apareció escribiendo esto y
  afectaba también a `sec.mail listar`, donde el asunto lo escribe cualquiera. Las dos
  CLI lo aplican ahora.

**Pendiente**

- **Probado contra la API real** (2026-09-17, cuenta de desarrollo): alta de eventos,
  serie anual expandida por el proveedor, recorrido completo, recorrido incremental,
  baja de un evento borrado en Google —llega como `cancelled` y la fila queda anulada
  sin borrarse— y el recorte por ventana. Lo que sigue **sin medir**: varias páginas
  de resultados (hace falta un calendario con más de 2500 eventos), una ocurrencia
  suelta movida o anulada dentro de una serie, y los eventos con zona horaria
  distinta de la del calendario, que solo se han visto contra el adaptador falso.
- **Tiempos medidos** (18/09/2026, calendario pequeño, portátil del abogado): consultar
  lo ya guardado —`agenda`, `colisiones`— es instantáneo, 0,000 s, porque no toca red;
  una llamada a la Calendar API, 0,37 s; una sincronización entera, 0,22 s. Google
  entrega hasta 2500 eventos por página, así que un calendario normal de despacho cabe
  en una sola petición. El coste real no está aquí sino en `sec.mail`, donde cada
  correo nuevo es una descarga aparte: 0,40 s cuando no hay nada nuevo, y proporcional
  al número de correos por bajar cuando lo hay. Por eso el correo va en tandas y el
  calendario no lo necesita.
- **Solo Google.** El adaptador de Microsoft Graph para calendario no está escrito;
  `calendario.abrir` lo dice con todas las letras en vez de fallar de forma rara.
  CalDAV (tercer mundo) tampoco.
- **Un solo calendario y un solo abogado.** Se lee `primary` de la cuenta conectada, y
  el abogado *es* la cuenta. Cruzar agendas entre abogados del despacho —que
  COMPONENTES.md exige— ya funciona en la consulta (las colisiones marcan `despacho`
  frente a `mismo_abogado`), pero hoy no hay de dónde sacar una segunda agenda.
- **Las fechas de los hitos hay que teclearlas.** Las producirá `pro.caducidad`
  cuando exista; hoy se ponen con `expedientes fechar`.
- **La vida del hito no dispara nada todavía.** Un plazo hecho deja de avisar cuando
  exista `sec.notificador`, que es quien avisa; hoy lo único que cambia es lo que se
  ve en la barra y en la agenda.
- **Sin pantalla en el Frontend.** No hay vista de agenda; se usa por CLI.

**Implementado — `expedientes`: la ficha, no la ruta**

No es un componente: es el **almacén** al que se subordina lo demás, como `sec.cuentas`
lo es de las credenciales. Un expediente es una instancia de un tipo documental, y el
tipo determina ruta, plazos y canal de salida.

| pieza | fichero |
|---|---|
| catálogo de los 89 tipos (dato) | `expedientes/datos/tipos.csv` |
| plantilla de hitos por tipo (dato, **borrador**) | `expedientes/datos/hitos.csv` |
| lectura y validación del catálogo | `expedientes/catalogo.py` |
| base SQLCipher | `expedientes/db.py` |
| interfaz al resto del sistema | `expedientes/agent.py` |
| CLI | `expedientes/__main__.py` |
| pantalla (iced) | `Frontend/src/screens/expedientes.rs` + `src/expedientes.rs` |
| vista de un expediente: la barra de nodos | `Frontend/src/screens/detalle.rs` |

Superficie: `tipos · abrir · listar · hitos · fechar · cerrar · eliminar · vaciar`.
Tablas: `expedientes` e `hitos`, en `~/.misyks/expedientes.db` —cifrada, que aquí no hay
debate: lleva el nombre del cliente y el del contrario—.

Decisiones que conviene no perder:

- **El catálogo es dato, no código.** Los 89 tipos salen de la matriz de activación de
  §5 a un CSV. Añadir un tipo es añadir una línea, y lo puede revisar quien no
  programa. Si CSV y §5 se separan, manda §5.
- **El arquetipo y el destino se copian al abrir**, no se miran cada vez. Si mañana se
  corrige la matriz, un expediente ya abierto no puede cambiar de ruta por su cuenta:
  eso es lo que hace que un plazo calculado hace tres meses deje de poder explicarse.
- **La referencia la pone la base** (`EXP-2026-001`), dentro de la misma transacción que
  la inserción —dos expedientes abiertos a la vez se llevarían el mismo número— y
  contando sobre las referencias del año, no sobre el total de filas: borrar no puede
  hacer que el siguiente repita un número que ya se usó en un escrito.
- **Cerrar y eliminar son cosas distintas.** Cerrar lo saca de los abiertos y lo deja;
  eliminar no deja rastro. Hoy eliminar vale porque un expediente es una ficha; en
  cuanto cuelguen documentos, plazos y acuses, tendrá que pasar a ser una operación con
  motivo y registro.
- **Borrar todo pide dos pulsaciones y dice cuántos se lleva.** En la CLI la
  confirmación es `--si`; sin él, la orden dice qué iba a borrar y no borra nada.
- **Leer directo, escribir por el Backend.** El Frontend lee la base con `rusqlite` y
  escribe invocando `python -m expedientes`. Una lectura desincronizada enseña un dato
  de menos; una escritura desincronizada corrompe.
- **La vida del hito se recibe, y `vencido` se deriva.** `pendiente · ocurrido ·
  en_pausa · cancelado` se guardan; **`vencido` no**, se calcula al leer: escribirlo
  sería el sistema dando un asunto por perdido por su cuenta, y esa decisión es de
  `pro.caducidad`. Además solo vence un plazo con fecha **firme**: si es `provisional`
  todavía puede moverse, y con datos dudosos no hay vencido.
- **El abogado puede marcar un nodo él mismo**, porque la mayor parte del trabajo de un
  despacho no pasa por el sistema. Queda como realizado **declarado** —lo dice quien lo
  hizo— frente al **acreditado**, que llegará con el justificante de `pro.acuse`:
  `cerrado_por` vale `abogado` o `acuse`, y esa diferencia es lo que permite a la
  auditoría separar lo que consta de lo que se ha dicho. Siempre guarda la **fecha del
  hecho**, no la del registro, porque de ella cuelgan plazos posteriores —el del
  silencio administrativo se cuenta desde la presentación—. Y se puede deshacer:
  marcar es un clic, y los clics se dan sin querer.
- **`documento_id` está previsto y vacío.** Un hito acreditado debería llevar el
  documento que lo prueba, pero del expediente todavía no cuelga ningún fichero: la
  columna existe para que cuando los haya no haya que migrar nada.
- **Pausar exige motivo y reanudar mueve la fecha.** Una pausa sin causa anotada no se
  puede explicar después, y una que no mueve el vencimiento es una marca decorativa
  —que es justo lo que hacía el ecosistema antiguo—. La fecha nueva llega ya
  recalculada de fuera: aquí no se computa nada.
- **Los hitos son del expediente, no del tipo.** Se copian de la plantilla al abrirlo
  y a partir de ahí son suyos: un expediente abierto hace tres meses sigue enseñando el
  recorrido con el que nació, aunque la plantilla se haya corregido. Misma razón que
  con el arquetipo.
- **Cuatro clases de hito, y cada una espera otra cosa de su fecha.** `acto` (ocurre y
  se fecha cuando ocurre), `limite` (un plazo, y la fecha es el último día: la
  calculará `pro.calendario`), `senalamiento` (lo fija el juzgado, y hasta entonces no
  hay fecha —y eso es el estado normal, no un hueco—) y `resolucion` (llega cuando
  llega). La fecha lleva además su **clase**: `real · limite · provisional ·
  sin_senalar`. Sin esa distinción, «el 2 de octubre» como tope propio y «el 2 de
  octubre» como día de vista se leen igual, que es justo el error caro.
- **La barra no avanza sola.** Un hito pasa a `ocurrido` cuando alguien aporta la
  prueba —hoy una persona por la CLI; mañana el acuse de `pro.acuse` o la notificación
  de LexNET—. Si el sistema pudiera marcarlo por su cuenta, antes o después daría por
  presentado algo que no lo está.
- **La plantilla de hitos es un borrador y la interfaz lo dice.** Hay cinco tipos de
  los 89, redactados a partir de los artículos que ya citan §6 y §7, y **ninguno lo ha
  revisado un abogado**: la columna `revisado` dice `no` en todas las filas y la
  pantalla lo advierte en rojo. Una barra que parece definitiva sin serlo es peor que
  no tenerla.
- **Un tipo sin plantilla no inventa nodos.** Dice que su recorrido no está escrito.
- **`Frontend/src/backend.rs`.** Localizar la carpeta del Backend y elegir intérprete
  estaba dentro de `secretario.rs` porque `sec.mail` era lo único que se invocaba. Con
  dos módulos ya no es de ninguno: mismo movimiento que `sec/cuentas` en el Backend.

**Pendiente**

- **Los hitos, revisados.** Hay plantilla para 5 de los 89 tipos y es un **borrador
  sin validar**: lo escribió el asistente a partir de los artículos que ya citan §6 y
  §7, no un abogado. Hasta que alguien los revise —y ponga `revisado=si` en el CSV— la
  pantalla los marca en rojo. Faltan los otros 84 tipos.
- **Las fechas `limite` hay que teclearlas.** Las tendría que producir
  `pro.calendario` en cuanto exista el motor de días; hoy se ponen con
  `expedientes fechar`, y aquí no se computa nada, igual que en `sec.agenda`.
- **Los expedientes abiertos antes de que existiera la tabla `hitos` no tienen
  ninguno**, y no se les añaden solos: la pantalla los enseña como un tipo sin
  recorrido escrito.
- **Poner fechas solo se puede por CLI.** La pantalla enseña la barra y deja **marcar un
  nodo como hecho** (y deshacerlo), que es lo que el abogado necesita a diario; poner o
  corregir una fecha, pausar y cancelar siguen siendo de la CLI.
- **Nada cuelga todavía del expediente**: ni documentos, ni correos, ni los eventos de
  `sec.agenda`, que ya tiene la columna `expediente` sin rellenar.
- **Sin partes ni órgano desde la interfaz.** La base los guarda; la pantalla solo pide
  el tipo.

**Implementado a medias — `pro.calendario`: el calendario, no el motor**

Segundo componente con código, también módulo. Está escrita **la fuente de datos**
—el calendario de festivos y el recolector que lo llena desde los boletines— y **no
el cómputo de plazos**, que es el módulo propiamente dicho. Importar el paquete no permite calcular
ninguna fecha todavía.

| pieza | fichero |
|---|---|
| esquema y consultas del calendario | `pro/calendario/db.py` |
| catálogo de ámbitos y de las 29 publicaciones | `pro/calendario/fuentes.py` |
| extractor del BOE (las dos resoluciones estatales) | `pro/calendario/boe.py` |
| extractor local de Madrid (datos abiertos) | `pro/calendario/madrid.py` |
| confianza TLS y raíces del sector público | `pro/calendario/certificados.py` |
| diagnóstico de fuentes que no se dejan leer | `pro/calendario/diagnostico.py` |
| verificación de festivos antes de escribirlos | `pro/calendario/verificacion.py` |
| carga de los festivos anotados a mano | `pro/calendario/semilla.py` |
| datos establecidos, con su cita | `pro/calendario/datos/festivos_locales.json` |
| recolector: recorre boletines y escribe | `pro/calendario/recolector.py` |
| CLI | `pro/calendario/__main__.py` |

Superficie: `recolectar [AÑO...] · semilla · comprobar URL [TEXTO] · estado · festivos ÁMBITO [AÑO] · calendario ÁMBITO [AÑO]`. El procedimiento para personas está en `RECOLECCION.md`. Tablas:
`versiones · ambitos · fuentes · festivos · cobertura`. Sin dependencias nuevas: el
Backend sigue con `sqlcipher3` como única externa, y esto va con `sqlite3`, `urllib`
y `xml.etree` de la estándar.

Decisiones que conviene no perder:

- **Base sin cifrar, y en local igualmente.** Los festivos son dato público del BOE,
  así que `calendario.db` va en SQLite a secas, sin la clave que sí lleva
  `sec_mail.db`. Pero vive en `~/.misyks` y no solo en el servidor: el motor que la
  consume toca expedientes y corre en el PC del abogado, y una base solo remota
  dejaría al despacho sin poder calcular plazos en cuanto se cayera la red.
- **Los festivos se guardan dispersos.** Solo los días que lo son. Una fila por día y
  municipio serían unos seis millones de filas, y sobre todo no sabrían distinguir
  «no es festivo» de «no sé si lo es».
- **`cobertura` responde aparte a «¿tengo el dato?».** Es una tabla por ámbito, año y
  cómputo. Ausencia de fila cuenta como `pendiente`, nunca como `confirmado`: una
  base vacía no sabe nada y tiene que comportarse como tal. Es lo que permitirá al
  motor marcar `provisional` en vez de dar por hábil un día que no ha comprobado.
- **Cuatro estados, y los tres que no son `confirmado` no son intercambiables.**
  `pendiente` (no se ha intentado), `sin_publicar` (se miró, el boletín aún no lo ha
  sacado) y `fallido` (se intentó y reventó, con el motivo en `detalle`). Para el
  motor los tres dan fecha prudente; la distinción es para mantenimiento, y es lo
  que hace que una regresión no se disfrace de trabajo pendiente.
- **Nada se borra: `alta` y `baja` por versión.** Las comunidades rectifican con el
  año empezado. Toda consulta acepta una versión, así que el `version_calendario` que
  el contrato del módulo devuelve basta para repetir un cálculo tal como se hizo.
- **Los ámbitos son un árbol, no una tabla de municipios.** `08019 → ES-CT → ES`, con
  un nivel insular intercalado donde existe (Canarias, Baleares). El motor recorre la
  cadena sin saber cuántos niveles tiene.
- **`computo` es una columna, no una etiqueta.** Judicial y administrativo son dos
  calendarios con dos fuentes. `inhabiles()` exige decir cuál, sin valor por defecto,
  para que no se mezclen por olvido.
- **El calendario administrativo se deriva, no se extrae.** La resolución de días
  inhábiles de la AGE no trae su anexo en el XML del BOE, solo en el PDF; pero su
  apartado segundo remite a los festivos laborales, igual que el art. 30.7 de la Ley
  39/2015. Se deriva de la rejilla laboral, que sí es legible. La primera versión
  intentaba leer fechas de la prosa del documento y devolvía dieciocho días
  inventados sin dar ningún error.
- **TLS verificado siempre, con raíces del sector público añadidas.** Varias
  administraciones emiten con CA propias (IZENPE en Euskadi, ACCV en la Comunitat
  Valenciana) cuyas raíces no trae Python, y la descarga falla con un mensaje que
  parece decir que el servidor está mal. El arreglo **no** es desactivar la
  verificación: quien se interpusiera elegiría qué días son inhábiles, sin error ni
  aviso. Se añaden las raíces concretas en `~/.misyks/ca/*.pem`
  (`pro/calendario/certificados.py`); sin ellas, la fuente falla y queda `pendiente`.
- **El establecimiento se hace a mano, y con prueba documental.** Los festivos locales
  que no tienen extractor se anotan en un JSON versionado, cada entrada con la cita
  literal del boletín, y `verificacion.py` los comprueba antes de escribirlos: día
  presente en la cita, mes coherente, día de la semana correcto, tope de dos locales
  por municipio y sin solape con niveles superiores. Nada entra sin cita. Automatizar
  un trabajo que se hace una vez cuesta más que hacerlo; lo que no puede faltar es que
  sea auditable, y por eso el dato vive en el repo con su URL al lado.
- **Un municipio con una entrada rechazada no se confirma entero.** Lo que se sabe de
  él está incompleto, así que sigue dando fecha provisional.
- **El recolector va aparte del motor.** Corren en sitios y momentos distintos, y
  sobre todo fallan distinto: si un boletín rediseña su web, el motor tiene que
  seguir calculando con lo que haya. Un fallo del recolector nunca se traga: deja la
  cobertura en `pendiente` y sigue con la siguiente fuente.

Lo que falta, y no es poco:

- **El motor de días.** Fines de semana, *dies a quo*, agosto, Navidad, cómputo por
  meses, fecha prudente: nada de eso está escrito. El calendario no sabe de reglas
  procesales a propósito.
- **Los festivos locales, salvo Madrid.** Las 29 publicaciones están registradas como
  fuentes, pero solo hay extractor para el BOE y para datos.madrid.es. Madrid es hoy
  el único ámbito que puede dar fecha **firme** en cómputo judicial; los otros nueve
  municipios constan `pendiente`. Para las nueve comunidades que cubren esos
  municipios, la vía preferente son los **datos abiertos** (Euskadi, Madrid y Galicia
  publican JSON o CSV) antes que rascar el HTML del boletín.
- **Una fuente solo retira lo que ella publica.** `_sincronizar` exige un `alcance`
  explícito. Sin él, el fichero de Madrid --dos fiestas locales-- habría retirado el
  calendario nacional entero al no encontrar esos días en su lista, y en silencio,
  porque retirar un festivo no es un error.
- **De un fichero municipal se toman solo las filas de competencia municipal.** El de
  Madrid trae el calendario completo de la ciudad y su clasificación no es fiable
  fuera de lo suyo: en 2026 etiqueta el 3 de abril como «Jueves Santo» y da por
  nacionales días que el BOE fija como autonómicos. En sus dos fiestas locales es la
  fuente autorizada; en el resto, no.
- **El calendario administrativo autonómico y local.** Sale del acuerdo propio de
  cada comunidad, y para lo local el art. 30.6 obliga además a mirar el municipio del
  interesado, no solo el del órgano.
- **Diez municipios, no 8.131.** El árbol arranca con las diez ciudades más pobladas
  como banco de pruebas; crecerá cuando `pro.destino` resuelva órganos nuevos.

Los otros cinco de `secretario`: `sec.ocr`, `sec.clasificador`, `sec.agenda`,
`sec.notificador`, `sec.entrega`. Después, grupo a grupo, según vaya funcionando cada
uno.

### 8.4 · Infraestructura: `maat` — hallazgo de seguridad pendiente

Auditoría real del firewall de `maat` (iptables/ufw), hecha al evaluar si un futuro
resumen de `sec.mail` por LLM podía generarse ahí en vez de en local (ver discusión de
privacidad más abajo). El resto del firewall está bien planteado -- política DROP por
defecto, Redis/Qdrant/Memgraph solo en `127.0.0.1`, Ollama (11434) escuchando en todas
las interfaces pero solo alcanzable desde la subred Docker interna `10.0.2.0/24` -- pero
hay un fallo concreto:

- **El puerto 3000 (`agents-api`, el backend real) está expuesto a todo internet**, no
  solo alcanzable vía Traefik como parece que se pretendía. Causa: dos reglas de
  iptables para el mismo puerto en orden equivocado -- una `ACCEPT` desde cualquier
  origen (`0.0.0.0/0`) se evalúa *antes* que la `DROP` que debería bloquear el acceso
  público, así que la de bloqueo nunca llega a aplicarse (iptables para en la primera
  regla que coincide).
- **Por qué no es crítico ahora mismo:** las rutas de `agents-api` exigen
  `x-internal-key` + JWT de Clerk (ver `server.ts`), así que llegar al puerto no basta
  para leer nada. El riesgo real es que cualquier fallo del propio servicio (una
  vulnerabilidad de dependencia, un endpoint mal protegido que se añada más adelante)
  queda expuesto directamente a cualquiera en internet, sin pasar por Traefik.
- **Arreglo, una línea, pendiente de ejecutar (requiere acceso root a `maat`):**
  ```
  iptables -D INPUT -p tcp --dport 3000 -j ACCEPT
  ```
  Borra la regla de "permitir desde cualquiera"; la regla `DROP` que ya existe justo
  detrás queda entonces activa de verdad.

**Contexto de la decisión LLM local vs. servidor:** se comparó enviar el contenido de
sec.mail a una API externa (DeepSeek) frente a generarlo con Ollama en `maat`. DeepSeek
almacena datos en China, sin DPA ni residencia UE/US -- se considera transferencia
internacional bajo RGPD, y ya ha sido bloqueado de emergencia en Italia por su autoridad
de protección de datos. `maat` está en Helsinki (Hetzner, UE/EEE): enviarle datos desde
España no es una transferencia internacional a efectos de RGPD. Sigue siendo un riesgo
real (quien tenga o consiga acceso al servidor), pero de una categoría distinta: uno que
se puede auditar y cerrar (como el hallazgo del puerto 3000 de arriba), no uno que
depende de la política de un tercero en otra jurisdicción. Decisión de arquitectura
(local vs. `maat`) pendiente de que el usuario la zanje.

**Decisión tomada: el resumen se genera con Ollama en `maat`, modelo `qwen2.5:7b`.**
`maat` no tiene GPU (solo el chip grafico de gestion remota del servidor) -- Ollama
corre en CPU pura, 12 nucleos, 62GB RAM. Comparado con datos reales antes de decidir:

| modelo | vel. (caliente) | 10 peticiones a la vez (peor caso) | calidad ES |
|---|---|---|---|
| `llama3.2:3b` | ~17 tok/s | 2.1s - 21.8s | pierde matices con >1 tema en el correo |
| `qwen2.5:7b` | ~7.6 tok/s | 4.0s - 36.6s | correcto, registro consistente |
| `llama3.1:8b` | ~7.3 tok/s (igual que qwen) | no probado | **error de sentido**: invirtio el significado de un correo con dos temas, y mezclo tu/usted a media frase |

A igual velocidad, Qwen acierta y Llama no -- por eso se descarta Llama pese a ser de la
misma familia que otros usos ya existentes en el ecosistema antiguo (`gemma3:12b` en
`~/maat/`). Los tres modelos probados sostienen 10 peticiones simultaneas sin fallar
(la cola de Ollama por defecto ya lo resuelve), aceptable porque el resumen se genera
en segundo plano, sin bloquear al usuario mientras sincroniza.

**Keep-warm.** Ollama descarga un modelo de RAM tras ~5 min sin uso; la siguiente
peticion paga el coste de recargarlo de disco (~3.4s en el caso mas ligero probado).
`Backend/scripts/ollama_keep_warm.py` manda una peticion minima (1 token) cada 4
minutos via cron en `maat`, para que ninguna peticion real caiga nunca sobre un modelo
frio. Mismo mecanismo que ya usa el ecosistema antiguo (`~/maat/scripts/`, para
`gemma3:12b`) pero independiente: script y cron propios de este repo, sin depender de
la automatizacion ajena (esa, de hecho, esta rota -- `gemma3:12b` ya no esta descargado
en el servidor, asi que ese cron lleva tiempo fallando en silencio).


### 8.5 · Portabilidad del Frontend a Windows

El `Frontend` se escribio y probo en macOS/Linux, y tenia tres dependencias de
Unix escondidas. La primera no era un fallo en ejecucion: **el binario no
compilaba en Windows**.

- **Aleatorios de la clave de la base.** `generar_clave_hex` leia `/dev/urandom`
  a mano en una funcion marcada `#[cfg(unix)]`, sin variante para el resto, asi
  que en Windows quedaba una llamada sin destino. Ahora usa la crate `getrandom`,
  que hace la llamada nativa de cada plataforma (`getrandom(2)`, `BCryptGenRandom`).
  Se mantiene la intencion del codigo anterior -- no arrastrar una crate de
  criptografia entera solo para 32 bytes -- porque `getrandom` es el envoltorio
  del RNG del SO, no una implementacion criptografica. No anade nada nuevo al
  arbol: la version ya estaba en `Cargo.lock` como dependencia transitiva de `iced`.
- **Resolucion de `~/.misyks`.** `LocalConfig::data_dir` hacia
  `env::var("HOME").expect(...)`. El panico en Windows era lo de menos; el modo de
  fallo grave es el silencioso: **si el Rust y el Python resuelven el home a
  directorios distintos, sec.mail sincroniza contra una base y la app abre otra,
  vacia, sin ningun error a la vista.** Los dos lados tienen que coincidir por
  contrato, asi que `home_dir()` replica el orden de `os.path.expanduser("~")` de
  CPython (`USERPROFILE`, luego `HOMEDRIVE`+`HOMEPATH`; `HOME` fuera de Windows),
  que es lo que hay detras del `Path.home()` de `config.py`. Cuidado con git-bash:
  ahi `HOME` si esta definido, y puede no ser el mismo directorio.
- **Ruta del interprete del venv.** `.venv/bin/python3` es POSIX; los venv de
  Windows ponen el ejecutable en `.venv/Scripts/python.exe`. Con la ruta fija, el
  boton Refrescar no lanzaba nada en Windows. Resuelto en `ruta_interprete()`.

**Permisos del archivo de secretos.** `restringir_permisos` aplicaba `0o600` en
Unix y **nada en Windows**, donde `~/.misyks/config` heredaba la ACL del perfil.
Comprobado en una maquina real: `NT AUTHORITY\SYSTEM`, `BUILTIN\Administrators`
y el propio usuario, los tres con `FullControl`. Ese archivo tiene la contrasena
de aplicacion de Gmail y la clave de `sec_mail.db`, asi que contradecia la premisa
de que los secretos no salen de la maquina del abogado.

Resuelto con `icacls`: `/inheritance:r` borra los ACE heredados y `/grant:r` deja
un unico ACE, el de la cuenta actual (`USERDOMAIN\USERNAME`, o `USERNAME` a secas
si no hay dominio). Se descarto la API Win32 (`SetNamedSecurityInfo`) para no
arrastrar `windows-sys` y varios bloques `unsafe` por un solo ajuste.

Con ello cambio tambien **el orden de escritura de `save()`**, que es la parte que
importa de verdad: antes escribia el archivo y recortaba permisos despues, lo que
deja una ventana con el secreto en disco accesible a quien herede la ACL -- y si
el recorte fallaba, el secreto quedaba escrito mientras la UI decia "no se pudo
guardar", un mensaje falso. Ahora se crea un temporal vacio, se le recortan los
permisos, se escribe y se renombra encima. Verificado que la ACL recortada
sobrevive al rename, que es lo que sostiene el planteamiento. Un fallo en
cualquier paso deja el archivo anterior intacto y el mensaje de error es cierto.

**`backend_dir()` y el empaquetado.** Se construia con `env!("CARGO_MANIFEST_DIR")`,
una ruta de *tiempo de compilacion*: valida con `cargo run` desde el checkout e
inexistente en la maquina de cualquier otro. No era un problema de plataforma --
se rompia igual en macOS -- pero se arreglo en el mismo repaso. Ahora se resuelve
en ejecucion, en tres intentos: la variable `MISYKS_BACKEND`, luego `Backend/`
junto al ejecutable (app empaquetada), y por ultimo la carpeta hermana de
`Frontend/` en el checkout (desarrollo). Cada candidata se valida comprobando que
contiene `sec/mail/__main__.py`, no solo que exista un directorio con ese nombre;
si ninguna vale, el error dice donde ha buscado. En la misma linea,
`ruta_interprete()` cae al Python del PATH cuando no hay venv en el Backend, en vez
de fallar: es lo que hara falta en una app distribuida.

**Ventanas de consola.** Una app de ventana que lanza un ejecutable de consola hace
parpadear una ventana negra en Windows. `sec.mail` (Python) e `icacls` se lanzan
ahora con `CREATE_NO_WINDOW` desde `Frontend/src/proceso.rs`, que en el resto de
plataformas no hace nada.

**El Backend si es instalable en Windows.** Comprobado: `sqlcipher3` 0.6.2 publica
wheel `win_amd64` en PyPI, asi que no hay que compilar SQLCipher a mano. Era el
riesgo gordo del lado Python y no existe.

**Sin verificar — leer antes de dar Windows por soportado.** El mecanismo de
`icacls` y la supervivencia de la ACL al rename estan comprobados ejecutandolos;
el resto, no. **Nada de este codigo se ha compilado, en ninguna plataforma**: en la
maquina del equipo no hay `cargo` instalado. Quedan tres incognitas que el primer
`cargo build` resuelve de golpe:

- que la firma de `getrandom` 0.3 sea `getrandom::fill(&mut buf)`;
- que `rusqlite` con `bundled-sqlcipher-vendored-openssl` compile en MSVC, que
  suele exigir Perl y NASM -- es decir, la premisa del comentario del `Cargo.toml`
  ("que compile igual en cualquier plataforma sin pedir librerias de sistema
  adicionales") puede no sostenerse en Windows;
- que `iced` 0.14 se comporte en Windows, donde nunca se ha ejecutado.

Tampoco se ha vuelto a compilar en macOS tras estos cambios.

### 8.6 · Acceso a correo y calendario: OAuth

Autenticación y transporte de `sec.mail` y `sec.agenda`. Alcance: cuentas de cualquier
dominio.

**Mecanismo.** Correo y calendario se obtienen de las APIs de cada proveedor,
autenticadas con OAuth 2.0 en flujo por navegador. Ambos scopes se solicitan en un
único consentimiento por cuenta. Las contraseñas de aplicación se usan solo en el
tercer mundo de la tabla.

| mundo | correo | calendario | cubre |
|---|---|---|---|
| Google | Gmail API | Calendar API, scope `calendar.events` | `@gmail.com` y todo Workspace |
| Microsoft | Microsoft Graph | Graph, permiso `Calendars.ReadWrite` | `@outlook.com`, `@hotmail.com` y todo Microsoft 365 |
| CalDAV/IMAP | IMAP con contraseña de aplicación | CalDAV con contraseña de aplicación | iCloud, Fastmail, Nextcloud, Zimbra, servidores propios |

Los dos primeros mundos van por OAuth y comparten pantalla de consentimiento. El
tercero usa contraseña de aplicación y **no está implementado**: no hay adaptador de
IMAP ni de CalDAV (§8.3). Que la autenticación básica siga retirada en Google y en
Exchange Online no afecta a este mundo: iCloud, Fastmail y los servidores propios
siguen admitiéndola, y para ellos no hay otra vía.

**Determinación del mundo.** Por los registros MX del dominio: `...google.com`,
`...protection.outlook.com`, u otro. Un dominio propio alojado en Google Workspace o
en Microsoft 365 cae en uno de los dos primeros mundos sin tratamiento adicional; un
dominio de Workspace usa la misma app OAuth que una cuenta `@gmail.com`.

**Registro de la aplicación.** Una única app externa, publicada en producción y
verificada, compartida por todos los clientes. Quedan fuera del alcance la app interna
(opera solo dentro de un Workspace propio) y la cuenta de servicio con delegación de
dominio (exige que el cliente sea un Workspace y que su administrador la instale).

Requisitos de publicación:

- **Google.** Dominio verificado, política de privacidad alojada en él, vídeo de
  demostración del flujo de consentimiento y justificación de cada scope.
- **Microsoft.** *Publisher verification*: cuenta de trabajo de Entra -- no una cuenta
  Microsoft personal -- e ID del Microsoft Cloud Partner Program.

Ambos trámites se miden en semanas y son independientes del desarrollo.

**Scopes.** El mínimo que cubre el contrato del componente. `calendar.events` da
lectura y escritura de eventos; `calendar` completo no se solicita.

**Restricciones del entorno.** Externas al proyecto:

- Las contraseñas de aplicación de Google cubren IMAP, SMTP y POP. No existe
  equivalente para calendario.
- CalDAV de Google no acepta autenticación básica: deprecada en 2014 y retirada el
  **14 de marzo de 2025** con el apagado de las *less secure apps*. Devuelve `401`.
- Exchange Online tiene la autenticación básica de IMAP **eliminada desde el 1 de
  octubre de 2022**.
- Un administrador de Google Workspace puede desactivar las contraseñas de aplicación
  en su dominio.
- Exchange Web Services se bloquea en Exchange Online desde el **1 de octubre de
  2026** (1 de marzo de 2026 en licencias F1, F3 y Kiosk), con apagado completo el 1
  de abril de 2027. Su sustituto es Graph.

**Flujo del cliente.** Una vez por cuenta, sin introducir datos en la aplicación:
Ajustes, «Conectar cuenta», navegador en el dominio del proveedor, elección de cuenta,
pantalla de consentimiento con correo y calendario, Permitir. La pestaña se cierra y
la aplicación almacena el refresh token. La contraseña del cliente no se escribe en
ninguna ventana de la aplicación.

**Condiciones de operación.**

- **El `client_secret` no es confidencial.** En una app de escritorio distribuida está
  en el binario y es extraíble. El flujo para aplicaciones nativas es **PKCE con
  redirect a loopback** (`127.0.0.1`, puerto libre), no el esquema de aplicación web.
- **Los tokens se revocan externamente:** cambio de contraseña, revocación desde la
  cuenta, o bloqueo de la app por un administrador de Workspace o Entra. La aplicación
  distingue token caducado -- renovación sin intervención -- de token revocado, que
  exige nuevo consentimiento y se refleja como estado visible en Ajustes.
- **Consentimiento administrativo.** En tenants corporativos la autorización la
  concede el administrador del dominio, no el usuario final. Es un estado previsto de
  la conexión, no un error.
- **La cuota es por proyecto**, repartida entre todos los clientes del producto, no
  por usuario.

**Modelo de datos.** Los tres mundos divergen en tres puntos, y los fallos derivados
se manifiestan como plazos incorrectos, no como errores:

- **Eventos recurrentes.** Las excepciones dentro de una serie -- una ocurrencia
  movida o cancelada -- se representan de forma distinta en cada proveedor.
- **Zonas horarias.** Un evento es una hora local con una zona asociada, no un
  instante universal.
- **Sincronización incremental.** Cada proveedor usa un mecanismo propio: sync tokens,
  delta queries o ETags.

**Interfaces.** `sec.mail` y `sec.agenda` no conocen el proveedor de origen. Hablan
con `Correo` y `Calendario` -- esta última con `listar_eventos(desde, hasta)`,
`crear_evento`, `actualizar` y `borrar` --, implementadas por un adaptador por mundo.

**Almacenamiento de credenciales.** Las secciones `[oauth.google]` y
`[oauth.microsoft]` de `~/.misyks/config` guardan, cada una, el `client_id` de la
aplicación y los tokens de la cuenta conectada. Como el consentimiento es uno por
cuenta y cubre los dos scopes, el flujo y el archivo viven en `sec/cuentas/`
(`oauth.py`, `ajustes.py`) y no dentro de `sec.mail`: los dos módulos entran por ahí.
Habilitar la API correspondiente en el proyecto del `client_id` es un paso aparte del
scope —Gmail y Calendar se habilitan por separado, y sin ello la llamada responde
`403` aunque el consentimiento sea correcto—. Le aplican el recorte de permisos y el orden de escritura de `save()`
de §8.5.

**Ubicación de los tokens: sin decidir.** Si `sec.agenda` corre en `maat`, los refresh
tokens de todos los clientes residen en el servidor; `sec.mail` corre en local por
tener las credenciales (§8.3). Factores en juego: un componente de vigilancia de
plazos debe operar con el equipo del abogado apagado, y un repositorio único de credenciales
de todos los clientes concentra el impacto de un acceso indebido.
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

**Sobre los componentes.** Los 56 son una propuesta de granularidad, no un contrato
cerrado. El criterio aplicado: un componente por tarea que pueda fallar de forma
independiente y verificarse por separado.
