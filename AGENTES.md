# Agentes

> Para qué sirve cada sub-agente y qué no puede hacer. Nueve grupos, 56 sub-agentes.
> Diseño completo y contratos en `ARQUITECTURA.md` §1 y §2. Última actualización: 2026-09-16

---

## SECRETARIO · despacho — 6

Canal con el mundo del despacho: correo, agenda, avisos. **No sabe derecho y no debe
aprender**: detecta y reparte, no decide. Es el grupo con credenciales de correo, y por
eso no toma decisiones jurídicas — separar canal de criterio permite auditar ambos.
No toca ningún canal procesal.

| sub-agente | uso | restricción |
|---|---|---|
| `sec.mail` | recibe Gmail por IMAP. **Implementado** | lee, no vacía; idempotente por `X-GM-MSGID` y `UIDVALIDITY`+UID; extrae adjuntos antes de resumir, nunca después |
| `sec.ocr` | documentos **fotografiados**, no escaneados | confianza por bloque, nunca global; umbral más duro en cifras y fechas; marca lo ilegible, no lo infiere |
| `sec.clasificador` | clase y etiquetas desde el resumen | ante la duda devuelve candidatos, no una clase; puede escalar a leer el original |
| `sec.agenda` | reuniones, juicios y plazos | **no calcula plazos: los recibe** de `procesal` |
| `sec.notificador` | avisos y log | todo lo que notifica queda registrado; la insistencia escala con la franja |
| `sec.entrega` | emisor: firma y envío a compañeros | archiva la versión **firmada**, no la enviada; destinatario explícito, nunca autocompletado |

`sec.mail` y `sec.entrega` son el mismo canal en direcciones opuestas, separados porque
fallan distinto: recibir mal cuesta una reclasificación, enviar mal puede mandar el
documento de un cliente a otro.

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

Valida al entrar, verifica antes de salir y **posee los canales procesales**.
Determinista de punta a punta. El envío lo ejecuta `secretario`.

*Puerta — justo después de la entrada*

| sub-agente | uso |
|---|---|
| `pro.calendario` | días hábiles, festivos locales, agosto |
| `pro.caducidad` | plazos perentorios por tipo de acto |
| `pro.prescripcion` | plazos sustantivos; en algunos tipos, por partida |
| `pro.procedibilidad` | requisitos previos: conciliación, vía administrativa, requerimiento |

*Verificación — justo antes de la salida*

| sub-agente | uso |
|---|---|
| `pro.plazo-vivo` | ¿sigue en plazo ahora? el pipeline ha consumido días |
| `pro.forma` | requisitos formales para ese órgano y destino |
| `pro.destino` | por qué canal debe salir |

*Salida — canales procesales* (asignados aquí a la espera de confirmación, §2.1)

| sub-agente | uso |
|---|---|
| `pro.lexnet` | canal judicial, bidireccional |
| `pro.registro` | registro administrativo |
| `pro.burofax` | requerimiento fehaciente |
| `pro.notaria` | elevación a público |
| `pro.acuse` | el cierre del plazo |

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

---

## Middleware transversal

`anonimizar` no es un grupo: es un filtro que atraviesa a todos. Seudonimiza antes de
que nada salga hacia un modelo externo y reinserta los datos reales en local al
redactar. **Obligatorio en penal, familia y todo lo que toque salud.**
