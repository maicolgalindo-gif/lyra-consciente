"""El antiguo «Lo que la IA debe saber del negocio» (IA Ajustes.contexto_negocio)
pasa a las notas del equipo en el alma, para no perder lo que ya se habia escrito.
El campo ya no existe en IA Ajustes, pero su valor sigue en tabSingles."""

import frappe


def execute():
	viejo = frappe.db.sql("SELECT value FROM `tabSingles` WHERE doctype = 'IA Ajustes' AND field = 'contexto_negocio'")
	texto = (viejo[0][0] if viejo else "") or ""
	if texto.strip() and not (frappe.db.get_single_value("Lyra Alma", "notas_equipo") or "").strip():
		frappe.db.set_single_value("Lyra Alma", "notas_equipo", texto.strip())
	frappe.db.sql("DELETE FROM `tabSingles` WHERE doctype = 'IA Ajustes' AND field = 'contexto_negocio'")
	from lyra_ia.alma import _guardar

	_guardar()
