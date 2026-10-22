"""Los cargos que Lyra reconoce, y qué le pregunta a cada uno.

La entrevista al funcionario tiene siempre los MISMOS temas (quién eres, cómo
llegaste, tu día, el paso a paso, con qué lo haces, qué papeles usas, qué te quita
tiempo, con quién te coordinas). Lo que cambia con el cargo son las palabras de
cada pregunta y los documentos que Lyra le pide.

Lyra aquí solo ENTREVISTA: no ofrece ayuda, no promete nada y no habla de lo que
ella hará. Eso se le dice al dueño, no a cada funcionario.

Que los temas sean fijos no es un detalle: así el mapa de todos los funcionarios
tiene la misma forma y se puede consolidar por área sin mirar quién dijo qué, que
es lo único que el dueño llega a ver.

Lyra no sabe de antemano el cargo de nadie: lo deduce de la primera respuesta
(«¿qué haces aquí?») con las SENALES de abajo o con la IA, y lo confirma antes de
seguir. Si no lo reconoce, usa el cargo GENERICO y la entrevista funciona igual.
"""

from __future__ import annotations

# Los temas, en orden. La pregunta de aqui es la generica: cada cargo puede
# cambiarla por una suya en PREGUNTAS.
TEMAS = [
	{"clave": "persona", "nombre": "Quién eres",
	 "pregunta": "Hola, soy Lyra. Antes de hablar de trabajo quiero conocerte: ¿cómo te llamas, qué haces aquí y desde cuándo?",
	 "definicion": "quién es: nombre, qué hace en la empresa, desde cuándo, su historia",
	 "sugerencias": []},
	{"clave": "camino", "nombre": "Cómo llegaste",
	 "pregunta": "¿Y cómo llegaste a este trabajo? Cuéntame qué es lo que más te gusta de lo que haces.",
	 "definicion": "cómo llegó al puesto, su experiencia previa, qué le gusta de su trabajo",
	 "sugerencias": []},
	{"clave": "dia",
	 "nombre": "Tu día",
	 "pregunta": "Cuéntame cómo es un día tuyo de trabajo, desde que llegas.",
	 "definicion": "cómo es su día: con qué empieza, qué hace seguido, qué es lo que más tiempo le toma",
	 "sugerencias": []},
	{"clave": "proceso", "nombre": "El paso a paso",
	 "pregunta": "De lo que haces, ¿cuál es lo más importante? Cuéntamelo paso a paso, como se lo explicarías a alguien nuevo.",
	 "definicion": "el paso a paso real de su trabajo principal: qué recibe, qué hace, en qué orden, qué entrega",
	 "sugerencias": []},
	{"clave": "herramientas", "nombre": "Con qué lo haces",
	 "pregunta": "¿Con qué lo llevas? Programas, Excel, cuadernos, grupos de WhatsApp…",
	 "definicion": "programas, archivos y medios con los que trabaja hoy",
	 "sugerencias": ["Excel", "Un programa", "WhatsApp", "En papel"]},
	{"clave": "documentos", "nombre": "Los papeles que usas",
	 "pregunta": "¿Qué formatos o documentos usas para eso? Si los tienes a la mano, compártemelos.",
	 "definicion": "formatos, plantillas, manuales y documentos que usa o llena",
	 "sugerencias": []},
	{"clave": "dolores", "nombre": "Lo que te quita tiempo",
	 "pregunta": "Si pudieras quitarte una sola cosa del día de encima, ¿cuál sería?",
	 "definicion": "lo repetitivo, lo que le quita tiempo, lo que se devuelve o toca rehacer",
	 "sugerencias": ["Pasar datos a mano", "Perseguir a la gente", "Buscar información", "Rehacer cosas"]},
	{"clave": "traspaso", "nombre": "Con quién te coordinas",
	 "pregunta": "¿De quién recibes trabajo y a quién se lo entregas?",
	 "definicion": "de quién recibe y a quién entrega: los traspasos entre áreas",
	 "sugerencias": []},
]
CLAVES = [t["clave"] for t in TEMAS]

# Conocer a la persona es igual para todos: esas dos no las cambia ningun cargo.
# Aqui NO hay un tema de «como nos ayudamos», que si tiene el dueno: a un
# funcionario Lyra solo lo entrevista. No le ofrece nada ni le promete nada.
FIJOS = ("persona", "camino")

GENERICO = "generico"

