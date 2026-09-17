# MISYKS-Beta

Sistema de agentes para un despacho de abogados: recibe documentos, controla plazos,
investiga, redacta y revisa. Backend en Python, frontend nativo en Rust con `iced`.
Nueve grupos de agentes, 56 sub-agentes diseñados, uno implementado (`sec.mail`).

## Normas de trabajo

- **Nada de branches.** Se trabaja directo sobre `main`.
- **La documentación se actualiza en el mismo cambio que la motiva, no después.**
  Un documento desactualizado es peor que no tenerlo.
- **Detalle, no titulares.** Se explica el porqué y las consecuencias, no solo el qué.
- **El ecosistema antiguo es referencia, no autoridad.** `misyks-repo`, `~/maat/` en
  el servidor y todo lo del "MAAT" que este proyecto reemplaza sirven para ver cómo
  se resolvió algo antes, pero no se copia ni se aplica sin consultarlo con el equipo.

## Idioma

El proyecto se desarrolla en un contexto de España, pero los tecnicismos pueden tratarse en inglés por conveniencia.

## Órdenes

Backend (desde `Backend/`, con el venv en `Backend/.venv`). El venv no está en el
repo y puede no existir todavía en la máquina; compruébalo antes de dar por hecho
que estas órdenes arrancan (crearlo: `INSTALACION.md`):

```bash
python -m sec.mail conectar google              # Autoriza una cuenta por OAuth (navegador)
python -m sec.mail estado                       # conectado / revocado / sin conectar
python -m sec.mail desconectar [PROVEEDOR]      # Revoca el acceso y borra los tokens
python -m sec.mail carpetas                     # Lista carpetas del buzón
python -m sec.mail sincronizar [CARPETA] -n 5   # Descarga una tanda de correos nuevos
python -m sec.mail listar [N]                   # Últimos N correos ya guardados
python -m sec.mail leido ID
python -m sec.mail mover ID CARPETA
```

`conectar` necesita un `client_id` en `~/.misyks/config` (`INSTALACION.md`).

```bash
python -m pro.calendario recolectar [AÑO...]     # Lee los boletines y llena el calendario
python -m pro.calendario semilla                 # Carga los festivos locales anotados a mano
python -m pro.calendario comprobar URL [TEXTO]   # Por qué no se puede leer una fuente
python -m pro.calendario estado                  # Qué hay, qué falta y qué ha fallado
python -m pro.calendario festivos ÁMBITO [AÑO]   # Días inhábiles de un sitio, por cómputo
python -m pro.calendario calendario ÁMBITO [AÑO] # El año en rejilla, para mirarlo a ojo
```

`recolectar` sin años usa la ventana deslizante (el año en curso y el siguiente) y
necesita red: descarga del BOE. No pide credenciales, solo lee dato público. Ojo:
`pro.calendario` **todavía no calcula plazos**, solo mantiene el calendario del que
se alimentará el motor. El proceso para añadir un municipio nuevo está en
`RECOLECCION.md`, escrito para personas del equipo.

En `estado`, la columna **FALLIDO** es la única que pide actuar: significa que se
intentó leer una fuente y reventó. `sin leer` es que aún no hay extractor para
ella, y `sin publicar`, que el boletín no ha sacado ese año todavía. Los tres dan
fecha prudente por igual; la distinción es para mantenimiento, no para el motor.

**Dónde viven los datos.** Las dos bases están en `~/.misyks/`, fuera del repo:
`sec_mail.db` (SQLCipher, con clave en `~/.misyks/config`) y `calendario.db`
(SQLite a secas, sin clave, porque los festivos son dato público). `recolectar`
tarda un par de minutos y va escribiendo; para mirar la base **mientras corre**,
hay que abrirla en solo lectura o se choca con el escritor:

```bash
python -c "import sqlite3,pathlib;p=pathlib.Path.home()/'.misyks/calendario.db';c=sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True);print(c.execute('SELECT count(*) FROM festivos').fetchone()[0],'festivos')"
```

En la consola de Windows, `python -X utf8 -m ...` evita que las tildes salgan
como interrogantes; no cambia lo que se guarda, solo lo que se ve.

Frontend (desde `Frontend/`): `cargo run`, `cargo build`, `cargo clippy`.

No hay suite de tests ni linter configurados todavía; no inventes órdenes de test.

## Arquitectura

Detallada en ARQUITECTURA.md.

## Agentes

AGENTES.md lista los agentes: solo incluye información de para qué sirve cada uno y
sus restricciones. Esas restricciones son invariantes, no estilo: al romperlas, el
código sigue compilando y aparentemente funcionando.

Los agentes de IA (los que invocan un LLM) corren todos en el servidor `maat`. Los
agentes de software corren donde están sus datos y credenciales: `sec.mail`, en el
PC del letrado.

## Historial

Existe una especie de diario que simplifica las acciones por días: DIARIO.md; sigue una estructura fija de: día, resumen, cambios.

## Manual e instalación

Dos documentos escritos para las personas del equipo, no para ti, y pensados para
macOS, que es donde trabaja el equipo:

- `INSTALACION.md` — dependencias y primera puesta en marcha (Homebrew, Python,
  Rust, Claude Code, clonar el repo, crear el venv del Backend). Es donde está el
  `python3 -m venv .venv` que las órdenes de arriba dan por hecho.
- `MANUAL.md` — el día a día: ubicarse en el repo, arrancar y qué leer primero.
