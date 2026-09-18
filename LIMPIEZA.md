# Limpieza de `maat`

> **Propuesta, no parte de trabajo. Nada de esto se ha ejecutado.**
> Inventario del servidor a 18/09/2026 y qué se propone hacer con cada cosa,
> para quedarnos con lo mínimo que sirva a los 54 componentes que faltan.
> Decide el equipo; cuando algo se borre, se anota aquí la fecha.

El servidor lleva encima dos sistemas a la vez: el ecosistema antiguo —que este
proyecto viene a reemplazar— y lo poco que MISYKS-Beta usa todavía. Ocupa 198 GB
de 460 GB, así que **el espacio no es el problema**. El problema es otro: hay
servicios escuchando, cron ejecutándose cada minuto y procesos vivos de cosas que
ya no se van a continuar, y cada uno es algo que puede romperse, gastar o quedar
expuesto sin que nadie lo esté mirando.

**Criterio para decidir:** no «¿esto funciona?», sino **¿a qué componente de los
que faltan le sirve?** Lo que no tenga respuesta a eso sobra, por bien hecho que
esté.

---

## 1 · Lo que se queda, sin discusión

| qué | dónde | para quién |
|---|---|---|
| Ollama + `qwen2.5:7b` | `/usr/share/ollama`, 5 GB | los 53 agentes IA: es el modelo |
| `mxbai-embed-large` | ídem, 669 MB | cualquier búsqueda semántica futura |
| `ollama_keep_warm.py` | cron cada 4 min | ya es de MISYKS-Beta (ARQUITECTURA §8.4) |
| `~/misyks-beta` | 4 GB | el repo nuevo; los 4 GB son `Frontend/target`, no fuente |

## 2 · Lo que hay que mirar antes de decidir: el corpus legal

Es lo único del sistema antiguo con valor real para lo que falta. En Qdrant
(1,3 GB):

| colección | puntos | qué es | a quién serviría |
|---|---|---|---|
| `articles_vectors` | 152.101 | artículos del BOE, con `law_id`, `article` y texto | `inv.normativa` |
| `legal_documents` | 62.670 | documentos del BOE en bruto | `inv.normativa`, `inv.doctrina` |
| `articles_vectors_robertalex` | 3.174 | los mismos, con embeddings de RoBERTalex | `anonimizar` (§1) |
| `jurisprudencia` | 70 | resoluciones | nada: 70 no es un corpus |
| `case_documents` | 0 | vacía | — |
| `case_voice_chunks` | 18 | voz | nada: MISYKS-Beta no tiene componente de voz |

**Y aquí hay una decisión de diseño, no de limpieza.** `inv.normativa` está
diseñado para consultar el BOE **por identificador y con cita literal**, porque
lo que exige el grupo es comprobabilidad: el texto lo devuelve la herramienta y
lo ensambla el código. Un índice vectorial no da eso — da *búsqueda*, que es otra
cosa: sirve para **encontrar qué artículo mirar**, nunca para citarlo.

Con esa condición, `articles_vectors` vale la pena; sin ella, es un atajo que
reintroduce justo el fallo del que huimos.

- **Propuesta:** conservar `articles_vectors` y `articles_vectors_robertalex`;
  tirar `jurisprudencia`, `case_documents` y `case_voice_chunks`.
- **Antes de tirar `legal_documents`:** ver si es más que un volcado del BOE. Si
  lo es, se queda; si no, lo cubre `articles_vectors`.
- **Lo que arrastra:** si se conserva el corpus, se conservan los cron que lo
  alimentan (`boe_sync.py` diario, `cendoj_sync.py` semanal) y `misyks-sync-api`.
  Si se tira, se van con él.

## 3 · Lo que sobra: la voz

Cinco piezas, ~8,5 GB y tres procesos vivos, para algo que **no existe en los 56
componentes**: ni dictado, ni transcripción, ni llamadas.

| qué | dónde | estado |
|---|---|---|
| `livekit-agent` | `/opt/livekit-agent`, 5,8 GB | pm2 `maat-livekit-lfm`, vivo |
| `whisper.cpp` | `/opt/whisper.cpp`, 2 GB | `whisper-server.service`, vivo, puerto 8081 |
| `kokoro-tts` | `/opt/kokoro-tts`, 338 MB | pm2 `maat-tts-svc`, vivo, puerto 8004 |
| `audio-svc` | repo antiguo | pm2, vivo, puerto 8002 |
| contenedor `maat-livekit` | Docker | vivo |

