"""Lo que Lyra sabe del sitio donde esta instalada.

Lyra Consciente no depende de ERPNext ni de las apps de WhatsApp: funciona con
solo Frappe. Si esas apps estan, las aprovecha (herramientas del asistente,
copiloto, datos para el alma); si no, sigue andando sin ellas. Toda pregunta de
«¿esta instalado X?» o «¿como se llama la empresa?» pasa por aqui, para no
repetir en cada archivo la misma suposicion.
"""

from __future__ import annotations

import frappe


def hay_app(nombre: str) -> bool:
	return nombre in frappe.get_installed_apps()


def hay_doctype(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def empresa() -> str:
	"""El nombre de la empresa: el de ERPNext si esta; si no, el que dio el dueno en
	la entrevista; si no, el nombre del sitio en Frappe."""
	if hay_app("erpnext"):
		nombre = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
		if nombre:
			return nombre
	if hay_doctype("Diagnostico Empresa"):
		nombre = frappe.db.get_value("Diagnostico Empresa", {"nombre_negocio": ["is", "set"]}, "nombre_negocio",
									 order_by="modified desc")
		if nombre:
			return nombre
	return frappe.db.get_single_value("Website Settings", "app_name") or frappe.local.site or ""
