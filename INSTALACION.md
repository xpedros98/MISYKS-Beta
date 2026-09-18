# Instalación

Primera puesta en marcha del repo en un Mac. Solo hace falta hacerlo una vez; el día
a día está en `MANUAL.md`.

---

## 1 · Dependencias

| | para qué | cómo |
|---|---|---|
| **Homebrew** | instalar lo demás | ver abajo |
| **Git** | traer y subir el código | `brew install git` |
| **Python 3** | el Backend (agentes y módulos) | `brew install python` |
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

La única dependencia sigue siendo `sqlcipher3` -- OAuth y las dos APIs de correo
van con la librería estándar, sin añadir nada --, y hay paquete precompilado tanto para Apple
Silicon como para Intel, así que no hace falta instalar SQLCipher aparte.

Para comprobar que responde:

```bash
cd Backend
.venv/bin/python -m sec.mail carpetas
```

Sin ninguna cuenta conectada dará un error diciendo que no la hay, y eso es lo
esperado en este punto.

### Registrar la aplicación ante Google

El acceso al correo es por OAuth: no hay contraseña que escribir en ningún sitio
(ARQUITECTURA.md 8.6). A cambio, la aplicación tiene que estar registrada ante
Google, y mientras no exista una app publicada y verificada del despacho, cada
máquina usa la suya. Se hace una vez y son diez minutos:

1. En `console.cloud.google.com`, crear un proyecto (por ejemplo `misyks`).
2. **APIs y servicios → Biblioteca**: habilitar **Gmail API** y **Google Calendar
   API**.
3. **Pantalla de consentimiento de OAuth**: tipo **Externo**, con nombre y correos
   de contacto. Se deja en estado **Testing**.
4. **Usuarios de prueba**: añadir las direcciones que vayáis a conectar. En estado
   *Testing* solo esas pueden autorizar, hasta un máximo de 100.
5. **Credenciales → Crear credenciales → ID de cliente de OAuth → Aplicación de
   escritorio**. Copiar el `client_id` y el `client_secret`.
6. Escribirlos en `~/.misyks/config`:

   ```ini
   [oauth.google]
   client_id = ....apps.googleusercontent.com
   client_secret = ...
   ```

   Ese `client_secret` no es un secreto real: en una aplicación de escritorio va
   dentro del binario y cualquiera puede extraerlo. Lo que protege el intercambio
   es PKCE, no él. El que **sí** hay que cuidar es el token que aparece en esa
   misma sección después de conectar: ese da acceso al correo.

Ya se puede conectar la cuenta:

```bash
.venv/bin/python -m sec.mail conectar google
```

Se abre el navegador, se elige la cuenta y se acepta. Como la app está en estado
*Testing* aparecerá un aviso de «Google no ha verificado esta aplicación»: se
continúa con **Configuración avanzada → Ir a (nombre del proyecto)**. La misma
operación se puede hacer desde la pantalla de Ajustes de la app.

**Dos avisos del estado *Testing*.** El permiso caduca a los siete días y hay que
volver a conectar: no es un fallo, es cómo trata Google a las apps sin publicar.
Y `python -m sec.mail estado` dirá entonces `revocado`, que es el estado previsto
para eso.

**La agenda no se conecta aparte.** Ese mismo consentimiento trae el calendario, así
que `sec.agenda` ya puede trabajar en cuanto `estado` diga `conectado`:

```bash
.venv/bin/python -m sec.agenda sincronizar
.venv/bin/python -m sec.agenda agenda
```

Si responde `403 ... Google Calendar API has not been used in project ...`, es el
paso 2 a medias: está habilitada la Gmail API y no la de Calendar. Se habilita en
**APIs y servicios → Biblioteca** del mismo proyecto y tarda un par de minutos en
propagarse. El consentimiento ya concedido sigue valiendo: no hay que reconectar.

Microsoft todavía no tiene registro hecho: el adaptador de Graph está escrito pero
sin probar contra una cuenta real.

## 4 · Preparar el Frontend

```bash
cd Frontend
cargo build
```

El primer build tarda: compila OpenSSL y SQLCipher desde fuente (van incrustados a
propósito, para no depender de librerías del sistema). Los siguientes son rápidos.

### Si compiláis en Windows

En Mac no hace falta nada más. En Windows sí: ese OpenSSL que se compila desde fuente
se configura con un script de Perl, y Windows no trae Perl. Sin él, `cargo build`
muere con `Command 'perl' not found. Is perl installed?` antes siquiera de empezar a
compilar código Rust.

```powershell
winget install --id StrawberryPerl.StrawberryPerl -e
```

Tiene que ser **Strawberry Perl**. El Perl que viene dentro de Git para Windows
(`C:\Program Files\Git\usr\bin\perl.exe`) no sirve aunque lo pongáis en el `PATH`: es
una versión de Cygwin recortada a la que le faltan módulos del núcleo
(`Locale::Maketext::Simple`), y el `Configure` de OpenSSL se cae igual.

Cerrad y volved a abrir el terminal después de instalarlo, para que Perl entre en el
`PATH`. NASM no hace falta: el build pide OpenSSL sin ensamblador.

Perl es una dependencia **solo de compilación**. No entra en el binario ni hace falta
en el ordenador de quien acabe usando la app: OpenSSL y SQLCipher quedan enlazados
estáticamente dentro del `.exe`.

Durante el enlazado veréis una avalancha de avisos `LNK4099: PDB 'ossl_static.pdb' was
not found`. Son ruido del OpenSSL incrustado, que no trae símbolos de depuración. La
compilación termina bien.

> **Aviso.** El Frontend está en desarrollo. Compila en Windows (probado el 16 de
> septiembre de 2026, algo menos de 8 minutos el primer build), pero en macOS todavía
> no lo ha levantado nadie del proyecto, así que este paso puede fallar. Si os da
> error, no os peleéis con él: pasadlo al grupo con el mensaje completo. El contexto
> está en `ARQUITECTURA.md` §8.5.

## 5 · Y ya

Volved a la raíz del repo y arrancad:

```bash
claude
```

A partir de aquí, `MANUAL.md`.
