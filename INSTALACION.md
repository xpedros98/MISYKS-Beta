# Instalación

Primera puesta en marcha del repo en un Mac. Solo hace falta hacerlo una vez; el día
a día está en `MANUAL.md`.

---

## 1 · Dependencias

| | para qué | cómo |
|---|---|---|
| **Homebrew** | instalar lo demás | ver abajo |
| **Git** | traer y subir el código | `brew install git` |
| **Python 3** | el Backend (los agentes) | `brew install python` |
| **Rust** | el Frontend (la app de escritorio) | `rustup`, ver abajo |
| **Node** | de él viene `npm` | `brew install node` |
| **Claude Code** | el asistente con el que trabajamos | `npm install -g @anthropic-ai/claude-code` |

**Homebrew**, si no lo tenéis:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Rust** se instala con `rustup`, no con Homebrew — es la vía oficial y la que permite
actualizar la toolchain:

```bash
curl --proto '=https' --tlsv1.2 https://sh.rustup.rs -sSf | sh
```

Cerrad y volved a abrir el terminal al acabar, para que `cargo` entre en el `PATH`.

Comprobad que está todo:

```bash
git --version
python3 --version
cargo --version
claude --version
```

## 2 · Traer el repo

```bash
git clone git@github.com:xpedros98/MISYKS-Beta.git
cd MISYKS-Beta
```

Esa URL es por **SSH**, así que necesitáis una clave SSH creada y subida a vuestra
cuenta de GitHub. Si os da error de permisos, es eso. La alternativa es HTTPS, que
para *traerse* el repo no pide nada porque es público:

```bash
git clone https://github.com/xpedros98/MISYKS-Beta.git
```

La diferencia aparece al **subir**: por SSH la clave ya os identifica; por HTTPS
GitHub os pedirá usuario y un token personal.

## 3 · Preparar el Backend

El entorno virtual (`.venv`) no viaja en el repo: cada uno crea el suyo.

```bash
cd Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ..
```

La única dependencia es `sqlcipher3`, y hay paquete precompilado tanto para Apple
Silicon como para Intel, así que no hace falta instalar SQLCipher aparte.

Para comprobar que responde:

```bash
cd Backend
.venv/bin/python -m sec.mail carpetas
```

Sin credenciales de Gmail configuradas dará un error diciendo que faltan, y eso es
lo esperado en este punto: las credenciales se escriben desde la pantalla de Ajustes
de la app, no a mano.

## 4 · Preparar el Frontend

```bash
cd Frontend
cargo build
```

El primer build tarda: compila OpenSSL y SQLCipher desde fuente (van incrustados a
propósito, para no depender de librerías del sistema). Los siguientes son rápidos.

> **Aviso.** El Frontend está en desarrollo y todavía no se ha compilado en ningún
> equipo del proyecto, así que este paso puede fallar. Si os da error, no os peleéis
> con él: pasadlo al grupo con el mensaje completo. El contexto está en
> `ARQUITECTURA.md` §8.5.

## 5 · Y ya

Volved a la raíz del repo y arrancad:

```bash
claude
```

A partir de aquí, `MANUAL.md`.
