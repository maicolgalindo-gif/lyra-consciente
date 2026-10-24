"""Lo que Lyra puede HACER, siempre preguntando antes.

Hasta aquí Lyra solo miraba: sabía que tres facturas estaban vencidas y no podía
escribirle al cliente. Esto es lo otro, con una regla que no se negocia:

	Lyra nunca hace nada sin que una persona diga que sí.

Cuando la IA decide que hay que hacer algo, no lo hace: deja una PROPUESTA con
el texto exacto de lo que haría. La persona la ve, dice sí o no, y solo entonces
se ejecuta. Todo queda en Lyra Accion: qué propuso, quién decidió, cómo salió y
cómo deshacerlo.

Es el principio del plan: se automatiza lo repetitivo de regla estable, se
asiste lo que exige juicio; en lo asistido el sistema propone y una persona
confirma. Esto es la parte asistida.

Cada app de Lyra declara las suyas con el hook lyra_ia_acciones. Cada acción:

	{
		"nombre": "enviar_whatsapp",
		"modulo": "WhatsApp",
		"descripcion": "...",               # la lee el modelo para decidir
		"parametros": {...},                # JSON Schema
		"resumen": callable -> str,         # lo que la persona ve antes de decir sí
		"ejecutar": callable -> dict,       # solo corre si dijo que sí
		"deshacer": callable | None,        # si se puede devolver
		"disponible": callable -> bool,     # app instalada y permiso de quien la usa
	}
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

DT = "Lyra Accion"


def todas() -> list[dict]:
	salida = []
	for metodo in frappe.get_hooks("lyra_ia_acciones") or []:
		try:
			salida.extend(frappe.get_attr(metodo)() or [])
		except Exception:
			frappe.log_error(title=f"Lyra: no se pudieron leer las acciones de {metodo}")
	return salida


def disponibles() -> list[dict]:
	"""Las que esta persona puede pedir: app instalada y permiso suyo."""
	salida = []
	for a in todas():
		try:
			if a["disponible"]():
				salida.append(a)
		except Exception:
			continue
	return salida


def para_el_modelo(lista: list[dict]) -> list[dict]:
	"""Las acciones en el formato de herramientas que entiende el modelo."""
	return [{"type": "function", "function": {
		"name": "proponer_" + a["nombre"],
		"description": a["descripcion"] + " " + _("No lo hace: deja la propuesta para que la persona la apruebe."),
		"parameters": a["parametros"],
	}} for a in lista]


def proponer(lista: list[dict], nombre: str, argumentos: dict, conversacion: str | None = None) -> dict:
	"""Deja la propuesta escrita. No ejecuta nada."""
	nombre = nombre.replace("proponer_", "", 1)
	accion = next((a for a in lista if a["nombre"] == nombre), None)
	if not accion:
		return {"error": _("Esa acción no existe o no está disponible para ti.")}
	try:
		resumen = accion["resumen"](**argumentos)
	except Exception as e:
		return {"error": str(e)[:200]}
	doc = frappe.get_doc({
		"doctype": DT, "accion": nombre, "resumen": resumen[:1000], "estado": "Propuesta",
		"usuario": frappe.session.user, "conversacion": conversacion,
		"propuesta_el": now_datetime(), "datos": json.dumps(argumentos, ensure_ascii=False),
	}).insert(ignore_permissions=True)
	return {"propuesta": doc.name, "resumen": resumen}


def _mia(name: str):
	doc = frappe.get_doc(DT, name)
	if doc.usuario != frappe.session.user:
		frappe.throw(_("Esa propuesta no es tuya."), frappe.PermissionError)
	return doc


@frappe.whitelist(methods=["POST"])
def confirmar(name: str) -> dict:
	"""La persona dijo que sí: ahora sí se hace."""
	doc = _mia(name)
	if doc.estado != "Propuesta":
		frappe.throw(_("Esto ya se decidió."))
	accion = next((a for a in disponibles() if a["nombre"] == doc.accion), None)
	if not accion:
		frappe.throw(_("Esa acción ya no está disponible."))
	argumentos = json.loads(doc.datos or "{}")
	try:
		resultado = accion["ejecutar"](**argumentos) or {}
	except Exception as e:
		doc.db_set({"estado": "Falló", "error": str(e)[:500], "decidida_el": now_datetime()})
		frappe.db.commit()
		frappe.throw(_("No se pudo: {0}").format(str(e)[:200]))
	doc.db_set({"estado": "Hecha", "decidida_el": now_datetime(),
				"resultado": json.dumps(resultado, ensure_ascii=False, default=str)})
	frappe.db.commit()
	return {"ok": True, "estado": "Hecha", "resultado": resultado,
			"se_puede_deshacer": bool(accion.get("deshacer"))}


@frappe.whitelist(methods=["POST"])
def rechazar(name: str) -> dict:
	"""La persona dijo que no. No pasa nada, pero queda escrito."""
	doc = _mia(name)
	if doc.estado != "Propuesta":
		frappe.throw(_("Esto ya se decidió."))
	doc.db_set({"estado": "Rechazada", "decidida_el": now_datetime()})
	frappe.db.commit()
	return {"ok": True, "estado": "Rechazada"}


@frappe.whitelist(methods=["POST"])
def deshacer(name: str) -> dict:
	"""Devolver lo que se hizo, si la acción sabe cómo."""
	doc = _mia(name)
	if doc.estado != "Hecha":
		frappe.throw(_("Esto no se ha hecho."))
	accion = next((a for a in disponibles() if a["nombre"] == doc.accion), None)
	if not accion or not accion.get("deshacer"):
		frappe.throw(_("Esto no se puede deshacer. Lo que salió, salió."))
	accion["deshacer"](json.loads(doc.datos or "{}"), json.loads(doc.resultado or "{}"))
	doc.db_set({"estado": "Deshecha"})
	frappe.db.commit()
	return {"ok": True, "estado": "Deshecha"}


@frappe.whitelist()
def mias(limite: int = 10) -> list[dict]:
	"""Lo que Lyra me ha propuesto y qué pasó con eso."""
	return frappe.get_all(DT, filters={"usuario": frappe.session.user},
						  fields=["name", "accion", "resumen", "estado", "propuesta_el", "decidida_el"],
						  order_by="creation desc", limit=int(limite))
