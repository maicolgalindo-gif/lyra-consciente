"""El organigrama de la empresa, armado solo con lo que la gente contó.

Nadie lo dibuja a mano: sale de las entrevistas. Cada persona dice de quién recibe
trabajo y a quién se lo entrega (tema «traspaso»), y de ahí salen las dos capas:

- quién REPORTA a quién, cuando alguien lo dijo con esas palabras («le reporto a
  gerencia»);
- cómo FLUYE el trabajo entre áreas («compras me pasa las facturas», «le entrego
  los informes a gerencia»), que suele ser lo interesante: casi nunca coincide con
  el cuadrito oficial.

Esto es para LYRA, no para el cliente: es con lo que el Equipo Lyra entiende cómo
funciona la empresa por dentro y arma la recomendación de módulos, igual que la
recomendación del diagnóstico. El dueño no lo ve, ni aunque sea System Manager;
a él le llega el consolidado por área (funcionario.consolidado()).

Dice el CARGO y el ÁREA de cada quien, nunca lo que contó en su entrevista. Con
`con_nombres=0` se ve solo por cargos, sin personas.
"""

from __future__ import annotations

import frappe
from frappe import _

from lyra_ia.diagnostico import cargos

DT = "Diagnostico Funcionario"

# Lo jerarquico se reconoce por el verbo: «le reporta a», «le reportan».
REPORTA_A = ("reporta a", "le reporta", "responde a", "rinde a", "reporto a")
LE_REPORTAN = ("le reportan", "reportan a", "tiene a cargo", "supervisa", "coordina a", "a su cargo")

# Para el flujo de trabajo el verbo no alcanza: «le pasa» sirve para dar y para
# recibir («compras me pasa las facturas» / «le pasa el pedido a operación»).
# Lo que no se presta a confusion es la preposicion que va PEGADA al otro cargo:
# «a operación» sale de aqui, «de compras» entra aqui.
HACIA = (" a ", " al ", " hacia ", " para ")
DESDE = (" de ", " del ", " desde ", " por ")
# Si no hay preposicion (p. ej. «compras me manda las facturas»), se mira el verbo.
VERBOS_SALIDA = ("entrega", "env", "manda", "sube", "informa", "pasa")
VERBOS_ENTRADA = ("recibe", "me llega", "me manda", "me pasa", "pide", "solicita")


# Como se NOMBRA a otra area, que no es lo mismo que las senales de cargos.py:
# esas dicen a que te dedicas tu («llevo las facturas» -> contabilidad) y aqui
# harian estragos, porque «recibe facturas de compras» habla de compras, no de
# contabilidad. Aqui solo van las palabras con las que se nombra a un area.
AREAS_NOMBRADAS = {
	"contabilidad": ("contabilidad", "contable", "contador", "contadora", "tesoreria", "tesorería", "cartera"),
	"rrhh": ("recursos humanos", "rrhh", "gestion humana", "gestión humana", "talento humano", "talento", "personal"),
	"ventas": ("ventas", "comercial", "vendedor", "vendedora", "asesor", "mercadeo"),
	"compras": ("compras", "abastecimiento", "suministros"),
	"operacion": ("operacion", "operación", "operaciones", "produccion", "producción", "tecnicos", "técnicos",
				  "campo", "obra", "ingenieria", "ingeniería"),
	"atencion": ("atencion al cliente", "atención al cliente", "servicio al cliente", "soporte", "recepcion", "recepción"),
	"administracion": ("administracion", "administración", "almacen", "almacén", "bodega", "logistica", "logística", "archivo"),
	"gerencia": ("gerencia", "gerente", "direccion", "dirección", "director", "directora", "jefe", "jefes", "jefatura"),
}


def _cargo_y_lugar(texto: str) -> tuple[str, int] | None:
	"""El otro cargo nombrado en la frase, y donde empieza. Gana la senal mas larga."""
	mejor, largo, lugar = None, 0, -1
	for clave, nombres in AREAS_NOMBRADAS.items():
		for s in nombres:
			i = texto.find(s)
			if i >= 0 and len(s) > largo:
				mejor, largo, lugar = clave, len(s), i
	return (mejor, lugar) if mejor else None


