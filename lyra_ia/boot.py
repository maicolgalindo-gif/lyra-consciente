import frappe


def boot(bootinfo):
	"""frappe.boot.lyra_ia.activa: la IA esta encendida y tiene clave."""
	try:
		a = frappe.get_cached_doc("IA Ajustes")
		activa = bool(a.activo and a.get_password("clave", raise_exception=False))
	except Exception:
		activa = False
	bootinfo.lyra_ia = {"activa": activa}
