"""/lyra: el primer acercamiento de Lyra con la empresa (entrevista al dueno).

Pagina propia, a pantalla completa, fuera del escritorio de Frappe. Los datos
van por lyra_ia.diagnostico.entrevista (con la sesion y el token CSRF).
"""

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/lyra"
		raise frappe.Redirect
	if "System Manager" not in frappe.get_roles():
		frappe.local.flags.redirect_location = "/app"
		raise frappe.Redirect
	context.no_breadcrumbs = True
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.nombre = (frappe.utils.get_fullname(frappe.session.user) or "").split(" ")[0]
	return context