# clave -> nombre visible, area, senales para deducirlo, preguntas propias y los
# documentos que Lyra le pide. Las senales se buscan en lo que la persona conto.
CARGOS = {
	"contabilidad": {
		"nombre": "Contabilidad", "area": "Contabilidad",
		"senales": ["contab", "contador", "contadora", "facturac", "factura", "cartera", "tesorer", "cuentas por pagar",
					"cuentas por cobrar", "impuesto", "dian", "causac", "conciliac", "nomina"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo: ¿con qué empiezas, facturas, pagos, conciliaciones?",
			"proceso": "Llévame paso a paso por el cierre de mes: ¿qué haces primero y qué tiene que estar listo antes?",
			"herramientas": "¿Con qué llevas la contabilidad y la facturación? ¿Es el mismo programa o son varios?",
			"documentos": "¿Qué formatos manejas: soportes, comprobantes, el plan de cuentas? Si los tienes, compártemelos.",
			"dolores": "¿Qué es lo que más tiempo te quita al cerrar el mes?",
			"traspaso": "¿Quién te pasa los soportes y a quién le entregas los informes?",
		},
		"documentos": ["el plan de cuentas", "un comprobante de ejemplo", "el formato de soportes", "el calendario tributario que siguen"],
	},
	"rrhh": {
		"nombre": "Recursos Humanos", "area": "Recursos Humanos",
		"senales": ["recursos humanos", "rrhh", "rh", "talento", "gestion humana", "personal", "selecc", "contratac",
					"nomina", "sst", "sg-sst", "seguridad y salud", "bienestar", "capacitac"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo: ¿contratación, nómina, permisos, bienestar?",
			"proceso": "Llévame paso a paso por una contratación, desde que se necesita a alguien hasta que entra.",
			"herramientas": "¿Dónde llevas las hojas de vida, los contratos y las novedades de nómina?",
			"documentos": "¿Qué formatos usas: contratos, exámenes, afiliaciones, el perfil de cada cargo? Si los tienes, compártemelos.",
			"dolores": "¿Qué parte de contratar o de la nómina te quita más tiempo?",
			"traspaso": "¿Quién te pide la gente nueva y a quién le entregas lo de nómina?",
		},
		"documentos": ["un contrato de ejemplo", "los perfiles de cargo", "el formato de ingreso", "lo del SG-SST"],
	},
	"ventas": {
		"nombre": "Ventas", "area": "Ventas",
		"senales": ["vend", "comercial", "cotiz", "asesor", "mercadeo", "marketing"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo: ¿buscas clientes, cotizas, haces seguimiento?",
			"proceso": "Llévame paso a paso desde que aparece un cliente interesado hasta que te compra.",
			"herramientas": "¿Dónde anotas los clientes y las cotizaciones?",
			"documentos": "¿Qué formatos usas: cotizaciones, listas de precios, propuestas? Si los tienes, compártemelos.",
			"dolores": "¿Qué es lo que más te hace perder ventas o tiempo?",
			"traspaso": "Cuando el cliente te compra, ¿a quién le pasas el pedido?",
		},
		"documentos": ["el formato de cotización", "la lista de precios", "una propuesta de ejemplo"],
	},
	"compras": {
		"nombre": "Compras", "area": "Compras",
		"senales": ["compra", "proveedor", "abastec", "adquisic", "suministro", "cotizar proveedores"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo: ¿pedidos, proveedores, seguimiento de entregas?",
			"proceso": "Llévame paso a paso desde que alguien pide algo hasta que llega y se paga.",
			"herramientas": "¿Dónde llevas las órdenes de compra y los proveedores?",
			"documentos": "¿Qué formatos usas: órdenes de compra, comparativos, fichas de proveedor? Compártemelos si los tienes.",
			"dolores": "¿Qué es lo que más se te complica al comprar?",
			"traspaso": "¿Quién te pide las compras y a quién le avisas cuando llegan?",
		},
		"documentos": ["el formato de orden de compra", "la lista de proveedores", "el comparativo de cotizaciones"],
	},
	"operacion": {
		"nombre": "Operación", "area": "Operación",
		"senales": ["operac", "produccion", "tecnico", "tecnica", "campo", "obra", "instalac", "mantenim",
					"proyecto", "ingenier", "servicio"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo en la operación, desde que llegas.",
			"proceso": "Llévame paso a paso por un trabajo típico: desde que te lo asignan hasta que lo entregas.",
			"herramientas": "¿Cómo te enteras de lo que hay que hacer y dónde reportas lo que hiciste?",
			"documentos": "¿Qué formatos llenas: actas, listas de chequeo, informes? Si los tienes, compártemelos.",
			"dolores": "¿Qué te hace perder tiempo o devolverte en un trabajo?",
			"traspaso": "¿Quién te asigna el trabajo y a quién le entregas cuando terminas?",
		},
		"documentos": ["la lista de chequeo", "el acta de entrega", "el formato de informe"],
	},
	"atencion": {
		"nombre": "Atención al cliente", "area": "Atención al cliente",
		"senales": ["atencion", "atiend", "servicio al cliente", "soporte", "pqr", "reclamo", "call", "recepcion", "chat"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo atendiendo clientes.",
			"proceso": "Llévame paso a paso por un caso: desde que el cliente escribe hasta que queda resuelto.",
			"herramientas": "¿Por dónde te escriben los clientes y dónde queda el registro?",
			"documentos": "¿Tienes respuestas guardadas o un formato para los casos? Compártemelo si lo tienes.",
			"dolores": "¿Qué es lo que más se repite o lo que más te cuesta resolver?",
			"traspaso": "Cuando no puedes resolver algo, ¿a quién se lo pasas?",
		},
		"documentos": ["las respuestas guardadas", "el formato de PQR", "el instructivo de atención"],
	},
	"administracion": {
		"nombre": "Administración", "area": "Administración",
		"senales": ["administrac", "administrativ", "asistente", "secretar", "auxiliar", "archivo", "logistica",
					"almacen", "inventario", "bodega"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo: ¿qué te piden y qué resuelves?",
			"proceso": "De lo que haces, ¿qué es lo que más se repite? Cuéntamelo paso a paso.",
			"herramientas": "¿Con qué lo llevas: Excel, carpetas, un programa?",
			"documentos": "¿Qué formatos manejas? Si los tienes a la mano, compártemelos.",
			"dolores": "¿Qué es lo que más tiempo te quita en la semana?",
			"traspaso": "¿Quién te pide cosas y a quién le entregas?",
		},
		"documentos": ["los formatos que llena", "el archivo donde lleva el control"],
	},
	"gerencia": {
		"nombre": "Gerencia", "area": "Dirección",
		"senales": ["gerente", "gerencia", "director", "directora", "jefe", "coordinador", "coordinadora", "lider",
					"dueno", "dueño", "socio", "project manager"],
		"preguntas": {
			"dia": "Cuéntame cómo es un día tuyo: ¿qué revisas y qué decides?",
			"proceso": "¿Cómo haces seguimiento a tu equipo y a los trabajos? Cuéntamelo paso a paso.",
			"herramientas": "¿Con qué te informas de cómo va todo: informes, reuniones, algún programa?",
			"documentos": "¿Qué informes o indicadores miras? Si los tienes, compártemelos.",
			"dolores": "¿Qué información te falta hoy para decidir tranquilo?",
			"traspaso": "¿Quién te reporta a ti y a quién le reportas tú?",
		},
		"documentos": ["los informes que recibe", "los indicadores que mira"],
	},
	GENERICO: {
		"nombre": "Su trabajo", "area": "Otras áreas",
		"senales": [], "preguntas": {}, "documentos": ["los formatos que usa"],
	},
}


