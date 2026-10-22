"""/lyra: la entrevista de Lyra, a pantalla completa y fuera del escritorio.

La misma página sirve para los dos primeros acercamientos, porque la conversación
es igual: primero la persona, después lo suyo.

- Al DUEÑO, su empresa (lyra_ia.diagnostico.entrevista). Es lo que ve un System
  Manager al entrar a /lyra.
- A CADA FUNCIONARIO, su trabajo (lyra_ia.diagnostico.funcionario). Es lo que ve
  cualquier otra persona de la empresa, y a lo que llega el dueño con /lyra?modo=trabajo
  cuando quiere contar también cómo trabaja él.

Lo único que cambia entre los dos son las rutas de la API y unas palabras, que
salen de aquí (txt). La conversación, el holograma, la voz y el micrófono son los
mismos.
"""

import frappe

no_cache = 1

EMPRESA = {
	"api": "lyra_ia.diagnostico.entrevista",
	"api_plan": "lyra_ia.diagnostico.recomendacion",
	"txt": {
		"titulo": "Lyra conoce tu empresa",
		"confirmar": "Confirmar mi empresa",
		"mapa": "Mapa de tu empresa",
		"listo": "Lyra ya conoce tu empresa",
		"fase": "Conociendo tu empresa",
		"centro": "Tu empresa",
		"entendi": "Esto es lo que entendí de tu empresa.",
	},
}

TRABAJO = {
	"api": "lyra_ia.diagnostico.funcionario",
	"api_plan": "lyra_ia.diagnostico.funcionario",
	"txt": {
		"titulo": "Lyra conoce tu trabajo",
		"confirmar": "Confirmar mi trabajo",
		"mapa": "Mapa de tu trabajo",
		"listo": "Lyra ya conoce tu trabajo",
		"fase": "Conociendo tu trabajo",
		"centro": "Tu trabajo",
		"entendi": "Esto es lo que entendí de tu trabajo.",
	},
}


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/lyra"
		raise frappe.Redirect
	# El dueño entra a la de su empresa; cualquier otra persona, a la de su trabajo.
	# Con ?modo=trabajo el dueño también cuenta cómo trabaja él.
	pedido = (frappe.form_dict.get("modo") or "").strip().lower()
	empresa = "System Manager" in frappe.get_roles() and pedido != "trabajo"
	modo = EMPRESA if empresa else TRABAJO
	context.no_breadcrumbs = True
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.nombre = (frappe.utils.get_fullname(frappe.session.user) or "").split(" ")[0]
	context.api = modo["api"]
	context.api_plan = modo["api_plan"]
	context.txt = modo["txt"]
	return context
