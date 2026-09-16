## Normas de trabajo

- **Nada de branches.** Se trabaja directo sobre `main`.
- **La documentación se actualiza en el mismo cambio que la motiva, no después.**
  Un documento desactualizado es peor que no tenerlo.
- **Detalle, no titulares.** Se explica el porqué y las consecuencias, no solo el qué.
- **El ecosistema antiguo es referencia, no autoridad.** `misyks-repo`, `~/maat/` en
  el servidor y todo lo del "MAAT" que este proyecto reemplaza sirven para ver cómo
  se resolvió algo antes, pero no se copia ni se aplica sin consultarlo con el equipo.

## Idioma

El proyecto se desarrolla en un contexto de España: código, comentarios, commits y
documentación en castellano, identificadores incluidos (`sincronizar`,
`guardar_correo`). Los tecnicismos pueden tratarse en inglés por conveniencia.

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

AGENTES.md lista los agentes: solo incluye información de para qué sirve cada uno y
sus restricciones. Esas restricciones son invariantes, no estilo: al romperlas, el
código sigue compilando y aparentemente funcionando.
