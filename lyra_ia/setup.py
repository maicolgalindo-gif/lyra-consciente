"""Instalacion y actualizacion de lyra_ia."""

import frappe

AJUSTES = ("Sense Ajustes", "IA Ajustes")


def crear_rol_equipo():
	"""«Equipo Lyra»: los que operan Lyra (nosotros), no el cliente. Ve IA Ajustes y el
	alma. Administrator lo tiene siempre; a otra persona del equipo se le asigna a mano."""
	if not frappe.db.exists("Role", "Equipo Lyra"):
		frappe.get_doc({"doctype": "Role", "role_name": "Equipo Lyra", "desk_access": 1}).insert(ignore_permissions=True)


def despues_de_migrar():
	crear_rol_equipo()
	"""Un Single no toma los 'default' de sus campos hasta que alguien lo guarda:
	sin esto «Lyra se da cuenta» arrancaria apagada y sin tope de avisos. Solo se
	llenan los campos que nunca se guardaron; lo configurado no se toca."""
	for dt in AJUSTES:
		if not frappe.db.exists("DocType", dt):
			continue
		guardados = set(frappe.db.sql_list("SELECT field FROM `tabSingles` WHERE doctype = %s", dt))
		for df in frappe.get_meta(dt).fields:
			if df.default and df.fieldname not in guardados and df.fieldtype not in ("Section Break", "Column Break", "Table"):
				frappe.db.set_single_value(dt, df.fieldname, df.default)
