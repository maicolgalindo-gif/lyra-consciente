"""Lyra Sense es un modulo nuevo de lyra_ia: en sitios donde lyra_ia ya estaba
instalada, su Module Def no existe y las tablas del modulo no se podrian cargar."""

import frappe


def execute():
	if not frappe.db.exists("Module Def", "Lyra Sense"):
		frappe.get_doc({"doctype": "Module Def", "module_name": "Lyra Sense", "app_name": "lyra_ia"}).insert(ignore_permissions=True)
