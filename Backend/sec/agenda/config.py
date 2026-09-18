"""Lo que es de sec.agenda y no de la cuenta.

Las credenciales, los tokens y la clave de la base viven en
`sec.cuentas.ajustes`: el consentimiento es uno por cuenta y cubre correo y
calendario a la vez (ARQUITECTURA.md §8.6).

sec.agenda corre hoy en local, junto a `sec.mail`, porque usa sus mismos
tokens y porque la agenda del despacho no es dato público. §8.6 deja abierto si
debería correr en `maat`: un componente que vigila plazos tiene que poder avisar
con el equipo del letrado apagado, pero eso pondría los refresh tokens de todos
los clientes en el servidor. Mientras no se decida, aquí.
"""
from ..cuentas.ajustes import DATA_DIR

DB_PATH = DATA_DIR / "sec_agenda.db"

# Ventana por defecto de la sincronización, **en meses enteros** alrededor del
# mes en curso. Hacia atrás poco: lo pasado ya no se puede atender, y solo
# interesa para saber qué había. Hacia delante un año largo, porque los
# señalamientos judiciales se ponen con muchos meses de antelación y una agenda
# que solo mira al mes que viene es exactamente el fallo que COMPONENTES.md le
# atribuye a este módulo («solo mira el día siguiente»).
#
# **En meses y no en días, y esto no es cosmético.** El cursor de Google se
# guarda con la ventana que lo pidió y se descarta si se pide otra. Con una
# ventana de «hoy ± N días», mañana la ventana ya es otra, el cursor no vale
# nunca y **todas las sincronizaciones son completas**: el camino incremental
# existiría sin llegar a usarse jamás. Medido el 18/09, un día después de
# escribirlo. Cuadrada al mes, la ventana cambia una vez cada treinta días: un
# recorrido completo al mes y el resto incrementales.
MESES_ATRAS = 1
MESES_ADELANTE = 13