def existe(clave: str) -> bool:
	return clave in CARGOS


def cargo(clave: str | None) -> dict:
	return CARGOS.get(clave or "", CARGOS[GENERICO])


def nombre(clave: str | None) -> str:
	return cargo(clave)["nombre"]


def area(clave: str | None) -> str:
	return cargo(clave)["area"]


def lista_para_ia() -> str:
	"""Los cargos, para que la IA elija uno al deducir."""
	return "\n".join(f"- {c}: {d['nombre']}" for c, d in CARGOS.items() if c != GENERICO)


def deducir(texto: str) -> str | None:
	"""El cargo segun lo que la persona conto, sin IA. None si no se reconoce.

	Gana el cargo con la senal mas larga encontrada: «cuentas por cobrar» pesa mas
	que «venta», que aparece dentro de otras palabras."""
	t = (texto or "").lower()
	mejor, largo = None, 0
	for clave, datos in CARGOS.items():
		for s in datos["senales"]:
			if s in t and len(s) > largo:
				mejor, largo = clave, len(s)
	return mejor


def temas(clave: str | None) -> list[dict]:
	"""Los temas con las preguntas de ese cargo."""
	propias = cargo(clave)["preguntas"]
	salida = []
	for t in TEMAS:
		copia = dict(t)
		if t["clave"] not in FIJOS and t["clave"] in propias:
			copia["pregunta"] = propias[t["clave"]]
		salida.append(copia)
	return salida


def documentos(clave: str | None) -> list[str]:
	return cargo(clave)["documentos"]