**Propuesta:** parar los servicios primero y dejarlos parados una semana. Si nada
se rompe —no se romperá—, borrar. El orden importa: parar es reversible en un
minuto, borrar no.

## 4 · Lo que sobra: el sistema antiguo en marcha

`~/misyks-repo` (829 MB) y sus servicios en pm2: `agents-api`, `ws-server`,
`ocr-svc`, `mcp-host`, `openrouter-proxy`. Es el sistema que MISYKS-Beta
reemplaza, corriendo.

Dos cosas que conviene mirar antes de apagarlo:

- **`workflow-retry-cron.sh` corre cada 15 minutos** contra ese sistema. Es decir,
  el sistema viejo sigue **ejecutando acciones** —crear plazos, mandar avisos—
  sobre datos de Supabase. Si hay clientes reales detrás, apagarlo no es limpieza,
  es una decisión de producto.
- **El código merece un vistazo antes de irse.** Su motor de workflows
  (`workflow_rules` / `workflow_executions`, con reintento e idempotencia por
  acción) es el precedente que nos servirá cuando marcar un hito tenga que
  disparar algo (DIARIO, 18/09). Eso se lee y se anota; no se copia.

**Propuesta:** no tocar hasta saber si hay clientes vivos. Después: leer lo que
valga, anotar la conclusión en el diario, y borrar el resto. El repo está en
GitHub: lo que se borre del servidor no se pierde.

## 5 · Lo que sobra sin matices

| qué | tamaño | por qué |
|---|---|---|
| `/opt/misyks-etl.bak.20260601_093805` | 300 MB | copia de seguridad de hace tres meses y medio |
| `/opt/misyks` | 15 MB | `agente-misyks.py` y **tres `.bak` distintos** de abril |
| `~/qa_out`, `~/Benchmarks` | 400 KB | salidas de pruebas de abril |
| `MAAT-NextJS` en Coolify | — | desplegado y parado; su código no está en el servidor |
| Imágenes Docker sin usar | **10,5 GB de 11 GB** | `docker system df` dice que el 96% es recuperable |

**Coolify entero** (cinco contenedores: proxy, base, redis, realtime, sentinel)
merece una pregunta aparte: es una plataforma de despliegue completa, con su
Postgres y su Traefik, para un único proyecto que ya no corre. Si no vais a
desplegar desde ahí, es la pieza que más superficie quita de golpe.

## 6 · Lo que hay que mirar sí o sí, aunque no se limpie nada

`ss -tlnp` da **ocho puertos escuchando en `0.0.0.0`**: 11435, 8081, 8010, 8002,
8004, 8000, 3004 y 6001-6002. Es decir, abiertos a internet salvo que el firewall
los tape.

Esto conecta con el hallazgo de seguridad de `ARQUITECTURA.md` §8.4 —el puerto
3000 de `agents-api` expuesto por dos reglas de iptables que no hacían lo que
parecía—, y lo amplía: **no es un puerto, son ocho**, y la mitad son de servicios
de voz que nadie va a volver a usar.

Apagar lo de §3 cierra cuatro de ellos sin tocar el firewall, que es la forma
menos arriesgada de arreglar un problema de seguridad: quitar lo que sobra en vez
de protegerlo mejor.

---

## Orden propuesto

1. **Comprobar si el sistema antiguo tiene clientes vivos.** Todo lo demás
   depende de esa respuesta, y no la tenemos.
2. **Parar la voz** (§3) y esperar una semana. Cierra cuatro puertos.
3. **`docker image prune`** — 10,5 GB, ningún riesgo.
4. **Borrar los `.bak` y las salidas de prueba** (§5).
5. **Decidir el corpus legal** (§2), que es la única decisión con contenido.
6. **Leer el motor de workflows antes de apagar el repo antiguo** (§4).

Lo que **no** se toca en ningún caso: Ollama y sus modelos, `~/misyks-beta`, y
`~/maat/backups` y `~/maat/data` (3,6 GB) hasta saber qué hay dentro.
