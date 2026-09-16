# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Normas de trabajo (de `ARQUITECTURA.md`)

- **Nada de branches.** Se trabaja directo sobre `main`, sin PRs.
- **El ecosistema antiguo es referencia, no autoridad.** `misyks-repo`, `~/maat/` en
  el servidor y todo lo del "MAAT" que este proyecto reemplaza sirven para ver cómo
  se resolvió algo antes, pero no se copia ni se aplica sin consultarlo con el equipo.

## Idioma

El proyecto nace en España, pero los tecnismos pueden tratarse en ingles por conveniencia.

## Órdenes

Backend (desde `Backend/`, con el venv creado en `Backend/.venv`):

```bash
python -m sec.mail carpetas                     # Lista carpetas de Gmail
python -m sec.mail sincronizar [CARPETA] -n 5   # Descarga una tanda de correos nuevos
python -m sec.mail listar [N]                   # Últimos N correos ya guardados
python -m sec.mail leido ID
python -m sec.mail mover ID CARPETA
```

Frontend (desde `Frontend/`): `cargo run`, `cargo build`, `cargo clippy`.

No hay suite de tests ni linter configurados todavía; no inventes órdenes de test.

## Arquitectura

Detallada en ARQUITECTURA.md, consultar en profundidad bajo demanda.

## Agentes

AGENTES.md lista los 56 sub-agentes de los nueve grupos: para que sirve cada uno y
que no puede hacer. Solo `sec.mail` existe en codigo; el resto es diseno.

Es un indice, no una explicacion — cada entrada remite a `ARQUITECTURA.md` §1 y §2,
donde estan los contratos completos. **No copies ahi el porque**: duplicarlo
garantiza que una de las dos copias envejezca, y un documento desactualizado es
peor que no tenerlo.

Las restricciones que lista no son estilo: al romperlas, el codigo sigue
compilando y aparentemente funcionando. Repasa las del sub-agente que vayas a
tocar antes de tocarlo.
