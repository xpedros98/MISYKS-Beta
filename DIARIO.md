# DIARIO

## 15/09/2026
*Resumen*: Hoy hemos creado el repo de MISYKS versión Beta, para migrar el código del primer prototipo. La intención es construirlo de nuevo, con más control sobre cada pieza.
*Cambios*: Usaremos un único repositorio, organizado en carpetas de Frontend y Backend. Prescindimos de Google Auth por ahora: intentaremos gestionar la autenticación nosotros, a bajo nivel, para poder incluir diferentes proveedores de correo. Empezamos pensando en correr el secretario en local (en el PC del abogado), pero eso ocuparía mucho espacio en su equipo y le consumiría recursos, así que de momento vamos a ejecutar todos los agentes en el servidor.

## 16/09/2026
*Resumen*: Hemos acotado el proyecto con los `.md` básicos (arquitectura, agentes y este diario) y sustituido IMAP por OAuth en `sec.mail`.
*Cambios*: Los agentes de IA corren en el servidor, donde está el modelo; `sec.mail` no es de IA sino de software y sigue en local, porque es quien tiene las credenciales del correo.
*Cambios (anonimizar)*: Dos capas. Lo que identifica con forma fija (DNI, IBAN, matrícula, nº de procedimiento) se detecta con reglas, sin modelo y sin fallos silenciosos; nombres y empresas sí necesitan modelo (candidato RoBERTalex, que habría que entrenar, así que arrancamos con uno general). Condición: mientras no podamos medir lo que se escapa, no sale nada del servidor.
*Cambios (OAuth)*: Se abandona IMAP para correo para usar OAuth para el calendario tambien.
*Cambios (OAuth implementado)*: Hecho el correo antes que el calendario, al revés de lo planeado: `sec.agenda` no existe todavía y escribir su adaptador antes del andamiaje de OAuth era empezar por el tejado. Las bases ya descargadas se convierten solas y ningún correo se vuelve a bajar: el identificador de la API y el de IMAP resultaron ser el mismo número en hexadecimal y en decimal.

## 17/09/2026
*Resumen*: Empezado `pro.calendario`. De momento no calcula plazos: lo escrito es el calendario de festivos y su recolector, que era la pieza que no podía improvisarse después.
*Cambios (sin cifrar, a propósito)*: Los festivos están publicados; cifrarlos añade una dependencia y un secreto que custodiar a cambio de nada. Vive en local igualmente porque el motor que la usa toca expedientes, y una base solo-en-servidor dejaría al despacho sin calcular plazos en cuanto se cayera la red.
*Cambios (son dos calendarios)*: El judicial y el administrativo no son el mismo con otro nombre: el judicial sale de las fiestas laborales (la LOPJ no tiene lista propia y remite a ellas) y el administrativo de otra resolución posterior. Coinciden a nivel estatal y autonómico, pero no tienen por qué a nivel municipal. Cada festivo se guarda sabiendo a qué cómputo sirve, y pedir días inhábiles sin decir cuál da error en vez de elegir por su cuenta.
*Cambios (quién lee los boletines)*: Descartado el agente de IA con navegador. Son dos trabajos distintos: **establecer** los festivos actuales es de una sola vez y automatizarlo cuesta más que hacerlo; **actualizarlos** cada año es lo que necesita correr solo, y queda para el actualizador. Descartado también llamar a un modelo externo, por gasto y no por calidad: lo que se obtiene se consigue igual escribiendo el dato una vez.
*Cambios (RECOLECCION.md)*: Documento nuevo con el procedimiento para el equipo: comprobar una fuente, qué boletín corresponde a cada comunidad, cómo anotar un festivo con su cita y cómo instalar la raíz de un certificado sin caer en el atajo de desactivar la verificación.
*Cambios (pantalla de mantenimiento)*: El frontend ya enseña lo que el calendario sabe y lo que no. No es la pantalla del letrado —esa es la de plazos y necesita el motor— sino la que evita que el calendario envejezca en silencio.
