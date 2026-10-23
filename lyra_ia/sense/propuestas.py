"""Las reglas que Lyra propone, sacadas de lo que la gente contó.

Hasta aquí las reglas de «Lyra se da cuenta» salían de una lista fija metida en
el código: las mismas cuatro para cualquier empresa, dijeran lo que dijeran sus
empleados. Eso no es darse cuenta de nada.

Esto las saca de las entrevistas: si en el área de ventas tres personas dijeron
que se les olvida ponerle fecha a las cotizaciones, Lyra propone vigilar ese
campo, y dice cuántos lo dijeron y con qué palabras. Nace APAGADA: la enciende
el Equipo Lyra después de leerla.

Dos límites que no se cruzan:

- La regla no la inventa la IA. Cada propuesta sale de este catálogo, donde cada
  entrada dice qué señales en el lenguaje de la gente apuntan a qué campo de qué
  documento. La IA no entra aquí: no puede inventar un campo que no existe ni
  decidir que algo se complete solo.
- Solo se propone lo que existe en ESTE sitio: si el doctype o el campo no
  están, la propuesta no se arma.
"""

from __future__ import annotations

import frappe
from frappe import _

DT_REGLA = "Sense Regla"
DT_ENTREVISTA = "Diagnostico Funcionario"

# Cada entrada: cuándo aplica (señales en lo que contaron), qué vigilar y por qué.
# Las señales se buscan en lo que la gente dijo que le cuesta y en cómo trabaja.
CATALOGO = [
	{
		"clave": "cotizacion_sin_vigencia",
		"titulo": "Cotización sin fecha de validez",
		"doctype": "Quotation", "campo": "valid_till", "evento": "Al guardar", "modo": "Avisar",
		"areas": ("Ventas",),
		"senales": ("fecha", "vigencia", "validez", "vence", "caduca", "desactualiz", "precio viejo"),
		"porque": "porque en ventas contaron que las cotizaciones se quedan sin fecha o con precios viejos",
	},
	{
		"clave": "lead_sin_contacto",
		"titulo": "Cliente potencial sin teléfono",
		"doctype": "Lead", "campo": "mobile_no", "evento": "Al crear", "modo": "Avisar",
		"areas": ("Ventas", "Atención al cliente"),
		"senales": ("sin datos", "no deja", "falta el tel", "sin tel", "no tengo como", "perder clientes",
					"se pierden", "no contesta", "volver a llamar"),
		"porque": "porque contaron que se pierden clientes por no tener cómo volver a contactarlos",
	},
	{
		"clave": "factura_sin_soporte",
		"titulo": "Factura de compra sin soporte adjunto",
		"doctype": "Purchase Invoice", "campo": "bill_no", "evento": "Al guardar", "modo": "Avisar",
		"areas": ("Contabilidad", "Compras"),
		"senales": ("soporte", "sin factura", "falta el papel", "adjunt", "buscar el documento", "rehac"),
		"porque": "porque en contabilidad contaron que se les va el tiempo buscando o persiguiendo soportes",
	},
	{
		"clave": "pedido_sin_responsable",
		"titulo": "Pedido sin quién responde por él",
		"doctype": "Sales Order", "campo": "sales_person", "evento": "Al crear", "modo": "Avisar",
		"areas": ("Ventas", "Operación"),
		"senales": ("quién", "quien responde", "nadie sabe", "se pierde", "no se sabe de quién", "sin dueño"),
		"porque": "porque contaron que a veces no se sabe quién responde por un pedido",
	},
	{
		"clave": "chat_sin_etiqueta",
		"titulo": "Chat resuelto sin decir de qué se trataba",
		"doctype": "WhatsApp Conversacion", "campo": "etiquetas", "evento": "Al guardar", "modo": "Avisar",
		"condicion": 'doc.estado == "Resuelta"',
		"areas": ("Atención al cliente", "Ventas"),
		"senales": ("whatsapp", "chat", "se repite", "lo mismo", "no queda registro", "no sé qué pasó"),
		"porque": "porque en atención contaron que no queda registro de qué se trataban los chats",
	},
]


def _existe(doctype: str, campo: str) -> bool:
	if not frappe.db.exists("DocType", doctype):
		return False
	try:
		return bool(frappe.get_meta(doctype).get_field(campo))
	except Exception:
		return False


def _lo_que_contaron() -> list[dict]:
	"""Lo que cada persona dijo que le cuesta, con su área. Sin nombres."""
	salida = []
	if not frappe.db.exists("DocType", DT_ENTREVISTA):
		return salida
	for d in frappe.get_all(DT_ENTREVISTA, filters={"estado": "Confirmado"}, fields=["area", "mapa"]):
		mapa = frappe.parse_json(d.mapa or "{}") or {}
		frases = []
		for clave in ("dolores", "proceso", "herramientas", "documentos"):
			frases.extend(x for x in (mapa.get(clave) or []) if x)
		if frases:
			salida.append({"area": d.area or "", "frases": frases})
	return salida


def proponer() -> list[dict]:
	"""Las reglas que Lyra propondría hoy, con quién lo dijo y con qué palabras."""
	contado = _lo_que_contaron()
	if not contado:
		return []
	salida = []
	for entrada in CATALOGO:
		if not _existe(entrada["doctype"], entrada["campo"]):
			continue
		if frappe.db.exists(DT_REGLA, {"titulo": entrada["titulo"]}):
			continue
		citas, personas = [], 0
		for persona in contado:
			if entrada["areas"] and persona["area"] not in entrada["areas"]:
				continue
			suyas = [f for f in persona["frases"] if any(s in f.lower() for s in entrada["senales"])]
			if suyas:
				personas += 1
				citas.extend(suyas[:2])
		if not personas:
			continue
		salida.append({**entrada, "personas": personas, "citas": list(dict.fromkeys(citas))[:4]})
	return salida


@frappe.whitelist(methods=["POST"])
def crear() -> dict:
	"""Crea las reglas propuestas, apagadas, con el porqué escrito encima."""
	frappe.only_for(("System Manager", "Equipo Lyra"))
	creadas = []
	for p in proponer():
		mensaje = _("Lo propuso Lyra {0}. Lo dijeron {1} persona(s): «{2}».").format(
			p["porque"], p["personas"], "; ".join(p["citas"]) or _("sin citas"))
		doc = frappe.get_doc({
			"doctype": DT_REGLA, "activa": 0, "titulo": p["titulo"], "ref_doctype": p["doctype"],
			"campo": p["campo"], "evento": p["evento"], "modo": p["modo"],
			"condicion": p.get("condicion") or "", "mensaje": mensaje[:500],
		})
		doc.insert()
		creadas.append({"titulo": p["titulo"], "personas": p["personas"]})
	return {"creadas": creadas, "cuantas": len(creadas)}
