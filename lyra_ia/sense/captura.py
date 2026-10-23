"""Lyra se da cuenta: captura de lo que pasa en el sistema.

doc_events "*" (hooks.py) llama aqui en cada guardado, validacion y anulacion.
Tiene que ser liviano: el empleado no puede notar nada.
- Se ignoran tablas, ajustes, registros tecnicos y los documentos de Lyra.
- Se anota un evento corto (Sense Evento): quien, que, que campos cambiaron y su
  area. El detalle completo ya esta en el historial de Frappe; no se duplica.
- Si hay reglas para ese tipo de documento, se encola su revision para despues
  de confirmar el guardado (reglas.py). Sin reglas no se encola nada.
"""

from __future__ import annotations

import frappe

# Modulos tecnicos: lo que pasa ahi no es trabajo de nadie.
MODULOS_IGNORADOS = {
	"Core", "Desk", "Email", "Integrations", "Custom", "Website", "Printing", "Automation", "Social",
	"Data Migration", "Geo", "Contacts Settings", "Lyra Sense", "Lyra IA", "Lyra Diagnostico",
}
DOCTYPES_IGNORADOS = {
	# Los que escribe un programa solo (mensajes que entran, campañas que corren,
	# chats que se sincronizan): no es nadie trabajando, y llenaban el registro.
	"WhatsApp Message", "WhatsApp Notification Log", "WAHA Mensaje", "WAHA Campana", "WAHA Chat",
	"WAHA Campana Envio", "Process Subscription", "Version", "Comment", "File",
	"Notification Log", "Communication", "ToDo", "Activity Log", "Access Log", "Error Log", "Scheduled Job Log",
	"Route History", "DocShare", "Deleted Document", "Email Queue", "Prepared Report", "Integration Request",
	"User Settings", "Session Default Settings", "Dashboard Settings",
}
NO_COMPARAR = {"modified", "modified_by", "creation", "owner", "idx", "docstatus", "_user_tags", "_comments",
			   "_assign", "_liked_by", "_seen"}
ACCIONES = {"on_update": "Guardar", "on_submit": "Validar", "on_cancel": "Cancelar"}


def _ignorar(doc) -> bool:
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch or frappe.flags.in_import:
		return True
	if frappe.flags.lyra_sense_cambio or frappe.session.user in ("Guest", None):
		return True
	if doc.doctype in DOCTYPES_IGNORADOS:
		return True
	try:
		meta = frappe.get_meta(doc.doctype)
	except Exception:
		return True
	return bool(meta.istable or meta.issingle or meta.module in MODULOS_IGNORADOS)


def _activo() -> bool:
	try:
		return bool(frappe.db.get_single_value("Sense Ajustes", "activo"))
	except Exception:
		return False


def area_de(usuario: str) -> str:
	"""El area de la persona: su departamento en RR. HH., o «General»."""
	clave = f"lyra_sense_area:{usuario}"
	area = frappe.cache.get_value(clave, expires=True)
	if area is None:
		area = "General"
		if frappe.db.exists("DocType", "Employee"):
			dep = frappe.db.get_value("Employee", {"user_id": usuario, "status": "Active"}, "department")
			if dep:
				# «Ventas - LE»: el sufijo es la empresa.
				area = dep.rsplit(" - ", 1)[0]
		frappe.cache.set_value(clave, area, expires_in_sec=3600)
	return area


def _cambios(doc) -> list[str]:
	antes = doc.get_doc_before_save()
	if not antes:
		return []
	salida = []
	for df in doc.meta.fields:
		if df.fieldtype in ("Table", "Table MultiSelect", "Section Break", "Column Break", "Tab Break", "HTML", "Button"):
			continue
		if df.fieldname in NO_COMPARAR:
			continue
		if (doc.get(df.fieldname) or None) != (antes.get(df.fieldname) or None):
			salida.append(df.fieldname)
	return salida[:30]


def capturar(doc, method=None) -> None:
	"""doc_events '*': on_update, on_submit y on_cancel."""
	try:
		if _ignorar(doc) or not _activo():
			return
		accion = ACCIONES.get(method, "Guardar")
		if accion == "Guardar" and doc.get_doc_before_save() is None:
			accion = "Crear"
		usuario = frappe.session.user
		ahora = frappe.utils.now_datetime()
		# db_insert: sin validaciones ni hooks, lo mas barato posible.
		frappe.get_doc({
			"doctype": "Sense Evento", "name": frappe.generate_hash(length=12), "owner": usuario, "modified_by": usuario,
			"creation": ahora, "modified": ahora, "usuario": usuario, "area": area_de(usuario), "accion": accion,
			"ref_doctype": doc.doctype, "ref_name": doc.name, "campos": ", ".join(_cambios(doc)) or None,
		}).db_insert()
		from lyra_ia.sense.reglas import hay_reglas

		if hay_reglas(doc.doctype):
			frappe.enqueue("lyra_ia.sense.reglas.revisar", queue="short", enqueue_after_commit=True,
						   ref_doctype=doc.doctype, ref_name=doc.name, accion=accion, usuario=usuario)
	except Exception:
		# Lyra nunca puede impedir que alguien guarde su trabajo.
		frappe.log_error(title="Lyra se da cuenta: no se pudo anotar un evento")
