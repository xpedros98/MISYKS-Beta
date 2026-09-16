# DIARIO

## 15/09/2026
*Resumen*: Hoy hemos creado el repo de MISYKS versión Beta, para migrar el código del primer prototipo. La intención es construirlo de nuevo, con más control sobre cada pieza.
*Cambios*: Usaremos un único repositorio, organizado en carpetas de Frontend y Backend. Prescindimos de Google Auth por ahora: intentaremos gestionar la autenticación nosotros, a bajo nivel, para poder incluir diferentes proveedores de correo. Empezamos pensando en correr el secretario en local (en el PC del abogado), pero eso ocuparía mucho espacio en su equipo y le consumiría recursos, así que de momento vamos a ejecutar todos los agentes en el servidor.

## 16/09/2026
*Resumen*: Hoy hemos acotado el proyecto definiendo los archivos básicos de información (los `.md`). Esto permitirá al equipo trabajar más en paralelo sin perder el hilo.
*Cambios*: Hemos añadido varios `.md`: uno de arquitectura, otro de agentes y este diario, más humano y no técnico. También hemos aclarado lo que ayer quedó a medias: los agentes de IA correrán todos en el servidor, porque es donde está el modelo de lenguaje, pero `sec.mail` no es un agente de IA sino de software, así que sigue corriendo en local — es quien tiene la contraseña del correo.
