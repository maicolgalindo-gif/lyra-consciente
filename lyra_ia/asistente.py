"""El asistente de Lyra: la conversacion de la pantalla «Asistente» del modulo Lyra IA.

Cada pregunta sigue el ciclo de las herramientas:
	usuario pregunta -> el modelo pide una herramienta -> Lyra la corre como ese
	usuario y le devuelve el resultado -> el modelo pide otra o responde.

Las conversaciones se guardan (IA Conversacion) y cada usuario ve solo las suyas.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import format_date, now_datetime, nowdate

from lyra_ia import cerebro, herramientas, privacidad
from lyra_ia.cerebro import IAError

DT = "IA Conversacion"
MAX_VUELTAS = 6       # herramientas seguidas antes de obligar a responder
MAX_HISTORIA = 20     # mensajes anteriores que se le recuerdan al modelo


def _empresa() -> str:
	from lyra_ia.entorno import empresa

	return empresa()


def _sistema(disponibles: list[dict]) -> str:
	modulos = sorted({h["modulo"] for h in disponibles})
	from lyra_ia import alma
	from lyra_ia.diagnostico.funcionario import contexto_de
	return (
		f"Eres Lyra, el asistente del ERP/CRM de {_empresa()} (Colombia). Hablas con "
		f"{frappe.utils.get_fullname(frappe.session.user)}. Hoy es {format_date(nowdate(), 'dd-MM-yyyy')}.\n"
		f"Módulos a los que tiene acceso: {', '.join(modulos) or 'ninguno'}.\n\n"
		"Reglas:\n"
		"- Para cualquier dato del negocio (clientes, facturas, chats, ventas) usa las herramientas. Nunca inventes "
		"cifras, nombres ni estados. Si una herramienta no trae el dato, dilo.\n"
		"- Responde en español, claro y breve. Usa listas o tablas cortas en Markdown cuando ayuden. Montos en pesos "
		"como los da la herramienta.\n"
		"- Cuando menciones un documento, pon su código (por ejemplo ACC-SINV-2026-00012) para que lo puedan abrir.\n"
		"- Todavía no puedes crear, enviar ni modificar nada. Si te lo piden, explica qué harías y que esa función "
		"llega pronto; si te piden redactar un mensaje, redáctalo para que la persona lo copie.\n"
		"- Si piden algo de un módulo al que no tienen acceso, dilo con amabilidad.\n"
		"- Ya sabes cómo trabaja esta persona porque te lo contó: no se lo hagas repetir, y habla con las "
		"palabras de su oficio. No le recites de vuelta lo que te contó ni le digas que tienes su perfil."
		+ alma.contexto_para_ia()
		+ contexto_de()
	)


def _mia(name: str):
	doc = frappe.get_doc(DT, name)
	if doc.usuario != frappe.session.user:
		raise frappe.PermissionError
	return doc


# --------------------------------------------------------------- lectura
@frappe.whitelist()
def estado() -> dict:
	"""Para la pantalla: si la IA esta lista y que puede consultar este usuario."""
	disponibles = herramientas.disponibles()
	return {
		"lista": cerebro.lista(),
		"es_equipo": "Equipo Lyra" in frappe.get_roles(),
		"modulos": sorted({h["modulo"] for h in disponibles}),
		"herramientas": [h["nombre"] for h in disponibles],
	}


@frappe.whitelist()
def conversaciones() -> list[dict]:
	return frappe.get_all(DT, filters={"usuario": frappe.session.user}, fields=["name", "titulo", "modified"],
						  order_by="modified desc", limit_page_length=50)


@frappe.whitelist()
def abrir(name: str) -> dict:
	doc = _mia(name)
	return {"name": doc.name, "titulo": doc.titulo, "mensajes": json.loads(doc.mensajes or "[]")}


@frappe.whitelist(methods=["POST"])
def borrar(name: str) -> dict:
	_mia(name)
	frappe.delete_doc(DT, name, ignore_permissions=True)
	return {"ok": True}


# ----------------------------------------------------------- preguntar
@frappe.whitelist(methods=["POST"])
def preguntar(texto: str, name: str | None = None) -> dict:
	texto = (texto or "").strip()
	if not texto:
		frappe.throw(_("Escribe tu pregunta."))
	if name:
		doc = _mia(name)
	else:
		doc = frappe.get_doc({"doctype": DT, "usuario": frappe.session.user, "titulo": texto[:80], "mensajes": "[]"})
		doc.insert(ignore_permissions=True)
	historia = json.loads(doc.mensajes or "[]")
	historia.append({"rol": "usuario", "texto": texto, "hora": str(now_datetime())})

	disponibles = herramientas.disponibles()
	mensajes = [{"role": "system", "content": _sistema(disponibles)}]
	for m in historia[-MAX_HISTORIA:]:
		mensajes.append({"role": "user" if m["rol"] == "usuario" else "assistant", "content": m["texto"]})

	mapa: dict = {}  # datos personales ocultos, el mismo para toda la pregunta
	usadas = []
	try:
		respuesta = ""
		for vuelta in range(MAX_VUELTAS + 1):
			mensaje = cerebro.llamar(
				mensajes, "asistente", mapa, referencia=(DT, doc.name),
				herramientas=herramientas.para_el_modelo(disponibles) if disponibles and vuelta < MAX_VUELTAS else None,
				max_tokens=1200,
			)
			llamadas = mensaje.get("tool_calls") or []
			if not llamadas:
				respuesta = privacidad.mostrar(mensaje.get("content") or "", mapa)
				break
			mensajes.append({"role": "assistant", "content": mensaje.get("content") or "", "tool_calls": llamadas})
			for ll in llamadas:
				nombre = ll["function"]["name"]
				try:
					args = json.loads(privacidad.mostrar(ll["function"].get("arguments") or "{}", mapa))
				except ValueError:
					args = {}
				resultado = herramientas.ejecutar(disponibles, nombre, args)
				usadas.append(nombre)
				mensajes.append({"role": "tool", "tool_call_id": ll["id"], "content": resultado})
	except IAError as e:
		frappe.throw(str(e), title=_("Lyra IA"))

	historia.append({"rol": "lyra", "texto": respuesta.strip() or _("No tengo una respuesta para eso."),
					 "hora": str(now_datetime()), "consultas": sorted(set(usadas))})
	doc.mensajes = json.dumps(historia, ensure_ascii=False)
	doc.save(ignore_permissions=True)
	return {"name": doc.name, "titulo": doc.titulo, "mensajes": historia}
