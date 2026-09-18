# Establecer los festivos de un municipio

Cómo se añade un sitio nuevo al calendario de `pro.calendario`, y por qué el
proceso es como es. Está escrito para una persona del equipo.

El sistema calcula plazos procesales y **el letrado no verifica las fechas que
salen**: recibe el aviso y actúa. Eso quiere decir que nadie va a detectar un
error aquí abajo. Por eso el proceso pide una cosa incómoda —copiar literalmente
el trozo del boletín del que sale cada fecha— y por eso el programa rechaza
entradas que no la traen. No es burocracia: es lo único que separa «lo he leído
bien» de «creo que lo he leído bien».

Si algo no se puede leer, **la respuesta correcta es dejarlo sin hacer**. Un
municipio sin datos da fecha provisional y avisa. Un municipio con una fecha
inventada da una fecha firme y equivocada.

---

## Lo que ya viene solo

No hay que tocar nada de esto a mano:

| Qué | De dónde sale |
|---|---|
| Festivos nacionales | Resolución anual de fiestas laborales (BOE) |
| Festivos de las 19 comunidades | La misma resolución |
| Calendario administrativo estatal y autonómico | Derivado de la anterior |
| Fiestas locales de Madrid | `datos.madrid.es`, datos abiertos |

Se recogen con:

```bash
cd Backend
python -m pro.calendario recolectar
```

Lo que falta son las **fiestas locales del resto de municipios**, que no publica
nadie de forma centralizada.

---

## El proceso, paso a paso

### 1 · Comprobar si la fuente se puede leer

Antes de nada, mira si el boletín es accesible. El segundo argumento es algo que
**tiene que aparecer** si la descarga ha servido de algo:

```bash
python -m pro.calendario comprobar "https://..." "festes locals"
```

Cinco respuestas posibles:

| Estado | Qué significa | Qué hacer |
|---|---|---|
| `ok` | Se lee y contiene lo buscado | Seguir al paso 2 |
| `sin_contenido` | Responde, pero el texto no está en el HTML | Página con JavaScript: hace falta navegador, o buscar otra URL del mismo organismo |
| `ca_ausente` | Certificado de una CA española que Python no trae | Instalar esa raíz (abajo) |
| `handshake` | El servidor negocia con cifrados viejos | Navegador. **No** desactivar la verificación |
| `http` / `red` | La URL ha cambiado, o no hay conexión | Buscar la URL nueva |

El estado `dudoso` sale cuando no le das qué buscar. Significa «no lo sé», no
«está bien».

**Nunca desactives la comprobación de certificados para salir del paso.** Quien
pudiera interponerse en esa conexión decidiría qué días son festivos, y no
daría ningún error: daría un plazo mal calculado con aspecto de correcto.

### 2 · Localizar la publicación oficial

La fuente buena es el **boletín**, no una web de calendarios ni un agregador.
Cada fecha tiene que poder justificarse ante alguien que pregunte «¿por qué?».

Por comunidad:

| Comunidad | Publicación |
|---|---|
| Andalucía | BOJA |
| Aragón | BOA |
| Asturias | BOPA |
| Baleares | BOIB |
| Canarias | BOC |
| Cantabria | BOC |
| Castilla-La Mancha | DOCM |
| **Castilla y León** | **los nueve boletines provinciales** |
| Cataluña | DOGC |
| Extremadura | DOE |
| Galicia | DOG |
| La Rioja | BOR |
| Madrid | BOCM |
| Murcia | BORM |
| Navarra | BON |
| **País Vasco** | **BOTHA, BOB y BOG** (por territorio histórico) |
| C. Valenciana | DOGV |
| Ceuta / Melilla | BOCCE / BOME |

Varias comunidades publican además el calendario como **datos abiertos** (JSON o
CSV), que es preferible al PDF: Euskadi lo da por municipio con código EUSTAT,
y Madrid y Galicia también tienen conjunto abierto. Si existe, úsalo.

### 3 · Anotar cada festivo con su cita

Se edita `Backend/pro/calendario/datos/festivos_locales.json`:

