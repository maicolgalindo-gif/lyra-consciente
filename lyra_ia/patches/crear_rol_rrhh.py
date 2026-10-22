"""El doctype Perfil Funcionario da permiso al rol «Recursos Humanos»: si el rol no
existe cuando Frappe sincroniza el doctype, la migracion falla. Por eso va antes
del model sync, igual que los modulos nuevos. El rol tambien se crea (o se repara)
en setup.despues_de_migrar."""

import frappe


def execute():
	if not frappe.db.exists("Role", "Recursos Humanos"):
		frappe.get_doc({"doctype": "Role", "role_name": "Recursos Humanos", "desk_access": 1}).insert(ignore_permissions=True)
