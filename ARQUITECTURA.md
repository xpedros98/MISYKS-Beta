# Arquitectura de agentes y tipos documentales

> Modelo de organización del enrutado de MISYKS.
> Última actualización: 2026-09-15

**Naturaleza del documento.** Diseño completo del sistema de agentes. No se
distingue entre lo implementado y lo pendiente salvo en §8.3, que recoge el estado
real del código.

**Normas de trabajo.**

- **Nada de branches.** Se trabaja siempre directo sobre `main`. Sin ramas de
  feature, sin PRs pendientes de fusionar: cada commit que llega a `main` ya
  se considera el estado real del proyecto.
- **Este documento se actualiza en el mismo cambio que lo motiva, no después.**
  Cualquier commit que altere una decisión de arquitectura, el estado de un
  sub-agente (§8.3) o el contrato de un grupo debe traer también el ajuste
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

Qué grupos hay, qué decide cada uno y cómo se componen. Los sub-agentes de cada
grupo —56 en total, con sus reglas y contratos— están en **`AGENTES.md`**.

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

**Contrato entrada:** `{cuenta}` → `{documento, resumen, clase, etiquetas[]}`
**Contrato salida:** `{documento, destinatario, motivo}` → `{enviado, retorno_esperado?}`

### ARCHIVADOR · estructura
Convierte un documento en una posición dentro del despacho.

**Contrato:** documento → `{expediente_id, metadatos, ruta, requiere_revision, candidatos[]}`

### PROCESAL · tiempo y forma
**Valida al entrar, verifica antes de salir y posee los canales procesales.** Decide si hay tiempo, si faltan requisitos y a qué destino corresponde;
el envío lo ejecuta el secretario. Determinista de punta a punta.

**Contrato puerta:** `{tipoActo, fechaActo}` → `{fecha_limite, franja, bloqueo, requisitos_pendientes}`
**Contrato verificación:** `{documento, expediente}` → `{en_plazo, defectos_formales[], destino}`

### INVESTIGADOR · derecho

**Contrato:** `{consulta, tipo_documento}` → `{artículos[], resoluciones[]}` con cita comprobable

### PROBATORIO · prueba

**Contrato:** `{material, tipo_proceso}` → `{estrategia, señalar_al_letrado}`

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

Movido a **`AGENTES.md`**: qué hace cada sub-agente, su contrato, las reglas de
dominio que respeta, cómo falla y de qué depende. Aquí solo queda la arquitectura
—cómo se componen los grupos, no el interior de cada uno.

La numeración de secciones se conserva a propósito: hay referencias a `§8.3` y
`§8.5` en comentarios del código y en otros documentos.

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
**Destinos:** lexnet 59 · admin 12 · cliente 8 · notarial 6 · burofax 2 · smac 1 · policial 1

Tres lecturas:

- `secretario`, `archivador`, `procesal`, `redactor` y `critico` entran en los 89.
  Los otros cuatro son enrutables.
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

Una por patrón, nombrando sub-agentes. Cubren los arquetipos A–G: cada tipo de esos
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

Primer sub-agente implementado. Gmail sobre IMAP con almacenamiento local cifrado.
Corre en el ordenador del letrado; solo lo ya anonimizado sube a los agentes del
servidor.

| pieza | fichero |
|---|---|
| interfaz al resto del sistema | `sec/mail/agent.py` |
| cliente IMAP | `sec/mail/imap.py` |
| parser de `.eml` | `sec/mail/parser.py` |
| base SQLCipher | `sec/mail/db.py` |
| credenciales y clave de la base | `sec/mail/config.py` |
| CLI | `sec/mail/__main__.py` |

Superficie: `carpetas · sincronizar [--limite N] · listar · marcar_leido · mover`.
Tablas: `correos · adjuntos · sincronizacion · acciones`.

Frontend (`iced`): botón **Refrescar** en la pantalla Secretario invoca
`sincronizar --limite 5` como subproceso y recarga la lista; se dispara también
solo al guardar credenciales válidas en Ajustes. El límite de la tanda de
descarga (5) y el límite de la lista mostrada (sin límite: se ve todo lo ya
guardado) son valores independientes -- confundirlos fue un bug real de esta
sesión, ya corregido.

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
- **Sincronización en tandas.** `--limite N` corta la llamada a los N UIDs pendientes
  más antiguos en vez de traer todo el histórico de golpe; como el puntero avanza
  correo a correo, la siguiente tanda sigue justo donde la anterior se quedó, sin
  duplicar nada (`guardar_correo` ya ignora un `gmail_msgid` repetido).
- **Secretos en local, sin llavero del sistema.** Usuario y contraseña de aplicación
  de Gmail (sección `[gmail]`) y clave de la base (sección `[secmail]`) viven en
  `~/.misyks/config`, junto a la base `~/.misyks/sec_mail.db`. Fuera del repo, para que
  sigan funcionando cuando la app se distribuya como binario. Los gestiona la pantalla
  de Ajustes de la app; `sec.mail` solo los lee.
- **Registro de acciones** en tabla propia: todo lo que el agente hace sobre un correo
  queda anotado.

**Pendiente**

En `sec.mail`, respecto a lo descrito en `AGENTES.md`:

- el **resumen** que consume `sec.clasificador` y el parámetro **ventana** del contrato;
- **descender por los reenvíos**: hoy un correo reenviado como adjunto se guarda entero
  como `.eml`, sin extraer sus adjuntos como documentos propios;
- la **fecha de recepción**: se guarda la cabecera `Date` (la que declara el remitente)
  y la hora de guardado, no la fecha de llegada al buzón (`INTERNALDATE`).

Los otros cinco de `secretario`: `sec.ocr`, `sec.clasificador`, `sec.agenda`,
`sec.notificador`, `sec.entrega`. Después, grupo a grupo, según vaya funcionando cada
uno.

**Decidido por el código**

La duda entre IMAP y API de Gmail queda resuelta: **IMAP**, a cambio de gestionar las
credenciales, que es lo que resuelve `~/.misyks/config`. El protocolo es estándar, pero
la implementación actual usa extensiones de Gmail (`X-GM-MSGID`, `X-GM-LABELS`) y
`imap.gmail.com`: llevarla a otro proveedor exige sustituir esa identidad estable (por
`Message-ID` o UID) y la lectura de etiquetas.

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
de que los secretos no salen de la maquina del letrado.

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

**Sobre los sub-agentes.** Los 56 son una propuesta de granularidad, no un contrato
cerrado. El criterio aplicado: un sub-agente por tarea que pueda fallar de forma
independiente y verificarse por separado.
