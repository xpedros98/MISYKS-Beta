"""Las credenciales de la cuenta del abogado, compartidas por los módulos que
las necesitan.

No es un componente: no hace ningún trabajo del despacho. Es lo que impide que
`sec.agenda` tenga que importar `sec.mail` para conectarse a la misma cuenta.
El consentimiento es **uno por cuenta** y cubre correo y calendario a la vez
(ARQUITECTURA.md §8.6), así que el refresh token tampoco puede ser de un módulo
en concreto.
"""
