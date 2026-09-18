# MISYKS-Beta

Sistema de componentes para un despacho de abogados: recibe documentos, controla
plazos, investiga, redacta y revisa. Backend en Python y **dos** frontends nativos en
Rust con `iced` —el del abogado y el de control—, que comparten el crate `nucleo`. Nueve grupos, 56 componentes diseñados, dos implementados (`sec.mail`, `sec.agenda`).

**Dos clases de componente, y no se mezclan.** Un **agente IA** invoca un modelo de
lenguaje; un **módulo** es código determinista, sin LLM. «Componente» los engloba;
«agente», a secas, significa siempre agente IA. De esa frontera dependen dónde corre
cada uno y qué garantías se le exigen: la salida de un agente hay que comprobarla, la
de un módulo se audita leyéndolo. `sec.mail`, `sec.agenda` y todo `pro.*` son módulos. Cuando se
hable del módulo de Python, dilo como *paquete*.

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

**«Abogado», y «letrado» nunca a secas.** El usuario del sistema es el **abogado**.
«Letrado» se reserva para el **Letrado de la Administración de Justicia** (**LAJ**), que
es otro papel —el antiguo secretario judicial: firma decretos y diligencias de
ordenación y notifica por LexNET— y aparece constantemente en las resoluciones que el
sistema tiene que leer. El de la otra parte es el **abogado contrario**. Sin esta
separación, la palabra «Letrado» de un documento se confunde con el usuario, y eso
acabaría en los prompts de `arc.partes` y `sec.clasificador`.

## Comandos

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
python -m expedientes tipos                      # Los 89 tipos documentales del catálogo
python -m expedientes abrir TIPO [--titulo T]    # Abre un expediente; la referencia la pone él
python -m expedientes listar [--todos]           # Los abiertos, o también los cerrados
python -m expedientes hitos ID                   # Por dónde pasa el caso: la barra, en texto
python -m expedientes hecho ID HITO [--fecha F]  # El abogado lo hizo por su cuenta
python -m expedientes deshacer ID HITO           # Deshace un «hecho» dado sin querer
python -m expedientes pausar ID HITO MOTIVO      # Suspende un plazo
python -m expedientes reanudar ID HITO [FECHA]   # Lo reanuda con la fecha recalculada fuera
python -m expedientes prorrogar ID HITO FECHA    # El órgano amplia el plazo (--resolucion)
python -m expedientes cancelar ID HITO MOTIVO    # Lo cancela; nunca se borra
python -m expedientes acciones ID [N]            # Por qué las fechas son las que son
python -m expedientes fechar ID ORDEN FECHA      # Pone fecha a un hito (--clase, --ocurrido)
python -m expedientes cerrar ID                  # Lo saca de los abiertos sin borrarlo
python -m expedientes eliminar ID --si           # Lo borra de verdad
python -m expedientes vaciar --si                # Los borra todos
```

`expedientes` no es un componente: es el almacén al que se subordinan los demás. El
catálogo de tipos es dato (`expedientes/datos/tipos.csv`), sacado de ARQUITECTURA §5.

```bash
python -m sec.agenda sincronizar                 # Trae el calendario de la cuenta ya conectada
python -m sec.agenda agenda [--desde F --hasta F] # Reuniones, vistas, plazos y obligaciones
python -m sec.agenda colisiones                  # Compromisos que se pisan
python -m sec.agenda apuntar TITULO FECHA        # Un compromiso propio (reunión, obligación)
python -m sec.agenda clasificar ID --tipo TIPO   # Dice si aquel evento era una vista o un café
python -m sec.agenda publicar ID                 # Escribe en el calendario del abogado, a petición
python -m sec.agenda acciones [N]                # Qué se ha hecho sobre cada evento
```

`sec.agenda` usa la cuenta que ya conectó `sec.mail`: el consentimiento trae correo y
calendario juntos. Necesita la **Calendar API habilitada** en el proyecto de Google
Cloud del `client_id` (`INSTALACION.md`).

```bash
python -m pro.calendario recolectar [AÑO...]     # Lee los boletines y llena el calendario
python -m pro.calendario semilla                 # Carga los festivos locales anotados a mano
python -m pro.calendario comprobar URL [TEXTO]   # Por qué no se puede leer una fuente
python -m pro.calendario estado                  # Qué hay, qué falta y qué ha fallado
python -m pro.calendario festivos ÁMBITO [AÑO]   # Días inhábiles de un sitio, por cómputo
python -m pro.calendario calendario ÁMBITO [AÑO] # El año en rejilla, para mirarlo a ojo
```

Frontend: **dos aplicaciones** en un workspace de Cargo, desde la raíz del repo.

```bash
cargo run -p misyks-beta-frontend      # La del abogado: expedientes, correo, cuenta
cargo run -p misyks-beta-admin         # La de control: cobertura del calendario
cargo check --workspace                # Comprueba las dos y lo compartido
cargo clippy --workspace
```

Lo común —acceso a bases, invocación del Backend, configuración local, estilos— vive en
el crate **`nucleo`** y no se copia: dos copias de `local_config.rs` acabarían escribiendo
con reglas distintas el archivo que guarda el refresh token y las claves de las bases.

No hay suite de tests ni linter configurados todavía; no inventes órdenes de test.

## Arquitectura

Detallada en ARQUITECTURA.md.

## Componentes

COMPONENTES.md los lista: solo incluye si es agente IA o módulo, dónde corre, para qué
sirve cada uno y sus restricciones. Esas restricciones son invariantes, no estilo: al
romperlas, el código sigue compilando y aparentemente funcionando.

## Limpieza del servidor

LIMPIEZA.md propone qué quitar de `maat` y qué conservar, con el inventario en el que
se apoya. Es **propuesta, no parte de trabajo**: nada de lo que hay ahí se ha ejecutado.
El criterio no es si algo funciona, sino a qué componente de los que faltan le sirve.

## Historial

Existe una especie de diario que simplifica las acciones por días: DIARIO.md; sigue una estructura fija de: día, resumen, cambios.

## Manual e instalación

Dos documentos escritos para las personas del equipo, no para ti, y pensados para
macOS, que es donde trabaja el equipo:

- `INSTALACION.md` — dependencias y primera puesta en marcha (Homebrew, Python,
  Rust, Claude Code, clonar el repo, crear el venv del Backend). Es donde está el
  `python3 -m venv .venv` que las órdenes de arriba dan por hecho.
- `MANUAL.md` — el día a día: ubicarse en el repo, arrancar y qué leer primero.
