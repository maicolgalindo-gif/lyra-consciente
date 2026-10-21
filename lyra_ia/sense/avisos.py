"""Lyra se da cuenta: los avisos privados a la persona, en tono de colega senior.

Llegan en tiempo real solo a quien guardo el documento (publish_realtime con
user=...), y quedan en Sense Aviso (cada uno ve solo los suyos). No se usa la
campanita de Frappe: puede mandar correos, y un aviso asi no debe salir del ERP.
"""

from __future__ import annotations

import random

import frappe
from frappe import _

DT = "Sense Aviso"
EVENTO = "lyra_sense_aviso"

# Varias formas de decir lo mismo: que no suene a robot repitiendo la misma frase.
FRASES_AVISO = [
	"Ojo, {nombre}: a {documento} le falta «{campo}». Cuando puedas, complétalo.",
	"{nombre}, se nos pasó algo en {documento}: falta «{campo}».",
	"Un detalle en {documento}, {nombre}: «{campo}» quedó vacío.",
]
FRASES_CORRECCION = [
	"Todo bien, {nombre}: {documento} no tenía «{campo}» y le puse «{valor}».",
	"Listo, {nombre}: completé «{campo}» en {documento} con «{valor}».",
	"{nombre}, a {documento} le faltaba «{campo}»; ya le puse «{valor}» para no frenar el proceso.",
]


def _nombre(usuario: str) -> str:
	return (frappe.utils.get_fullname(usuario) or "").split(" ")[0] or ""


def _bajo_el_tope(usuario: str) -> bool:
	tope = frappe.db.get_single_value("Sense Ajustes", "max_avisos_hora") or 6
	clave = f"lyra_sense_avisos_hora:{usuario}"
	n = frappe.cache.get_value(clave, expires=True) or 0
	if n >= tope:
		return False
	frappe.cache.set_value(clave, n + 1, expires_in_sec=3600)
	return True


def enviar(regla, doc, usuario: str, tipo: str, campo: str, anterior=None, nuevo=None) -> None:
	from lyra_ia.sense.captura import area_de

	# El aviso en el idioma de la persona (el proceso de fondo no lo tiene).
	frappe.local.lang = frappe.db.get_value("User", usuario, "language") or frappe.db.get_default("lang") or "es"
	df = doc.meta.get_field(campo)
	etiqueta = _(df.label) if df and df.label else campo
	documento = f"{_(doc.doctype)} {doc.name}"
	datos = {"nombre": _nombre(usuario), "documento": documento, "campo": etiqueta, "valor": nuevo or ""}
	plantilla = (regla.mensaje or "").strip() or random.choice(FRASES_CORRECCION if tipo == "Corrección" else FRASES_AVISO)
	try:
		mensaje = plantilla.format(**datos)
	except (KeyError, IndexError, ValueError):
		mensaje = plantilla
	mensaje = mensaje.replace(" ,", ",").replace(":  ", ": ").strip()
	if mensaje.startswith(", ") or mensaje.startswith(": "):
		mensaje = mensaje[2:]
	aviso = frappe.get_doc({
		"doctype": DT, "usuario": usuario, "owner": usuario, "tipo": tipo, "estado": "Nuevo", "mensaje": mensaje,
		"regla": regla.name, "area": area_de(usuario), "ref_doctype": doc.doctype, "ref_name": doc.name, "campo": campo,
		"valor_anterior": None if anterior in (None, "") else str(anterior), "valor_nuevo": None if nuevo is None else str(nuevo),
	})
	aviso.flags.ignore_permissions = True
	aviso.insert()
	frappe.db.set_value(DT, aviso.name, "owner", usuario, update_modified=False)
	frappe.db.sql("UPDATE `tabSense Regla` SET veces = IFNULL(veces, 0) + 1 WHERE name = %s", regla.name)
	# Las correcciones cuentan siempre (las metricas las necesitan); el aviso en
	# pantalla respeta el tope por hora.
	if _bajo_el_tope(usuario):
		frappe.publish_realtime(EVENTO, {
			"aviso": aviso.name, "mensaje": mensaje, "tipo": tipo,
			"ruta": f"/app/{frappe.scrub(doc.doctype).replace('_', '-')}/{doc.name}",
		}, user=usuario, after_commit=True)


@frappe.whitelist()
def mis_avisos(limite: int = 20) -> list[dict]:
	return frappe.get_all(DT, filters={"usuario": frappe.session.user},
						  fields=["name", "tipo", "estado", "mensaje", "ref_doctype", "ref_name", "creation"],
						  order_by="creation desc", limit_page_length=min(int(limite or 20), 100))


@frappe.whitelist(methods=["POST"])
def marcar_visto(aviso: str) -> dict:
	if frappe.db.get_value(DT, aviso, "usuario") == frappe.session.user:
		frappe.db.set_value(DT, aviso, "estado", "Visto", update_modified=False)
	return {"ok": True}
