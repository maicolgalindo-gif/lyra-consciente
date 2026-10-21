"""Lyra Diagnostico es un modulo nuevo de lyra_ia (ver crear_modulo_sense)."""

import frappe


def execute():
	if not frappe.db.exists("Module Def", "Lyra Diagnostico"):
		frappe.get_doc({"doctype": "Module Def", "module_name": "Lyra Diagnostico", "app_name": "lyra_ia"}).insert(ignore_permissions=True)