```json
{
  "ambito": "08019",
  "fecha": "2026-09-24",
  "computo": "judicial",
  "nombre": "La Mercè",
  "fuente": "DOGC - Ordre EMT/208/2025, d'11 de desembre",
  "url": "https://dogc.gencat.cat/...",
  "cita": "Barcelona: 25 de maig i dijous 24 de setembre"
}
```

Reglas al rellenarlo:

- **`cita` se copia literal, en el idioma del boletín.** Nada de traducir: la
  traducción ya es interpretación, y la interpretación es lo que estamos
  comprobando. El verificador entiende castellano, catalán, gallego y euskera.
- **Si el documento da el día de la semana, inclúyelo en la cita.** Es la
  comprobación más potente que hay: una fecha mal transcrita casi nunca cae en
  el día de la semana correcto.
- **Si el día está en una celda y el mes en una cabecera aparte**, incluye las
  dos cosas en la cita. Si no, el verificador no puede resolver el mes y
  rechaza la entrada — a propósito.
- **`computo` es `judicial` para las fiestas locales del ayuntamiento.** El art.
  182 LOPJ declara inhábiles las fiestas laborales de la localidad. El cómputo
  *administrativo* de un municipio es otra cosa: son los días que fije el
  calendario de su **comunidad**, y salen de otra publicación.
- **`ambito` es el código INE de cinco dígitos**, con el cero delante si lo
  lleva (`08019`, no `8019`).

### 4 · Cargar y verificar

```bash
python -m pro.calendario semilla
```

Verifica todo antes de escribir nada. Cinco comprobaciones:

1. El día aparece en la cita.
2. El mes que nombra la cita coincide con el de la fecha.
3. El día de la semana cuadra, si la cita lo dice.
4. Como mucho dos fiestas locales por municipio y año (lo fija la ley).
5. Una fiesta local no cae en un festivo autonómico o nacional — si coincide,
   es que se ha leído mal la columna.

Lo rechazado no se escribe, y **un municipio con una entrada rechazada queda
`fallido`**, con el motivo guardado: lo que se sabe de él está incompleto, así
que sigue dando fecha provisional, pero se ve que hay algo que corregir en el
fichero y no que falte por hacer.

En `python -m pro.calendario estado`, la columna **FALLIDO** es la única que
pide que alguien actúe. `sin leer` es trabajo previsto y `sin publicar` es
esperar a que salga el boletín.

La orden devuelve código de salida 1 si hay rechazos, para que se note en un
script.

### 5 · Comprobar el resultado

```bash
python -m pro.calendario festivos 08019 2026
python -m pro.calendario estado
```

El primero lista los días inhábiles del municipio y avisa de lo que falte. El
segundo da el recuento general por nivel.

---

## Instalar una raíz de certificado

Varias administraciones emiten con autoridades del sector público español que
Python no trae. Confirmadas hasta ahora:

| Autoridad | Dónde aparece |
|---|---|
| IZENPE | Gobierno Vasco (`opendata.euskadi.eus`) |
| Firmaprofesional | Ajuntament de Barcelona |

Para añadir una:

1. Descarga la raíz **de la sede de la propia autoridad**, no de un buscador.
2. Comprueba su huella contra la que la autoridad publica.
3. Déjala en `~/.misyks/ca/`, con extensión `.pem`.

Añadir una raíz concreta y comprobada no es lo mismo que aceptar cualquiera:
sigue habiendo verificación, y sigue fallando si alguien se interpone.

---

## Lo que este proceso no hace

**No se actualiza solo.** Cuando salgan los festivos de 2028, o cuando una
comunidad rectifique a mitad de año —en 2026, Andalucía lo hizo en febrero y en
abril—, hay que volver a pasar por aquí.

Eso no es un agujero silencioso. La tabla de cobertura marca esos años como
`pendiente`, el motor da fecha prudente y `sec.notificador` avisa. El sistema
sabe lo que no sabe, que es la propiedad que había que conservar.

El actualizador que vigile esos cambios solo está pendiente de escribir.