def _dir_y_cargo(frase: str) -> tuple[str, str] | None:
	"""De «Entrega informes a gerencia» saca ('entrega', 'gerencia'). None si no se reconoce."""
	bajo = " " + (frase or "").lower() + " "
	leido = _cargo_y_lugar(bajo)
	if not leido:
		return None
	otro, lugar = leido
	# Lo jerarquico manda: si dijo que le reporta, eso es lo que vale.
	if any(s in bajo for s in LE_REPORTAN):
		return "supervisa", otro
	if any(s in bajo for s in REPORTA_A):
		return "reporta", otro
	# La preposicion pegada al cargo (los 12 caracteres de antes).
	antes = bajo[max(0, lugar - 12):lugar]
	if any(p in antes for p in DESDE):
		return "recibe", otro
	if any(p in antes for p in HACIA):
		return "entrega", otro
	if any(v in bajo for v in VERBOS_ENTRADA):
		return "recibe", otro
	if any(v in bajo for v in VERBOS_SALIDA):
		return "entrega", otro
	return None


def _arista(aristas: dict, de: str, a: str, tipo: str, porque: str) -> None:
	if de == a:
		return
	clave = (de, a, tipo)
	if clave not in aristas:
		aristas[clave] = {"de": de, "a": a, "tipo": tipo, "porque": porque[:90]}


def armar(con_nombres: bool = True) -> dict:
	"""Nodos (un cargo) y aristas (reporta / entrega), con la frase que lo justifica."""
	nodos: dict = {}
	aristas: dict = {}
	for d in frappe.get_all(DT, filters={"estado": "Confirmado"},
							fields=["name", "cargo", "cargo_nombre", "area", "nombre_persona", "mapa"]):
		cargo = d.cargo or cargos.GENERICO
		nodo = nodos.setdefault(cargo, {"clave": cargo, "cargo": d.cargo_nombre or cargos.nombre(cargo),
										"area": d.area or cargos.area(cargo), "personas": [], "cuantos": 0})
		nodo["cuantos"] += 1
		if con_nombres and d.nombre_persona and d.nombre_persona not in nodo["personas"]:
			nodo["personas"].append(d.nombre_persona)
		mapa = frappe.parse_json(d.mapa or "{}") or {}
		for frase in mapa.get("traspaso") or []:
			leido = _dir_y_cargo(frase)
			if not leido:
				continue
			tipo, otro = leido
			if tipo == "reporta":
				_arista(aristas, cargo, otro, "reporta", frase)
			elif tipo == "supervisa":
				_arista(aristas, otro, cargo, "reporta", frase)
			elif tipo == "entrega":
				_arista(aristas, cargo, otro, "entrega", frase)
			else:
				_arista(aristas, otro, cargo, "entrega", frase)
	# Los cargos que alguien nombró pero que todavía no se han entrevistado: se
	# dibujan en gris, porque la empresa los tiene aunque Lyra no los conozca.
	for (de, a, _t) in list(aristas):
		for clave in (de, a):
			if clave not in nodos:
				nodos[clave] = {"clave": clave, "cargo": cargos.nombre(clave), "area": cargos.area(clave),
								"personas": [], "cuantos": 0}
	return {"nodos": sorted(nodos.values(), key=lambda n: (-n["cuantos"], n["cargo"])),
			"aristas": sorted(aristas.values(), key=lambda a: (a["tipo"], a["de"], a["a"]))}


def niveles(datos: dict) -> list[list[str]]:
	"""Los pisos del organigrama: arriba quien no le reporta a nadie.

	Si alguien reporta en círculo (pasa: «yo le reporto a él y él a mí»), el que
	quede sin colocar se pone en el último piso en vez de trabarlo todo."""
	jefes = {a["de"]: a["a"] for a in datos["aristas"] if a["tipo"] == "reporta"}
	claves = [n["clave"] for n in datos["nodos"]]
	pisos: list[list[str]] = []
	colocados: set = set()
	for _vuelta in range(len(claves) + 1):
		piso = [c for c in claves if c not in colocados
				and (c not in jefes or jefes[c] in colocados or jefes[c] not in claves)]
		if not piso:
			break
		pisos.append(piso)
		colocados.update(piso)
	sobrantes = [c for c in claves if c not in colocados]
	if sobrantes:
		pisos.append(sobrantes)
	return pisos


@frappe.whitelist()
def organigrama(con_nombres: int = 1) -> dict:
	"""Solo para el Equipo Lyra: es material de trabajo nuestro, no del cliente."""
	frappe.only_for("Equipo Lyra")
	datos = armar(con_nombres=bool(int(con_nombres)))
	datos["niveles"] = niveles(datos)
	datos["entrevistados"] = frappe.db.count(DT, {"estado": "Confirmado"})
	datos["sin_entrevistar"] = [n["cargo"] for n in datos["nodos"] if not n["cuantos"]]
	return datos
